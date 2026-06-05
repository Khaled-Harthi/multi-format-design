#!/usr/bin/env python3
"""
Decompose a design into its REAL components — preserve pixels, never regenerate.
recompose.py then RE-ARRANGES these real components per format.

    python scripts/decompose.py <input.pdf|.ai|.psd> [project-dir]

THE PROCESS (same every time): PROBE -> REPLAY -> (recompose) RE-ARRANGE.

1) PROBE the real source: list embedded rasters by xref (+ their soft masks), dump every
   vector drawing with its fill colour / bbox / area, read live text runs, sample the true
   background colour, detect direction, flag whether the art is vector-flattened (outlined).
2) REPLAY the real components onto transparent canvases:
   - vector elements (title, blobs, logo, body, footer ...) are rebuilt by REPLAYING their
     own vector paths in their own real fill colour — never re-typeset, never cropped (a
     crop drags in whatever overlaps it; replaying a path lifts only that element, so a
     title sitting on a background blob still comes away clean).
   - embedded photos are lifted by xref and re-clipped with their OWN mask shape, with their
     OWN decorative ring/frame composited back on — not approximated in CSS.
   - if the source still has LIVE text (a normal structured PDF/PSD), the text is keyed to
     transparent in its own ink instead of replayed; everything else is identical.
Output: assets/layers/*.png + layers.json (role, file, normalized bbox, z, colour).
"""
import sys, os, io, json
import numpy as np
from pathlib import Path
from PIL import Image

SCALE = 5  # supersample for crisp replayed vector edges

def log(*a): print("[decompose]", *a)
def hexof(c):  # c in 0..1 floats or 0..255 ints
    if c is None: return None
    if max(c[:3]) <= 1.0: c = [x*255 for x in c[:3]]
    return "#%02x%02x%02x" % tuple(int(x) for x in c[:3])
def is_black(c): return c is not None and max(c[:3]) <= 0.12
def is_white(c): return c is not None and min(c[:3]) >= 0.90

# ---------------- raster helpers ----------------
def pix_to_img(doc, xref, smask=0):
    import fitz
    pix = fitz.Pixmap(doc, xref)
    if smask:
        try: pix = fitz.Pixmap(pix, fitz.Pixmap(doc, smask))
        except Exception: pass
    if pix.colorspace and pix.colorspace.name == "CMYK":
        pix = fitz.Pixmap(fitz.csRGB, pix)
    return Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGBA")

def img_stats(im):
    a = np.asarray(im).astype(float)
    al = a[...,3] if a.shape[-1] == 4 else np.full(a.shape[:2], 255.0)
    m = al > 24
    if m.sum() == 0: return 0.0, 1.0, 0.0
    rgb = a[...,:3][m] / 255.0
    mx = rgb.max(1); mn = rgb.min(1)
    return float(np.where(mx>0,(mx-mn)/np.clip(mx,1e-6,1),0).mean()), float(((mx+mn)/2).mean()), float(m.mean())

def key_color(img, ink, k=2.0):
    a = np.asarray(img).astype(float)[...,:3]; ink = np.array(ink, float)
    d = np.sqrt(((a-ink)**2).sum(2)); al = np.clip(255-d*k, 0, 255)
    out = np.zeros((*a.shape[:2],4)); out[...,0],out[...,1],out[...,2]=ink; out[...,3]=al
    return Image.fromarray(out.astype("uint8"), "RGBA")

# ---------------- vector replay (the heart of the preserve-don't-invent method) ----------------
def replay(W, H, pathdicts, clip):
    """Re-draw each given path dict's own items onto a transparent page in its own real fill
    colour/opacity, and return the clipped region as an RGBA image. `pathdicts` are drawing
    dicts (from get_drawings) or synthetic ones (e.g. a clip path used as a mask)."""
    import fitz
    nd = fitz.open(); pg = nd.new_page(width=W, height=H); sh = pg.new_shape()
    for d in pathdicts:
        for it in d["items"]:
            op = it[0]
            try:
                if   op == "l":  sh.draw_line(it[1], it[2])
                elif op == "c":  sh.draw_bezier(it[1], it[2], it[3], it[4])
                elif op == "qu": sh.draw_quad(it[1])
                elif op == "re": sh.draw_rect(it[1])
            except Exception: pass
        sh.finish(fill=d.get("fill"), color=d.get("color"), width=(d.get("width") or 1),
                  fill_opacity=(d.get("fill_opacity") or 1), stroke_opacity=(d.get("stroke_opacity") or 1),
                  even_odd=bool(d.get("even_odd")), closePath=bool(d.get("closePath")))
    sh.commit()
    pix = pg.get_pixmap(matrix=fitz.Matrix(SCALE, SCALE), clip=clip, alpha=True)
    img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGBA"); nd.close()
    return img

