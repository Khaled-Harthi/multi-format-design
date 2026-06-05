#!/usr/bin/env python3
"""
Re-adapt by RE-ARRANGING the real components from layers.json (preserve, don't
regenerate). The kit comes from decompose.py: hero (photo, centre or anchored),
headline / subhead / body, footer(s), qr, logo, and blob decorations — each a real
lifted pixel, never re-typeset.

    python scripts/recompose.py [project] [--only k,k] [--overrides overrides.json]

Layout is chosen by the target aspect:
  • portrait  -> poster: logo top · headline+subhead · hero centred · body · qr · footer
  • landscape -> split:  hero one side · (logo·headline·subhead·body·footer) other side · qr corner
  • square    -> hybrid
A full-bleed 'background' raster (product ads) keeps the old cover/anchored behaviour.

overrides.json (all optional, per format key) — SKILL.md has the full, current knob list:
  heroAnchorY/heroSide/heroPct/heroFit, marginPct/gapPct/widthPct/cap/scale, side/topPct,
  logoPct/qrPct/framePos/photoWidthPct, decorOpacity/decorScale/hideDecor, and portrait
  positions titleTop/heroTop/bodyTop/qrTop/noteTop/logoTop/buttonTop/buttonPct/buttonGap.
"""
import sys, os, json, argparse
from pathlib import Path
from PIL import Image as _PILImage

ap=argparse.ArgumentParser(); ap.add_argument("project",nargs="?",default=".")
ap.add_argument("--only",default=None); ap.add_argument("--overrides",default=None)
A,_=ap.parse_known_args()
_ovp=Path(A.overrides).resolve() if A.overrides else None   # resolve BEFORE chdir
PROJ=Path(A.project).resolve(); os.chdir(PROJ)
M=json.load(open("layers.json")); F=json.load(open("formats.json"))
OVR=json.load(open(_ovp)) if (_ovp and _ovp.exists()) else {}
SRCW,SRCH=M["page"]; DIR=M.get("dir","ltr"); BGC=M.get("bgColor","#ffffff"); SUBJ=M.get("subject","left")
RTL=DIR=="rtl"
L={}
for la in M["layers"]: L.setdefault(la["role"],[]).append(la)
def U(rel): return "file://"+os.path.abspath(rel)
def first(role): return L[role][0] if L.get(role) else None
def width_of(la): b=la["bbox"]; return max(1e-3,b[2]-b[0])
def blobs(): return [la for la in L.get("decoration",[]) if la.get("kind")!="logo"]
def logo(): return next((la for la in L.get("decoration",[]) if la.get("kind")=="logo"), None)

def img(la, css): return f'<img src="{U(la["file"])}" style="position:absolute;{css}">'

# ---- background blob/decoration: anchor to the edge/corner it originally bled from ----
def blob_html(la, cw, ch, ov):
    b=la["bbox"]; ox0,oy0,ox1,oy1=b; ocx=(ox0+ox1)/2; ocy=(oy0+oy1)/2; ow=ox1-ox0
    full = ox0<=0.06 and ox1>=0.94
    w = (1.12 if full else max(0.30, min(0.6, ow))) * cw
    if full or 0.4<ocx<0.6: hx=f"left:{(cw-w)/2:.0f}px"
    elif ocx<=0.4:          hx="left:-4%"
    else:                   hx="right:-4%"
    vy = "top:-3%" if ocy<0.42 else ("bottom:-3%" if ocy>0.58 else "top:32%")
    op = ov.get("decorOpacity", 1.0)
    return img(la, f"{hx};{vy};width:{w:.0f}px;opacity:{op};z-index:0")

# ---- a vertical stack of text parts, widths kept in their real relative proportion ----
_ar={}
def aspect(la):
    if la["file"] not in _ar:
        try:
            with _PILImage.open(la["file"]) as im: _ar[la["file"]]=im.width/max(1,im.height)
        except Exception: _ar[la["file"]]=1.0
    return _ar[la["file"]]
