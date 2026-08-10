/**
 * praxis-front-door — first-class Pi integration for the praxis process/orchestration engine.
 *
 * This is the Pi-native counterpart of the Claude Code integration (an MCP server + three shell
 * hooks). It replaces both:
 *
 *   MCP server (praxis/front-door/server.py)  →  four native pi tools (begin_work, compose_spawn,
 *                                                 close_work, work_status) that shell to the
 *                                                 transport-free CLI (praxis/front-door/cli.py).
 *
 *   praxis-frame-gate.sh   (PreToolUse gate)  →  a `tool_call` handler that blocks edit/write in a
 *                                                 praxis-managed root unless an OPEN unit of work in
 *                                                 the conductor journal authorizes it. The decision
 *                                                 delegates to praxis/scripts/gate.py
 *                                                 (conductor/journal.open_unit) — the single, shared
 *                                                 gate implementation.
 *   praxis-frame-stamp.sh  (RETIRED)          →  no per-session tmp stamp: begin_work / close_work
 *                                                 (front_door_core's bridge, run via the CLI) write
 *                                                 unit.framed / unit.closed events, which the gate
 *                                                 reads. The journal is the single source of truth.
 *   praxis-payload-read-stamp.sh (PostToolUse) → a `tool_result` handler on read that records the
 *                                                 payload was read as a journal note
 *                                                 (gate.py mark-payload-read), replacing the `.read`
 *                                                 tmp stamp. Inline delivery injects the payload
 *                                                 body into the begin_work result and records the
 *                                                 read at injection time.
 *
 * The brain is unchanged: the CLI runs praxis's python scripts, which invoke corpora (the judgment
 * engine) for composition and spawn assembly.
 *
 * Configuration:
 *   PRAXIS_HOUSE        — repo root that holds praxis/front-door/cli.py. Defaults to the repo this
 *                         extension file lives in (resolved through symlinks), i.e. ~/jdev/skills.
 *   PRAXIS_PYTHON       — python interpreter (default: python3).
 *   PRAXIS_HOOK_BYPASS  — set to any value to disable the edit gate entirely.
 */