def cluster(marks, gapx, gapy):
    """Union marks whose bboxes are within (gapx,gapy) — groups glyphs into a word/line/block,
    but leaves a big gap (e.g. left vs right footer) as separate elements."""
    n = len(marks); parent = list(range(n))
    def find(i):
        while parent[i] != i: parent[i] = parent[parent[i]]; i = parent[i]
        return i
    for i in range(n):
        for j in range(i+1, n):
            ri, rj = marks[i]["r"], marks[j]["r"]
            dx = max(0, max(ri[0],rj[0]) - min(ri[2],rj[2]))
            dy = max(0, max(ri[1],rj[1]) - min(ri[3],rj[3]))
            if dx <= gapx and dy <= gapy: parent[find(i)] = find(j)
    g = {}
    for i in range(n): g.setdefault(find(i), []).append(i)
    return list(g.values())

# ---------------- main PDF/AI decomposition ----------------
def decompose_pdf(path, proj):
    import fitz
    doc = fitz.open(path); page = doc[0]; W, H = page.rect.width, page.rect.height
    Ldir = proj/"assets/layers"; Ldir.mkdir(parents=True, exist_ok=True)
    draws = page.get_drawings()
    def clipnb(r):  # clip rect to page, return (x0,y0,x1,y1) in points
        return [max(0,min(W,r[0])), max(0,min(H,r[1])), max(0,min(W,r[2])), max(0,min(H,r[3]))]
    def nb(r): return [round(r[0]/W,4),round(r[1]/H,4),round(r[2]/W,4),round(r[3]/H,4)]
    def area(r): c=clipnb(r); return max(0,(c[2]-c[0]))*max(0,(c[3]-c[1]))/(W*H)
    layers=[]; z=0

    # ---- PROBE: rasters ----
    rasters=[]
    for im in page.get_images(full=True):
        xref, smask = im[0], im[1]
        rects = page.get_image_rects(xref)
        if not rects: continue
        r = rects[0]; pic = pix_to_img(doc, xref, smask); sat, light, opq = img_stats(pic)
        rasters.append({"xref":xref,"smask":smask,"r":[r[0],r[1],r[2],r[3]],"pic":pic,
                        "sat":sat,"light":light,"opq":opq,"area":area([r[0],r[1],r[2],r[3]]),
                        "masks":[],"rings":[]})

    # ---- PROBE: clip paths. A photo is often cropped by a rounded/organic CLIP path (not a
    # fill mask) — capture it so the real masked/rounded edge is preserved, not squared off. ----
    def carea(r): c=[max(0,min(W,r[0])),max(0,min(H,r[1])),max(0,min(W,r[2])),max(0,min(H,r[3]))]; return max(0,c[2]-c[0])*max(0,c[3]-c[1])/(W*H)
    def cinside(a,b):
        ix0=max(a[0],b[0]);iy0=max(a[1],b[1]);ix1=min(a[2],b[2]);iy1=min(a[3],b[3])
        return max(0,ix1-ix0)*max(0,iy1-iy0)/max(1e-6,(a[2]-a[0])*(a[3]-a[1]))
    clips=[]
    try:
        for dd in page.get_drawings(extended=True):
            if dd.get("type")=="clip":
                sc=dd.get("scissor") or dd.get("rect")
                if sc is None: continue
                clips.append({"items":dd.get("items",[]),"rect":[sc.x0,sc.y0,sc.x1,sc.y1],
                              "even_odd":bool(dd.get("even_odd"))})
    except Exception: pass
    for rs in rasters:
        cand=[c for c in clips if cinside(c["rect"],rs["r"])>=0.8 and carea(c["rect"])<0.92
              and (any(it[0] in ("c","qu") for it in c["items"]) or carea(c["rect"])<0.85*max(1e-6,carea(rs["r"])))]
        if cand: rs["clip"]=min(cand, key=lambda c:carea(c["rect"]))

    # ---- PROBE: classify drawings -> field / mask / ring / blob / mark (multi-pass) ----
    field_color=None; blobs=[]; marks=[]; used=set()
    def rectof(d): r=d["rect"]; return [r[0],r[1],r[2],r[3]]
    def inside_ratio(d_rect, r_rect):
        c=clipnb(d_rect); ix0=max(c[0],r_rect[0]); iy0=max(c[1],r_rect[1])
        ix1=min(c[2],r_rect[2]); iy1=min(c[3],r_rect[3])
        inter=max(0,ix1-ix0)*max(0,iy1-iy0); da=max(1e-6,(c[2]-c[0])*(c[3]-c[1]))
        return inter/da
    # pass 0: a full-page solid fill = the background FIELD — record its REAL colour
    # (white, lavender, navy, anything). Any small black/white rect = a knockout plate -> drop.
    for i,d in enumerate(draws):
        f=d.get("fill"); A=area(rectof(d)); ni=len(d["items"])
        if f is None: continue
        if ni<=5 and A>0.9:
            # a COLOURED full-page ground (lavender/cream/navy) is the real bg and always wins,
            # even if a white knockout plate was painted first; white is only a fallback.
            if not is_black(f) and not is_white(f): field_color=f
            elif is_white(f) and field_color is None: field_color=f
            used.add(i); continue
        if ni<=5 and (is_black(f) or is_white(f)):
            used.add(i)
    # pass 1: a raster's clip-mask = a black fill that sits inside the raster rect
    for rs in rasters:
        for i,d in enumerate(draws):
            if i in used: continue
            if is_black(d.get("fill")) and 0.03<area(rectof(d))<0.7 and inside_ratio(rectof(d),rs["r"])>=0.6:
                rs["masks"].append(i); used.add(i)
        if rs["masks"]:
            xs=[clipnb(rectof(draws[i])) for i in rs["masks"]]
            rs["disp"]=[min(c[0] for c in xs),min(c[1] for c in xs),max(c[2] for c in xs),max(c[3] for c in xs)]
        elif rs.get("clip"): rs["disp"]=clipnb(rs["clip"]["rect"])   # rounded/organic crop bounds
        else: rs["disp"]=clipnb(rs["r"])
        rs["darea"]=max(1e-6,(rs["disp"][2]-rs["disp"][0])*(rs["disp"][3]-rs["disp"][1])/(W*H))
    # pass 2: rings/frames = colour fills that BLANKET a raster's displayed region (they
    # surround/frame the photo). A decoration that merely clips the photo's big bounding box
    # in one corner is NOT a ring — require it to both sit inside AND cover most of the region.
    def coverage(d_rect, r_rect):
        c=clipnb(d_rect); ix0=max(c[0],r_rect[0]);iy0=max(c[1],r_rect[1]);ix1=min(c[2],r_rect[2]);iy1=min(c[3],r_rect[3])
        inter=max(0,ix1-ix0)*max(0,iy1-iy0); ra=max(1e-6,(r_rect[2]-r_rect[0])*(r_rect[3]-r_rect[1]))
        return inter/ra
    for rs in rasters:
        for i,d in enumerate(draws):
            if i in used or d.get("fill") is None: continue
            ir=inside_ratio(rectof(d), rs["disp"]); cov=coverage(rectof(d), rs["disp"])
            if ir>=0.6 and cov>=0.45:
                rs["rings"].append(i); used.add(i)
    # pass 3: big SMOOTH fills = background blobs. Keyed on LOW path-item count so glyph-dense
    # text never qualifies; the area floor is low so a big soft shape can't bridge text clusters.
    for i,d in enumerate(draws):
        if i in used or d.get("fill") is None: continue
        if area(rectof(d))>=0.08 and len(d["items"])<=120: blobs.append(i); used.add(i)
    # pass 4: everything else with a fill is a text/art mark -> cluster + replay
    for i,d in enumerate(draws):
        if i in used or d.get("fill") is None: continue
        marks.append({"i":i,"r":clipnb(rectof(d)),"A":area(rectof(d))})
    if os.environ.get("DBG"):
        log("DBG marks", sorted(m["i"] for m in marks), "blobs", blobs,
            "masks", {rs["xref"]:rs["masks"] for rs in rasters},
            "rings", {rs["xref"]:rs["rings"] for rs in rasters})

    # ---- live text? (a structured source still has selectable runs) ----
    tdict=page.get_text("dict")["blocks"]
    runs=[]
    for b in tdict:
        for ln in b.get("lines",[]):
            spans=[s for s in ln["spans"] if s["text"].strip()]
            if not spans: continue
            x0=min(s["bbox"][0] for s in spans); y0=min(s["bbox"][1] for s in spans)
            x1=max(s["bbox"][2] for s in spans); y1=max(s["bbox"][3] for s in spans)
            col=spans[0]["color"]; ink=((col>>16)&255,(col>>8)&255,col&255)
            runs.append({"size":max(s["size"] for s in spans),"r":[x0,y0,x1,y1],"ink":ink})
    nlive=len(runs)
    vector_flat = nlive<=1 and len(draws)>=12

    # ---- REPLAY: rasters (photo/qr/background) with their real masks + rings ----
    def autofit(im, thr=8):
        a=np.asarray(im)
        if a.shape[-1]<4: return im,(0,0)
        m=a[...,3]>thr; ys,xs=np.where(m)
        if len(xs)==0: return im,(0,0)
        return Image.fromarray(a[ys.min():ys.max()+1, xs.min():xs.max()+1]), (xs.min(),ys.min())
    def render_raster(rs, role, kind=None):
        nonlocal z
        import fitz
        # clip over the DISPLAYED (masked) region ∪ rings — not the raw image rect
        ux0,uy0,ux1,uy1=rs["disp"]
        for idx in rs["rings"]:
            rr=draws[idx]["rect"]; ux0=min(ux0,rr[0]); uy0=min(uy0,rr[1]); ux1=max(ux1,rr[2]); uy1=max(uy1,rr[3])
        clip=fitz.Rect(max(0,ux0),max(0,uy0),min(W,ux1),min(H,uy1))
        pdoc=fitz.open(); pp=pdoc.new_page(width=W,height=H)
        _buf=io.BytesIO(); pix_to_img(doc, rs["xref"], rs["smask"]).save(_buf,"PNG")
        pp.insert_image(fitz.Rect(*rs["r"]), stream=_buf.getvalue())
        base=Image.open(io.BytesIO(pp.get_pixmap(matrix=fitz.Matrix(SCALE,SCALE),clip=clip,alpha=True).tobytes("png"))).convert("RGBA")
        # mask the photo to its real displayed shape: a black-fill clip shape if present,
        # else a real PDF clip path (e.g. the rounded/organic crop), so the edge is preserved.
        if rs["masks"]:
            maskdicts=[draws[i] for i in rs["masks"]]
        elif rs.get("clip"):
            maskdicts=[{"items":rs["clip"]["items"],"fill":(0,0,0),"fill_opacity":1,"color":None,
                        "width":1,"stroke_opacity":1,"even_odd":rs["clip"]["even_odd"],"closePath":True}]
        else:
            maskdicts=[]
        if maskdicts:
            m=replay(W,H,maskdicts,clip); ma=np.asarray(m)[...,3]
            ba=np.asarray(base).astype("uint8").copy(); ba[...,3]=np.minimum(ba[...,3],ma)
            base=Image.fromarray(ba,"RGBA")
        if rs["rings"]:
            base=Image.alpha_composite(base, replay(W,H,[draws[i] for i in rs["rings"]],clip))
        base,_=autofit(base)
        fn=f"assets/layers/{role}_{rs['xref']}.png"; base.save(proj/fn)
        ent={"id":f"img{rs['xref']}","role":role,"file":fn,"bbox":nb(rs["disp"]),"z":z}
        if kind: ent["kind"]=kind
        # TASTE: read the cutout's silhouette to find its natural anchor. A figure that is
        # CUT FLAT at an edge (its opaque pixels span most of the width/height there — e.g. a
        # seated person cropped at the legs) must SIT on that edge so the crop hides in the
        # frame, instead of floating mid-canvas with a chopped-off body.
        if role=="hero":
            aa=np.asarray(base); al=aa[...,3] if aa.shape[-1]==4 else np.full(aa.shape[:2],255)
            op=al>40; Hh,Ww=op.shape
            by=max(1,int(0.04*Hh)); bx=max(1,int(0.04*Ww))
            rw=op.sum(1); ch=op.sum(0); mw=max(1,int(rw.max())); mh=max(1,int(ch.max()))
            botf=op[-by:].sum(1).max()/mw; topf=op[:by].sum(1).max()/mw
            lftf=op[:,:bx].sum(0).max()/mh; rgtf=op[:,-bx:].sum(0).max()/mh
            ent["anchorY"]="bottom" if (botf>0.5 and topf<0.5) else ("top" if (topf>0.5 and botf<0.5) else "center")
            ent["anchorX"]="left" if (lftf>0.7 and rgtf<0.7) else ("right" if (rgtf>0.7 and lftf<0.7) else "center")
            # FRAMED = a rectangular opaque photo (fills its box) vs a transparent cut-out figure.
            # A framed photo must get its OWN zone in re-arrangement; text may never overlay it.
            ent["framed"]=bool(op.mean()>0.9)
            log(f"  hero silhouette anchor: Y={ent['anchorY']} X={ent['anchorX']} "
                f"(bot={botf:.2f} top={topf:.2f}) framed={ent['framed']}")
        layers.append(ent); z+=1; return ent

    button_rects=[]
    for rs in rasters:
        r=rs["r"]; bleed=(r[0]<=0.03*W)+(r[1]<=0.03*H)+(r[2]>=0.97*W)+(r[3]>=0.97*H)>=3
        asp=(r[2]-r[0])/max(1,(r[3]-r[1]))
        if rs["area"]>0.5 and rs["opq"]>0.9 and bleed: role,kind="background",None
        elif rs["area"]<0.05 and rs["sat"]<0.25 and 0.7<asp<1.4: role,kind="qr","qr"
        elif 1.8<asp<6 and rs["area"]<0.06 and rs["light"]>0.6: role,kind="button","button"
        else:
            role="hero"
            cx=(r[0]+r[2])/2/W; cy=(r[1]+r[3])/2/H
            kind="center" if (0.30<cx<0.70 and not bleed) else "anchor"
        ent=render_raster(rs, role, kind)
        if role=="hero": ent["placement"]=kind
        if role=="button": button_rects.append((rs["r"], proj/ent["file"]))
        log(f"raster x{rs['xref']}: {role}{'/'+str(kind) if kind else ''}  area={rs['area']:.3f} asp={asp:.2f} masks={len(rs['masks'])} rings={len(rs['rings'])}")

    # ---- REPLAY: vector pill buttons. A small COLOURED fill that a live text label sits on is a
    # CTA pill. Rasterise the page over the pill (exact pixels, label baked in, all clips/paint
    # order respected) and mask it to its real (often rounded) clip shape so the corners aren't
    # squared off or left with stray background. ----
    button_zones=[]
    if nlive>=2:
        import fitz
        for m in marks:
            i=m["i"]; d=draws[i]; f=d.get("fill")
            if f is None or is_black(f) or is_white(f): continue
            rr=[d["rect"][0],d["rect"][1],d["rect"][2],d["rect"][3]]; r=clipnb(rr)
            asp=(r[2]-r[0])/max(1,(r[3]-r[1]))
            if not (1.6<asp<9 and 0.003<m["A"]<0.06): continue
            cx=(r[0]+r[2])/2; cy=(r[1]+r[3])/2
            if not any(rn["r"][0]<=cx<=rn["r"][2] and rn["r"][1]<=cy<=rn["r"][3] for rn in runs): continue
            clip=fitz.Rect(*r)
            base=Image.open(io.BytesIO(page.get_pixmap(matrix=fitz.Matrix(SCALE,SCALE),clip=clip,alpha=True).tobytes("png"))).convert("RGBA")
            cand=[c for c in clips if cinside(c["rect"],rr)>=0.55 and cinside(rr,c["rect"])>=0.55
                  and any(it[0] in ("c","qu","l") for it in c["items"])]
            shape=min(cand,key=lambda c:carea(c["rect"])) if cand else {"items":d["items"],"even_odd":bool(d.get("even_odd"))}
            mdict={"items":shape["items"],"fill":(0,0,0),"fill_opacity":1,"color":None,"width":1,
                   "stroke_opacity":1,"even_odd":shape.get("even_odd",False),"closePath":True}
            mk=replay(W,H,[mdict],clip); ma=np.asarray(mk)[...,3]
            ba=np.asarray(base).astype("uint8").copy(); ba[...,3]=np.minimum(ba[...,3],ma)
            base=Image.fromarray(ba,"RGBA"); base,_=autofit(base)
            fn=f"assets/layers/button_{i}.png"; base.save(proj/fn)
            layers.append({"id":f"btn{i}","role":"button","kind":"button","file":fn,"bbox":nb(r),"z":z,
                           "color":hexof(f)}); z+=1
            button_zones.append(rr)
        if button_zones: log(f"vector pill buttons: {len(button_zones)}")

    # ---- REPLAY: standalone background blobs ----
    for i in blobs:
        r=draws[i]["rect"]; clip=__import__("fitz").Rect(*clipnb([r[0],r[1],r[2],r[3]]))
        img=replay(W,H,[draws[i]],clip); fn=f"assets/layers/decoration_{i}.png"; img.save(proj/fn)
        layers.append({"id":f"blob{i}","role":"decoration","kind":"blob","file":fn,"bbox":nb([clip.x0,clip.y0,clip.x1,clip.y1]),
                       "z":z,"color":hexof(draws[i].get("fill"))}); z+=1
    if blobs: log(f"blobs (vector background shapes): {len(blobs)}")

    # ---- text: live runs (keyed) OR outlined marks (clustered + replayed) ----
    def role_for_flow(k):  # reading order, top -> bottom
        return ["headline","subhead","body","note","note","note"][min(k,5)]

    if nlive>=2:
        # structured: key live text to transparent in its own ink (preserve type pixels).
        # First DROP any run baked into a button pill, then MERGE runs whose boxes overlap into
        # a single lockup — a nestled pair like "تصل إلى" tucked over "50%" is one unit the
        # designer composed; keeping it whole preserves that and avoids a double-printed ghost.
        cruns=[]
        for rn in runs:
            x0,y0,x1,y1=rn["r"]; cx=(x0+x1)/2; cy=(y0+y1)/2
            if any(bz[0]<=cx<=bz[2] and bz[1]<=cy<=bz[3] for bz in button_zones): continue  # baked into vector pill
            host=next((bf for (br,bf) in button_rects if br[0]<=cx<=br[2] and br[1]<=cy<=br[3]), None)
            if host is not None:   # raster pill: composite its keyed label onto the pill, keep one layer
                reg=key_color(_render(page,[x0-2,y0-2,x1+2,y1+2]), rn["ink"])
                pill=Image.open(host).convert("RGBA"); pw,ph=pill.size
                bx0,by0,bx1,by1=[br for (br,bf) in button_rects if bf==host][0]
                lab=reg.resize((max(1,int((x1-x0)/max(1,bx1-bx0)*pw)),max(1,int((y1-y0)/max(1,by1-by0)*ph))))
                pill.alpha_composite(lab,(int((x0-bx0)/max(1,bx1-bx0)*pw),int((y0-by0)/max(1,by1-by0)*ph))); pill.save(host)
                continue
            cruns.append(rn)
        def ov_ratio(a,b):
            ix=max(0,min(a[2],b[2])-max(a[0],b[0])); iy=max(0,min(a[3],b[3])-max(a[1],b[1]))
            inter=ix*iy; sa=(a[2]-a[0])*(a[3]-a[1]); sb=(b[2]-b[0])*(b[3]-b[1])
            return inter/max(1e-6,min(sa,sb))
        groups=[]
        for rn in cruns:
            g=next((g for g in groups if any(ov_ratio(rn["r"],o["r"])>0.12 for o in g)), None)
            (g.append(rn) if g else groups.append([rn]))
        changed=True
        while changed:  # transitively close (a∩b, b∩c -> one group)
            changed=False
            for i in range(len(groups)):
                for j in range(i+1,len(groups)):
                    if any(ov_ratio(a["r"],b["r"])>0.12 for a in groups[i] for b in groups[j]):
                        groups[i]+=groups.pop(j); changed=True; break
                if changed: break
        content=[]
        for g in groups:
            x0=min(o["r"][0] for o in g); y0=min(o["r"][1] for o in g)
            x1=max(o["r"][2] for o in g); y1=max(o["r"][3] for o in g); pad=2
            dom=max(g, key=lambda o:(o["r"][2]-o["r"][0])*(o["r"][3]-o["r"][1]))
            ink=dom["ink"]; size=max(o["size"] for o in g)
            reg=key_color(_render(page,[x0-pad,y0-pad,x1+pad,y1+pad]), ink)
            content.append((size,(x0,y0,x1,y1),ink,reg))
        content.sort(key=lambda t:-t[0])
        for k,(size,bb,ink,reg) in enumerate(content):
            role=role_for_flow(k); fn=f"assets/layers/text_{role}_{k}.png"; reg.save(proj/fn)
            layers.append({"id":f"txt{k}","role":role,"file":fn,"bbox":nb(bb),"z":100+k,"color":hexof(ink)})
        log(f"live text runs -> {len(content)} text layers (from {len(cruns)} runs)")
    else:
        # vector-flattened: cluster outlined marks, replay each element's real paths
        groups=cluster(marks, gapx=0.06*W, gapy=0.022*H)
        elems=[]
        for grp in groups:
            idxs=[marks[g]["i"] for g in grp]
            rs=[marks[g]["r"] for g in grp]
            x0=min(r[0] for r in rs); y0=min(r[1] for r in rs); x1=max(r[2] for r in rs); y1=max(r[3] for r in rs)
            elems.append({"idxs":idxs,"bb":[x0,y0,x1,y1],"w":(x1-x0)/W,"h":(y1-y0)/H,
                          "cy":(y0+y1)/2/H,"cx":(x0+x1)/2/W,"a":((x1-x0)/W)*((y1-y0)/H)})
        # Role by SIZE first (the headline is the biggest type, wherever it sits), then by
        # position: a small block in a corner is an eyebrow (top) or footer (bottom), never
        # the headline. A compact square mark up top is a logo, not a wide caption.
        amax=max(e["a"] for e in elems) if elems else 1.0
        flow=[]
        for e in elems:
            top=e["cy"]<0.16; bottom=e["cy"]>0.85
            islogo = e["w"]<0.22 and e["h"]>0.02 and e["cy"]<0.18 and (e["w"]/max(e["h"],1e-3))<2.2
            if islogo:                 e["role"]="logo"
            elif e["a"]>=0.55*amax:    e["role"]="flow"; flow.append(e)
            elif bottom:               e["role"]="footer"
            elif top:                  e["role"]="note"
            else:                      e["role"]="body"
        flow.sort(key=lambda e:e["bb"][1])
        for k,e in enumerate(flow): e["role"]=["headline","subhead","body","note"][min(k,3)]
        for band in ("footer","note"):
            sub=sorted([e for e in elems if e["role"]==band], key=lambda e:e["bb"][0])
            for fi,e in enumerate(sub): e["fi"]=fi
        for e in elems:
            import fitz
            pad=0.006
            clip=fitz.Rect(max(0,e["bb"][0]-pad*W),max(0,e["bb"][1]-pad*H),min(W,e["bb"][2]+pad*W),min(H,e["bb"][3]+pad*H))
            img=replay(W,H,[draws[j] for j in e["idxs"]],clip)
            nm=e["role"]+(f"_{e.get('fi')}" if e["role"] in ("footer","note") else "")
            fn=f"assets/layers/{nm}.png"; img.save(proj/fn)
            ent={"id":nm,"role":("decoration" if e["role"]=="logo" else e["role"]),
                 "file":fn,"bbox":nb([clip.x0,clip.y0,clip.x1,clip.y1]),"z":z}
            if e["role"]=="logo": ent["kind"]="logo"
            layers.append(ent); z+=1
        log(f"vector-flattened: {len(elems)} elements "
            f"({', '.join(sorted(set((e['role']) for e in elems)))})")

    # ---- backdrop colour + direction ----
    bgc = hexof(field_color) if field_color else "#ffffff"
    txt=" ".join(s["text"] for b in tdict for ln in b.get("lines",[]) for s in ln["spans"])
    ar=sum(1 for c in txt if '؀'<=c<='ۿ'); la=sum(1 for c in txt if c.isascii() and c.isalpha())
    dirr="rtl" if (nlive>=2 and ar>la) else "ltr"
    subj="left"
    if vector_flat:
        log("note: vector-flattened source — components were lifted by replaying their real "
            "vector paths (no live layers, but every element preserved).")
    try:  # a reference render of the source, for the reviewer to compare against
        Image.open(io.BytesIO(page.get_pixmap(matrix=fitz.Matrix(2,2)).tobytes("png"))).convert("RGB").save(proj/"source.png")
    except Exception: pass
    man={"page":[round(W),round(H)],"dir":dirr,"bgColor":bgc,"subject":subj,
         "vectorFlattened":vector_flat,"layers":layers}
    return man