def fit_scale(items, colw_px, avail_h_px, gap_px, scale, cap):
    """Estimate the stack's rendered height from each PNG's real aspect and return a scale
    that keeps it within avail_h_px — so a crowded column can never overflow the canvas."""
    if not items: return 1.0
    base=max(width_of(x) for x in items); tot=gap_px*(len(items)-1)
    for la in items:
        wpx=min(width_of(la)/base*scale, cap)*colw_px
        tot+=wpx/max(0.05, aspect(la))
    return min(1.0, avail_h_px/tot) if tot>0 else 1.0
def stack(items, colw_px, align, gap_px, scale=1.0, cap=1.0):
    if not items: return ""
    base=max(width_of(x) for x in items)
    rows=[]
    for la in items:
        w=min(width_of(la)/base*scale, cap)*100
        rows.append(f'<img src="{U(la["file"])}" style="width:{w:.1f}%">')
    return (f'<div style="width:{colw_px:.0f}px;display:flex;flex-direction:column;'
            f'align-items:{align};gap:{gap_px:.0f}px">{"".join(rows)}</div>')

def read_order(items):
    """Order layers the way the source reads: top-to-bottom, and within a row right-to-left
    for RTL (left-to-right otherwise). Used when re-stacking copy so the new layout preserves
    the designer's reading flow instead of an arbitrary by-size role order."""
    return sorted(items, key=lambda la: (round(la["bbox"][1]*40),
                                         -la["bbox"][0] if RTL else la["bbox"][0]))

def captions(role, cw, ch, ov, y_css):
    """Place a band of small captions (eyebrows at top, contact/footer at bottom). One is
    centred; two go to their original left/right; their real relative width is preserved."""
    cs=sorted(L.get(role,[]), key=lambda la: la["bbox"][0])
    if not cs: return ""
    m=ov.get("marginPct",7)
    if len(cs)==1:
        return img(cs[0], f"left:50%;{y_css};transform:translateX(-50%);width:{min(50,width_of(cs[0])*60):.0f}%")
    left,right=cs[0],cs[-1]
    return (img(left,  f"left:{m}%;{y_css};width:{min(42,width_of(left)*62):.0f}%")+
            img(right, f"right:{m}%;{y_css};width:{min(40,width_of(right)*62):.0f}%"))

# ======================================================================================
# Dispatcher: a full-bleed BACKGROUND raster -> product-ad model (cover/anchored bg +
# text column on the empty side). Otherwise -> poster/split model (hero + blobs + stacks).
# ======================================================================================
def compose(f):
    return compose_product(f) if first("background") else compose_poster(f)

# ---------------- product-ad model (background + content column + button + decor) ----
def decor_html(la, cw, ch, ov):
    b=la["bbox"]; cx=(b[0]+b[2])/2; cy=(b[1]+b[3])/2; sw=(b[2]-b[0])*SRCW
    scale=(min(cw,ch)/min(SRCW,SRCH))*ov.get("decorScale",1.0)
    w=min(sw*scale, 0.42*cw)
    horiz="left:-3%" if cx<0.5 else "right:-3%"; vert="top:-6%" if cy<0.5 else "bottom:-6%"
    op=ov.get("decorOpacity",0.7)
    return f'<img src="{U(la["file"])}" style="position:absolute;{horiz};{vert};width:{w:.0f}px;opacity:{op};z-index:1">'

def bg_product(cw, ch, ov):
    bg=first("background"); portrait=ch/cw>=1.25
    if not bg: return ""
    if portrait:
        pw=ov.get("photoWidthPct",150)
        return img(bg, f"left:50%;bottom:0;transform:translateX(-50%);width:{pw}%;max-width:none;"
                   f"-webkit-mask-image:linear-gradient(to bottom,transparent 0,#000 15%);"
                   f"mask-image:linear-gradient(to bottom,transparent 0,#000 15%);z-index:0")
    fp=ov.get("framePos","left" if SUBJ=="left" else "right")
    return f'<div style="position:absolute;inset:0;z-index:0;background:url(\'{U(bg["file"])}\') {fp} center/cover"></div>'

