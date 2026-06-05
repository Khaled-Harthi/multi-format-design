#!/usr/bin/env python3
"""
Brand-agnostic multi-format design engine.

Reads content.json (copy + STYLE TOKENS + assets) and formats.json, then renders
each target size by RE-COMPOSING the components through a layout chosen by the
target's aspect ratio (not a naive scale/crop).

Nothing about any particular brand is baked in. Background, ink colour, accent,
fonts, text direction (LTR/RTL) and the optional decorative motif ALL come from
content.json's `style` block. The same engine renders a navy medical poster, a
cream Arabic perfume ad, or anything else — only the tokens differ.

  square     -> balanced composition, hero to one side
  portrait   -> vertical stack, hero centred-bottom (stories / standees)
  landscape  -> text / hero split
  strip      -> single horizontal row (web banners)
  billboard  -> huge headline + CTA, hero one side, no body (outdoor)

Content adapts by `level`: full | medium | minimal.
"""
import json, os, math, argparse
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser(description="Render every format from content.json + formats.json")
ap.add_argument("project", nargs="?", default=".", help="project dir with content.json / formats.json / assets")
ap.add_argument("--only", default=None, help="comma-separated format keys (default: all)")
ARGS, _ = ap.parse_known_args()
PROJ = Path(ARGS.project).resolve()
os.chdir(PROJ)

C  = json.load(open("content.json"))
F  = json.load(open("formats.json"))
CP = C.get("copy", {})
S  = C.get("style", C.get("theme", {})) or {}     # style tokens (legacy alias: theme)

def sget(k, d=None): return S.get(k, d)

# ---- universal style tokens (neutral fallbacks; ingest fills them per design) ----
RTL    = (sget("dir","ltr") == "rtl") or bool(sget("rtl", False))
DIRATTR= "rtl" if RTL else "ltr"
LANG   = sget("lang", "ar" if RTL else "en")
INK    = sget("ink", "#1b1c22")
BG     = sget("bg", "linear-gradient(135deg,#2a2e38 0%,#15181f 100%)")
STAGEBG= sget("stageBg", "#15181f")
ACCENT = sget("accent", "#7c8696")
HLCOL  = sget("headline", INK)
HLACC  = sget("headlineAccent")                    # if set: words after the 1st get this colour
UPPER  = "uppercase" if sget("uppercase", False) else "none"
TRACK  = "0" if RTL else sget("tracking", ".06em")
KTRACK = "0" if RTL else sget("kickerTracking", ".18em")
SCRIM  = sget("scrim", "#000000")                  # base colour of the footer overlay over the hero
DECOR  = sget("decor", "none")                     # none | hex | dots | soft
DECORCOL = sget("decorColor", INK)
_cta   = sget("cta", {}) or {}
CTA_BG = _cta.get("bg", ACCENT)
CTA_INK= _cta.get("ink", "#ffffff")
CTA_BD = _cta.get("border", "none")
HEROSHADOW = sget("heroShadow", "0 2vmin 5vmin rgba(0,0,0,.30)")
ALIGN  = "right" if RTL else "left"                # logical start edge

def _resolve_font(name):
    for base in (PROJ/"assets/fonts", SKILL_DIR/"assets/fonts"):
        if name and (base/name).exists():
            return str(base/name)
    return str(SKILL_DIR/"assets/fonts"/(name or "Montserrat.ttf"))
_f = sget("fonts", {}) or {}
FONT_DISPLAY = _resolve_font(_f.get("display", C.get("brand",{}).get("fontDisplayFile","Montserrat.ttf")))
FONT_BODY    = _resolve_font(_f.get("body",    C.get("brand",{}).get("fontBodyFile","OpenSans.ttf")))

_a = C.get("assets", {})
_hero = _a.get("hero") or _a.get("doctor") or ""   # legacy alias: doctor
HERO  = os.path.abspath(_hero) if _hero else ""
_logo = _a.get("logo") or ""
LOGO_IMG = os.path.abspath(_logo) if _logo else ""
BR = C.get("brand", {})
BRAND  = BR.get("name") or BR.get("logoTop") or ""
BRAND2 = BR.get("tagline") or BR.get("logoBottom") or ""

# ---------------------------------------------------------------- generic icons
def svg(inner, vb="0 0 24 24"):
    return f'<svg viewBox="{vb}" xmlns="http://www.w3.org/2000/svg" width="100%" height="100%">{inner}</svg>'