def _render(page, bbox, scale=8):
    import fitz
    pix=page.get_pixmap(matrix=fitz.Matrix(scale,scale), clip=fitz.Rect(*bbox), alpha=False)
    return Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")

# ---------------- PSD ----------------
def decompose_psd(path, proj):
    from psd_tools import PSDImage
    psd=PSDImage.open(path); W,H=psd.width,psd.height
    (proj/"assets/layers").mkdir(parents=True, exist_ok=True)
    layers=[]; z=0
    for layer in psd.descendants():
        try:
            if not layer.is_visible() or layer.kind=="group": continue
            bb=layer.bbox
            if bb[2]<=bb[0] or bb[3]<=bb[1]: continue
            f=((bb[2]-bb[0])*(bb[3]-bb[1]))/(W*H); img=layer.composite().convert("RGBA")
            nm=(layer.name or "").lower()
            if layer.kind=="type": role="headline" if f>0.04 else "subhead"
            elif f>0.7: role="background"
            elif any(k in nm for k in ("btn","button","cta")): role="button"
            elif f>0.2: role="hero"
            else: role="decoration"
            fn=f"assets/layers/{role}_{z}.png"; img.save(proj/fn)
            layers.append({"id":f"l{z}","role":role,"file":fn,
                           "bbox":[round(bb[0]/W,4),round(bb[1]/H,4),round(bb[2]/W,4),round(bb[3]/H,4)],"z":z}); z+=1
        except Exception: continue
    return {"page":[W,H],"dir":"ltr","bgColor":"#ffffff","subject":"left","vectorFlattened":False,"layers":layers}

def main():
    if len(sys.argv)<2: raise SystemExit("usage: decompose.py <input.pdf|.psd> [project]")
    path=Path(sys.argv[1]).expanduser().resolve()
    proj=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else Path(".").resolve()
    (proj/"assets").mkdir(parents=True, exist_ok=True)
    ext=path.suffix.lower()
    if ext in (".psd",".psb"): man=decompose_psd(path, proj)
    elif ext in (".pdf",".ai"): man=decompose_pdf(path, proj)
    else: raise SystemExit(f"decompose needs a layered/vector source (PDF/AI/PSD); got {ext}. For a flat photo use ingest.py + build.py.")
    SK=Path(__file__).resolve().parent.parent
    if not (proj/"formats.json").exists():
        import shutil; shutil.copy(SK/"assets/formats.json", proj/"formats.json")
    json.dump(man, open(proj/"layers.json","w"), indent=2, ensure_ascii=False)
    roles=[l["role"] for l in man["layers"]]
    log(f"wrote layers.json: {len(man['layers'])} components {roles}  dir={man['dir']} bg={man['bgColor']}")
    print("\nNEXT: python scripts/recompose.py", str(proj), " (re-arranges the REAL components per size)")

if __name__=="__main__": main()