def content_col(cw, ch, ov):
    portrait=ch/cw>=1.25
    where=ov.get("side","top" if portrait else ("right" if SUBJ=="left" else "left"))
    margin=ov.get("marginPct",8); scale=ov.get("scale",1.0); gap=ov.get("gapPct",3.2)
    if where=="top": pos=f"left:{margin}%;right:{margin}%;top:{ov.get('topPct',8)}%"; align="center"
    else:
        width=ov.get("widthPct",46); top=ov.get("topPct",50)
        pos=f"{where}:{margin*0.6:.0f}%;top:{top}%;transform:translateY(-50%);width:{width}%"
        align="flex-end" if RTL else "flex-start"
    items=[L[r][0] for r in ("headline","subhead","body") if L.get(r)]
    if L.get("button"): items.append(L["button"][0])
    if not items: return ""
    base=max(width_of(x) for x in items)
    rows=[]
    for la in items:
        w=min(width_of(la)/base*scale,1.0)*100; mt="margin-top:2%" if la["role"]=="button" else ""
        rows.append(f'<img src="{U(la["file"])}" style="width:{w:.0f}%;{mt}">')
    return (f'<div style="position:absolute;{pos};display:flex;flex-direction:column;'
            f'align-items:{align};gap:{gap}%;z-index:2">{"".join(rows)}</div>')

def compose_product(f):
    cw,ch=f["w"],f["h"]; ov=OVR.get(f["key"],{})
    P=[f'<div class="stage" style="width:{cw}px;height:{ch}px;background:{BGC}">', bg_product(cw,ch,ov)]
    if not ov.get("hideDecor",False):
        for la in L.get("overlay",[])+L.get("decoration",[]):
            P.append(decor_html(la,cw,ch,ov))
    P.append(content_col(cw,ch,ov)); P.append("</div>")
    return "".join(P)

