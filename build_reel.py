#!/usr/bin/env python3
"""Costruisce un reel Instagram 1080x1920 nel formato MDP a partire da un articolo
di ilmagazinedelparrucchiere.com (API REST pubbliche di WordPress).

Uso: python3 build_reel.py <post_id> <cartella_output>
Produce <cartella_output>/<post_id>.mp4 e <post_id>.jpg (fotogramma di copertina).
"""
import html
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request

from PIL import Image, ImageDraw, ImageFont, ImageOps

SITE = "https://ilmagazinedelparrucchiere.com"
HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 1080, 1920
BLACK = (14, 14, 14)
GOLD = (201, 162, 39)
WHITE = (245, 243, 238)
GREY = (205, 202, 196)
PHOTO_H = 1060          # altezza della foto in alto
MARGIN = 125            # margine sinistro come nelle copertine
FPS = 30

F_TITLE = os.path.join(HERE, "fonts", "oswald-latin-700-normal.ttf")
F_BODY = os.path.join(HERE, "fonts", "work-sans-latin-400-normal.ttf")
F_LABEL = os.path.join(HERE, "fonts", "work-sans-latin-500-normal.ttf")
LOGO = os.path.join(HERE, "assets", "mdp-logo.png")

UA = {"User-Agent": "MDP-Reel-Builder/1.0"}


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def text_of(fragment):
    t = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", html.unescape(t)).strip()


