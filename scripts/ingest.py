#!/usr/bin/env python3
"""
Ingest a design from any supported tool and produce a *draft* content model with
a full STYLE token block — so the brand-agnostic engine renders it on-brand.

    python scripts/ingest.py <input-file> [project-dir]

Supported inputs: .psd/.psb (Photoshop, layer-aware) · .ai/.pdf (Illustrator /
Canva PDF export) · .svg · .png/.jpg. Writes <project>/content.json
(or content.draft.json if one exists), copies formats.json in, and saves
assets/components/hero.png.

What it derives automatically (all editable afterwards):
  • palette  -> background, ink, accent, headline, scrim, light/dark mode
  • script   -> Arabic/Hebrew text flips dir:rtl and picks an Arabic font (Cairo)
  • text     -> headline / subhead / body from live text or PSD type layers
  • hero     -> largest non-background layer (PSD) or a rembg subject cutout
The richer the source, the more is auto-filled; a flat PNG gives hero + palette only.
"""
import sys, os, json, shutil, colorsys, io
from pathlib import Path
from collections import Counter

SKILL_DIR = Path(__file__).resolve().parent.parent
RASTER_EXT = {".png",".jpg",".jpeg",".webp",".bmp",".tif",".tiff"}

DEFAULT_CONTENT = {
  "_comment":"Draft from ingest.py — EDIT copy + style tokens, then run build.py.",
  "brand":{"name":"", "tagline":""},
  "copy":{"kicker":"", "headline":"YOUR HEADLINE",
          "subhead":"A short supporting line that sells the idea in one breath",
          "body":"One or two plain sentences, shown only where there is room.",
          "cta":"Learn more", "contact":{}},
  "style":{},                       # filled by derive_style()
  "assets":{"hero":"assets/components/hero.png"}
}

def log(*a): print("[ingest]", *a)
def hexof(rgb): return "#%02x%02x%02x" % tuple(int(c) for c in rgb[:3])
def _rgb(h): return tuple(int(h[i:i+2],16) for i in (1,3,5))
def _lum(rgb): return (0.2126*rgb[0]+0.7152*rgb[1]+0.0722*rgb[2])/255
def _hls(h): r,g,b=_rgb(h); return colorsys.rgb_to_hls(r/255,g/255,b/255)
def _shift(h, dl):
    H,L,S=_hls(h); L=max(0,min(1,L+dl)); r,g,b=colorsys.hls_to_rgb(H,L,S)
    return "#%02x%02x%02x"%(int(r*255),int(g*255),int(b*255))
def _has_rtl(s): return any('֐'<=c<='ۿ' or 'ݐ'<=c<='ݿ' for c in (s or ""))

# ----------------------------------------------------------------- rasterise
def load_raster(path):
    from PIL import Image
    ext = path.suffix.lower()
    if ext in RASTER_EXT or ext in (".psd",".psb"):
        return Image.open(path).convert("RGBA")
    if ext in (".pdf",".ai"):
        import fitz
        page = fitz.open(path)[0]
        scale = 2000/max(page.rect.width, page.rect.height)
        pix = page.get_pixmap(matrix=fitz.Matrix(scale,scale), alpha=False)
        return Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGBA")
    if ext == ".svg":
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b=p.chromium.launch(); pg=b.new_page(viewport={"width":1600,"height":1600})
            pg.goto("file://"+str(path.resolve())); png=pg.screenshot(full_page=True); b.close()
        return Image.open(io.BytesIO(png)).convert("RGBA")
    raise SystemExit(f"Unsupported input type: {ext}")

# ----------------------------------------------------------------- palette + style
def palette(img, n=8):
    from PIL import Image
    bg = Image.new("RGB", img.size, (255,255,255)); bg.paste(img, mask=img.split()[-1])
    q = bg.resize((240, max(1,int(240*img.height/img.width)))).convert("P", palette=Image.ADAPTIVE, colors=n)
    pal = q.getpalette()
    return [(hexof(pal[idx*3:idx*3+3]), cnt) for cnt, idx in sorted(q.getcolors(), reverse=True)]

