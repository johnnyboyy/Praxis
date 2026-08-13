#!/usr/bin/env python3
"""Generator for diagram.webp — the praxis high-level overview (dark, monospace).
Boxes are drawn rectangles (not border glyphs) so alignment is exact. Edit `segments`
and re-run: `python3 diagram.py`."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = str(Path(__file__).resolve().parent / "diagram.webp")
FONT = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 26)
FG, BG, BORDER = "#e8e8e8", "#000000", "#9a9a9a"
PAD, LH, INSET = 40, 40, 22

segments = [
    ("plain", [" task", "   │", "   ▼"]),
    ("box", [
        "PLANNER  (intake workflow)",
        "  interview → frontier (cleared)",
        "  BARRIER decided — acceptance tests authored UP FRONT",
        "                    (contract) + coverage threshold set",
    ]),
    ("plain", ["     │  plan: units decomposed, each pointing at barrier items", "     ▼"]),
    ("box", [
        "FAN OUT — implementers (parallel, each isolated)",
        "",
        "  for each unit:",
        "    implement → [ coverage gate ]    ← PER-UNIT, fast, in-progress",
        "                unit \"done\" ⇔ acceptance tests pass at threshold",
        "                  │ pass",
        "                  ▼",
        "              test-cleanup — prune scaffolding (noise),",
        "                            keep the boundary tests",
    ]),
    ("plain", ["     │  all implementers finish", "     ▼"]),
    ("box", [
        "FINAL BARRIER — full suite + MUTATION signal    ← GLOBAL, slow,",
        "                                                  run ONCE",
        "    pass → close       fail → fix loop (bounded) → re-verify",
    ]),
    ("plain", ["     │  certified: close reachable ONLY through passed gates", "     ▼", " CLOSE"]),
]

meas = ImageDraw.Draw(Image.new("RGB", (1, 1)))
def w(s): return meas.textlength(s, font=FONT)

box_content_w = max(w(l) for typ, ls in segments if typ == "box" for l in ls)
box_right = PAD + INSET + box_content_w + INSET
img_w = int(box_right + PAD)
img_h = PAD * 2 + LH * sum(len(ls) for _, ls in segments) + 16 * sum(1 for t, _ in segments if t == "box")

img = Image.new("RGB", (img_w, img_h), BG)
d = ImageDraw.Draw(img)
y = PAD
for typ, ls in segments:
    if typ == "box":
        top = y - 4
        for l in ls:
            d.text((PAD + INSET, y), l, font=FONT, fill=FG)
            y += LH
        d.rounded_rectangle([PAD, top, box_right, y + 4], radius=6, outline=BORDER, width=2)
        y += 16
    else:
        for l in ls:
            d.text((PAD, y), l, font=FONT, fill=FG)
            y += LH
img.save(OUT, "WEBP", quality=92)
print(f"wrote {OUT}  ({img_w}x{img_h})")