# ---------------- poster/split model (hero + headline/subhead/body + footer/qr/logo) --
def compose_poster(f):
    cw,ch=f["w"],f["h"]; ov=OVR.get(f["key"],{})
    portrait = ch/cw>=1.18; landscape = cw/ch>=1.18
    P=[f'<div class="stage" style="width:{cw}px;height:{ch}px;background:{BGC}">']

    # blob decorations to their original corners
    if not ov.get("hideDecor",False):
        for la in blobs(): P.append(blob_html(la,cw,ch,ov))

    hero=first("hero"); lg=logo()
    head=[x for x in (first("headline"),) if x]; sub=[x for x in (first("subhead"),) if x]
    body=[x for x in (first("body"),) if x]
    margin=ov.get("marginPct",7); gap=ov.get("gapPct",3.2); scale=ov.get("scale",1.0)

    if landscape:
        # A very short canvas (a web strip) can't carry a stack: keep only headline beside
        # the hero — a glanceable minimal. Tall wides (billboard, 16:9) keep the full column.
        compact = ch<420 and (f.get("level")=="minimal" or cw/ch>4)
        heroPct=ov.get("heroPct", 92 if compact else 84)
        if hero:
            side = ov.get("heroSide", "left" if not RTL else "right")
            ayl = ov.get("heroAnchorY", hero.get("anchorY","center"))   # reviewer can override the silhouette anchor
            if ayl=="bottom" and not compact:   # seat a cropped figure on the floor
                P.append(img(hero, f"{side}:3.5%;bottom:0;height:{heroPct}%;z-index:1"))
            else:
                P.append(img(hero, f"{side}:3.5%;top:50%;transform:translateY(-50%);height:{heroPct}%;z-index:1"))
        colside = "right" if not RTL else "left"
        colw=ov.get("widthPct",46)/100*cw
        # everything that isn't the hero goes in the content COLUMN (eyebrows on top,
        # contact/footer at the bottom) so nothing collides with the side hero.
        col_items=[]
        if compact:
            col_items+=head+(sub if ch>170 else [])
        else:
            col_items+=sorted(L.get("note",[]),key=lambda la:la["bbox"][0])
            if lg: col_items.append(lg)
            col_items+=head+sub+body+([first("button")] if first("button") else [])
            col_items+=sorted(L.get("footer",[]),key=lambda la:la["bbox"][0])
        gap_px=ov.get("gapPct",2.6)/100*ch; cap=ov.get("cap",0.92)
        sfit=fit_scale(col_items, colw, 0.88*ch, gap_px, scale, cap)
        inner=stack(col_items, colw, "center", gap_px, scale*sfit, cap=cap)
        P.append(f'<div style="position:absolute;{colside}:{margin*0.7:.0f}%;top:50%;transform:translateY(-50%);'
                 f'display:flex;justify-content:center;width:{colw:.0f}px;z-index:2">{inner}</div>')
        if not compact:
            qr=first("qr")
            if qr:
                qp=ov.get("qrPct",6.6); qx="right" if not RTL else "left"
                P.append(img(qr, f"{qx}:3%;bottom:7%;width:{qp}%;z-index:3"))

    elif portrait and hero is not None and hero.get("framed") and ov.get("heroAnchorY","")!="overlay":
        # FRAMED PHOTO, portrait -> SPLIT: the photo owns its own band (bottom), all copy stacks
        # in the band above it (source reading order). Text never overlays an opaque photo.
        heroPct=ov.get("heroPct",54); seam=100-heroPct
        if lg: P.append(img(lg, f"left:50%;top:{ov.get('logoTop',5)}%;transform:translateX(-50%);height:{ov.get('logoPct',6)}%;z-index:2"))
        if ov.get("heroFit","cover")=="contain":
            P.append(img(hero, f"left:50%;bottom:0;transform:translateX(-50%);height:{heroPct}%;z-index:1"))
        else:
            P.append(f'<div style="position:absolute;left:0;right:0;bottom:0;height:{heroPct}%;'
                     f'background:url(\'{U(hero["file"])}\') center bottom/cover;z-index:1"></div>')
        titems=read_order(head+sub+body+L.get("note",[]))
        colw=cw*(1-2*margin/100)
        gap_px=ov.get("gapPct",2.8)/100*ch
        topPad=ov.get("titleTop",6) + (ov.get("logoPct",6)+2 if lg else 0)
        btn=first("button"); btn_h=(0.085*ch if btn else 0)
        avail=(seam/100*ch)-(topPad/100*ch)-btn_h-0.03*ch
        cap=ov.get("cap",0.82)
        sfit=fit_scale(titems, colw, avail, gap_px, scale, cap)
        inner=stack(titems, colw, "center", gap_px, scale*sfit, cap=cap)
        P.append(f'<div style="position:absolute;left:{margin}%;right:{margin}%;top:{topPad}%;'
                 f'display:flex;justify-content:center;z-index:2">{inner}</div>')
        if btn:
            bw=ov.get("buttonPct",44)   # seat the pill just ABOVE the photo band's top edge
            P.append(img(btn, f"left:50%;bottom:{heroPct+ov.get('buttonGap',2)}%;transform:translateX(-50%);width:{bw}%;z-index:3"))

    elif portrait:
        # poster: logo top · headline+subhead · hero centre · body · qr · footer
        if lg: P.append(img(lg, f"left:50%;top:{ov.get('logoTop',5)}%;transform:translateX(-50%);height:{ov.get('logoPct',6)}%;z-index:2"))
        topblock=stack(head+sub, cw*0.78, "center", 0.012*ch, scale, cap=0.78)
        P.append(f'<div style="position:absolute;left:50%;top:{ov.get("titleTop",12)}%;transform:translateX(-50%);'
                 f'display:flex;justify-content:center;width:78%;z-index:2">{topblock}</div>')
        ay=ov.get("heroAnchorY", hero.get("anchorY","center")) if hero else "center"
        if hero:
            if ay=="bottom":                                    # seat a cropped figure on the floor
                hp=ov.get("heroPct",80)
                P.append(img(hero, f"left:50%;bottom:0;transform:translateX(-50%);width:{hp}%;z-index:1"))
            elif ay=="top":
                hp=ov.get("heroPct",72)
                P.append(img(hero, f"left:50%;top:{ov.get('heroTop',18)}%;transform:translateX(-50%);width:{hp}%;z-index:1"))
            else:
                hp=ov.get("heroPct",70)
                P.append(img(hero, f"left:50%;top:{ov.get('heroTop',46)}%;transform:translate(-50%,-50%);width:{hp}%;z-index:1"))
        if body:
            P.append(img(body[0], f"left:50%;top:{ov.get('bodyTop',67)}%;transform:translateX(-50%);width:82%;z-index:2"))
        if first("button"):
            P.append(img(first("button"), f"left:50%;top:{ov.get('buttonTop',75)}%;transform:translateX(-50%);width:36%;z-index:2"))
        qr=first("qr")
        if qr: P.append(img(qr, f"left:50%;top:{ov.get('qrTop',78.5)}%;transform:translateX(-50%);width:{ov.get('qrPct',15)}%;z-index:2"))
        P.append(captions("note",cw,ch,ov,f"top:{ov.get('noteTop',5)}%"))
        if ay=="bottom":
            # the figure owns the bottom-centre; tuck a small contact/decoration into a corner
            fs=L.get("footer",[])
            if fs: P.append(img(fs[0], f"right:7%;bottom:5%;width:{min(20,width_of(fs[0])*55):.0f}%;z-index:3"))
        else:
            P.append(captions("footer",cw,ch,ov,"bottom:4%"))

    else:
        # square hybrid: hero one side, everything else stacked in the column on the other
        hs = "right" if not RTL else "left"; cs = "left" if not RTL else "right"
        if hero: P.append(img(hero, f"{hs}:4%;top:46%;transform:translateY(-50%);width:46%;z-index:1"))
        items=sorted(L.get("note",[]),key=lambda la:la["bbox"][0])
        if lg: items.append(lg)
        items+=head+sub+body+([first("button")] if first("button") else [])
        items+=sorted(L.get("footer",[]),key=lambda la:la["bbox"][0])
        gap_px=ov.get("gapPct",2.6)/100*ch; cap=ov.get("cap",0.92)
        sfit=fit_scale(items, cw*0.46, 0.86*ch, gap_px, scale, cap)
        inner=stack(items, cw*0.46, "flex-start" if not RTL else "flex-end", gap_px, scale*sfit, cap=cap)
        P.append(f'<div style="position:absolute;{cs}:{margin}%;top:50%;transform:translateY(-50%);'
                 f'display:flex;width:46%;z-index:2">{inner}</div>')
        qr=first("qr")
        if qr: P.append(img(qr, f"{cs}:{margin}%;bottom:5%;width:9%;z-index:3"))

    P.append("</div>")
    return "".join(P)