def _corner_bg(img):
    from PIL import Image
    bg=Image.new("RGB",img.size,(255,255,255)); bg.paste(img,mask=img.split()[-1])
    w,h=bg.size
    c=Counter(bg.getpixel(p) for p in [(2,2),(w-3,2),(2,h-3),(w-3,h-3)])
    return c.most_common(1)[0][0]

def derive_style(img, pal, text):
    """Best-effort style tokens from the artwork. Always editable afterwards."""
    rtl = _has_rtl(text)
    cols = [h for h,_ in pal] or ["#222222","#dddddd","#8a8a8a"]
    sat  = lambda h:_hls(h)[2]; lit = lambda h:_hls(h)[1]
    accent  = max(cols, key=sat)
    darkest = min(cols, key=lit)
    bgc = _corner_bg(img); light = _lum(bgc) > 0.6; bgh = hexof(bgc)
    if light:
        ink = darkest
        strong = [c for c in cols if sat(c) > 0.35 and lit(c) < 0.55]
        headline = min(strong, key=lit) if strong else ink
        bg = f"radial-gradient(60% 55% at 78% 20%, {_shift(bgh,0.04)} 0%, transparent 60%), linear-gradient(150deg, #ffffff 0%, {bgh} 66%, {_shift(bgh,-0.05)} 100%)"
        cta = {"bg":"#ffffff","ink":headline,"border":f"0.3vmin solid {_shift(bgh,-0.12)}"}
        scrim = bgh; stage = bgh
    else:
        ink = "#ffffff"; headline = "#ffffff"
        bg = f"linear-gradient(135deg, {darkest} 0%, {_shift(darkest,0.08)} 100%)"
        cta = {"bg":accent, "ink":darkest}
        scrim = darkest; stage = darkest
    fonts = {"display":"Cairo.ttf","body":"Cairo.ttf"} if rtl else {"display":"Montserrat.ttf","body":"OpenSans.ttf"}
    return {"dir":"rtl" if rtl else "ltr", "lang":"ar" if rtl else "en", "fonts":fonts,
            "bg":bg, "stageBg":stage, "ink":ink, "accent":accent, "headline":headline,
            "uppercase": (not rtl), "scrim":scrim, "decor":"none", "cta":cta}

# ----------------------------------------------------------------- hero cutout
def cutout(img, out_path):
    try:
        from rembg import remove, new_session
        from PIL import Image, ImageFilter
        import numpy as np
        res = remove(img, session=new_session("isnet-general-use"), post_process_mask=True)
        a = np.array(res)
        res.putalpha(Image.fromarray(a[...,3]).filter(ImageFilter.MinFilter(5)))
        bb = res.getbbox()
        if bb: res = res.crop(bb)
        out_path.parent.mkdir(parents=True, exist_ok=True); res.save(out_path)
        log(f"hero cutout -> {out_path.name}  {res.size}")
    except Exception as e:
        log("hero cutout skipped (rembg failed):", e)

# ----------------------------------------------------------------- PSD layers
def extract_psd(path, proj):
    from psd_tools import PSDImage
    psd = PSDImage.open(path); W,H = psd.width, psd.height
    comp = psd.composite().convert("RGBA")
    texts=[]; pixels=[]
    for layer in psd.descendants():
        try:
            if not layer.is_visible(): continue
            if layer.kind == "type":
                t=(layer.text or "").strip()
                if t: texts.append((t, layer.bbox))
            elif layer.kind in ("pixel","smartobject","shape"):
                bb=layer.bbox; area=(bb[2]-bb[0])*(bb[3]-bb[1])
                pixels.append((area, area >= 0.9*W*H, layer))
        except Exception: continue
    copy={}
    for role,(txt,_) in zip(["headline","subhead","body"],
                            sorted(texts, key=lambda t:-((t[1][2]-t[1][0])*(t[1][3]-t[1][1])))):
        copy[role]=txt
    if texts: log(f"PSD: {len(texts)} text layer(s) -> {list(copy)}")
    cands=[l for (area,full,l) in sorted(pixels,reverse=True,key=lambda x:x[0]) if not full]
    hero=proj/"assets/components/hero.png"
    if cands:
        try: cands[0].composite().convert("RGBA").save(hero); log(f"PSD hero <- layer '{cands[0].name}'")
        except Exception: cutout(comp, hero)
    else: cutout(comp, hero)
    return {"copy":copy, "_text":" ".join(t for t,_ in texts)}

