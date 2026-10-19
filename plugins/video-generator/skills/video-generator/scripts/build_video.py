#!/usr/bin/env python3
"""Render a short, silent motion-graphics video from a JSON beat sheet.

    python3 build_video.py beats.json acme-bakery-video
    python3 build_video.py - acme-bakery-video  <<'JSON' ... JSON      (beats on stdin)
    python3 build_video.py --help                                      (this text)

The second argument is the output folder. Its name minus a trailing "-video"
is the stem, so "acme-bakery-video" writes:

    acme-bakery-video/acme-bakery.mp4     the video
    acme-bakery-video/poster.png          the first beat, settled - a thumbnail
    acme-bakery-video/storyboard.png      every beat, settled, in one image
    acme-bakery-video.zip                 the folder, zipped

Beat sheet shape:

{
  "size": "9:16",                 9:16 (1080x1920), 1:1 (1080x1080),
                                  4:5 (1080x1350) or 16:9 (1920x1080)
  "style": {"bg": "FFF8F0", "ink": "2B1D14", "accent": "C2410C",
            "weight": "bold",     bold or regular (soft and blocks only)
            "look": "soft",       soft, kinetic, editorial or blocks
            "pace": "normal"},    calm, normal or snappy
  "beats": [
    {"text": "Fresh bread before sunrise", "motion": "rise"},
    {"text": "Sourdough baked at 5am", "kicker": "Every day",
     "motion": "wipe", "tone": "accent"},
    {"text": "Order ahead at acmebakery.com", "emphasis": ["Order"]}
  ]
}

Looks - each is its own layout, background, transition and type:

  soft       centred type, a soft circle drifting behind, a bar under each
             line, colour panels that wipe in. Sans.
  kinetic    huge condensed capitals, left-aligned beside an accent bar, a
             diagonal stripe that slides, hard cuts with a 2-frame flash.
  editorial  serif type, centred with wide margins, a hairline frame, a
             spaced-out kicker between thin rules, slow cross-fades.
  blocks     text on a card, left-aligned; colour blocks slide in from the
             edges and recompose on every beat.

Rules the script enforces, so the beat sheet never has to:

  * "text" is at most 8 words and "kicker" at most 4. A longer beat is an
    error naming the beat - split it in two, never cram.
  * Each beat lasts max(1.6, 0.9 + 0.32 x words) seconds, kicker words
    included, so every line stays on screen long enough to read. The last
    beat holds 1.0 s longer. A total over 30 s is an error naming the
    longest beats; nothing is ever sped up to fit.
  * "pace" changes only how long entrances, exits and transitions take.
    The time a line sits fully readable on screen is the same at every
    pace, so snappy is shorter and calm is longer by transition time only.
  * "motion" is one of rise, fade, wipe, scale, type, slide, pop, words.
    Leave it out and the look's own entrance is used (soft rise, kinetic
    words, editorial fade, blocks slide).
  * "tone" is "base" (bg colour) or "accent" (accent colour fills the frame).
  * "emphasis" is up to 2 words from "text", drawn in the accent colour.
    Allowed on base-tone beats, and on any blocks beat (its card is bg).
  * Text is wrapped and sized to fit the platform safe area automatically.
  * ink is darkened or lightened until it clears 4.5:1 on bg, accent until
    it clears 3:1. Text on an accent beat uses whichever of bg, ink, white
    or black reads best. The final colours are printed - use those.
  * Fonts are found on the machine. The summary prints the fonts actually
    used; if no serif exists, editorial says so in "notes".

Output ladder (the script takes the first rung that works and says which):

  1. mp4   Pillow draws the frames, ffmpeg encodes H.264 (yuv420p, 30 fps).
  2. gif   no ffmpeg: Pillow writes an animated GIF at reduced size.
  3. html  no Pillow (or no scalable font): a self-contained HTML animation.

--format mp4|gif|html forces a rung, for testing. On success a JSON summary
is printed to stdout; on any problem the script exits non-zero with a reason.
"""
import json
import math
import os
import re
import shutil
import subprocess
import sys
import zipfile

SIZES = {"9:16": (1080, 1920), "1:1": (1080, 1080), "4:5": (1080, 1350),
         "16:9": (1920, 1080)}
MOTIONS = ("rise", "fade", "wipe", "scale", "type", "slide", "pop", "words")
LOOKS = ("soft", "kinetic", "editorial", "blocks")
LOOK_MOTION = {"soft": "rise", "kinetic": "words", "editorial": "fade", "blocks": "slide"}
PACES = {"calm": 1.5, "normal": 1.0, "snappy": 0.6}
MAX_WORDS, MAX_KICKER_WORDS, MAX_SECONDS, MAX_EMPHASIS = 8, 4, 30.0, 2
FPS = 30
ENTER, EXIT, FINAL_HOLD = 0.5, 0.25, 1.0
WIPE, WIPE_DELAY = 0.45, 0.35   # panel colour change; text waits for it
FLASH = 2 / FPS                 # kinetic's cut flash; text waits for it
SCRIM = (12, 12, 14)            # the darkening laid over a photo behind light text
KEN_BURNS = 0.08                # how far an image zooms across its beat
MIN_IMAGE_SIDE = 512