import { execFileSync, spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { StringEnum } from "@earendil-works/pi-ai";
import { Text } from "@earendil-works/pi-tui";

const MAX_AGE_SECONDS = 1800;
const PAYLOAD_BASENAME = ".frame-payload.md";
const MARKER_BASENAME = ".last-frame-at";

// ── Locating the house / CLI ────────────────────────────────────────────────────────────────────

function resolveHouse(): string {
	const env = process.env.PRAXIS_HOUSE;
	if (env && fs.existsSync(path.join(env, "praxis", "front-door", "cli.py"))) return env;
	// This file is <house>/pi-extension/praxis/index.ts; follow symlinks to the real repo copy.
	let self = fileURLToPath(import.meta.url);
	try {
		self = fs.realpathSync(self);
	} catch {
		/* keep unresolved */
	}
	const candidate = path.resolve(path.dirname(self), "..", "..");
	if (fs.existsSync(path.join(candidate, "praxis", "front-door", "cli.py"))) return candidate;
	// Fall back to env even if unverified, so the error surfaced names a real path.
	return env || candidate;
}

const HOUSE = resolveHouse();
const CLI = path.join(HOUSE, "praxis", "front-door", "cli.py");
const GATE_PY = path.join(HOUSE, "praxis", "scripts", "gate.py");
const PYTHON = process.env.PRAXIS_PYTHON || "python3";

function runCli(subcommand: string, args: Record<string, string | undefined>): string {
	const argv = [CLI, subcommand];
	for (const [key, value] of Object.entries(args)) {
		if (value !== undefined && value !== null && value !== "") argv.push(`--${key}`, value);
	}
	return execFileSync(PYTHON, argv, {
		encoding: "utf-8",
		maxBuffer: 64 * 1024 * 1024,
		cwd: process.cwd(),
	});
}

/** The edit-gate decision, delegated to praxis/scripts/gate.py — the single implementation of the
 *  journal-backed gate (conductor/journal.open_unit), shared with the Claude Code shell hook. Fails
 *  open (returns { verdict: "no_unit" }) on any error, matching gate.py's own discipline. */
function runGate(subcommand: string, args: Record<string, string | undefined>): any {
	const argv = [GATE_PY, subcommand];
	for (const [key, value] of Object.entries(args)) {
		if (value !== undefined && value !== null && value !== "") argv.push(`--${key}`, value);
	}
	try {
		return JSON.parse(execFileSync(PYTHON, argv, { encoding: "utf-8", cwd: process.cwd() }));
	} catch {
		return { verdict: "no_unit" };
	}
}

// ── #4 Native spawn: an isolated `pi` subprocess seeded with the composed payload ──────────────

interface SpawnResult {
	text: string;
	exitCode: number | null;
	toolCalls: string[];
	error?: string;
}

/** Extract the final assistant text (the handoff) from pi's JSONL event stream. */
function parseSpawnStream(stdout: string): { text: string; toolCalls: string[] } {
	let finalText = "";
	const toolCalls: string[] = [];
	for (const line of stdout.split("\n")) {
		const t = line.trim();
		if (!t) continue;
		let ev: any;
		try {
			ev = JSON.parse(t);
		} catch {
			continue;
		}
		if (ev.type === "tool_execution_start" && ev.toolName) toolCalls.push(ev.toolName);
		if (ev.type === "agent_end" && Array.isArray(ev.messages)) {
			for (let i = ev.messages.length - 1; i >= 0; i--) {
				const m = ev.messages[i];
				if (m?.role === "assistant" && Array.isArray(m.content)) {
					const txt = m.content.filter((p: any) => p?.type === "text").map((p: any) => p.text).join("");
					if (txt) {
						finalText = txt;
						break;
					}
				}
			}
		}
	}
	return { text: finalText, toolCalls };
}

/** Spawn an isolated pi process. `-ne` disables extension discovery, so the child has no praxis
 *  gate — the parent's frame authorizes this whole unit, and the payload IS the frame, carried in
 *  the child's system prompt (invariants-first, so same-composition spawns share a cacheable
 *  prefix). One spawn = one unit = one handoff; the child dies with its context. */
function spawnPi(
	payloadPath: string,
	taskPrompt: string,
	cwd: string,
	model: string | undefined,
	thinking: string | undefined,
	signal: AbortSignal | undefined,
	onUpdate: ((u: { content: { type: "text"; text: string }[] }) => void) | undefined,
): Promise<SpawnResult> {
	return new Promise((resolve) => {
		const args = ["--mode", "json", "-p", "-ne", "--no-session", "--append-system-prompt", payloadPath];
		if (model) args.push("--model", model);
		// #9 praxis's runtime recommendation — the child runs the unit at this reasoning budget.
		if (thinking) args.push("--thinking", thinking);
		args.push(taskPrompt);
		// stdin ignored: an open stdin pipe makes the child wait even under -p.
		const child = spawn("pi", args, { cwd, env: process.env, stdio: ["ignore", "pipe", "pipe"] });
		let stdout = "";
		let stderr = "";
		const seen = new Set<string>();
		const onAbort = () => child.kill("SIGTERM");
		signal?.addEventListener("abort", onAbort, { once: true });
		child.stdout.on("data", (d) => {
			stdout += d.toString();
			// Live progress: surface each new tool the child runs.
			for (const line of stdout.split("\n")) {
				try {
					const ev = JSON.parse(line);
					if (ev.type === "tool_execution_start" && ev.toolName && !seen.has(ev.toolCallId)) {
						seen.add(ev.toolCallId);
						onUpdate?.({ content: [{ type: "text", text: `spawn · ${ev.toolName} (${seen.size} tool calls)` }] });
					}
				} catch {
					/* partial line */
				}
			}
		});
		child.stderr.on("data", (d) => {
			stderr += d.toString();
		});
		child.on("error", (e) => {
			signal?.removeEventListener("abort", onAbort);
			resolve({ text: "", exitCode: null, toolCalls: [], error: `failed to spawn pi: ${e.message}` });
		});
		child.on("close", (code) => {
			signal?.removeEventListener("abort", onAbort);
			const { text, toolCalls } = parseSpawnStream(stdout);
			resolve({
				text,
				exitCode: code,
				toolCalls,
				error: code === 0 ? undefined : stderr.trim() || `pi exited ${code}`,
			});
		});
	});
}

// ── Root discovery / stamp bookkeeping (ports of praxis-hooks-lib.sh) ─────────────────────────────

const MARKER_DIRS = [".praxis", "praxis"] as const;

/** Nearest ancestor carrying `<marker>/config.md` (`.praxis` wins over legacy `praxis`). Syntactic
 *  walk: it never requires the path to exist, matching root_tree.governing_root_above. */
function walkToRoot(startDir: string): { root: string; praxisDir: string } | null {
	let dir = startDir;
	while (dir && dir !== path.dirname(dir)) {
		for (const m of MARKER_DIRS) {
			if (fs.existsSync(path.join(dir, m, "config.md"))) {
				return { root: dir, praxisDir: path.join(dir, m) };
			}
		}
		dir = path.dirname(dir);
	}
	return null;
}

function praxisDirOf(root: string): string {
	for (const m of MARKER_DIRS) {
		if (fs.existsSync(path.join(root, m))) return path.join(root, m);
	}
	return path.join(root, ".praxis");
}

function fileAgeSeconds(p: string): number | null {
	try {
		const mtime = fs.statSync(p).mtimeMs / 1000;
		return Math.floor(Date.now() / 1000 - mtime);
	} catch {
		return null;
	}
}

function readJson(p: string): any | null {
	try {
		return JSON.parse(fs.readFileSync(p, "utf-8"));
	} catch {
		return null;
	}
}

// ── The gate (journal-backed; delegates to praxis/scripts/gate.py) ────────────────────────────────

/** Record that the open unit's payload was read (a `unit.note payload_read` journal event) — the
 *  journal equivalent of the retired `.read` tmp stamp. No-op when there is no open unit. */
function markPayloadRead(root: string): void {
	runGate("mark-payload-read", { root });
}

/** Returns a deny reason string, or null to allow. Fail-open on any ambiguity. The decision itself
 *  is gate.py's (conductor/journal.open_unit): is there an open unit for this root, and does it
 *  authorize THIS edit? — no per-session tmp stamp, no freshness window. */
function gateDecision(filePath: string, _sessionId: string | undefined): string | null {
	if (process.env.PRAXIS_HOOK_BYPASS) return null;
	let absFile: string;
	try {
		const dir = fs.realpathSync(path.dirname(filePath));
		absFile = path.join(dir, path.basename(filePath));
	} catch {
		// New file whose parent may not exist yet — resolve syntactically.
		absFile = path.resolve(filePath);
	}
	const found = walkToRoot(path.dirname(absFile));
	if (!found) return null; // not a praxis-managed root — transparent
	const { root } = found;

	const decision = runGate("check", { root, file: absFile });
	switch (decision?.verdict) {
		case "allow":
			return null;
		case "deny":
			return (
				decision.reason ||
				`This edit is not authorized by the open unit of work for this root (${root}) — call ` +
					`begin_work for the unit whose work this edit is.`
			);
		case "no_unit":
			return (
				`No open unit of work in the journal for this root (${root}) — call the praxis begin_work ` +
				`tool for this unit of work before editing (praxis/SKILL.md: 'frame before acting').`
			);
		default:
			return null; // unrecognized ⇒ fail open
	}
}

// ── Extension ─────────────────────────────────────────────────────────────────────────────────

function sessionIdOf(ctx: ExtensionContext): string | undefined {
	try {
		return ctx.sessionManager?.getSessionId?.();
	} catch {
		return undefined;
	}
}

// ── #7 Evict injected judgment from context once its unit closes ─────────────────────────
// Inline begin_work injects the composed judgment (7–140KB) into context. While the unit is open
// that judgment is what the work runs under; once close_work fires it is dead weight. Each injected
// block carries a pxid; on close we mark the open ids evictable, and the `context` handler strips
// their bodies from the OUTGOING LLM context (the stored transcript keeps the full record).
const JUDGMENT_MARKER = "--- COMPOSED JUDGMENT";
const judgmentBySession = new Map<string, { open: string[]; evictable: Set<string> }>();

function judgmentState(sid: string) {
	let s = judgmentBySession.get(sid);
	if (!s) {
		s = { open: [], evictable: new Set() };
		judgmentBySession.set(sid, s);
	}
	return s;
}

function newJudgmentId(): string {
	return randomUUID().replace(/-/g, "").slice(0, 8);
}

// ── #9 Runtime policy: apply praxis's how-it-runs recommendation, and audit it ───────────────
// The DECISION is praxis's (runtime_policy.py, surfaced as the `runtime` block); the extension only
// APPLIES it (child `--thinking` for a spawn, setThinkingLevel for inline) and records what it did
// to <root>/.praxis/runtime-audit.log so every runtime choice is reviewable (also via work_status).
const runtimeDisabled = () => !!process.env.PRAXIS_NO_RUNTIME;
const priorThinkingBySession = new Map<string, string | undefined>();

function logRuntimeAudit(root: string, entry: Record<string, unknown>): void {
	try {
		const p = path.join(praxisDirOf(root), "runtime-audit.log");
		fs.appendFileSync(p, `${JSON.stringify({ ts: Math.floor(Date.now() / 1000), ...entry })}\n`);
	} catch {
		/* audit is best-effort */
	}
}

// ── Workflow trace ─────────────────────────────────────────────────────────────────────────────
// No longer a standalone trace.jsonl: the workflow trace is a view over the conductor journal. The
// frame is recorded by begin-work's bridge (unit.framed); the spawn outcome by record-outcome
// (unit.receipt on the open unit); close-work by unit.closed. `runCli("trace")` reads them back.

const STATUS_ENUM = ["complete", "blocked", "questions-pending", "tradeoffs-pending"] as const;

/** Read the spawn's outcome from the status footer the child was asked to emit. A stall (any
 *  non-complete status) is a first-class outcome, not a failure. Falls back to "delivered" when the
 *  child exited without declaring — marked inferred so the trace stays honest. */
function parseSpawnOutcome(text: string): {
	outcome: "result" | "stall";
	status: string;
	surfaced: string | null;
	source: "declared" | "inferred";
} {
	const m = new RegExp(`praxis-status:\\s*(${STATUS_ENUM.join("|")})`, "i").exec(text);
	const s = /praxis-surfaced:\s*(.+)/i.exec(text);
	if (m) {
		const status = m[1].toLowerCase();
		return {
			outcome: status === "complete" ? "result" : "stall",
			status,
			surfaced: s ? s[1].trim() : null,
			source: "declared",
		};
	}
	return { outcome: "result", status: "complete", surfaced: null, source: "inferred" };
}

function formatTraceSummary(t: any): string {
	const sum = t?.summary ?? {};
	const fmt = (v: any) => `${v.result}/${v.runs} \u2713${v.stall ? ` (${v.stall} stall)` : ""}`;
	const lines: string[] = [`praxis trace @ ${t?.root ? path.basename(t.root) : "?"}`];
	const byPhase = Object.entries(sum.by_phase ?? {});
	if (byPhase.length) {
		lines.push("by phase:");
		for (const [k, v] of byPhase) lines.push(`  ${k}: ${fmt(v)}`);
	} else {
		lines.push("  (no outcomes traced yet)");
	}
	const byWf = Object.entries(sum.by_workflow ?? {});
	if (byWf.length) {
		lines.push("by workflow:");
		for (const [k, v] of byWf) lines.push(`  ${k}: ${fmt(v)}`);
	}
	// The journal fold's recent_stalls key the unit by `phase` (its label / unit-of-work).
	for (const st of sum.recent_stalls ?? [])
		lines.push(`stall · ${st.phase}[${st.status}] ${st.surfaced ?? ""}`);
	return lines.join("\n");
}

// ── #2 Ambient framing status (footer) ────────────────────────────────────────────────────────

/** A one-line summary of the governing root's frame state, or "" when cwd is not in a praxis root. */
function statusLine(cwd: string): string {
	const found = walkToRoot(cwd);
	if (!found) return "";
	const name = path.basename(found.root);
	const marker = path.join(found.praxisDir, MARKER_BASENAME);
	const data = readJson(marker);
	const age = fileAgeSeconds(marker);
	if (!data || typeof data !== "object") {
		return age !== null ? `praxis[${name}]: framed (cli)` : `praxis[${name}]: UNFRAMED`;
	}
	if (data.closed) return `praxis[${name}]: unframed (last: ${data.unit_of_work ?? "?"})`;
	const mins = age === null ? "?" : Math.floor(age / 60);
	if (age !== null && age > MAX_AGE_SECONDS) {
		return `praxis[${name}]: frame STALE ${mins}m (${data.unit_of_work ?? "?"})`;
	}
	return `praxis[${name}]: ${data.unit_of_work ?? "?"} \u00b7 ${mins}m`;
}

function refreshStatus(ctx: ExtensionContext): void {
	try {
		if (!ctx.hasUI) return;
		const base = statusLine(ctx.cwd);
		const on = modeOn(sessionIdOf(ctx));
		ctx.ui.setStatus("praxis", on ? `\u25c9 ${base || "praxis mode on"}` : base);
	} catch {
		/* fire-and-forget */
	}
}

// ── L1 praxis mode: auto-frame edit-intent asks at the INPUT boundary ─────────────────────
// Opt-in (default off; `/praxis on` or PRAXIS_MODE=on). When on, an edit-intent ask is pre-framed
// before the model responds: praxis's deterministic facts (governing root, span verdict, size,
// phases) are injected so the model frames up front instead of getting bounced by the gate
// mid-edit. The gate remains the backstop, so a missed classification still can't skip framing.
const praxisModeBySession = new Map<string, boolean>();
const defaultMode = (): boolean => process.env.PRAXIS_MODE === "on";
function modeOn(sid: string | undefined): boolean {
	return praxisModeBySession.get(sid ?? "default") ?? defaultMode();
}

const EDIT_INTENT =
	/\b(add|fix|implement|refactor|edit|change|modify|update|create|write|remove|delete|rename|move|patch|wire|rewrite|replace|introduce|extract|migrate|convert|split|revise|build|correct|adjust|clean\s?up)\b/i;

/** Best-effort extraction of file paths named in the ask, so preframe resolves the real root(s). */
function extractPaths(text: string, cwd: string): { target?: string; files?: string } {
	const toks = text
		.split(/\s+/)
		.map((t) => t.replace(/^[("'`]+|[)"'`:,.]+$/g, ""))
		.filter((t) => t && (t.includes("/") || /\.\w{1,6}$/.test(t)));
	const existing = toks.filter((t) => {
		try {
			return fs.existsSync(path.isAbsolute(t) ? t : path.join(cwd, t));
		} catch {
			return false;
		}
	});
	if (existing.length === 0) return {};
	return { target: existing[0], files: existing.slice(1).join(",") || undefined };
}

function framingPreamble(pf: any): string | null {
	const lines = ["[praxis mode] This ask looks like it may edit files — frame it before editing:"];
	if (pf.spans) {
		lines.push("- it spans multiple roots → DECOMPOSE into one unit per root; no single agent straddles them.");
	} else if (pf.root) {
		lines.push(`- governing root: ${path.basename(pf.root)} (${pf.root}); size floor: ${pf.size_floor}`);
	} else {
		return null; // not in a governed root and not spanning — nothing to frame
	}
	const phases: Array<{ phase: string }> = Array.isArray(pf.phases) ? pf.phases : [];
	if (phases.length) lines.push(`- this root's phases: ${phases.map((p) => p.phase).join(", ")}`);
	lines.push(
		"Declare the unit-of-work and call begin_work(unit_of_work=…, target=…, execution=…) first — it " +
			"composes the judgment, opens the edit gate, and sets the reasoning budget. Prefer praxis_spawn " +
			"to delegate implementation, and verify its handoff yourself. State begin_work's assumptions " +
			"before acting. (/praxis off to disable.)",
	);
	return lines.join("\n");
}

export default function praxisFrontDoor(pi: ExtensionAPI) {
	// #2 Ambient status: surface the governing root's frame state in the footer on start.
	pi.on("session_start", async (_event, ctx) => {
		refreshStatus(ctx);
	});

	// #7 Prune closed units' injected judgment from the outgoing LLM context.
	pi.on("context", async (event, ctx) => {
		const sid = sessionIdOf(ctx);
		if (!sid) return;
		const s = judgmentBySession.get(sid);
		if (!s || s.evictable.size === 0) return;
		const evictRe = new RegExp(`${JUDGMENT_MARKER.replace(/[-]/g, "\\$&")} \\[pxid:([0-9a-f]+)\\]`);
		let changed = false;
		for (const m of event.messages as Array<{ content?: unknown }>) {
			if (!Array.isArray(m.content)) continue;
			for (const part of m.content as Array<{ type?: string; text?: string }>) {
				if (part?.type !== "text" || typeof part.text !== "string") continue;
				if (part.text.includes("[evicted after close_work]")) continue;
				const match = part.text.match(evictRe);
				if (match && s.evictable.has(match[1])) {
					const before = part.text.length;
					part.text =
						`\n${JUDGMENT_MARKER} [pxid:${match[1]}] [evicted after close_work] ---\n` +
						"(judgment for this closed unit was removed from context to reclaim tokens; " +
						"re-frame with begin_work if you need it again)";
					changed = true;
					if (process.env.PRAXIS_DEBUG) {
						try {
							fs.appendFileSync(
								path.join(process.env.TMPDIR || "/tmp", "praxis-evict.log"),
								`evicted pxid:${match[1]} — ${before} → ${part.text.length} chars (−${before - part.text.length})\n`,
							);
						} catch {
							/* ignore */
						}
					}
				}
			}
		}
		return changed ? { messages: event.messages } : undefined;
	});

	// L1: /praxis toggle.
	pi.registerCommand("praxis", {
		description: "Praxis: mode toggle + trace. Usage: /praxis [on|off|status|trace|workflows]",
			handler: async (args, ctx) => {
			const cwd = (ctx as any).cwd ?? process.cwd();
			const arg = (args ?? "").trim().toLowerCase();
			const sub = arg.split(/\s+/)[0];

			// Read-only introspection subcommands.
			if (sub === "trace") {
				try {
					const t = JSON.parse(runCli("trace", { "search-base": cwd }));
					ctx.ui.notify(t.error ? `praxis: ${t.error}` : formatTraceSummary(t), "info");
				} catch (e) {
					ctx.ui.notify(`praxis trace failed: ${e}`, "error");
				}
				return;
			}
			if (sub === "workflows") {
				try {
					const t = JSON.parse(runCli("trace", { "search-base": cwd }));
					const wfs = Object.entries(t.workflows ?? {});
					const lines = wfs.length
						? wfs.map(([k, v]) => `  ${k}: ${(v as string[]).join(" \u2192 ")}`)
						: ["  (none declared in .praxis/workflow.json)"];
					ctx.ui.notify(["workflows:", ...lines].join("\n"), "info");
				} catch (e) {
					ctx.ui.notify(`praxis workflows failed: ${e}`, "error");
				}
				return;
			}

			// Mode toggle (default action).
			const sid = sessionIdOf(ctx as unknown as ExtensionContext) ?? "default";
			let on = praxisModeBySession.get(sid) ?? defaultMode();
			if (sub === "on") on = true;
			else if (sub === "off") on = false;
			else if (sub !== "status") on = !on;
			praxisModeBySession.set(sid, on);
			ctx.ui.notify(
				on
					? "praxis mode ON — edit-intent asks are auto-framed (gate still backstops)"
					: "praxis mode OFF — framing is manual (the edit gate still applies)",
				"info",
			);
			try {
				(ctx as unknown as ExtensionContext).ui.setStatus(
					"praxis",
					on ? "\u25c9 praxis mode on" : "",
				);
			} catch {
				/* ignore */
			}
		},
	});

	// L1: pre-frame edit-intent asks at the input boundary.
	pi.on("input", async (event, ctx) => {
		if (!modeOn(sessionIdOf(ctx))) return;
		if (event.source === "extension") return;
		const text = event.text ?? "";
		const trimmed = text.trim();
		if (!trimmed || trimmed.startsWith("/") || trimmed.startsWith("!")) return;
		if (/begin_work|\[praxis mode\]/.test(text)) return; // already framed/annotated
		if (!EDIT_INTENT.test(text)) return;
		const { target, files } = extractPaths(text, ctx.cwd);
		let pf: any;
		try {
			pf = JSON.parse(runCli("preframe", { target, files, "search-base": ctx.cwd }));
		} catch {
			return; // preframe is advisory — never block input on its failure
		}
		const preamble = framingPreamble(pf);
		if (!preamble) return;
		if (process.env.PRAXIS_DEBUG) {
			try {
				fs.appendFileSync(
					path.join(process.env.TMPDIR || "/tmp", "praxis-input.log"),
					`${preamble}\n---\n`,
				);
			} catch {
				/* ignore */
			}
		}
		return { action: "transform", text: `${text}\n\n${preamble}` };
	});

	if (!fs.existsSync(CLI)) {
		// Surface loudly but do not crash the harness.
		console.error(
			`[praxis] cli not found at ${CLI} — set PRAXIS_HOUSE to the repo holding praxis/front-door/cli.py`,
		);
	}

	// ---- Tool: begin_work ----
	pi.registerTool({
		name: "begin_work",
		label: "praxis · begin work",
		description:
			"Praxis front door: frame + route a unit of work (which root governs it, how big it " +
			"is, the composed judgment, and the assumptions being made), then open the edit gate for " +
			"this session. EVERY task that will edit files must pass through this first — the gate " +
			"blocks edits in a praxis-managed root until begin_work has run here. `execution` is your " +
			"routing decision: 'spawn' (default — a subagent implements; call compose_spawn next) or " +
			"'inline' (you implement here, an explicit exception for operator-requested or trivial work).",
		promptSnippet: "Frame and route a unit of work before editing (praxis front door)",
		promptGuidelines: [
			"Call begin_work before editing any file in a praxis-managed root — the edit gate depends on it.",
			"State begin_work's assumptions to the user before acting; redirect happens before they are realized.",
		],
		parameters: Type.Object({
			unit_of_work: Type.String({
				description: "The kind of work, e.g. implement-feature, fix-bug, scan-architecture, refactor.",
			}),
			target: Type.Optional(Type.String({ description: "Primary file/dir the task touches." })),
			files: Type.Optional(
				Type.String({ description: "Comma-separated additional paths the task touches." }),
			),
			workstream: Type.Optional(
				Type.String({ description: "Name to persist the frame under (a resumable workstream)." }),
			),
			execution: Type.Optional(StringEnum(["spawn", "inline"] as const)),
			search_base: Type.Optional(
				Type.String({ description: "Root-discovery base (defaults to cwd)." }),
			),
			workflow: Type.Optional(
				Type.String({ description: "Workflow id (from .praxis/workflow.json) to tag this unit's trace with." }),
			),
		}),
		async execute(_id, params, _signal, _onUpdate, ctx) {
			const out = runCli("begin-work", {
				"unit-of-work": params.unit_of_work,
				target: params.target,
				files: params.files,
				workstream: params.workstream,
				execution: params.execution,
				"search-base": params.search_base ?? ctx.cwd,
				workflow: params.workflow,
			});
			const parsed = JSON.parse(out);
			// The journal now holds the frame: begin-work (front_door_core's bridge) wrote a
			// unit.framed event that conductor/journal.open_unit reads — no per-session stamp file,
			// and no separate trace.jsonl (the workflow trace is a view over that journal).
			const sid = sessionIdOf(ctx);
			// #1 Inline delivery: inject the composed judgment straight into context. The payload
			// file remains the brain's artifact; we read it and inline its body so the parent works
			// under the judgment by construction. Injecting IS the read, so we record it on the open
			// journal unit (markPayloadRead) — the gate's payload-read requirement is satisfied
			// without a separate Read tool call.
			const content: Array<{ type: "text"; text: string }> = [];
			let injected = false;
			const payloadPath = parsed?.payload?.path as string | undefined;
			if (payloadPath && fs.existsSync(payloadPath)) {
				try {
					const body = fs.readFileSync(payloadPath, "utf-8");
					parsed.delivery =
						"inline — the composed judgment is included in this tool result below; no " +
						"separate read is needed, and the edit gate is open for this unit.";
					if (parsed.root) markPayloadRead(parsed.root);
					const pxid = newJudgmentId();
					if (sid) judgmentState(sid).open.push(pxid);
					content.push({ type: "text", text: JSON.stringify(parsed, null, 2) });
					content.push({
						type: "text",
						text: `\n${JUDGMENT_MARKER} [pxid:${pxid}] (loaded for inline work) ---\n${body}`,
					});
					injected = true;
				} catch {
					/* fall through to the plain result */
				}
			}
			if (!injected) content.push({ type: "text", text: out });
			// #9 Inline work runs in THIS session — apply the reasoning budget praxis recommends.
			const runtime = parsed.runtime;
			if (injected && runtime?.enabled && runtime.thinking && !runtimeDisabled()) {
				try {
					const prev = (ctx as any).thinkingLevel as string | undefined;
					if (sid) priorThinkingBySession.set(sid, prev);
					(pi as any).setThinkingLevel?.(runtime.thinking);
					parsed.runtime_applied = `thinking: ${runtime.thinking} (${runtime.reason})`;
					if (parsed.root)
						logRuntimeAudit(parsed.root, {
							unit_of_work: params.unit_of_work,
							mode: "inline",
							stance: runtime.stance,
							thinking: runtime.thinking,
							prev: prev ?? null,
							reason: runtime.reason,
						});
				} catch {
					/* thinking control is best-effort */
				}
			}
			refreshStatus(ctx);
			return { content, details: parsed };
		},
		renderResult(result: any, _options: any, theme: any) {
			const d = (result?.details ?? {}) as any;
			if (d.error) return new Text(theme.fg("error", `praxis: ${d.error}`), 0, 0);
			const frame = d.frame ?? {};
			const uow = frame.unit_of_work ?? "?";
			const root = d.root ? String(d.root).split("/").pop() : "(no single root)";
			const comp: string[] = Array.isArray(frame.composition) ? frame.composition : [];
			const size = frame.size_floor ?? "?";
			const gate = String(d.gate ?? "");
			const gateColor = gate.startsWith("open") ? "success" : "warning";
			const lines: string[] = [];
			lines.push(
				theme.fg("accent", theme.bold(`\u2b21 ${uow}`)) +
					theme.fg("muted", `  root:${root}  size:${size}`),
			);
			if (comp.length) lines.push(theme.fg("dim", `  judgment: ${comp.join(", ")}`));
			const rt = d.runtime;
			if (rt?.thinking)
				lines.push(theme.fg("muted", `  runtime: ${rt.stance} \u2192 thinking:${rt.thinking}`));
			const warnings: string[] = Array.isArray(d.warnings) ? d.warnings : [];
			for (const w of warnings) lines.push(theme.fg("warning", `  \u26a0 ${String(w).split("\n")[0]}`));
			lines.push(theme.fg(gateColor, `  gate: ${gate.split("\u2014")[0].trim() || gate}`));
			return new Text(lines.join("\n"), 0, 0);
		},
	});

	// ---- Tool: compose_spawn ----
	pi.registerTool({
		name: "compose_spawn",
		label: "praxis · compose spawn",
		description:
			"Compose the domain set for a unit of work and write the assembled spawn-prompt parts " +
			"(stance frame, full domain bodies, handoff schema) to <root>/.praxis/.frame-payload.md, " +
			"returning the path. Read that file and inject its content into the spawned agent's prompt — " +
			"the implementer's judgment rides there, not in the parent.",
		parameters: Type.Object({
			unit_of_work: Type.String(),
			target: Type.Optional(Type.String()),
			files: Type.Optional(Type.String({ description: "Comma-separated paths." })),
			search_base: Type.Optional(Type.String()),
		}),
		async execute(_id, params, _signal, _onUpdate, ctx) {
			const out = runCli("compose-spawn", {
				"unit-of-work": params.unit_of_work,
				target: params.target,
				files: params.files,
				"search-base": params.search_base ?? ctx.cwd,
			});
			return { content: [{ type: "text", text: out }], details: JSON.parse(out) };
		},
	});

	// ---- Tool: praxis_spawn (native, isolated pi subprocess) ----
	pi.registerTool({
		name: "praxis_spawn",
		label: "praxis · spawn",
		description:
			"Run a unit of work as an ISOLATED pi subprocess seeded with the composed judgment as its " +
			"system prompt. This is the automated form of the spawn path: it composes the domain set, " +
			"launches a fresh pi with that judgment (its own context window, no praxis gate), runs the " +
			"task, and returns the child's final message as the unit's handoff. One spawn = one unit = one " +
			"handoff; the child dies with its context. The returned handoff is a CLAIM — verification stays " +
			"with you (the router): re-run the suites yourself; route any defect to a fresh spawn, never " +
			"back into the finished child.",
		promptSnippet: "Delegate a unit of work to an isolated pi subprocess under composed judgment",
		promptGuidelines: [
			"Prefer praxis_spawn over inline editing for any non-trivial unit — it isolates the implementer's context and yields one handoff, which you then verify.",
		],
		parameters: Type.Object({
			unit_of_work: Type.String(),
			task: Type.String({ description: "The concrete brief for the implementer (goes as the child's user prompt)." }),
			target: Type.Optional(Type.String()),
			files: Type.Optional(Type.String({ description: "Comma-separated paths." })),
			search_base: Type.Optional(Type.String()),
			model: Type.Optional(Type.String({ description: "Override the child's model." })),
			workflow: Type.Optional(Type.String({ description: "Workflow id (from .praxis/workflow.json) to tag this unit's trace with." })),
		}),
		async execute(_id, params, signal, onUpdate, ctx) {
			const base = params.search_base ?? ctx.cwd;
			const out = runCli("compose-spawn", {
				"unit-of-work": params.unit_of_work,
				target: params.target,
				files: params.files,
				"search-base": base,
				workflow: params.workflow,
			});
			const composed = JSON.parse(out);
			if (composed.error) {
				return { content: [{ type: "text", text: out }], details: composed };
			}
			const root: string = composed.root;
			const payloadPath: string | undefined = composed?.payload?.path;
			if (!payloadPath || !fs.existsSync(payloadPath)) {
				throw new Error(`compose-spawn produced no payload file (${payloadPath ?? "none"})`);
			}
			// #9 Apply praxis's runtime recommendation to the child, unless the caller pinned a model
			// (their choice wins) or the policy is disabled/off.
			const runtime = composed.runtime;
			const thinking =
				!params.model && runtime?.enabled && runtime?.thinking && !runtimeDisabled()
					? (runtime.thinking as string)
					: undefined;
			const rtNote = thinking ? ` · thinking:${thinking} (${runtime.stance})` : "";
			onUpdate?.({ content: [{ type: "text", text: `spawn · composing under [${(composed.composition || []).join(", ")}]${rtNote}…` }] });
			// Ask the child to end with a machine-readable status line so a stall is a detected
			// outcome, not guessed from prose.
			const taskWithFooter =
				`Task: ${params.task}\n\n` +
				"When finished, end your final message with a line exactly:\n" +
				"praxis-status: <complete|blocked|questions-pending|tradeoffs-pending>\n" +
				"If not complete, add a second line: praxis-surfaced: <one line of what is needed or why>";
			const result = await spawnPi(payloadPath, taskWithFooter, root, params.model, thinking, signal, onUpdate);
			if (result.error) {
				throw new Error(`spawn failed: ${result.error}`);
			}
			if (thinking)
				logRuntimeAudit(root, {
					unit_of_work: params.unit_of_work,
					mode: "spawn",
					stance: runtime.stance,
					thinking,
					reason: runtime.reason,
				});
			const outcome = parseSpawnOutcome(result.text || "");
			// Record the spawn's outcome on the journal's open unit (the one begin_work framed), so
			// the workflow trace — now a view over the conductor journal, not a standalone
			// trace.jsonl — carries the deliver-vs-stall data. Best-effort: a failed bridge must not
			// fail the spawn.
			try {
				runCli("record-outcome", {
					outcome: outcome.outcome,
					status: outcome.status,
					surfaced: outcome.surfaced ?? undefined,
					"tool-calls": String(result.toolCalls.length),
					"search-base": root,
				});
			} catch {
				/* trace is best-effort */
			}
			const nextPhase = composed.workflow?.next_phase;
			const outcomeLine =
				outcome.outcome === "stall"
					? `outcome: STALL [${outcome.status}]${outcome.surfaced ? ` — ${outcome.surfaced}` : ""} — route this back to planning or surface it; do not mark the unit done`
					: `outcome: result [${outcome.status}${outcome.source === "inferred" ? ", inferred" : ""}]` +
						(nextPhase ? ` · next phase in workflow: ${nextPhase}` : "");
			const header =
				`⬡ spawn complete · unit-of-work: ${params.unit_of_work} · root: ${path.basename(root)}${rtNote}\n` +
				`composition: ${(composed.composition || []).join(", ")} · child tool calls: ${result.toolCalls.length}\n` +
				`${outcomeLine}\n` +
				`\n--- HANDOFF (a CLAIM — verify by re-running suites yourself; route defects to a fresh spawn) ---\n`;
			return {
				content: [{ type: "text", text: header + (result.text || "(child produced no final message)") }],
				details: {
					root,
					unit_of_work: params.unit_of_work,
					composition: composed.composition,
					runtime: composed.runtime,
					workflow: composed.workflow,
					thinking_applied: thinking ?? null,
					outcome: outcome.outcome,
					status: outcome.status,
					surfaced: outcome.surfaced,
					exit_code: result.exitCode,
					tool_calls: result.toolCalls,
					handoff: result.text,
				},
			};
		},
	});

	// ---- Tool: close_work ----
	pi.registerTool({
		name: "close_work",
		label: "praxis · close work",
		description:
			"Close out the current unit of work for the governing root: the next edit anywhere in the " +
			"root then requires a fresh begin_work. Call this when the unit's output is delivered, not " +
			"when the clock runs out.",
		parameters: Type.Object({
			search_base: Type.Optional(Type.String()),
		}),
		async execute(_id, params, _signal, _onUpdate, ctx) {
			const out = runCli("close-work", { "search-base": params.search_base ?? ctx.cwd });
			const parsed = JSON.parse(out);
			const sid = sessionIdOf(ctx);
			// close-work (front_door_core's bridge) wrote a unit.closed event; the journal fold now
			// shows no open unit for this root, so the gate closes and the trace records the close —
			// no stamp file to clear, no separate trace.jsonl to append.
			// #7 The unit is closing — its injected judgment is now evictable from context.
			if (sid) {
				const s = judgmentState(sid);
				for (const id of s.open) s.evictable.add(id);
				s.open = [];
			}
			// #9 Restore the session's prior thinking level once the inline unit ends.
			if (sid && priorThinkingBySession.has(sid) && !runtimeDisabled()) {
				const prev = priorThinkingBySession.get(sid);
				try {
					if (prev) (pi as any).setThinkingLevel?.(prev);
				} catch {
					/* best-effort */
				}
				priorThinkingBySession.delete(sid);
				if (parsed.root)
					logRuntimeAudit(parsed.root, { mode: "inline-restore", thinking: prev ?? "(default)" });
			}
			refreshStatus(ctx);
			return { content: [{ type: "text", text: out }], details: parsed };
		},
	});

	// ---- Tool: work_status ----
	pi.registerTool({
		name: "work_status",
		label: "praxis · work status",
		description:
			"Read-only: the governing root, the frame marker's contents and age, and which sessions " +
			"currently hold a stamp for it.",
		parameters: Type.Object({
			search_base: Type.Optional(Type.String()),
		}),
		async execute(_id, params, _signal, _onUpdate, ctx) {
			const out = runCli("work-status", { "search-base": params.search_base ?? ctx.cwd });
			return { content: [{ type: "text", text: out }], details: JSON.parse(out) };
		},
	});

	// ---- The edit gate (port of praxis-frame-gate.sh) ----
	pi.on("tool_call", async (event, ctx) => {
		if (event.toolName !== "edit" && event.toolName !== "write") return;
		const input = event.input as { path?: string };
		if (!input?.path) return;
		const reason = gateDecision(input.path, sessionIdOf(ctx));
		if (reason) return { block: true, reason };
	});

	// ---- Payload read → journal note (port of praxis-payload-read-stamp.sh) ----
	// Reading the frame payload file records the read on the root's open journal unit (a
	// unit.note payload_read event), which the gate then honors for file/spawn delivery — the
	// journal equivalent of the retired `.read` tmp stamp.
	pi.on("tool_result", async (event, ctx) => {
		if (event.toolName !== "read" || event.isError) return;
		const input = event.input as { path?: string };
		const p = input?.path;
		if (!p) return;
		if (!p.endsWith(`${path.sep}${PAYLOAD_BASENAME}`)) return;
		const praxisDir = path.dirname(p);
		if (!fs.existsSync(path.join(praxisDir, "config.md"))) return;
		const root = path.dirname(praxisDir);
		try {
			markPayloadRead(root);
		} catch {
			/* fail open */
		}
	});
}