# ----------------------------------------------------------------- generic raster/vector
def extract_generic(path, proj):
    from PIL import ImageDraw
    img = load_raster(path); copy={}; blob=""; boxes=[]
    if path.suffix.lower() in (".pdf",".ai"):
        try:
            import fitz
            page = fitz.open(path)[0]
            sc = 2000/max(page.rect.width, page.rect.height)   # same scale as load_raster
            spans=[]
            for b in page.get_text("dict")["blocks"]:
                for ln in b.get("lines",[]):
                    for sp in ln["spans"]:
                        if sp["text"].strip():
                            spans.append((sp["size"], sp["text"].strip()))
                            x0,y0,x1,y1 = sp["bbox"]; boxes.append((x0*sc,y0*sc,x1*sc,y1*sc))
            blob=" ".join(t for _,t in spans)
            for role,(_,txt) in zip(["headline","subhead","body"], sorted(spans, reverse=True)):
                copy[role]=txt
            log(f"live text: {len(spans)} spans -> {list(copy)}" if spans else "no live text (type copy in by hand)")
        except Exception as e: log("text scan skipped:", e)
    # erase the live-text boxes first, so the hero cutout keeps the artwork, not the type
    hero_src = img
    if boxes:
        hero_src = img.copy(); d = ImageDraw.Draw(hero_src); fill = _corner_bg(img)+(255,)
        for (x0,y0,x1,y1) in boxes: d.rectangle([x0-6,y0-6,x1+6,y1+6], fill=fill)
        log(f"masked {len(boxes)} text box(es) before hero cutout")
    cutout(hero_src, proj/"assets/components/hero.png")
    return {"copy":copy, "_text":blob}

# ----------------------------------------------------------------- main
def main():
    if len(sys.argv) < 2: raise SystemExit("usage: ingest.py <input-file> [project-dir]")
    path = Path(sys.argv[1]).expanduser().resolve()
    proj = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else Path(".").resolve()
    if not path.exists(): raise SystemExit(f"no such file: {path}")
    (proj/"assets").mkdir(parents=True, exist_ok=True)
    log(f"input  : {path.name} ({path.suffix.lower()})"); log(f"project: {proj}")

    ext = path.suffix.lower()
    if ext in (".psd",".psb"):
        try: ov = extract_psd(path, proj)
        except Exception as e: log("PSD parse failed -> flattened raster:", e); ov = extract_generic(path, proj)
    else:
        ov = extract_generic(path, proj)

    img = load_raster(path); pal = palette(img)
    text = (ov.get("_text","") + " " + " ".join(ov.get("copy",{}).values())).strip()
    style = derive_style(img, pal, text)
    log(f"style  : {'RTL/Arabic' if style['dir']=='rtl' else 'LTR'}, "
        f"{'light' if style['ink'].lower()!='#ffffff' else 'dark'} bg, accent {style['accent']}")

    content = json.loads(json.dumps(DEFAULT_CONTENT))
    content["style"] = style
    content["copy"].update({k:v for k,v in ov.get("copy",{}).items() if v})
    content["_extractedPalette"] = [h for h,_ in pal]

    if not (proj/"formats.json").exists():
        shutil.copy(SKILL_DIR/"assets/formats.json", proj/"formats.json"); log("wrote formats.json")
    target = proj/"content.json"
    if target.exists(): target = proj/"content.draft.json"; log("content.json exists -> content.draft.json")
    target.write_text(json.dumps(content, indent=2, ensure_ascii=False)); log(f"wrote {target.name}")
    print("\nNEXT: review", target.name, "(copy + style tokens), check assets/components/hero.png,")
    print("      then:  python scripts/build.py", str(proj))

if __name__ == "__main__":
    main()