ICON = {
 "phone": svg('<path fill="currentColor" d="M6.6 2.5 3.3 3.6c-.7.2-1.1 1-1 1.7C3.5 12.9 9.1 18.5 16.7 19.7c.7.1 1.5-.3 1.7-1l1.1-3.3c.2-.6-.1-1.3-.7-1.6l-3.3-1.4c-.5-.2-1.1-.1-1.5.3l-1.2 1.2a13 13 0 0 1-5.2-5.2l1.2-1.2c.4-.4.5-1 .3-1.5L7.7 3.2c-.3-.6-.9-.9-1.1-.7z"/>'),
 "globe": svg('<g fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="9.2"/><ellipse cx="12" cy="12" rx="4" ry="9.2"/><path d="M3 12h18M4.4 7h15.2M4.4 17h15.2"/></g>'),
 "mail":  svg('<g fill="none" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round"><rect x="2.5" y="4.8" width="19" height="14.4" rx="2.2"/><path d="m3.2 6 8.8 6.6L20.8 6"/></g>'),
 "pin":   svg('<path fill="currentColor" d="M12 2a7 7 0 0 0-7 7c0 5 7 13 7 13s7-8 7-13a7 7 0 0 0-7-7zm0 9.5A2.5 2.5 0 1 1 12 6a2.5 2.5 0 0 1 0 5.5z"/>'),
}

# ---------------------------------------------------------------- decorative motif (optional, neutral)
def _hex_points(cx, cy, r):
    return [(cx + r*math.cos(math.radians(60*i-30)), cy + r*math.sin(math.radians(60*i-30))) for i in range(6)]
def decor_layer():
    if DECOR == "none":
        return ""
    if DECOR == "hex":
        r=46; w=round(math.sqrt(3)*r,2); h=round(3*r,2)
        paths=[]
        for cx,cy in [(0,0),(w,0),(0,h),(w,h),(w/2,h/2)]:
            pts=_hex_points(cx,cy,r); paths.append('<path d="M'+" L".join(f"{x:.1f},{y:.1f}" for x,y in pts)+' Z"/>')
        return (f'<svg style="position:absolute;inset:0;z-index:1;opacity:.06" width="100%" height="100%" '
                f'xmlns="http://www.w3.org/2000/svg"><defs><pattern id="hx" width="{w}" height="{h}" '
                f'patternUnits="userSpaceOnUse"><g fill="none" stroke="{DECORCOL}" stroke-width="1.4">'
                f'{"".join(paths)}</g></pattern></defs><rect width="100%" height="100%" fill="url(#hx)"/></svg>')
    if DECOR == "dots":
        return (f'<div style="position:absolute;inset:0;z-index:1;opacity:.10;'
                f'background-image:radial-gradient({DECORCOL} 1.4px, transparent 1.6px);'
                f'background-size:26px 26px"></div>')
    if DECOR == "soft":   # two blurred tonal glows
        return (f'<div style="position:absolute;left:-8%;top:-6%;width:42%;height:42%;z-index:1;border-radius:50%;'
                f'background:{ACCENT};opacity:.18;filter:blur(60px)"></div>'
                f'<div style="position:absolute;right:-8%;bottom:-6%;width:46%;height:46%;z-index:1;border-radius:50%;'
                f'background:{DECORCOL};opacity:.10;filter:blur(70px)"></div>')
    return ""

# ---------------------------------------------------------------- reusable bits
def logo_block(scale=1.0, stacked=False):
    if LOGO_IMG:
        return f'<img class="logo-img" style="--ls:{scale}" src="file://{LOGO_IMG}" alt="">'
    if not BRAND:
        return ""
    sub = f'<div class="logo-bot">{BRAND2}</div>' if BRAND2 else ""
    return (f'<div class="logo {"stacked" if stacked else ""}" style="--ls:{scale}">'
            f'<div class="logo-top">{BRAND}</div>{sub}</div>')

def cta_button():
    return f'<div class="cta">{CP["cta"]}</div>' if CP.get("cta") else ""

def contact_row(items=("phone","web","email")):
    ct = CP.get("contact", {}) or {}
    m = {"phone":("phone",ct.get("phone","")), "web":("globe",ct.get("web","")),
         "email":("mail",ct.get("email","")), "address":("pin",ct.get("address",""))}
    cells=[]
    for k in items:
        ic,val = m.get(k,("",""))
        if not val: continue
        cells.append(f'<div class="c-cell"><span class="c-ic">{ICON[ic]}</span><span>{val}</span></div>')
    return f'<div class="contact">{"".join(cells)}</div>' if cells else ""

def hero_img(cls="hero"):
    return f'<img class="{cls}" src="file://{HERO}" alt="">' if HERO else ""

def headline_html():
    hl = (CP.get("headline","") or "").split(" ")
    if HLACC and len(hl) > 1:
        return hl[0] + ' <span class="accent">' + " ".join(hl[1:]) + '</span>'
    return CP.get("headline","")

