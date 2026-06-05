#!/usr/bin/env python3
"""Assemble all rendered formats into one labelled contact sheet for review."""
import json, os, math, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

PROJ = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(".").resolve()
SKILL_FONTS = Path(__file__).resolve().parent.parent / "assets" / "fonts"
os.chdir(PROJ)

F = json.load(open("formats.json"))["formats"]
CELL_W, PAD, LABEL_H = 460, 34, 54
COLS = 3
BG=(22,20,46); CARD=(36,33,74); TXT=(255,255,255); SUB=(150,200,230)
def _font(name, size):
    for base in (PROJ/"assets/fonts", SKILL_FONTS):
        if (base/name).exists():
            return ImageFont.truetype(str(base/name), size)
    return ImageFont.load_default()
fnt, fnt2 = _font("Montserrat.ttf",22), _font("OpenSans.ttf",18)

cells=[]
for f in F:
    p=f"out/{f['key']}.png"
    if not os.path.exists(p): continue
    im=Image.open(p).convert("RGB")
    scale=min(CELL_W/im.width, CELL_W/im.height)
    tw,th=int(im.width*scale),int(im.height*scale)
    im=im.resize((tw,th), Image.LANCZOS)
    cells.append((f,im))

rows=math.ceil(len(cells)/COLS)
cell_box=CELL_W+PAD
sheet_w=COLS*cell_box+PAD
sheet_h=rows*(CELL_W+LABEL_H+PAD)+PAD+70
sheet=Image.new("RGB",(sheet_w,sheet_h),BG)
d=ImageDraw.Draw(sheet)
_title="one design · every size"
try:   # brand the header from the project's own content.json when available
    _c=json.load(open("content.json")); _b=(_c.get("brand") or {})
    _nm=_b.get("name") or _c.get("headline") or ""
    if _nm: _title=f"{_nm}  —  one design, every size"
except Exception: pass
d.text((PAD,24),_title,font=fnt,fill=TXT)

for i,(f,im) in enumerate(cells):
    r,c=divmod(i,COLS)
    x=PAD+c*cell_box
    y=70+PAD+r*(CELL_W+LABEL_H+PAD)
    # card
    d.rounded_rectangle([x,y,x+CELL_W,y+CELL_W+LABEL_H],12,fill=CARD)
    ox=x+(CELL_W-im.width)//2
    oy=y+(CELL_W-im.height)//2
    sheet.paste(im,(ox,oy))
    d.text((x+14,y+CELL_W+8), f["label"], font=fnt, fill=TXT)
    d.text((x+14,y+CELL_W+32), f'{f["w"]}×{f["h"]}  ·  {f["layoutClass"]}/{f["level"]}', font=fnt2, fill=SUB)

sheet.save("out/_contact_sheet.png")
print("wrote out/_contact_sheet.png", sheet.size)