def first_sentence(t, limit=150):
    m = re.match(r"(.+?[.!?])(\s|$)", t)
    s = m.group(1) if m else t
    if len(s) > limit:
        s = s[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "..."
    return s


def load_post(pid):
    d = json.loads(get(f"{SITE}/wp-json/wp/v2/posts/{pid}?_embed=wp:featuredmedia,wp:term"))
    title = text_of(d["title"]["rendered"])
    content = d["content"]["rendered"]
    emb = d.get("_embedded", {})
    feat = None
    try:
        feat = emb["wp:featuredmedia"][0]["source_url"]
    except (KeyError, IndexError):
        pass
    cats = [t["name"] for g in emb.get("wp:term", []) for t in g if t.get("taxonomy") == "category"]
    label = (cats[0] if cats else "Il Magazine").upper()
    imgs = re.findall(r'<img[^>]+src="([^"]+)"', content)
    # sezioni: ogni h2 con il primo paragrafo che lo segue
    sections = []
    parts = re.split(r"<h2[^>]*>(.*?)</h2>", content, flags=re.S)
    for i in range(1, len(parts) - 1, 2):
        head = text_of(parts[i])
        if re.search(r"domande frequenti|faq|fonti|limiti", head, re.I):
            continue
        para = re.search(r"<p[^>]*>(.*?)</p>", parts[i + 1], re.S)
        body = first_sentence(text_of(para.group(1))) if para else ""
        if head and body:
            sections.append((head, body))
    if ":" in title:
        main, sub = [x.strip() for x in title.split(":", 1)]
    else:
        main, sub = title, first_sentence(text_of(d["excerpt"]["rendered"]), 90)
    return {"title": main, "subtitle": sub[:1].upper() + sub[1:], "label": label,
            "feat": feat, "imgs": imgs, "sections": sections[:4]}


def fit_cover(img, w, h):
    return ImageOps.fit(img.convert("RGB"), (w, h), Image.LANCZOS, centering=(0.5, 0.35))


def wrap(draw, text, font, maxw):
    words, lines, cur = text.split(), [], ""
    for wd in words:
        test = (cur + " " + wd).strip()
        if draw.textlength(test, font=font) <= maxw:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def fit_title(draw, text, maxw, maxlines, start=150, minsize=70):
    size = start
    while size >= minsize:
        f = ImageFont.truetype(F_TITLE, size)
        lines = wrap(draw, text.upper(), f, maxw)
        if len(lines) <= maxlines:
            return f, lines
        size -= 6
    f = ImageFont.truetype(F_TITLE, minsize)
    return f, wrap(draw, text.upper(), f, maxw)[:maxlines]


def spaced(draw, xy, text, font, fill, spacing=6):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + spacing


def logo_img(width=200):
    lg = Image.open(LOGO).convert("RGB")
    # logo nero su bianco -> bianco su trasparente
    gray = ImageOps.grayscale(lg)
    alpha = ImageOps.invert(gray)
    white = Image.new("RGBA", lg.size, (255, 255, 255, 255))
    white.putalpha(alpha)
    r = width / lg.width
    return white.resize((width, int(lg.height * r)), Image.LANCZOS)


def band(canvas, top):
    d = ImageDraw.Draw(canvas)
    d.rectangle([0, top, W, H], fill=BLACK)
    d.rectangle([0, top, W, top + 7], fill=GOLD)
    return d


def slide_cover(photo, p):
    c = Image.new("RGB", (W, H), BLACK)
    c.paste(fit_cover(photo, W, PHOTO_H), (0, 0))
    d = band(c, PHOTO_H)
    lab = ImageFont.truetype(F_LABEL, 34)
    spaced(d, (MARGIN, PHOTO_H + 70), p["label"], lab, GOLD)
    lg = logo_img(190)
    c.paste(lg, (W - MARGIN - lg.width, PHOTO_H + 55), lg)
    ft, lines = fit_title(d, p["title"], W - 2 * MARGIN, 2)
    y = PHOTO_H + 150
    for ln in lines:
        d.text((MARGIN, y), ln, font=ft, fill=WHITE)
        y += int(ft.size * 1.08)
    fb = ImageFont.truetype(F_BODY, 46)
    y += 55
    for ln in wrap(d, p["subtitle"], fb, W - 2 * MARGIN)[:3]:
        d.text((MARGIN, y), ln, font=fb, fill=GREY)
        y += 62
    return c


def slide_section(photo, p, head, body, n, tot):
    c = Image.new("RGB", (W, H), BLACK)
    c.paste(fit_cover(photo, W, PHOTO_H), (0, 0))
    d = band(c, PHOTO_H)
    lab = ImageFont.truetype(F_LABEL, 30)
    spaced(d, (MARGIN, PHOTO_H + 70), f"{p['label']}  ·  {n}/{tot}", lab, GOLD)
    ft, lines = fit_title(d, head, W - 2 * MARGIN, 2, start=118, minsize=64)
    y = PHOTO_H + 140
    for ln in lines:
        d.text((MARGIN, y), ln, font=ft, fill=WHITE)
        y += int(ft.size * 1.1)
    fb = ImageFont.truetype(F_BODY, 44)
    y += 45
    for ln in wrap(d, body, fb, W - 2 * MARGIN)[:5]:
        d.text((MARGIN, y), ln, font=fb, fill=GREY)
        y += 60
    return c


def slide_end(p):
    c = Image.new("RGB", (W, H), BLACK)
    d = ImageDraw.Draw(c)
    lg = logo_img(420)
    c.paste(lg, ((W - lg.width) // 2, 640), lg)
    d.rectangle([(W - 160) // 2, 900, (W + 160) // 2, 906], fill=GOLD)
    fb = ImageFont.truetype(F_BODY, 46)
    y = 960
    for ln in ["L'articolo completo è su", "ilmagazinedelparrucchiere.com"]:
        tw = d.textlength(ln, font=fb)
        d.text(((W - tw) / 2, y), ln, font=fb, fill=WHITE)
        y += 64
    ft = ImageFont.truetype(F_TITLE, 84)
    tw = d.textlength("LINK IN BIO", font=ft)
    d.text(((W - tw) / 2, y + 50), "LINK IN BIO", font=ft, fill=GOLD)
    return c


def pick_music(tmp, seconds):
    """Traccia dalla cartella music/ (a rotazione per articolo); se vuota, base generata."""
    folder = os.path.join(HERE, "music")
    tracks = sorted(f for f in os.listdir(folder) if f.lower().endswith((".mp3", ".m4a", ".wav", ".aac"))) \
        if os.path.isdir(folder) else []
    pid = os.environ.get("MDP_POST_ID", "0")
    if tracks:
        return os.path.join(folder, tracks[int(pid) % len(tracks)])
    out = os.path.join(tmp, "base.wav")
    subprocess.run([sys.executable, os.path.join(HERE, "music_gen.py"), f"{seconds + 1:.1f}", out, pid], check=True)
    return out


def render(slides, durations, out_mp4, tmp):
    """Ogni slide: zoom lento sulla parte alta (foto), dissolvenza tra slide."""
    inputs, filters = [], []
    for i, (img, dur) in enumerate(zip(slides, durations)):
        path = os.path.join(tmp, f"s{i}.png")
        img.save(path)
        inputs += ["-framerate", str(FPS), "-loop", "1", "-t", f"{dur:.2f}", "-i", path]
        frames = int(dur * FPS)
        # zoom 1.00 -> 1.06 centrato in alto, solo se la slide ha la foto
        zoom = "zoompan=z='min(1+0.06*on/{f},1.06)':x='iw/2-(iw/zoom/2)':y='0':d=1:s={w}x{h}:fps={fps}".format(
            f=frames, w=W, h=H, fps=FPS) if i < len(slides) - 1 else f"fps={FPS},scale={W}:{H}"
        filters.append(f"[{i}:v]scale={W*2}:{H*2},{zoom},format=yuv420p,setsar=1[v{i}]")
    xf = 0.5
    last, t = "[v0]", durations[0]
    for i in range(1, len(slides)):
        off = t - xf
        out = f"[x{i}]"
        filters.append(f"{last}[v{i}]xfade=transition=fade:duration={xf}:offset={off:.2f}{out}")
        last, t = out, t + durations[i] - xf
    total = t
    track = pick_music(tmp, total)
    a = len(slides)
    filters.append(f"[{a}:a]atrim=0:{total:.2f},asetpts=PTS-STARTPTS,volume=0.8,"
                   f"afade=t=in:st=0:d=1,afade=t=out:st={total-1.5:.2f}:d=1.5,aresample=48000[aud]")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", *inputs,
           "-stream_loop", "-1", "-i", track,
           "-filter_complex", ";".join(filters),
           "-map", last, "-map", "[aud]",
           "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", str(FPS),
           "-g", str(FPS * 2), "-b:v", "4M", "-maxrate", "4.5M", "-bufsize", "8M",
           "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-shortest",
           "-movflags", "+faststart", out_mp4]
    subprocess.run(cmd, check=True)
    return total


def main():
    pid, outdir = sys.argv[1], sys.argv[2]
    os.environ["MDP_POST_ID"] = pid
    os.makedirs(outdir, exist_ok=True)
    p = load_post(pid)
    pics = []
    for u in ([p["feat"]] if p["feat"] else []) + p["imgs"]:
        try:
            pics.append(Image.open(io.BytesIO(get(u))))
        except Exception as e:  # immagine non scaricabile: si salta
            print("immagine saltata", u, e, file=sys.stderr)
    if not pics:
        raise SystemExit("nessuna immagine nell'articolo")
    secs = p["sections"] or [(p["title"], p["subtitle"])]
    slides = [slide_cover(pics[0], p)]
    for i, (h, b) in enumerate(secs, 1):
        photo = pics[i % len(pics)] if len(pics) > 1 else pics[0]
        slides.append(slide_section(photo, p, h, b, i, len(secs)))
    slides.append(slide_end(p))
    durations = [3.5] + [4.5] * len(secs) + [3.0]
    with tempfile.TemporaryDirectory() as tmp:
        total = render(slides, durations, os.path.join(outdir, f"{pid}.mp4"), tmp)
    slides[0].save(os.path.join(outdir, f"{pid}.jpg"), quality=90)
    print(json.dumps({"post_id": pid, "seconds": round(total, 1), "slides": len(slides)}))


if __name__ == "__main__":
    main()
