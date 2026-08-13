#!/usr/bin/env python3
import ast
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
PRAXIS = HERE.parent.parent
sys.path.insert(0, str(PRAXIS))
sys.path.insert(0, str(PRAXIS / "scripts"))

MCP_SERVER_PY = PRAXIS / "mcp_server.py"

try:
    import mcp  # noqa: F401
    _HAVE_MCP = True
except ImportError:
    _HAVE_MCP = False

def _tools_and_imports(src: str):
    tree = ast.parse(src)
    imported = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                imported.add(a.asname or a.name.split(".")[0])
        elif isinstance(n, ast.ImportFrom):
            for a in n.names:
                imported.add(a.asname or a.name)
    tools = []
    for n in tree.body:
        if isinstance(n, ast.FunctionDef):
            for d in n.decorator_list:
                fn = d.func if isinstance(d, ast.Call) else d
                if isinstance(fn, ast.Attribute) and fn.attr == "tool":
                    tools.append(n.name)
    return tools, imported

class ShadowGuardTest(unittest.TestCase):
    def test_no_tool_name_shadows_an_imported_module(self):
        tools, imported = _tools_and_imports(MCP_SERVER_PY.read_text())
        clash = set(tools) & imported
        self.assertEqual(clash, set(),
                         f"MCP tool name(s) {clash} shadow imported module(s) — the body will "
                         f"resolve the tool, not the module (AttributeError at call time). Alias "
                         f"the import (e.g. `import conduct as conduct_engine`).")

    def test_the_known_tools_are_present(self):
        tools, _ = _tools_and_imports(MCP_SERVER_PY.read_text())
        for expected in ("init", "plan_status", "register_plan", "next_handoff",
                         "read_handoff", "next_phase", "record_phase", "close_unit",
                         "record_receipt", "escalate_unit", "conductor_status"):
            self.assertIn(expected, tools)

    def test_the_engine_tools_are_gone(self):
        tools, _ = _tools_and_imports(MCP_SERVER_PY.read_text())
        self.assertNotIn("conduct", tools)
        self.assertNotIn("plan", tools)

@unittest.skipUnless(_HAVE_MCP, "mcp package not installed")
class ToolCallThroughTest(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / ".praxis").mkdir()
        (self.root / ".praxis" / "config.json").write_text("{}\n")
        self.base = str(self.root)
        import mcp_server
        self.srv = mcp_server

    def tearDown(self):
        self._tmp.cleanup()

    def _json(self, s):
        return json.loads(s)

    def test_register_plan_then_pull_does_not_spawn(self):
        tasks = json.dumps([{"intent": "types", "id": "types", "task_kind": "create"},
                            {"intent": "solver", "id": "solver", "depends_on": ["types"]}])
        reg = self._json(self.srv.register_plan(tasks, search_base=self.base))
        self.assertEqual(reg["status"], "registered")
        self.assertEqual(reg["plan"]["units"], ["types", "solver"])
        pull = self._json(self.srv.next_handoff(search_base=self.base))
        self.assertEqual(pull["status"], "ready")
        self.assertEqual(pull["unit"], "types")
        import journal
        self.assertEqual(journal.open_unit(self.root)["unit"], "types")

    def test_next_handoff_no_plan(self):
        out = self._json(self.srv.next_handoff(search_base=self.base))
        self.assertEqual(out["status"], "no-plan")

    def test_plan_status_reports_progress(self):
        tasks = json.dumps([{"intent": "a", "id": "a"}])
        self.srv.register_plan(tasks, search_base=self.base)
        out = self._json(self.srv.plan_status(search_base=self.base))
        self.assertEqual(out["status"], "open")
        self.assertIn("a", out["progress"]["waiting"])

    def test_status_resolves_its_modules(self):
        st = self._json(self.srv.conductor_status(search_base=self.base))
        self.assertIn("summary", st)

    def test_gaps_and_mint_tools_are_gone(self):
        tools, _ = _tools_and_imports(MCP_SERVER_PY.read_text())
        self.assertNotIn("conductor_gaps", tools)
        self.assertNotIn("conductor_mint", tools)

    def test_bad_json_is_reported_not_raised(self):
        out = self._json(self.srv.register_plan("{not json", search_base=self.base))
        self.assertIn("error", out)

if __name__ == "__main__":
    unittest.main()