def main():
    from playwright.sync_api import sync_playwright
    from PIL import Image
    os.makedirs("out", exist_ok=True); os.makedirs("work", exist_ok=True)
    only=set(s.strip() for s in A.only.split(",")) if A.only else None
    with sync_playwright() as p:
        b=p.chromium.launch()
        for f in F["formats"]:
            if only and f["key"] not in only: continue
            doc=(f'<!doctype html><html dir="{DIR}"><head><meta charset="utf-8"><style>'
                 f'*{{margin:0;padding:0;box-sizing:border-box}}img{{display:block}}'
                 f'.stage{{position:relative;overflow:hidden}}</style></head><body>{compose(f)}</body></html>')
            hp=os.path.abspath(f"work/{f['key']}.html"); open(hp,"w").write(doc)
            pg=b.new_page(viewport={"width":f["w"],"height":f["h"]},device_scale_factor=2)
            pg.goto("file://"+hp); pg.wait_for_timeout(300)
            pg.screenshot(path=f"work/{f['key']}@2x.png",clip={"x":0,"y":0,"width":f["w"],"height":f["h"]})
            pg.close()
            Image.open(f"work/{f['key']}@2x.png").convert("RGB").resize((f["w"],f["h"]),Image.LANCZOS).save(f"out/{f['key']}.png")
            print(f"  out/{f['key']}.png  {f['w']}x{f['h']}  [{f['layoutClass']}]")
        b.close()

if __name__=="__main__": main()