def block_text(level, hl_size, kick_size, sub_size, body_size, align=None):
    align = align or ALIGN
    parts=[]
    if CP.get("kicker"):
        parts.append(f'<div class="kicker" style="font-size:{kick_size}">{CP["kicker"]}</div>')
    parts.append(f'<div class="headline" style="font-size:{hl_size}">{headline_html()}</div>')
    if level in ("full","medium") and CP.get("subhead"):
        parts.append(f'<div class="subhead" style="font-size:{sub_size}">{CP["subhead"]}</div>')
    if level=="full" and CP.get("body"):
        parts.append(f'<div class="body" style="font-size:{body_size}">{CP["body"]}</div>')
    return f'<div class="txt" style="text-align:{align}">{"".join(parts)}</div>'

# ---------------------------------------------------------------- base css
def base_css(w,h):
    hl_lh   = "1.06" if RTL else ".96"
    sub_lh  = "1.4"  if RTL else "1.18"
    body_lh = "1.7"  if RTL else "1.5"
    return f"""
*{{margin:0;padding:0;box-sizing:border-box}}
@font-face{{font-family:'Display';src:url('file://{FONT_DISPLAY}') format('truetype');font-weight:100 900}}
@font-face{{font-family:'Body';src:url('file://{FONT_BODY}') format('truetype');font-weight:300 800}}
html,body{{width:{w}px;height:{h}px;overflow:hidden}}
.stage{{position:relative;width:{w}px;height:{h}px;overflow:hidden;direction:{DIRATTR};
  font-family:'Body',sans-serif;color:{INK};background:{STAGEBG}}}
.bg{{position:absolute;inset:0;z-index:0;background:{BG}}}
.kicker{{font-family:'Display';font-weight:700;color:{ACCENT};
  text-transform:{UPPER};letter-spacing:{KTRACK};line-height:1.3}}
.headline{{font-family:'Display';font-weight:800;line-height:{hl_lh};
  text-transform:{UPPER};letter-spacing:{TRACK};color:{HLCOL}}}
.headline .accent{{color:{HLACC or ACCENT}}}
.subhead{{font-family:'Display';font-weight:600;line-height:{sub_lh};color:{INK};opacity:.95}}
.body{{font-family:'Body';font-weight:400;line-height:{body_lh};color:{INK};opacity:.85}}
.cta{{display:inline-block;font-family:'Display';font-weight:700;color:{CTA_INK};background:{CTA_BG};
  border:{CTA_BD};border-radius:999px;text-transform:{UPPER};letter-spacing:{'0' if RTL else '.03em'};
  white-space:nowrap}}
.logo{{display:flex;flex-direction:column;color:{INK}}}
.logo.stacked{{align-items:center;text-align:center}}
.logo-img{{height:calc(9vmin*var(--ls));width:auto;object-fit:contain}}
.logo-top{{font-family:'Display';font-weight:800;letter-spacing:{'0' if RTL else '.02em'};line-height:1.05;
  font-size:calc(4.4vmin*var(--ls))}}
.logo-bot{{font-family:'Display';font-weight:600;letter-spacing:{'0' if RTL else '.3em'};line-height:1.1;
  font-size:calc(1.7vmin*var(--ls));opacity:.9}}
.contact{{display:flex;flex-wrap:wrap;gap:2.2vmin 4vmin;align-items:center;
  font-family:'Display';font-weight:600;color:{INK}}}
.c-cell{{display:flex;align-items:center;gap:1.2vmin;white-space:nowrap}}
.c-ic{{display:inline-flex;width:2.6vmin;height:2.6vmin;color:{ACCENT};flex:none}}
.hero{{position:absolute;object-fit:contain;object-position:bottom;filter:drop-shadow({HEROSHADOW})}}
.scrimup{{position:absolute;left:0;right:0;bottom:0;z-index:3;
  background:linear-gradient(0deg,{SCRIM}f2 0%,{SCRIM}cc 35%,{SCRIM}00 100%)}}
"""