def fail(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


# --- colour --------------------------------------------------------------------

def parse_hex(value, field):
    s = str(value).strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6 or any(c not in "0123456789abcdefABCDEF" for c in s):
        fail(f"style.{field} must be a hex colour like C2410C, got {value!r}")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def to_hex(rgb):
    return "".join(f"{c:02X}" for c in rgb)


def luminance(rgb):
    def ch(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def mix(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def ensure_contrast(fg, bg, ratio):
    """Move fg toward black or white, whichever pole contrasts more with bg."""
    if contrast(fg, bg) >= ratio:
        return fg
    pole = (0, 0, 0) if contrast((0, 0, 0), bg) >= contrast((255, 255, 255), bg) \
        else (255, 255, 255)
    for i in range(1, 101):
        c = mix(fg, pole, i / 100)
        if contrast(c, bg) >= ratio:
            return c
    return pole


def text_on(panel, preferred):
    """Best-reading text colour on a panel, preferring the brand colours."""
    for c in preferred:
        if contrast(c, panel) >= 4.5:
            return c
    return max(((0, 0, 0), (255, 255, 255)), key=lambda c: contrast(c, panel))


# --- beat sheet ----------------------------------------------------------------

def words(s):
    return len(str(s).split())


def norm_word(s):
    return re.sub(r"[^\w']", "", s.lower())


def load_sheet(raw):
    try:
        sheet = json.loads(raw)
    except json.JSONDecodeError as e:
        fail(f"beat sheet is not valid JSON: {e}")
    if not isinstance(sheet, dict):
        fail("beat sheet must be a JSON object")

    size = sheet.get("size", "16:9")
    if size not in SIZES:
        fail(f"size must be one of {', '.join(SIZES)}, got {size!r}")

    style = sheet.get("style") or {}
    bg = parse_hex(style.get("bg", "FFFFFF"), "bg")
    ink = ensure_contrast(parse_hex(style.get("ink", "111111"), "ink"), bg, 4.5)
    accent = ensure_contrast(parse_hex(style.get("accent", "4B22E8"), "accent"), bg, 3.0)
    weight = style.get("weight", "bold")
    if weight not in ("bold", "regular"):
        fail(f"style.weight must be bold or regular, got {weight!r}")
    look = style.get("look", "soft")
    if look not in LOOKS:
        fail(f"style.look must be one of {', '.join(LOOKS)}, got {look!r}")
    pace = style.get("pace", "normal")
    if pace not in PACES:
        fail(f"style.pace must be one of {', '.join(PACES)}, got {pace!r}")
    f = PACES[pace]

    beats = sheet.get("beats")
    if not isinstance(beats, list) or len(beats) < 2:
        fail("beats must be a list of at least 2 beats - a hook and an ending")
    out = []
    for n, b in enumerate(beats, 1):
        if not isinstance(b, dict) or not str(b.get("text", "")).strip():
            fail(f"beat {n} has no text")
        text = " ".join(str(b["text"]).split())
        kicker = " ".join(str(b.get("kicker", "")).split())
        if words(text) > MAX_WORDS:
            fail(f"beat {n} has {words(text)} words (max {MAX_WORDS}): {text!r} - split it into two beats")
        if words(kicker) > MAX_KICKER_WORDS:
            fail(f"beat {n} kicker has {words(kicker)} words (max {MAX_KICKER_WORDS}): {kicker!r}")
        motion = b.get("motion") or LOOK_MOTION[look]
        if motion not in MOTIONS:
            fail(f"beat {n} motion must be one of {', '.join(MOTIONS)}, got {motion!r}")
        tone = b.get("tone", "base")
        if tone not in ("base", "accent"):
            fail(f"beat {n} tone must be base or accent, got {tone!r}")
        emph = b.get("emphasis") or []
        if isinstance(emph, str):
            emph = emph.split()
        emph = [norm_word(e) for e in emph if norm_word(e)]
        if len(emph) > MAX_EMPHASIS:
            fail(f"beat {n} emphasis has {len(emph)} words (max {MAX_EMPHASIS})")
        in_text = {norm_word(x) for x in text.split()}
        for e in emph:
            if e not in in_text:
                fail(f"beat {n} emphasis word {e!r} is not in its text {text!r}")
        if emph and tone == "accent" and look != "blocks":
            fail(f"beat {n} sets emphasis on an accent beat - the accent colour would vanish "
                 f"into the panel. Use a base beat, or drop the emphasis")
        image = b.get("image")
        if image:
            image = os.path.abspath(os.path.expanduser(str(image)))
            if not os.path.isfile(image):
                fail(f"beat {n} image not found: {image}")
            if b.get("tone", "base") == "accent":
                fail(f"beat {n} has an image, so it cannot also be an accent beat - drop the tone")
            if emph and look != "blocks":
                fail(f"beat {n} sets emphasis over an image - the accent colour cannot be "
                     f"guaranteed to read on a photo. Move the emphasis to a beat without an image")
            tone = "image"
        dur = max(1.6, 0.9 + 0.32 * (words(text) + words(kicker)))
        if n == len(beats):
            dur += FINAL_HOLD
        dur = round(dur, 2)
        if f != 1.0:
            # Entrances and exits stretch or shrink with pace; the readable hold does not.
            # The last beat has no exit, so only its entrance changes.
            dur += ENTER * (f - 1) + (EXIT * (f - 1) if n < len(beats) else 0.0)
        out.append({"n": n, "text": text, "kicker": kicker, "motion": motion,
                    "tone": tone, "emphasis": emph, "dur": dur, "image": image or None})

    # What fills the frame behind a beat: a colour panel, or one particular image.
    for b in out:
        b["ground"] = ("image", b["image"]) if b["image"] else ("tone", b["tone"])
    t, prev_tone = 0.0, out[0]["ground"]
    for k, b in enumerate(out):
        # The text waits for the transition into its beat, and the beat grows
        # by that wait so reading time is never eaten by the transition.
        if look == "kinetic":
            b["delay"] = round(FLASH, 3) if k else 0.0
        else:
            b["delay"] = WIPE_DELAY * f if b["ground"] != prev_tone else 0.0
        if f == 1.0:
            b["dur"] = round(b["dur"] + b["delay"], 2)
        else:
            # Round up once, so a pace change can never shave reading time.
            b["dur"] = math.ceil(round((b["dur"] + b["delay"]) * 100, 6)) / 100
        prev_tone = b["ground"]
        b["start"] = round(t, 3)
        t += b["dur"]
        if b["tone"] == "image":
            # Light text over a darkening scrim the renderer sizes to the photo.
            b["fg"] = next((c for c in (bg, ink) if luminance(c) > 0.6), (255, 255, 255))
            b["panel"] = SCRIM if luminance(ink) > 0.05 else mix(ink, (0, 0, 0), 0.4)
            continue
        panel = accent if b["tone"] == "accent" else bg
        b["panel"] = panel
        b["fg"] = ink if b["tone"] == "base" else text_on(accent, [bg, ink])
    if t > MAX_SECONDS:
        longest = sorted(out[:-1], key=lambda b: -b["dur"])[:3]
        names = ", ".join(f"beat {b['n']} ({b['dur']}s)" for b in longest)
        fail(f"video would run {t:.1f}s (max {MAX_SECONDS:.0f}s). Cut a beat or shorten "
             f"the longest: {names}. Keep the last beat - it is the ending. "
             f"Beats are never sped up to fit.")
    return {"size": size, "w": SIZES[size][0], "h": SIZES[size][1], "bg": bg,
            "ink": ink, "accent": accent, "weight": weight, "look": look, "pace": pace,
            "f": f, "beats": out, "total": round(t, 2)}


def safe_area(w, h):
    """Box text may occupy. Vertical video keeps clear of platform UI top and bottom."""
    if h > w * 1.5:
        return (int(w * 0.09), int(h * 0.16), int(w * 0.91), int(h * 0.70))
    return (int(w * 0.09), int(h * 0.14), int(w * 0.91), int(h * 0.86))


# --- easing ----------------------------------------------------------------------

def clamp01(x):
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def ease_out(x):
    return 1 - (1 - clamp01(x)) ** 3


def ease_in_out(x):
    x = clamp01(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def back_out(x):
    """Overshoots past 1 then settles - the spring in 'pop'."""
    x = clamp01(x)
    c1 = 1.70158
    return 1 + (c1 + 1) * (x - 1) ** 3 + c1 * (x - 1) ** 2


# --- fonts ---------------------------------------------------------------------------

FONT_CANDIDATES = [
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
]

# (path, accepted style names) in order of preference.
DISPLAY_CANDIDATES = [
    ("/System/Library/Fonts/HelveticaNeue.ttc", ("condensed black",)),
    ("/System/Library/Fonts/HelveticaNeue.ttc", ("condensed bold",)),
    ("/System/Library/Fonts/Supplemental/Arial Black.ttf", ("regular", "black")),
    ("/Library/Fonts/Arial Black.ttf", ("regular", "black")),
    ("C:/Windows/Fonts/ariblk.ttf", ("regular", "black")),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf", ("condensed bold", "bold")),
    ("/usr/share/fonts/truetype/liberation/LiberationSansNarrow-Bold.ttf", ("bold",)),
]
SERIF_CANDIDATES = [
    ("/System/Library/Fonts/Supplemental/Didot.ttc", ("regular",)),
    ("/System/Library/Fonts/Supplemental/Baskerville.ttc", ("regular",)),
    ("/System/Library/Fonts/Supplemental/Georgia.ttf", ("regular",)),
    ("/System/Library/Fonts/Supplemental/Times New Roman.ttf", ("regular",)),
    ("/Library/Fonts/Georgia.ttf", ("regular",)),
    ("C:/Windows/Fonts/georgia.ttf", ("regular",)),
    ("C:/Windows/Fonts/times.ttf", ("regular",)),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", ("book", "regular")),
    ("/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf", ("regular",)),
    ("/usr/share/fonts/dejavu/DejaVuSerif.ttf", ("book", "regular")),
]


def find_font(ImageFont, weight):
    """Return a loader size -> FreeTypeFont, preferring the requested weight."""
    want = "bold" if weight == "bold" else "regular"
    fallback = None
    for path in FONT_CANDIDATES:
        if not os.path.isfile(path):
            continue
        for index in range(8 if path.endswith(".ttc") else 1):
            try:
                f = ImageFont.truetype(path, 20, index=index)
            except Exception:
                break
            style = f.getname()[1].lower()
            if style == want or (want == "regular" and style in ("roman", "book")):
                name = " ".join(f.getname())
                return (lambda s, p=path, i=index: ImageFont.truetype(p, s, index=i)), name
            if fallback is None and "italic" not in style and "oblique" not in style:
                fallback = (path, index, " ".join(f.getname()))
    if fallback:
        p, i, name = fallback
        return (lambda s: ImageFont.truetype(p, s, index=i)), name
    try:
        f = ImageFont.load_default(size=20)
        if hasattr(f, "getname"):
            return (lambda s: ImageFont.load_default(size=s)), " ".join(f.getname())
    except TypeError:
        pass
    return None, None


def find_styled(ImageFont, candidates):
    """First candidate face whose style name matches. Returns (loader, name) or (None, None)."""
    for path, styles in candidates:
        if not os.path.isfile(path):
            continue
        for index in range(16 if path.endswith(".ttc") else 1):
            try:
                f = ImageFont.truetype(path, 20, index=index)
            except Exception:
                break
            if f.getname()[1].lower() in styles:
                return (lambda s, p=path, i=index: ImageFont.truetype(p, s, index=i)), \
                    " ".join(f.getname())
    return None, None


# --- text layout ---------------------------------------------------------------------

def wrap(draw, text, font, max_w):
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def balanced_wrap(draw, text, font, max_w):
    """Greedy wrap, then narrow the measure while the line count holds, so no line is an orphan."""
    lines = wrap(draw, text, font, max_w)
    if len(lines) < 2:
        return lines
    lo, hi = max_w * 0.4, max_w
    for _ in range(12):
        mid = (lo + hi) / 2
        if len(wrap(draw, text, font, mid)) == len(lines):
            hi = mid
        else:
            lo = mid
    return wrap(draw, text, font, hi)


def word_boxes(draw, line, font, lx, y, line_h):
    """Box of every word in a drawn line, in reading order."""
    boxes, pos = [], 0
    for word in line.split(" "):
        start = line.index(word, pos)
        x0 = lx + draw.textlength(line[:start], font=font)
        x1 = x0 + draw.textlength(word, font=font)
        boxes.append((int(x0), int(y), int(math.ceil(x1)), int(y + line_h), word))
        pos = start + len(word)
    return boxes


def tracked_width(draw, text, font, track):
    return sum(draw.textlength(c, font=font) for c in text) + track * max(len(text) - 1, 0)


def draw_tracked(d, probe, x, y, text, font, track):
    for c in text:
        d.text((x, y), c, font=font, fill=255)
        x += probe.textlength(c, font=font) + track


def layout_beat(beat, w, h, load_font, Image, ImageDraw):
    """Soft: fit main text (and kicker) into the safe area. Returns a text mask and boxes."""
    x0, y0, x1, y1 = safe_area(w, h)
    box_w, box_h = x1 - x0, y1 - y0
    probe = ImageDraw.Draw(Image.new("L", (8, 8)))
    size = int(min(w, h) * (0.13 if h > w else 0.12))
    while True:
        font = load_font(size)
        lines = balanced_wrap(probe, beat["text"], font, box_w)
        widest = max(probe.textlength(line, font=font) for line in lines)
        asc, desc = font.getmetrics()
        line_h = int((asc + desc) * 1.08)
        k_size = max(int(size * 0.42), 14)
        k_font = load_font(k_size)
        k_text = beat["kicker"].upper()
        k_h = int(sum(k_font.getmetrics()) * 1.6) if k_text else 0
        k_w = probe.textlength(k_text, font=k_font) if k_text else 0
        bar_h = max(int(size * 0.09), 4)
        gap = int(size * 0.42)
        total_h = k_h + line_h * len(lines) + gap + bar_h
        if (widest <= box_w and k_w <= box_w and len(lines) <= 4 and total_h <= box_h) \
                or size <= 18:
            break
        size = int(size * 0.94)

    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    top = y0 + (box_h - total_h) // 2
    line_boxes, words_ = [], []
    if k_text:
        d.text(((w - k_w) / 2, top), k_text, font=k_font, fill=255)
    y = top + k_h
    for line in lines:
        lw = probe.textlength(line, font=font)
        lx = (w - lw) / 2
        d.text((lx, y), line, font=font, fill=255)
        line_boxes.append((int(lx), int(y), int(math.ceil(lx + lw)), int(y + line_h)))
        words_ += word_boxes(probe, line, font, lx, y, line_h)
        y += line_h
    bar_w = int(min(widest * 0.5, box_w * 0.4))
    bar = ((w - bar_w) // 2, int(y + gap), (w + bar_w) // 2, int(y + gap + bar_h))
    block = (x0, int(top), x1, int(y + gap + bar_h))
    return {"mask": mask, "lines": line_boxes, "words": words_, "bar": bar, "block": block,
            "kicker_box": (0, int(top), w, int(top + k_h)) if k_text else None}


def layout_text(beat, w, h, box, P, load_font, load_kicker, Image, ImageDraw):
    """Kinetic, editorial and blocks: fit the text into box with the look's parameters P."""
    x0, y0, x1, y1 = box
    box_w, box_h = x1 - x0, y1 - y0
    probe = ImageDraw.Draw(Image.new("L", (8, 8)))
    text = beat["text"].upper() if P["upper"] else beat["text"]
    k_text = beat["kicker"].upper()
    size = int(min(w, h) * (P["size_v"] if h > w else P["size_h"]))
    while True:
        font = load_font(size)
        lines = balanced_wrap(probe, text, font, box_w)
        widest = max(probe.textlength(line, font=font) for line in lines)
        asc, desc = font.getmetrics()
        line_h = int((asc + desc) * P["lh"])
        k_size = max(int(size * P["kscale"]), int(14 * min(w, h) / 1080))
        k_font = load_kicker(k_size)
        track = k_size * P["ktrack"]
        k_h = int(sum(k_font.getmetrics()) * 1.7) if k_text else 0
        k_w = tracked_width(probe, k_text, k_font, track) if k_text else 0
        rule = int(k_size * 2.2) if P.get("rules") and k_text else 0
        total_h = k_h + line_h * len(lines)
        if (widest <= box_w and k_w + 2 * rule <= box_w and len(lines) <= P["max_lines"]
                and total_h <= box_h) or size <= 18:
            break
        size = int(size * 0.94)

    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    top = y0 + (box_h - total_h) // 2
    center = P["align"] == "center"
    shapes = None
    if k_text:
        kx = (w - k_w) / 2 if center else x0
        draw_tracked(d, probe, kx, top, k_text, k_font, track)
        if rule:
            shapes = Image.new("L", (w, h), 0)
            sd = ImageDraw.Draw(shapes)
            ky = top + k_font.getmetrics()[0] * 0.62
            th = max(1, round(min(w, h) / 540))
            gap = k_size * 0.9
            sd.rectangle((kx - gap - rule, ky, kx - gap, ky + th), fill=255)
            sd.rectangle((kx + k_w + gap, ky, kx + k_w + gap + rule, ky + th), fill=255)
    y = top + k_h
    line_boxes, words_ = [], []
    for line in lines:
        lw = probe.textlength(line, font=font)
        lx = (w - lw) / 2 if center else x0
        d.text((lx, y), line, font=font, fill=255)
        line_boxes.append((int(lx), int(y), int(math.ceil(lx + lw)), int(y + line_h)))
        words_ += word_boxes(probe, line, font, lx, y, line_h)
        y += line_h
    text_x1 = max([b[2] for b in line_boxes] + [int(x0 + k_w) if not center else 0])
    return {"mask": mask, "shapes": shapes, "lines": line_boxes, "words": words_,
            "block": (x0, int(top), x1, int(y)), "size": size, "text_x1": text_x1,
            "kicker_box": (0, int(top), w, int(top + k_h)) if k_text else None}


def split_emphasis(Image, lay, emph):
    """Move the emphasised words out of the main mask into their own mask."""
    if not emph:
        return None
    em = Image.new("L", lay["mask"].size, 0)
    for x0, y0, x1, y1, word in lay["words"]:
        if norm_word(word) in emph:
            em.paste(lay["mask"].crop((x0, y0, x1, y1)), (x0, y0))
            lay["mask"].paste(0, (x0, y0, x1, y1))
    return em


def soft_circle(Image, ImageDraw, r):
    big = Image.new("L", (r * 8, r * 8), 0)
    ImageDraw.Draw(big).ellipse((0, 0, r * 8 - 1, r * 8 - 1), fill=255)
    return big.resize((r * 2, r * 2), Image.LANCZOS)


# --- renderer core -------------------------------------------------------------------

class Renderer:
    """Shared timeline, motion and compositing. A Look draws what is particular to it."""

    def __init__(self, spec, scale, Image, ImageDraw, ImageFont, still_photos=False):
        self.Image, self.ImageDraw = Image, ImageDraw
        self.spec = spec
        self.still_photos = still_photos
        self.w = int(spec["w"] * scale) // 2 * 2
        self.h = int(spec["h"] * scale) // 2 * 2
        f = spec["f"]
        self.enter, self.exit, self.wipe = ENTER * f, EXIT * f, WIPE * f
        self.notes = []
        self.look = {"soft": Soft, "kinetic": Kinetic, "editorial": Editorial,
                     "blocks": Blocks}[spec["look"]](self, ImageFont)
        self.font_name = self.look.font_name
        self.fonts = self.look.fonts

    def frame(self, t, settle=None):
        """Draw time t. settle=i draws beat i fully entered, for stills."""
        beats = self.spec["beats"]
        if settle is not None:
            i = settle
            local = beats[i]["dur"] - (0.01 if i == len(beats) - 1 else self.exit + 1 / FPS)
        else:
            i = next((k for k, b in enumerate(beats) if t < b["start"] + b["dur"]), len(beats) - 1)
            local = t - beats[i]["start"]
        beat, lay = beats[i], self.look.layouts[i]
        last = i == len(beats) - 1

        now = beat["start"] + local
        im = self.look.background(i, local, now)
        out = 1.0 if last else clamp01((beat["dur"] - local) / self.exit)
        local = local - beat["delay"]
        if local < 0:
            return im
        self.look.under(im, i, local, out)
        for kind, mask, color in lay["layers"]:
            m, alpha = self.move(beat, lay, mask, kind, local)
            alpha *= out
            if alpha < 1:
                m = m.point(lambda v, a=alpha: int(v * a))
            im.paste(color, (0, 0), m)
        self.look.over(im, i, local, out)
        return im

    def move(self, beat, lay, mask, kind, local):
        """Apply the beat's entrance to one mask. Returns (mask, alpha)."""
        Image, w, h = self.Image, self.w, self.h
        motion = beat["motion"]
        if kind == "shape" and motion in ("type", "words", "wipe"):
            motion = "fade"
        e = ease_out(local / self.enter)
        if motion == "rise":
            dy = int(h * 0.05 * (1 - e))
            return mask.transform(mask.size, Image.AFFINE, (1, 0, 0, 0, 1, -dy)), e
        if motion == "fade":
            return mask, e
        if motion == "slide":
            dx = int(w * 0.06 * (1 - e))
            return mask.transform(mask.size, Image.AFFINE, (1, 0, dx, 0, 1, 0)), e
        if motion in ("scale", "pop"):
            s = 0.86 + 0.14 * e if motion == "scale" else \
                0.6 + 0.4 * back_out(local / (self.enter * 1.2))
            cx0, cy0 = w / 2, (lay["block"][1] + lay["block"][3]) / 2
            if self.spec["look"] in ("kinetic", "blocks"):
                cx0 = lay["block"][0]
            return mask.transform(mask.size, Image.AFFINE,
                                  (1 / s, 0, cx0 - cx0 / s, 0, 1 / s, cy0 - cy0 / s),
                                  resample=Image.BILINEAR), e
        if motion == "wipe":
            cut = Image.new("L", mask.size, 0)
            x0, y0, x1, y1 = lay["block"]
            edge = int(x0 + (x1 - x0) * e)
            cut.paste(mask.crop((0, 0, edge, h)), (0, 0))
            return cut, e
        if motion == "type":
            return self.typed(beat, lay, mask, local), 1.0
        return self.worded(beat, lay, mask, local), 1.0

    def typed(self, beat, lay, mask, local):
        """Reveal the lines left to right in reading order, at about 28 characters a second."""
        Image = self.Image
        lines = lay["lines"]
        chars = [b[2] - b[0] for b in lines]
        span = min(max(len(beat["text"]) / 28, 0.6), 1.4, beat["dur"] * 0.5)
        reveal = clamp01(local / span) * sum(chars)
        cut = Image.new("L", mask.size, 0)
        if lay["kicker_box"]:
            cut.paste(mask.crop(lay["kicker_box"]), lay["kicker_box"][:2])
        for (x0, y0, x1, y1), wdt in zip(lines, chars):
            take = int(min(max(reveal, 0), wdt))
            if take > 0:
                cut.paste(mask.crop((x0, y0, x0 + take, y1)), (x0, y0))
            reveal -= wdt
        return cut

    def worded(self, beat, lay, mask, local):
        """Words land one at a time, each scaling down from 125% as it fades in."""
        Image, ImageChops = self.Image, self.chops
        boxes = lay["words"]
        f = self.spec["f"]
        land = 0.18 * f
        stagger = min(0.07 * f, max(beat["dur"] * 0.5 - land, 0.1) / max(len(boxes) - 1, 1))
        if local >= land + stagger * (len(boxes) - 1):
            return mask
        bx0, by0, bx1, by1 = lay["block"]
        pad = int((by1 - by0) * 0.3) + 4
        rx0, ry0 = max(bx0 - pad, 0), max(by0 - pad, 0)
        rx1, ry1 = min(max(bx1, lay["text_x1"] if "text_x1" in lay else bx1) + pad, self.w), \
            min(by1 + pad, self.h)
        region = Image.new("L", (rx1 - rx0, ry1 - ry0), 0)
        if lay["kicker_box"]:
            a = clamp01(local / land)
            kb = lay["kicker_box"]
            k = mask.crop(kb).point(lambda v, a=a: int(v * a))
            region.paste(k, (kb[0] - rx0, kb[1] - ry0))
        for k, (x0, y0, x1, y1, _) in enumerate(boxes):
            p = clamp01((local - k * stagger) / land)
            if p <= 0:
                continue
            piece = mask.crop((x0, y0, x1, y1))
            if p < 1:
                s = 1.25 - 0.25 * ease_out(p)
                pw, ph = max(int(piece.width * s), 1), max(int(piece.height * s), 1)
                piece = piece.resize((pw, ph), Image.BILINEAR).point(
                    lambda v, a=ease_out(p): int(v * a))
                px = int((x0 + x1) / 2 - pw / 2) - rx0
                py = int((y0 + y1) / 2 - ph / 2) - ry0
            else:
                px, py = x0 - rx0, y0 - ry0
            layer = Image.new("L", region.size, 0)
            layer.paste(piece, (px, py))
            region = ImageChops.lighter(region, layer)
        cut = Image.new("L", mask.size, 0)
        cut.paste(region, (rx0, ry0))
        return cut


class Look:
    def __init__(self, r, ImageFont):
        self.r = r
        self.Image, self.ImageDraw = r.Image, r.ImageDraw
        from PIL import ImageChops
        r.chops = ImageChops
        self.spec = r.spec
        self.w, self.h = r.w, r.h
        self.setup(ImageFont)
        self.layouts = [self.layout(b) for b in self.spec["beats"]]
        for b, lay in zip(self.spec["beats"], self.layouts):
            em = split_emphasis(self.Image, lay, b["emphasis"])
            if em is not None:
                lay["layers"].append(("text", em, self.spec["accent"]))
        self.prepare_photos()

    # Text sits on a card in blocks, so only the other looks need a scrim behind it.
    needs_scrim = True

    def prepare_photos(self):
        """Cover-crop every image beat once, and size the scrim that keeps its text readable."""
        from PIL import ImageFilter
        Image, w, h = self.Image, self.w, self.h
        self.photos, self.scrims = {}, {}
        for i, b in enumerate(self.spec["beats"]):
            if not b["image"]:
                continue
            try:
                src = Image.open(b["image"])
                src.load()
                src = src.convert("RGB")
            except Exception as e:
                raise RuntimeError(f"beat {b['n']} image could not be read: {e}")
            if min(src.size) < MIN_IMAGE_SIDE:
                fail(f"beat {b['n']} image is {src.width}x{src.height} - at least "
                     f"{MIN_IMAGE_SIDE}px on the short side is needed")
            # 10% margin all round leaves room for the slow zoom and pan.
            bw, bh = int(w * 1.1), int(h * 1.1)
            k = max(bw / src.width, bh / src.height)
            full_k = max(self.spec["w"] * 1.1 / src.width, self.spec["h"] * 1.1 / src.height)
            if full_k > 1.6:
                note = (f"beat {b['n']} image is {src.width}x{src.height}, enlarged "
                        f"{full_k:.1f}x for this size - it may look soft")
                if note not in self.r.notes:
                    self.r.notes.append(note)
            rw, rh = max(int(math.ceil(src.width * k)), bw), max(int(math.ceil(src.height * k)), bh)
            big = src.resize((rw, rh), Image.LANCZOS)
            base = big.crop(((rw - bw) // 2, (rh - bh) // 2, (rw - bw) // 2 + bw, (rh - bh) // 2 + bh))
            self.photos[i] = {"base": base, "mask": None}
            self.photos[i]["mask"], self.scrims[i] = self.scrim_mask(i, ImageFilter)

    def text_region(self, i):
        """Everything the beat draws as text, padded for how far its entrance moves it."""
        lay, w, h = self.layouts[i], self.w, self.h
        x0, y0, x1, y1 = lay["block"]
        if "bar" in lay:
            x0, y0 = min(x0, lay["bar"][0]), min(y0, lay["bar"][1])
            x1, y1 = max(x1, lay["bar"][2]), max(y1, lay["bar"][3])
        if lay.get("kicker_box"):
            y0 = min(y0, lay["kicker_box"][1])
        mx, my = int(w * 0.07), int(h * 0.06)
        return (max(x0 - mx, 0), max(y0 - my, 0), min(x1 + mx, w), min(y1 + my, h))

    def scrim_mask(self, i, ImageFilter):
        """Darken just enough that light text clears 4.5:1 on the brightest 1% of the photo."""
        Image, w, h = self.Image, self.w, self.h
        b = self.spec["beats"][i]
        veil = 0.18
        if not self.needs_scrim:
            return Image.new("L", (w, h), int(255 * 0.1)), 0.1
        region = self.text_region(i)
        worst = 0.0
        for e in (0.0, 0.25, 0.5, 0.75, 1.0):
            # Full resolution: shrinking first averages away small highlights like a flame.
            # Each channel's 99.5th percentile, combined, is at least as bright as the real pixel.
            frame = self.photo(i, None, e=e, scrim=False).crop(region)
            hist, total = frame.histogram(), frame.width * frame.height
            bright = []
            for c in range(3):
                counts, seen = hist[c * 256:(c + 1) * 256], 0
                for v in range(255, -1, -1):
                    seen += counts[v]
                    if seen > total * 0.005:
                        break
                bright.append(v)
            bright = tuple(bright)
            a = 0.0
            while a < 0.95 and contrast(b["fg"], mix(bright, b["panel"], a)) < 4.6:
                a += 0.01
            worst = max(worst, a)
        band = min(worst + 0.03, 0.95)
        base = max(veil, band * 0.45)
        mask = Image.new("L", (w, h), int(255 * base))
        r = max(int(min(w, h) * 0.04), 2)
        x0, y0, x1, y1 = region
        mask.paste(int(255 * band), (x0 - 3 * r, y0 - 3 * r, x1 + 3 * r, y1 + 3 * r))
        mask = mask.filter(ImageFilter.GaussianBlur(r))
        # The blur softens the edge; the text region itself always gets the full band.
        mask.paste(int(math.ceil(255 * band)), region)
        return mask, round(band, 2)

    def photo(self, i, now, e=None, scrim=True):
        """An image beat's frame: the photo drifting slowly in, under its scrim."""
        b, w, h = self.spec["beats"][i], self.w, self.h
        ph = self.photos[i]
        if e is None:
            # A GIF cannot compress a moving photo, so its rung holds photos still.
            e = 0.5 if self.r.still_photos else ease_in_out((now - b["start"]) / b["dur"])
        z = 1 + KEN_BURNS * (e if i % 2 == 0 else 1 - e)
        pan = w * 0.03 * (e - 0.5) * (1 if i % 2 == 0 else -1)
        cx, cy = ph["base"].width / 2 + pan, ph["base"].height / 2
        im = ph["base"].transform((w, h), self.Image.AFFINE,
                                  (1 / z, 0, cx - w / (2 * z), 0, 1 / z, cy - h / (2 * z)),
                                  resample=self.Image.BILINEAR)
        if scrim:
            im.paste(b["panel"], (0, 0), ph["mask"])
        return im

    def ground(self, i, now):
        """What fills the frame behind beat i: its photo, or the look's own panel."""
        return self.photo(i, now) if self.spec["beats"][i]["image"] else self.panel(i, now)

    def under(self, im, i, local, out):
        pass

    def over(self, im, i, local, out):
        pass

    def wiped(self, i, local, now, horizontal=None):
        """The beat's background, with a colour change wiping in over the previous one."""
        beats, w, h = self.spec["beats"], self.w, self.h
        im = self.ground(i, now)
        if i and beats[i - 1]["ground"] != beats[i]["ground"] and local < self.r.wipe:
            p = ease_in_out(local / self.r.wipe)
            old = self.ground(i - 1, now)
            if (h > w) if horizontal is None else not horizontal:
                edge = int(h * (1 - p))
                old.paste(im.crop((0, edge, w, h)), (0, edge))
            else:
                old.paste(im.crop((0, 0, int(w * p), h)), (0, 0))
            im = old
        return im


class Soft(Look):
    def setup(self, ImageFont):
        load, self.font_name = find_font(ImageFont, self.spec["weight"])
        if load is None:
            raise RuntimeError("no scalable font available")
        self.load = load
        self.fonts = {"text": self.font_name, "kicker": self.font_name}
        self.rad = int(min(self.w, self.h) * 0.42)
        self.circle = soft_circle(self.Image, self.ImageDraw, self.rad)

    def layout(self, beat):
        lay = layout_beat(beat, self.w, self.h, self.load, self.Image, self.ImageDraw)
        lay["layers"] = [("text", lay["mask"], beat["fg"])]
        return lay

    def background(self, i, local, now):
        return self.wiped(i, local, now)

    def panel(self, i, now):
        """A beat's background: its panel colour plus a soft circle drifting over the video."""
        beat, w, h = self.spec["beats"][i], self.w, self.h
        im = self.Image.new("RGB", (w, h), beat["panel"])
        tt = now / max(self.spec["total"], 0.1)
        cx = int(w * (0.78 - 0.5 * tt))
        cy = int(h * (0.22 + 0.3 * math.sin(tt * math.pi)))
        tint = mix(beat["panel"], self.spec["accent"] if beat["tone"] == "base" else beat["fg"], 0.10)
        im.paste(tint, (cx - self.rad, cy - self.rad), self.circle)
        return im

    def over(self, im, i, local, out):
        # Accent bar under the text grows in; on an accent beat it is drawn in fg.
        beat, lay = self.spec["beats"][i], self.layouts[i]
        bx0, by0, bx1, by1 = lay["bar"]
        grow = ease_out((local - 0.15) / self.r.enter) * out
        if grow > 0:
            bw = int((bx1 - bx0) * grow)
            mid = (bx0 + bx1) // 2
            bar_col = self.spec["accent"] if beat["tone"] == "base" else beat["fg"]
            im.paste(bar_col, (mid - bw // 2, by0, mid - bw // 2 + max(bw, 1), by1))


class Kinetic(Look):
    def setup(self, ImageFont):
        load, name = find_styled(ImageFont, DISPLAY_CANDIDATES)
        if load is None:
            load, name = find_font(ImageFont, "bold")
            if load is None:
                raise RuntimeError("no scalable font available")
            self.r.notes.append(f"no condensed display font found; kinetic used {name}")
        self.load, self.font_name = load, name
        kload, kname = find_font(ImageFont, "bold")
        self.kload = kload or load
        self.fonts = {"text": name, "kicker": kname or name}
        w, h = self.w, self.h
        # One antialiased diagonal band, drawn once at 2x and slid across every frame.
        band = int(min(w, h) * 0.34)
        lean = int(h * 0.42)
        big = self.Image.new("L", ((w * 2 + lean) * 2, h * 2), 0)
        self.ImageDraw.Draw(big).polygon(
            [(0, h * 2), (band * 2, h * 2), (band * 2 + lean * 2, 0), (lean * 2, 0)], fill=255)
        self.band = big.resize((w * 2 + lean, h), self.Image.LANCZOS).crop((0, 0, band + lean, h))

    def layout(self, beat):
        w, h = self.w, self.h
        x0, y0, x1, y1 = safe_area(w, h)
        self.bar_w = max(int(min(w, h) * 0.022), 6)
        gap = int(self.bar_w * 2.2)
        P = {"align": "left", "size_v": 0.22, "size_h": 0.18, "lh": 0.96, "kscale": 0.26,
             "ktrack": 0.14, "upper": True, "max_lines": 4}
        lay = layout_text(beat, w, h, (x0 + self.bar_w + gap, y0, x1, y1), P,
                          self.load, self.kload, self.Image, self.ImageDraw)
        lay["bar"] = (x0, lay["block"][1], x0 + self.bar_w, lay["block"][3])
        lay["layers"] = [("text", lay["mask"], beat["fg"])]
        return lay

    def panel(self, i, now):
        beat, w, h = self.spec["beats"][i], self.w, self.h
        im = self.Image.new("RGB", (w, h), beat["panel"])
        tint = mix(beat["panel"], self.spec["accent"] if beat["tone"] == "base" else beat["fg"],
                   0.16 if beat["tone"] == "base" else 0.14)
        local = now - beat["start"]
        tt = now / max(self.spec["total"], 0.1)
        kick = (1 - ease_out(local / (self.r.enter * 1.4))) * w * 0.3
        x = int(w * (0.55 - 0.35 * tt) + kick)
        im.paste(tint, (x, 0), self.band)
        return im

    def background(self, i, local, now):
        beat = self.spec["beats"][i]
        if i and local < FLASH:
            flash = self.spec["accent"] if beat["panel"] != self.spec["accent"] else self.spec["bg"]
            return self.Image.new("RGB", (self.w, self.h), flash)
        return self.ground(i, now)

    def under(self, im, i, local, out):
        beat, lay = self.spec["beats"][i], self.layouts[i]
        x0, y0, x1, y1 = lay["bar"]
        grow = ease_out(local / (self.r.enter * 1.2)) * out
        if grow > 0:
            col = self.spec["accent"] if beat["tone"] == "base" else beat["fg"]
            im.paste(col, (x0, y0, x1, y0 + max(int((y1 - y0) * grow), 1)))


class Editorial(Look):
    def setup(self, ImageFont):
        load, name = find_styled(ImageFont, SERIF_CANDIDATES)
        if load is None:
            load, name = find_font(ImageFont, "regular")
            if load is None:
                raise RuntimeError("no scalable font available")
            self.r.notes.append(f"no serif font found; editorial used {name}")
        self.load, self.font_name = load, name
        self.fonts = {"text": name, "kicker": name}
        m = int(min(self.w, self.h) * 0.045)
        self.inset = m
        self.hair = max(2, round(min(self.w, self.h) / 540))

    def layout(self, beat):
        w, h = self.w, self.h
        x0, y0, x1, y1 = safe_area(w, h)
        inset = int(w * 0.05)
        P = {"align": "center", "size_v": 0.12, "size_h": 0.115, "lh": 1.18, "kscale": 0.3,
             "ktrack": 0.32, "upper": False, "max_lines": 4, "rules": True}
        lay = layout_text(beat, w, h, (x0 + inset, y0, x1 - inset, y1), P,
                          self.load, self.load, self.Image, self.ImageDraw)
        lay["layers"] = [("text", lay["mask"], beat["fg"])]
        if lay["shapes"] is not None:
            lay["layers"].insert(0, ("shape", lay["shapes"], mix(beat["panel"], beat["fg"], 0.55)))
        return lay

    def panel(self, i, now):
        beat = self.spec["beats"][i]
        im = self.Image.new("RGB", (self.w, self.h), beat["panel"])
        m, t = self.inset, self.hair
        self.ImageDraw.Draw(im).rectangle((m, m, self.w - m - 1, self.h - m - 1),
                                          outline=mix(beat["panel"], beat["fg"], 0.3), width=t)
        return im

    def background(self, i, local, now):
        beats = self.spec["beats"]
        im = self.ground(i, now)
        if i and beats[i - 1]["ground"] != beats[i]["ground"] and local < self.r.wipe:
            p = ease_in_out(local / self.r.wipe)
            im = self.Image.blend(self.ground(i - 1, now), im, p)
        return im

    def ground(self, i, now):
        im = super().ground(i, now)
        beat = self.spec["beats"][i]
        if beat["image"]:
            m, t = self.inset, self.hair
            self.ImageDraw.Draw(im).rectangle((m, m, self.w - m - 1, self.h - m - 1),
                                              outline=mix(beat["panel"], beat["fg"], 0.45), width=t)
        return im


# Block compositions as (x0, y0, x1, y1) fractions of the frame and a colour role.
COMPOSITIONS = [
    [(0.00, 0.00, 0.40, 0.40, "a"), (0.62, 0.72, 1.00, 1.00, "m"), (0.72, 0.00, 1.00, 0.16, "s")],
    [(0.56, 0.00, 1.00, 0.46, "a"), (0.00, 0.80, 0.46, 1.00, "m"), (0.00, 0.00, 0.12, 0.38, "s")],
    [(0.00, 0.62, 0.52, 1.00, "a"), (0.60, 0.00, 1.00, 0.28, "m"), (0.86, 0.40, 1.00, 0.80, "s")],
    [(0.42, 0.76, 1.00, 1.00, "a"), (0.00, 0.00, 0.46, 0.24, "m"), (0.00, 0.34, 0.10, 0.70, "s")],
]


class Blocks(Look):
    def setup(self, ImageFont):
        load, self.font_name = find_font(ImageFont, self.spec["weight"])
        if load is None:
            raise RuntimeError("no scalable font available")
        self.load = load
        self.fonts = {"text": self.font_name, "kicker": self.font_name}

    def layout(self, beat):
        w, h = self.w, self.h
        x0, y0, x1, y1 = safe_area(w, h)
        unit = int(min(w, h) * 0.1)
        pad, strip = int(unit * 0.55), max(int(unit * 0.12), 6)
        inner_x0 = x0 + strip + pad
        P = {"align": "left", "size_v": 0.115, "size_h": 0.1, "lh": 1.1, "kscale": 0.34,
             "ktrack": 0.08, "upper": False, "max_lines": 4}
        lay = layout_text(beat, w, h, (inner_x0, y0 + pad, x0 + int((x1 - x0) * 0.86), y1 - pad),
                          P, self.load, self.load, self.Image, self.ImageDraw)
        bx0, by0, bx1, by1 = lay["block"]
        card = (x0, by0 - pad, lay["text_x1"] + pad, by1 + pad)
        cm = self.Image.new("L", (w, h), 0)
        self.ImageDraw.Draw(cm).rectangle(card, fill=255)
        sm = self.Image.new("L", (w, h), 0)
        self.ImageDraw.Draw(sm).rectangle((x0, card[1], x0 + strip, card[3]), fill=255)
        lay["block"] = (x0, card[1], card[2], card[3])
        strip_col = self.spec["accent"] if beat["tone"] != "accent" else self.spec["ink"]
        lay["layers"] = [("shape", cm, self.spec["bg"]), ("shape", sm, strip_col),
                         ("text", lay["mask"], self.spec["ink"])]
        return lay

    needs_scrim = False

    def colours(self, beat):
        a, bg, ink, p = self.spec["accent"], self.spec["bg"], self.spec["ink"], beat["panel"]
        if beat["tone"] == "image":
            return {"a": a, "m": bg, "s": mix(bg, a, 0.35)}
        if beat["tone"] == "base":
            return {"a": a, "m": mix(a, p, 0.55), "s": mix(ink, p, 0.82)}
        return {"a": mix(bg, p, 0.3), "m": mix(bg, p, 0.6), "s": mix(ink, p, 0.7)}

    def rects(self, i, p, leaving):
        """Composition i's blocks, slid toward (leaving) or from (arriving) their nearest edge."""
        w, h = self.w, self.h
        out = []
        for fx0, fy0, fx1, fy1, role in COMPOSITIONS[i % len(COMPOSITIONS)]:
            x0, y0, x1, y1 = fx0 * w, fy0 * h, fx1 * w, fy1 * h
            d = {"l": fx0, "r": 1 - fx1, "t": fy0, "b": 1 - fy1}
            edge = min(d, key=d.get)
            off = (1 - p) if not leaving else p
            dx = {"l": -(x1 + 2), "r": w - x0 + 2, "t": 0, "b": 0}[edge] * off
            dy = {"t": -(y1 + 2), "b": h - y0 + 2, "l": 0, "r": 0}[edge] * off
            out.append((int(x0 + dx), int(y0 + dy), int(x1 + dx), int(y1 + dy), role))
        return out

    def panel(self, i, now):
        # A base beat's ground is tinted toward the accent so the bg-coloured card stands out.
        beat = self.spec["beats"][i]
        ground = mix(beat["panel"], self.spec["accent"], 0.08) if beat["tone"] == "base" \
            else beat["panel"]
        return self.Image.new("RGB", (self.w, self.h), ground)

    def background(self, i, local, now):
        im = self.wiped(i, local, now, horizontal=True)
        d = self.ImageDraw.Draw(im)
        p = ease_out(local / max(self.r.wipe * 1.2, 0.2))
        beats = self.spec["beats"]
        if i and p < 1:
            col = self.colours(beats[i - 1])
            for x0, y0, x1, y1, role in self.rects(i - 1, p, True):
                d.rectangle((x0, y0, x1, y1), fill=col[role])
        col = self.colours(beats[i])
        for x0, y0, x1, y1, role in self.rects(i, p, False):
            d.rectangle((x0, y0, x1, y1), fill=col[role])
        return im


# --- output --------------------------------------------------------------------------

def render_frames(r, total):
    n = int(round(total * FPS))
    for k in range(n):
        yield r.frame(k / FPS)


def stills(r, out_dir, Image):
    beats = r.spec["beats"]
    poster = r.frame(0, settle=0)
    poster.save(os.path.join(out_dir, "poster.png"))
    tiles = [r.frame(0, settle=i) for i in range(len(beats))]
    tw = 480 if r.h <= r.w else 300
    th = int(tw * r.h / r.w)
    cols = min(len(tiles), 4 if r.h > r.w else 3)
    rows = math.ceil(len(tiles) / cols)
    gap = 16
    sheet = Image.new("RGB", (cols * tw + (cols + 1) * gap, rows * th + (rows + 1) * gap),
                      (236, 236, 236))
    for k, tile in enumerate(tiles):
        x = gap + (k % cols) * (tw + gap)
        y = gap + (k // cols) * (th + gap)
        sheet.paste(tile.resize((tw, th), Image.LANCZOS), (x, y))
    sheet.save(os.path.join(out_dir, "storyboard.png"))


def find_ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def encode_mp4(r, path, ffmpeg):
    cmd = [ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{r.w}x{r.h}", "-r", str(FPS), "-i", "-", "-c:v", "libx264",
           "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-profile:v", "high",
           "-movflags", "+faststart", "-tag:v", "avc1", path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for im in render_frames(r, r.spec["total"]):
            proc.stdin.write(im.tobytes())
        proc.stdin.close()
    except BrokenPipeError:
        pass
    err = proc.stderr.read().decode(errors="replace")
    if proc.wait() != 0 or not os.path.isfile(path) or os.path.getsize(path) == 0:
        raise RuntimeError(f"ffmpeg failed: {err.strip()[:400]}")


def encode_gif(r, path):
    step = 2  # 15 fps
    frames = []
    n = int(round(r.spec["total"] * FPS))
    if any(b["image"] for b in r.spec["beats"]):
        # One palette for the whole GIF, built from every settled beat, so a still photo
        # quantizes to the same pixels each frame and the GIF only stores what changed.
        tiles = [r.frame(0, settle=i) for i in range(len(r.spec["beats"]))]
        sheet = r.Image.new("RGB", (r.w, r.h * len(tiles)))
        for k, t in enumerate(tiles):
            sheet.paste(t, (0, k * r.h))
        pal = sheet.quantize(colors=200, method=r.Image.Quantize.MEDIANCUT)
        for k in range(0, n, step):
            frames.append(r.frame(k / FPS).quantize(palette=pal, dither=r.Image.Dither.NONE))
    else:
        for k in range(0, n, step):
            frames.append(r.frame(k / FPS).quantize(colors=64, method=r.Image.Quantize.MEDIANCUT,
                                                    dither=r.Image.Dither.NONE))
    frames[0].save(path, save_all=True, append_images=frames[1:],
                   duration=int(1000 * step / FPS), loop=0, optimize=True, disposal=1)


# --- rung 3: HTML ------------------------------------------------------------------

HTML_LOOK = {
    "soft": {"font": "'Helvetica Neue',Helvetica,Arial,sans-serif", "align": "center",
             "upper": False, "lh": "1.08"},
    "kinetic": {"font": "'Helvetica Neue Condensed Black','Arial Black',Impact,sans-serif",
                "align": "left", "upper": True, "lh": ".96"},
    "editorial": {"font": "Didot,Baskerville,Georgia,'Times New Roman',serif", "align": "center",
                  "upper": False, "lh": "1.18"},
    "blocks": {"font": "'Helvetica Neue',Helvetica,Arial,sans-serif", "align": "left",
               "upper": False, "lh": "1.1"},
}


def html_page(spec, stem):
    import html
    total = spec["total"]
    w, h = spec["w"], spec["h"]
    look, L = spec["look"], HTML_LOOK[spec["look"]]
    enter_s, exit_s = ENTER * spec["f"], EXIT * spec["f"]
    css, body = [], []
    for b in spec["beats"]:
        s, d, n = b["start"], b["dur"], b["n"]
        p0, p1 = (s + b["delay"]) / total * 100, (s + d) / total * 100
        pin = min(p1, (s + b["delay"] + enter_s) / total * 100)
        pout = p1 if b["n"] == len(spec["beats"]) else max(pin, (s + d - exit_s) / total * 100)
        enter = {"rise": "transform:translateY(6%);", "scale": "transform:scale(.86);",
                 "wipe": "clip-path:inset(0 100% 0 0);", "type": "clip-path:inset(0 100% 0 0);",
                 "fade": "", "slide": "transform:translateX(-6%);", "pop": "transform:scale(.6);",
                 "words": "transform:scale(1.15);"}[b["motion"]]
        settled = {"rise": "transform:none;", "scale": "transform:none;",
                   "wipe": "clip-path:inset(0 0 0 0);", "type": "clip-path:inset(0 0 0 0);",
                   "fade": "", "slide": "transform:none;", "pop": "transform:none;",
                   "words": "transform:none;"}[b["motion"]]
        fg = spec["ink"] if look == "blocks" else b["fg"]
        deco = spec["accent"] if b["tone"] == "base" else b["fg"]
        photo = ""
        if b["image"]:
            veil = "rgba(12,12,14,.6)" if look != "blocks" else "rgba(12,12,14,.1)"
            photo = (f"#b{n}{{background:linear-gradient({veil},{veil}),"
                     f"url('{b['html_image']}') center/cover}}")
        css.append(
            f"@keyframes b{n}{{0%,{p0:.3f}%{{opacity:0;{enter}}}"
            f"{pin:.3f}%{{opacity:1;{settled}}}{pout:.3f}%{{opacity:1;{settled}}}"
            f"{p1:.3f}%,100%{{opacity:0;{settled}}}}}"
            f"#b{n}{{background:#{to_hex(b['panel'])};color:#{to_hex(fg)};"
            f"animation:b{n} {total}s linear infinite}}"
            f"#b{n} i{{background:#{to_hex(deco)}}}"
            f"#b{n} .card{{border-color:#{to_hex(deco if b['tone'] == 'base' else spec['ink'])}}}"
            f"#b{n} .frame{{border-color:#{to_hex(mix(b['panel'], b['fg'], 0.3))}}}" + photo)
        if b["n"] == len(spec["beats"]):
            css.append(f"@keyframes b{n}{{0%,{p0:.3f}%{{opacity:0;{enter}}}"
                       f"{pin:.3f}%,99.9%{{opacity:1;{settled}}}100%{{opacity:0}}}}")
        text = b["text"].upper() if L["upper"] else b["text"]
        parts = []
        for word in text.split(" "):
            e = html.escape(word)
            parts.append(f'<em style="color:#{to_hex(spec["accent"])}">{e}</em>'
                         if norm_word(word) in b["emphasis"] else e)
        k = f"<small>{html.escape(b['kicker'])}</small>" if b["kicker"] else ""
        inner = f'{k}<p>{" ".join(parts)}</p>'
        if look == "soft":
            inner += "<i></i>"
        frame = '<span class="frame"></span>' if look == "editorial" else ""
        body.append(f'<div class="beat" id="b{n}">{frame}<div class="{"card" if look == "blocks" else "tx"}">{inner}</div></div>')
    weight = 400 if look == "editorial" else 900 if look == "kinetic" else \
        (700 if spec["weight"] == "bold" else 400)
    big = {"soft": ("11.5cqw", "7.5cqw"), "kinetic": ("17cqw", "10cqw"),
           "editorial": ("9.5cqw", "6cqw"), "blocks": ("9cqw", "5.6cqw")}[look]
    fs = big[0] if h > w else big[1]
    look_css = {
        "soft": "",
        "kinetic": f".tx{{border-left:{'2.2cqw' if h > w else '1.3cqw'} solid currentColor;padding-left:4cqw}}"
                   f".beat .tx{{border-left-color:#{to_hex(spec['accent'])}}}",
        "editorial": ".frame{position:absolute;inset:4.5cqw;border:1px solid}"
                     ".beat small{letter-spacing:.32em}",
        "blocks": f".card{{background:#{to_hex(spec['bg'])};border-left:1.2cqw solid;padding:5cqw;"
                  f"width:auto!important;max-width:78%;margin-left:9%;justify-self:start}}",
    }[look]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(stem)} video</title>
<style>
html,body{{margin:0;height:100%;background:#111}}
body{{display:grid;place-items:center}}
.stage{{position:relative;width:min(100vw,calc(100vh*{w}/{h}));aspect-ratio:{w}/{h};
overflow:hidden;background:#{to_hex(spec['bg'])};container-type:inline-size}}
.beat{{position:absolute;inset:0;display:grid;place-items:center;opacity:0;text-align:{L['align']};
font-family:{L['font']};font-weight:{weight}}}
.beat>div{{width:82%}}
.beat p{{margin:0;font-size:{fs};line-height:{L['lh']}}}
.beat em{{font-style:normal}}
.beat small{{display:block;font-size:{'4.8cqw' if h > w else '3.2cqw'};text-transform:uppercase;
letter-spacing:.06em;margin-bottom:.8em}}
.beat i{{display:block;width:22%;height:{'1.2cqw' if h > w else '.8cqw'};margin:{'4cqw' if h > w else '2.4cqw'} auto 0}}
{look_css}
{''.join(css)}
@media (prefers-reduced-motion:reduce){{.beat{{animation:none!important}}#b{len(spec['beats'])}{{opacity:1}}}}
</style></head><body><div class="stage">{''.join(body)}</div></body></html>
"""


# --- main --------------------------------------------------------------------------

def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    force = None
    if "--format" in argv:
        k = argv.index("--format")
        if k + 1 >= len(argv) or argv[k + 1] not in ("mp4", "gif", "html"):
            fail("--format takes mp4, gif or html")
        force = argv[k + 1]
        argv = argv[:k] + argv[k + 2:]
    if len(argv) != 2:
        fail("usage: build_video.py <beats.json | -> <output-folder>   (see --help)")
    src, out_dir = argv
    raw = sys.stdin.read() if src == "-" else open(src, encoding="utf-8").read()
    spec = load_sheet(raw)

    out_dir = out_dir.rstrip("/\\")
    folder = os.path.basename(out_dir)
    stem = folder[:-6] if folder.endswith("-video") and len(folder) > 6 else folder
    os.makedirs(out_dir, exist_ok=True)

    notes, fmt, font_name, fonts, written, scrims = [], None, None, None, [], {}
    pil = None
    if force != "html":
        try:
            from PIL import Image, ImageDraw, ImageFont
            pil = (Image, ImageDraw, ImageFont)
        except ImportError:
            notes.append("Pillow is not installed, so no frames could be drawn")

    if pil and force in (None, "mp4"):
        ffmpeg = find_ffmpeg()
        if ffmpeg:
            try:
                r = Renderer(spec, 1.0, *pil)
                font_name, fonts, scrims = r.font_name, r.fonts, r.look.scrims
                notes += r.notes
                path = os.path.join(out_dir, f"{stem}.mp4")
                encode_mp4(r, path, ffmpeg)
                stills(r, out_dir, pil[0])
                fmt = "mp4"
                written = [path, os.path.join(out_dir, "poster.png"),
                           os.path.join(out_dir, "storyboard.png")]
            except RuntimeError as e:
                notes.append(str(e))
        else:
            notes.append("ffmpeg is not installed, so no MP4 could be encoded")
        if fmt is None and force == "mp4":
            fail("; ".join(notes))

    if fmt is None and pil and force in (None, "gif"):
        try:
            r = Renderer(spec, 0.5, *pil, still_photos=True)
            font_name, fonts = r.font_name, r.fonts
            notes += [n for n in r.notes if n not in notes]
            path = os.path.join(out_dir, f"{stem}.gif")
            encode_gif(r, path)
            full = Renderer(spec, 1.0, *pil)
            scrims = full.look.scrims
            notes += [n for n in full.notes if n not in notes]
            stills(full, out_dir, pil[0])
            fmt = "gif"
            written = [path, os.path.join(out_dir, "poster.png"),
                       os.path.join(out_dir, "storyboard.png")]
        except RuntimeError as e:
            notes.append(str(e))
            if force == "gif":
                fail("; ".join(notes))

    if fmt is None:
        # The page references its images beside it, so they travel in the folder and the zip.
        copies = []
        for b in spec["beats"]:
            if b["image"]:
                name = f"scene-{b['n']}{os.path.splitext(b['image'])[1].lower()}"
                shutil.copyfile(b["image"], os.path.join(out_dir, name))
                b["html_image"] = name
                copies.append(os.path.join(out_dir, name))
        path = os.path.join(out_dir, f"{stem}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html_page(spec, stem))
        fmt = "html"
        written = [path] + copies
        fonts = {"text": "browser default for the look's font stack"}
        font_name = fonts["text"]

    # Stale outputs of another format from an earlier run would ship in the zip.
    for ext in ("mp4", "gif", "html"):
        other = os.path.join(out_dir, f"{stem}.{ext}")
        if ext != fmt and os.path.isfile(other):
            os.remove(other)
    if fmt == "html":
        for still in ("poster.png", "storyboard.png"):
            p = os.path.join(out_dir, still)
            if os.path.isfile(p):
                os.remove(p)

    zip_path = out_dir + ".zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in written:
            z.write(p, f"{folder}/{os.path.basename(p)}")

    summary = {
        "format": fmt,
        "video": written[0],
        "poster": next((p for p in written if p.endswith("poster.png")), None),
        "storyboard": next((p for p in written if p.endswith("storyboard.png")), None),
        "zip": zip_path,
        "size": f"{spec['w']}x{spec['h']}" if fmt != "gif" else f"{spec['w'] // 2}x{spec['h'] // 2}",
        "aspect": spec["size"],
        "look": spec["look"],
        "pace": spec["pace"],
        "seconds": spec["total"],
        "beats": [dict({"n": b["n"], "seconds": b["dur"], "text": b["text"], "motion": b["motion"]},
                       **({"image": os.path.basename(b["image"]), "scrim": scrims.get(k)}
                          if b["image"] else {}))
                  for k, b in enumerate(spec["beats"])],
        "images": sum(1 for b in spec["beats"] if b["image"]),
        "colors": {"bg": to_hex(spec["bg"]), "ink": to_hex(spec["ink"]),
                   "accent": to_hex(spec["accent"])},
        "font": font_name,
        "fonts": fonts,
        "notes": notes,
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