# ---------------------------------------------------------------- layouts
# Each returns (css, inner). Content z-index >=4, hero 2, scrim 3, decor 1, bg 0.
def layout_square(f, level):
    hside = "left" if RTL else "right"
    css=f"""
    .stage{{padding:7vmin}}
    .top{{position:absolute;inset-inline-start:7vmin;top:6vmin;z-index:5}}
    .txt{{position:absolute;inset-inline-start:7vmin;top:23vmin;width:58%;z-index:5;
      display:flex;flex-direction:column;gap:2.4vmin}}
    .hero{{ {hside}:-6vmin;bottom:0;height:74vmin;z-index:2}}
    .scrimup{{height:30vmin}}
    .foot{{position:absolute;inset-inline:7vmin;bottom:6vmin;z-index:5;display:flex;
      justify-content:space-between;align-items:center;gap:3vmin}}
    .cta{{font-size:3.2vmin;padding:2.1vmin 3.8vmin}}
    """
    inner = (f'<div class="top">{logo_block(1.0)}</div>'
      + block_text(level,"10vmin","2.6vmin","3.2vmin","2.4vmin")
      + hero_img() + '<div class="scrimup"></div>'
      + f'<div class="foot">{cta_button()}{contact_row(("phone","web"))}</div>')
    return css, inner

def layout_portrait(f, level):
    css=f"""
    .stage{{display:flex;flex-direction:column;align-items:center;padding:7vh 7vw 0}}
    .top{{z-index:6;margin-bottom:3vh}}
    .txt{{z-index:5;text-align:center;display:flex;flex-direction:column;align-items:center;gap:1.8vh;width:100%}}
    .hero{{position:absolute;left:50%;transform:translateX(-50%);bottom:0;height:56vh;z-index:2}}
    .scrimup{{height:34vh}}
    .foot{{position:absolute;inset-inline:0;bottom:5vh;z-index:6;display:flex;flex-direction:column;
      align-items:center;gap:2.6vh}}
    .cta{{font-size:2.4vh;padding:1.7vh 6vw}}
    .kicker{{font-size:1.9vh}}.headline{{font-size:7.6vh}}.subhead{{font-size:2.7vh}}.body{{font-size:1.95vh;max-width:82%}}
    """
    eff = "medium" if level == "full" else level   # a story is glanceable -> no paragraph
    inner = (f'<div class="top">{logo_block(1.1, stacked=True)}</div>'
      + block_text(eff,"7.6vh","1.9vh","2.7vh","1.95vh","center")
      + hero_img() + '<div class="scrimup"></div>'
      + f'<div class="foot">{cta_button()}{contact_row(("phone","web"))}</div>')
    return css, inner

def layout_landscape(f, level):
    hside = "left" if RTL else "right"
    cols  = "42% 58%" if RTL else "58% 42%"
    css=f"""
    .stage{{display:grid;grid-template-columns:{cols};align-items:center;padding:8vh 6vw}}
    .col{{z-index:4;display:flex;flex-direction:column;gap:2.4vh;{'grid-column:2' if RTL else ''}}}
    .top{{position:absolute;inset-inline-start:6vw;top:7vh;z-index:6}}
    .hero{{ {hside}:3vw;bottom:0;height:99vh;z-index:2}}
    .foot{{position:absolute;inset-inline-start:6vw;bottom:6vh;z-index:6;display:flex;align-items:center;gap:4vw}}
    .cta{{font-size:3vh;padding:1.8vh 3vw}}
    .kicker{{font-size:2.1vh}}.headline{{font-size:9vh}}.subhead{{font-size:3vh}}.body{{font-size:2.3vh;max-width:92%}}
    .col .txt{{display:flex;flex-direction:column;gap:2.2vh;margin-top:9vh}}
    """
    inner = (f'<div class="top">{logo_block(1.0)}</div>'
      + f'<div class="col">{block_text(level,"9vh","2.1vh","3vh","2.3vh")}'
      +   (f'<div>{cta_button()}</div>' if level!="minimal" else "")+'</div>'
      + hero_img()
      + f'<div class="foot">{contact_row()}</div>')
    return css, inner

def layout_strip(f, level):
    h=f["h"]; w=f["w"]; tiny = h < 140
    hl=int(h*(0.42 if tiny else 0.30)); ctaf=int(h*(0.30 if tiny else 0.20))
    show_name = bool(BRAND) and w >= 1100
    css=f"""
    .stage{{display:flex;align-items:center;gap:{int(w*0.025)}px;padding:0 {int(w*0.03)}px;
      {'flex-direction:row-reverse' if RTL else ''}}}
    .s-logo,.divider,.s-mid,.s-cta{{position:relative;z-index:2}}
    .s-name{{font-family:'Display';font-weight:800;line-height:1;font-size:{int(h*0.22)}px;color:{INK}}}
    .s-mid{{flex:1 1 auto;min-width:0;display:flex;flex-direction:column;justify-content:center;text-align:{ALIGN}}}
    .s-head{{font-family:'Display';font-weight:800;text-transform:{UPPER};color:{HLCOL};
      font-size:{hl}px;line-height:.98;{'white-space:nowrap;overflow:hidden;text-overflow:ellipsis' if tiny else ''}}}
    .s-head .accent{{color:{HLACC or ACCENT}}}
    .s-cta{{flex:none;font-family:'Display';font-weight:700;color:{CTA_INK};background:{CTA_BG};border:{CTA_BD};
      border-radius:999px;white-space:nowrap;font-size:{ctaf}px;padding:{int(h*0.15)}px {int(h*0.26)}px}}
    .divider{{flex:none;width:2px;height:{int(h*0.5)}px;background:{INK};opacity:.2}}
    """
    hlw = CP.get("headline","")
    if HLACC and not tiny:
        p=hlw.split(" "); hlw = (p[0]+'<br><span class="accent">'+" ".join(p[1:])+'</span>') if len(p)>1 else hlw
    logo = f'<div class="s-logo"><div class="s-name">{BRAND}</div></div>' if show_name else ''
    div  = '<div class="divider"></div>' if show_name else ''
    cta  = f'<div class="s-cta">{CP["cta"]}</div>' if CP.get("cta") else ''
    return css, logo+div+f'<div class="s-mid"><div class="s-head">{hlw}</div></div>'+cta

def layout_billboard(f, level):
    hside = "left" if RTL else "right"
    css=f"""
    .stage{{display:flex;align-items:center;padding:9vh 5vw;{'flex-direction:row-reverse' if RTL else ''}}}
    .col{{width:60%;z-index:4;display:flex;flex-direction:column;gap:3vh;text-align:{ALIGN}}}
    .top{{position:absolute;inset-inline-start:5vw;top:9vh;z-index:6}}
    .hero{{ {hside}:2vw;bottom:0;height:100vh;z-index:2}}
    .kicker{{font-size:3.4vh}}
    .headline{{font-size:14vh;line-height:{'1.04' if RTL else '.92'}}}
    .subhead{{font-size:3.8vh;font-weight:600;opacity:.92}}
    .bb-act{{display:flex;align-items:center;gap:2vw;margin-top:1vh;{'justify-content:flex-end' if RTL else ''}}}
    .bb-act .cta{{font-size:4vh;padding:2vh 4.5vw}}
    """
    parts=[]
    if CP.get("kicker"): parts.append(f'<div class="kicker">{CP["kicker"]}</div>')
    parts.append(f'<div class="headline">{headline_html()}</div>')
    if CP.get("subhead"): parts.append(f'<div class="subhead">{CP["subhead"]}</div>')
    act = cta_button()
    if not act and CP.get("contact",{}).get("phone"):
        act = f'<div class="cta">{CP["contact"]["phone"]}</div>'
    parts.append(f'<div class="bb-act">{act}</div>')
    inner = (f'<div class="top">{logo_block(1.5)}</div>'
      + f'<div class="col">{"".join(parts)}</div>'
      + hero_img())
    return css, inner

LAYOUTS={"square":layout_square,"portrait":layout_portrait,"landscape":layout_landscape,
         "strip":layout_strip,"billboard":layout_billboard}

def doc_html(f):
    css, inner = LAYOUTS[f["layoutClass"]](f, f["level"])
    return f"""<!doctype html><html dir="{DIRATTR}" lang="{LANG}"><head><meta charset="utf-8"><style>
{base_css(f['w'],f['h'])}
{css}
</style></head><body><div class="stage">
<div class="bg"></div>{decor_layer()}
{inner}
</div></body></html>"""

# ---------------------------------------------------------------- render
def main():
    os.makedirs("work", exist_ok=True); os.makedirs("out", exist_ok=True)
    from playwright.sync_api import sync_playwright
    from PIL import Image
    only = set(s.strip() for s in ARGS.only.split(",")) if ARGS.only else None
    with sync_playwright() as p:
        browser=p.chromium.launch()
        for f in F["formats"]:
            if only and f["key"] not in only: continue
            hp=os.path.abspath(f"work/{f['key']}.html")
            open(hp,"w").write(doc_html(f))
            page=browser.new_page(viewport={"width":f["w"],"height":f["h"]}, device_scale_factor=2)
            page.goto("file://"+hp); page.wait_for_timeout(350)
            shot=f"work/{f['key']}@2x.png"
            page.screenshot(path=shot, clip={"x":0,"y":0,"width":f["w"],"height":f["h"]})
            page.close()
            Image.open(shot).convert("RGB").resize((f["w"],f["h"]), Image.LANCZOS).save(f"out/{f['key']}.png", quality=95)
            print(f"  out/{f['key']}.png  {f['w']}x{f['h']}  [{f['layoutClass']}/{f['level']}]")
        browser.close()

if __name__=="__main__":
    main()
