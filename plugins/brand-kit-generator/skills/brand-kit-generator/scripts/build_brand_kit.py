#!/usr/bin/env python3
"""Build a brand kit - logo files, a brand board, a one-page brand guide, CSS and
JSON tokens - from one brand spec, so every file agrees with every other.

    python3 build_brand_kit.py - acme-bakery-brand-kit  <<'JSON' ... JSON   (spec on stdin)
    python3 build_brand_kit.py spec.json acme-bakery-brand-kit
    python3 build_brand_kit.py --inspect their-logo.png     (the colors in a supplied logo)
    python3 build_brand_kit.py --help                        (this text)

The second argument is the output folder; it should end in "-brand-kit". It writes:

    acme-bakery-brand-kit/brand-guide.html      one printable page: logo, colors, type, rules
    acme-bakery-brand-kit/brand-board.svg/.png  one image of the whole kit (the preview)
    acme-bakery-brand-kit/logo/                 logo.svg, logo-icon.svg, logo-mono.svg,
                                                logo-reversed.svg, PNGs of each,
                                                favicon-32.png, apple-touch-icon.png
    acme-bakery-brand-kit/colors.css            CSS custom properties
    acme-bakery-brand-kit/brand.json            the spec - edit it and rebuild from it
    acme-bakery-brand-kit.zip                   the folder, zipped

Spec shape:

{
  "name": "Acme Bakery",            the exact name, or null for a nameless kit
  "about": "a sourdough bakery in Portland",     what it does, from the user
  "line": "Slow-fermented bread, baked every morning.",
                                    one sentence for the type specimen, built
                                    only from what the user said
  "colors": {
    "primary": {"hex": "B4532A", "use": "The logo, buttons, headlines"},
    "ink":     {"hex": "2B1D14", "use": "Body text"},
    "surface": {"hex": "FBF6EF", "use": "Page background"},
    "accent":  {"hex": "E8B04B", "use": "Highlights, sale tags"}     optional
  },
  "type": "warm",                   one of the pairings below
  "voice": ["Warm", "Plain", "Local"],                   optional, up to 3 words
  "mark": [                         the logo mark, drawn in a 100 x 100 box,
    {"type": "circle", "cx": 50, "cy": 50, "r": 46, "fill": "primary"},
    {"type": "letter", "char": "A", "cx": 50, "cy": 52, "size": 58,
     "fill": "surface"}
  ],
  "wordmark": {"case": "as-is", "tracking": 0.0, "color": "ink"}   optional
}

  * Colors are given by ROLE. Every shape's "fill"/"stroke" names a role
    (primary, ink, surface, accent) or "none" - never a hex. That is what lets
    the mono and reversed logos, the board, the guide and the CSS all come from
    the same four values.
  * Shapes: circle (cx cy r), ellipse (cx cy rx ry), rect (x y w h, optional r),
    polygon (points [[x,y],...]), line (x1 y1 x2 y2, needs stroke), letter (char
    cx cy size, set in the heading font). Each takes "fill", "stroke", "width". 1 to 6 shapes.
  * Leave "mark" out with a name to get a wordmark-only logo (the icon becomes
    the first letter on a primary square). Without a name, "mark" is required.
  * Instead of "mark", "logo": "/path/to/their-logo.svg|png|jpg" builds the kit
    around a logo the user already has. Run --inspect on it first and take
    colors.primary from the colors it reports (and accent too, when the logo has a
    second color) - the script refuses a primary that is not in the logo.
  * wordmark.case: as-is, upper or lower. tracking: -0.05 to 0.3 em.

Type pairings (heading / body), all free Google Fonts under the OFL. Only the
heading font ships with this script (it sets the logo and the board); the body
font is named in the guide and colors.css and loads from Google Fonts there:

  warm       Fraunces SemiBold / Figtree         food, crafts, local shops, cafes
  elegant    Cormorant Garamond SemiBold / Manrope    beauty, weddings, boutiques, hospitality
  editorial  Instrument Serif / Inter            studios, consultancies, writers, publications
  tech       Space Grotesk Bold / Inter          software, engineering, agencies
  bold       Archivo Black / Work Sans           trades, fitness, construction, events
  friendly   Poppins SemiBold / Newsreader       education, health, community, kids
  modern     Outfit SemiBold / DM Sans           services, real estate, startups
  classic    Young Serif / Figtree               law, finance, restaurants with history

Rules the script enforces, so the spec never has to:

  * ink on surface must reach 4.5:1 (body text). A spec that misses it is an
    error naming both colors - change ink or surface, never primary.
  * Every color pair is graded and only passing pairs are published: 4.5:1+
    body text, 3:1+ large text and graphics, below that decoration only. The
    button pairing (text on primary, or primary-free if nothing passes) is
    chosen here. Do no contrast arithmetic yourself.
  * Text is set in the bundled heading font and written into the SVGs as
    outlines, so the logo looks the same in every app and in every PNG. The
    fonts cover Western European languages; a character outside them is an
    error.
  * Unknown pairing, missing role, unknown shape or role name, a shape outside
    the 100 box: an error naming the field.

PNGs need Pillow. Without it the kit ships SVG, HTML, CSS and JSON only and the
summary says "png": "none" - say there is no image preview; never invent one.
On success a JSON summary is printed to stdout; on any problem the script exits
non-zero with a reason.
"""
import base64
import html
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import zipfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, "fonts")
ROLES = ("primary", "ink", "surface", "accent")
SHAPES = ("circle", "ellipse", "rect", "polygon", "line", "letter")
MAX_SHAPES = 6
SS = 2                      # Pillow supersampling for antialiased shapes

TYPE = {
    "warm":      (("Fraunces", "Fraunces-SemiBold.ttf", 600, "SemiBold", "Georgia, serif"),
                  ("Figtree", None, 400, "Regular", "Helvetica, Arial, sans-serif")),
    "elegant":   (("Cormorant Garamond", "CormorantGaramond-SemiBold.ttf", 600, "SemiBold", "Garamond, Georgia, serif"),
                  ("Manrope", None, 400, "Regular", "Helvetica, Arial, sans-serif")),
    "editorial": (("Instrument Serif", "InstrumentSerif-Regular.ttf", 400, "Regular", "Georgia, serif"),
                  ("Inter", None, 400, "Regular", "Helvetica, Arial, sans-serif")),
    "tech":      (("Space Grotesk", "SpaceGrotesk-Bold.ttf", 700, "Bold", "Helvetica, Arial, sans-serif"),
                  ("Inter", None, 400, "Regular", "Helvetica, Arial, sans-serif")),
    "bold":      (("Archivo Black", "ArchivoBlack-Regular.ttf", 400, "Regular", "'Arial Black', Arial, sans-serif"),
                  ("Work Sans", None, 400, "Regular", "Helvetica, Arial, sans-serif")),
    "friendly":  (("Poppins", "Poppins-SemiBold.ttf", 600, "SemiBold", "Helvetica, Arial, sans-serif"),
                  ("Newsreader", None, 400, "Regular", "Georgia, serif")),
    "modern":    (("Outfit", "Outfit-SemiBold.ttf", 600, "SemiBold", "Helvetica, Arial, sans-serif"),
                  ("DM Sans", None, 400, "Regular", "Helvetica, Arial, sans-serif")),
    "classic":   (("Young Serif", "YoungSerif-Regular.ttf", 400, "Regular", "Georgia, serif"),
                  ("Figtree", None, 400, "Regular", "Helvetica, Arial, sans-serif")),
}


def fail(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


# --- color ---------------------------------------------------------------------

def parse_hex(value, field):
    s = str(value).strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6 or any(c not in "0123456789abcdefABCDEF" for c in s):
        fail(f"{field} must be a hex color like B4532A, got {value!r}")
    return "#" + s.upper()


def rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def luminance(h):
    def ch(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(c) for c in rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def grade(ratio):
    if ratio >= 4.5:
        return "body text"
    if ratio >= 3:
        return "large text and graphics"
    return "decoration only"


def distance(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(rgb(a), rgb(b))))


# --- fonts: a small TrueType reader (glyf outlines, cmap, hmtx, kern format 0) ----

class Font:
    def __init__(self, path):
        with open(path, "rb") as f:
            self.data = d = f.read()
        num = struct.unpack(">H", d[4:6])[0]
        self.tables = {}
        for i in range(num):
            tag, _, off, length = struct.unpack(">4sIII", d[12 + 16 * i:28 + 16 * i])
            self.tables[tag.decode("latin-1")] = (off, length)
        head = self.tables["head"][0]
        self.upem = struct.unpack(">H", d[head + 18:head + 20])[0]
        self.loca_long = struct.unpack(">h", d[head + 50:head + 52])[0] == 1
        hhea = self.tables["hhea"][0]
        self.ascent, self.descent = struct.unpack(">hh", d[hhea + 4:hhea + 8])
        self.n_hmetrics = struct.unpack(">H", d[hhea + 34:hhea + 36])[0]
        maxp = self.tables["maxp"][0]
        self.num_glyphs = struct.unpack(">H", d[maxp + 4:maxp + 6])[0]
        os2 = self.tables.get("OS/2")
        self.cap = None
        if os2:
            ver = struct.unpack(">H", d[os2[0]:os2[0] + 2])[0]
            if ver >= 2:
                self.cap = struct.unpack(">h", d[os2[0] + 88:os2[0] + 90])[0] or None
        self.cmap = self._cmap()
        self.kern = self._kern()
        self._contours = {}
        if not self.cap:
            g = self.cmap.get(ord("H"))
            self.cap = self.bbox(g)[3] if g is not None else int(self.upem * 0.7)

    def _cmap(self):
        d = self.data
        base = self.tables["cmap"][0]
        n = struct.unpack(">H", d[base + 2:base + 4])[0]
        best = None
        for i in range(n):
            pid, eid, off = struct.unpack(">HHI", d[base + 4 + 8 * i:base + 12 + 8 * i])
            fmt = struct.unpack(">H", d[base + off:base + off + 2])[0]
            if fmt == 12 or (fmt == 4 and best is None):
                best = (fmt, base + off)
        fmt, o = best
        m = {}
        if fmt == 4:
            segx2 = struct.unpack(">H", d[o + 6:o + 8])[0]
            ends = o + 14
            starts = ends + segx2 + 2
            deltas = starts + segx2
            ranges = deltas + segx2
            for s in range(segx2 // 2):
                end, = struct.unpack(">H", d[ends + 2 * s:ends + 2 * s + 2])
                start, = struct.unpack(">H", d[starts + 2 * s:starts + 2 * s + 2])
                delta, = struct.unpack(">h", d[deltas + 2 * s:deltas + 2 * s + 2])
                ro, = struct.unpack(">H", d[ranges + 2 * s:ranges + 2 * s + 2])
                for c in range(start, end + 1):
                    if c == 0xFFFF:
                        continue
                    if ro == 0:
                        g = (c + delta) & 0xFFFF
                    else:
                        a = ranges + 2 * s + ro + 2 * (c - start)
                        g, = struct.unpack(">H", d[a:a + 2])
                        if g:
                            g = (g + delta) & 0xFFFF
                    if g:
                        m[c] = g
        else:
            n_groups = struct.unpack(">I", d[o + 12:o + 16])[0]
            for i in range(n_groups):
                s, e, g = struct.unpack(">III", d[o + 16 + 12 * i:o + 28 + 12 * i])
                for c in range(s, e + 1):
                    m[c] = g + c - s
        return m

    def _kern(self):
        k = {}
        t = self.tables.get("kern")
        if not t:
            return k
        d, o = self.data, t[0]
        n_tables = struct.unpack(">H", d[o + 2:o + 4])[0]
        o += 4
        for _ in range(n_tables):
            length, cov = struct.unpack(">HH", d[o + 2:o + 6])
            if cov >> 8 == 0:
                n_pairs = struct.unpack(">H", d[o + 6:o + 8])[0]
                p = o + 14
                for i in range(n_pairs):
                    l, r, v = struct.unpack(">HHh", d[p + 6 * i:p + 6 * i + 6])
                    k[(l, r)] = v
            o += length
        return k

    def advance(self, g):
        d = self.data
        h = self.tables["hmtx"][0]
        i = min(g, self.n_hmetrics - 1)
        return struct.unpack(">H", d[h + 4 * i:h + 4 * i + 2])[0]

    def _glyph_range(self, g):
        d = self.data
        loca = self.tables["loca"][0]
        if self.loca_long:
            a, b = struct.unpack(">II", d[loca + 4 * g:loca + 4 * g + 8])
        else:
            a, b = (x * 2 for x in struct.unpack(">HH", d[loca + 2 * g:loca + 2 * g + 4]))
        return self.tables["glyf"][0] + a, b - a

    def contours(self, g):
        """List of contours, each a list of (x, y, on_curve), in font units."""
        if g in self._contours:
            return self._contours[g]
        d = self.data
        o, length = self._glyph_range(g)
        out = []
        if length:
            nc = struct.unpack(">h", d[o:o + 2])[0]
            if nc >= 0:
                out = self._simple(o, nc)
            else:
                out = self._composite(o + 10)
        self._contours[g] = out
        return out

    def _simple(self, o, nc):
        d = self.data
        p = o + 10
        ends = struct.unpack(">%dH" % nc, d[p:p + 2 * nc])
        p += 2 * nc
        ilen = struct.unpack(">H", d[p:p + 2])[0]
        p += 2 + ilen
        n = ends[-1] + 1 if nc else 0
        flags = []
        while len(flags) < n:
            f = d[p]
            p += 1
            flags.append(f)
            if f & 8:
                r = d[p]
                p += 1
                flags.extend([f] * r)
        xs, ys = [], []
        for coords, short, same in ((xs, 2, 16), (ys, 4, 32)):
            v = 0
            for f in flags:
                if f & short:
                    dv = d[p]
                    p += 1
                    v += dv if f & same else -dv
                elif not f & same:
                    v += struct.unpack(">h", d[p:p + 2])[0]
                    p += 2
                coords.append(v)
        out, start = [], 0
        for e in ends:
            out.append([(xs[i], ys[i], bool(flags[i] & 1)) for i in range(start, e + 1)])
            start = e + 1
        return out

    def _composite(self, p):
        d = self.data
        out = []
        while True:
            flags, gi = struct.unpack(">HH", d[p:p + 4])
            p += 4
            if flags & 1:
                a1, a2 = struct.unpack(">hh", d[p:p + 4])
                p += 4
            else:
                a1, a2 = struct.unpack(">bb", d[p:p + 2])
                p += 2
            dx, dy = (a1, a2) if flags & 2 else (0, 0)
            xx, xy, yx, yy = 1.0, 0.0, 0.0, 1.0
            if flags & 8:
                xx = yy = struct.unpack(">h", d[p:p + 2])[0] / 16384
                p += 2
            elif flags & 0x40:
                xx, yy = (v / 16384 for v in struct.unpack(">hh", d[p:p + 4]))
                p += 4
            elif flags & 0x80:
                xx, xy, yx, yy = (v / 16384 for v in struct.unpack(">hhhh", d[p:p + 8]))
                p += 8
            for c in self.contours(gi):
                out.append([(x * xx + y * yx + dx, x * xy + y * yy + dy, on) for x, y, on in c])
            if not flags & 0x20:
                break
        return out

    def bbox(self, g):
        pts = [(x, y) for c in self.contours(g) for x, y, _ in c]
        if not pts:
            return (0, 0, 0, 0)
        xs, ys = zip(*pts)
        return (min(xs), min(ys), max(xs), max(ys))

    def glyph(self, ch):
        return self.cmap.get(ord(ch))

    def layout(self, text, size, tracking=0.0):
        """[(char, glyph, x_offset)], width - offsets in px for a font size in px."""
        s = size / self.upem
        x, out, prev = 0.0, [], None
        for ch in text:
            g = self.glyph(ch)
            if prev is not None:
                x += self.kern.get((prev, g), 0) * s
            out.append((ch, g, x))
            x += self.advance(g) * s + tracking * size
            prev = g
        width = x - (tracking * size if text else 0)
        return out, width

    def path(self, g, ox, oy, s):
        """SVG path data for one glyph at origin (ox, oy baseline), scale s px/unit."""
        parts = []
        for c in self.contours(g):
            if not c:
                continue
            pts = [(ox + x * s, oy - y * s, on) for x, y, on in c]
            n = len(pts)
            start = next((i for i, p in enumerate(pts) if p[2]), None)
            if start is None:
                a, b = pts[0], pts[1]
                pts.insert(0, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, True))
                start, n = 0, n + 1
            pts = pts[start:] + pts[:start]
            seg = [f"M{pts[0][0]:.2f} {pts[0][1]:.2f}"]
            i = 1
            while i <= n:
                p = pts[i % n]
                if p[2]:
                    seg.append(f"L{p[0]:.2f} {p[1]:.2f}")
                    i += 1
                else:
                    nxt = pts[(i + 1) % n]
                    if nxt[2]:
                        end = nxt
                        i += 2
                    else:
                        end = ((p[0] + nxt[0]) / 2, (p[1] + nxt[1]) / 2, True)
                        i += 1
                    seg.append(f"Q{p[0]:.2f} {p[1]:.2f} {end[0]:.2f} {end[1]:.2f}")
            seg.append("Z")
            parts.append("".join(seg))
        return "".join(parts)


_FONTS = {}


def font(file):
    if file not in _FONTS:
        _FONTS[file] = Font(os.path.join(FONT_DIR, file))
    return _FONTS[file]


def check_glyphs(text, f, field, family):
    missing = sorted({ch for ch in text if f.glyph(ch) is None})
    if missing:
        fail(f"{field} contains {''.join(missing)!r}, which {family} does not cover (the bundled "
             f"fonts cover Western European languages only) - check the spelling, or this kit cannot set it")


# --- the display list ----------------------------------------------------------
# Every drawable is a dict in absolute coordinates with resolved hex colors; the
# SVG and Pillow backends each draw the same list.

def text_item(f, file, text, size, x, baseline, fill, tracking=0.0):
    glyphs, width = f.layout(text, size, tracking)
    return {"k": "text", "file": file, "size": size, "x": x, "y": baseline, "fill": fill,
            "glyphs": [(ch, g, dx) for ch, g, dx in glyphs], "w": width}


def item_bbox(it):
    sw = it.get("sw", 0) / 2 if it.get("stroke") else 0
    k = it["k"]
    if k == "circle":
        r = it["r"] + sw
        return (it["cx"] - r, it["cy"] - r, it["cx"] + r, it["cy"] + r)
    if k == "ellipse":
        return (it["cx"] - it["rx"] - sw, it["cy"] - it["ry"] - sw, it["cx"] + it["rx"] + sw, it["cy"] + it["ry"] + sw)
    if k == "rect":
        return (it["x"] - sw, it["y"] - sw, it["x"] + it["w"] + sw, it["y"] + it["h"] + sw)
    if k == "poly":
        xs, ys = zip(*it["points"])
        return (min(xs) - sw, min(ys) - sw, max(xs) + sw, max(ys) + sw)
    if k == "line":
        sw = it["sw"] / 2
        return (min(it["x1"], it["x2"]) - sw, min(it["y1"], it["y2"]) - sw, max(it["x1"], it["x2"]) + sw, max(it["y1"], it["y2"]) + sw)
    if k == "text":
        f = font(it["file"])
        s = it["size"] / f.upem
        boxes = []
        for _, g, dx in it["glyphs"]:
            b = f.bbox(g)
            if b != (0, 0, 0, 0):
                boxes.append((it["x"] + dx + b[0] * s, it["y"] - b[3] * s, it["x"] + dx + b[2] * s, it["y"] - b[1] * s))
        if not boxes:
            return (it["x"], it["y"], it["x"], it["y"])
        return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
    if k == "image":
        return (it["x"], it["y"], it["x"] + it["w"], it["y"] + it["h"])
    raise ValueError(k)


def union(boxes):
    boxes = list(boxes)
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def transform(it, s, tx, ty):
    """Scale by s about the origin, then translate."""
    it = dict(it)
    k = it["k"]
    if "sw" in it:
        it["sw"] = it["sw"] * s
    if k in ("circle", "ellipse"):
        it["cx"], it["cy"] = it["cx"] * s + tx, it["cy"] * s + ty
        for key in ("r", "rx", "ry"):
            if key in it:
                it[key] *= s
    elif k in ("rect", "image"):
        it["x"], it["y"], it["w"], it["h"] = it["x"] * s + tx, it["y"] * s + ty, it["w"] * s, it["h"] * s
        if "r" in it:
            it["r"] *= s
    elif k == "poly":
        it["points"] = [(x * s + tx, y * s + ty) for x, y in it["points"]]
    elif k == "line":
        it["x1"], it["y1"], it["x2"], it["y2"] = it["x1"] * s + tx, it["y1"] * s + ty, it["x2"] * s + tx, it["y2"] * s + ty
    elif k == "text":
        it["x"], it["y"], it["size"] = it["x"] * s + tx, it["y"] * s + ty, it["size"] * s
        it["glyphs"] = [(ch, g, dx * s) for ch, g, dx in it["glyphs"]]
        it["w"] *= s
    return it


def place(items, box, align="center", valign="center"):
    """Fit a group of items into box (x0, y0, x1, y1), keeping proportions."""
    b = union(item_bbox(i) for i in items)
    w, h = b[2] - b[0], b[3] - b[1]
    s = min((box[2] - box[0]) / w, (box[3] - box[1]) / h)
    tx = box[0] - b[0] * s
    if align == "center":
        tx += ((box[2] - box[0]) - w * s) / 2
    ty = box[1] - b[1] * s
    if valign == "center":
        ty += ((box[3] - box[1]) - h * s) / 2
    return [transform(i, s, tx, ty) for i in items]


def n(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


def paint_attrs(it):
    a = f' fill="{it["fill"]}"' if it.get("fill") else ' fill="none"'
    if it.get("stroke"):
        a += f' stroke="{it["stroke"]}" stroke-width="{n(it["sw"])}" stroke-linejoin="round"'
    return a


def svg_items(items):
    out = []
    for it in items:
        k = it["k"]
        if k == "circle":
            out.append(f'<circle cx="{n(it["cx"])}" cy="{n(it["cy"])}" r="{n(it["r"])}"{paint_attrs(it)}/>')
        elif k == "ellipse":
            out.append(f'<ellipse cx="{n(it["cx"])}" cy="{n(it["cy"])}" rx="{n(it["rx"])}" ry="{n(it["ry"])}"{paint_attrs(it)}/>')
        elif k == "rect":
            r = f' rx="{n(it["r"])}"' if it.get("r") else ""
            out.append(f'<rect x="{n(it["x"])}" y="{n(it["y"])}" width="{n(it["w"])}" height="{n(it["h"])}"{r}{paint_attrs(it)}/>')
        elif k == "poly":
            pts = " ".join(f"{n(x)},{n(y)}" for x, y in it["points"])
            out.append(f'<polygon points="{pts}"{paint_attrs(it)}/>')
        elif k == "line":
            out.append(f'<line x1="{n(it["x1"])}" y1="{n(it["y1"])}" x2="{n(it["x2"])}" y2="{n(it["y2"])}" '
                       f'stroke="{it["stroke"]}" stroke-width="{n(it["sw"])}"/>')
        elif k == "text":
            f = font(it["file"])
            s = it["size"] / f.upem
            d = "".join(f.path(g, it["x"] + dx, it["y"], s) for _, g, dx in it["glyphs"])
            if d:
                out.append(f'<path d="{d}" fill="{it["fill"]}"/>')
        elif k == "image":
            out.append(f'<image href="{it["href"]}" x="{n(it["x"])}" y="{n(it["y"])}" width="{n(it["w"])}" '
                       f'height="{n(it["h"])}" preserveAspectRatio="xMidYMid meet"/>')
    return out


def svg_doc(items, box, title, pad=0.0):
    x0, y0, x1, y1 = box
    x0, y0, x1, y1 = x0 - pad, y0 - pad, x1 + pad, y1 + pad
    body = "\n  ".join(svg_items(items))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{n(x0)} {n(y0)} {n(x1 - x0)} {n(y1 - y0)}" '
            f'role="img">\n  <title>{html.escape(title)}</title>\n  {body}\n</svg>\n')


# --- Pillow backend --------------------------------------------------------------

def have_pillow():
    try:
        from PIL import Image, ImageDraw, ImageFont  # noqa: F401
        return True
    except Exception:
        return False


def render_png(items, box, out_w, path, bg=None, pad=0.0):
    from PIL import Image, ImageDraw, ImageFont
    x0, y0, x1, y1 = box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad
    s = out_w / (x1 - x0)
    W, H = round((x1 - x0) * s), round((y1 - y0) * s)
    k = s * SS
    img = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0) if bg is None else rgb(bg) + (255,))
    dr = ImageDraw.Draw(img)

    def P(x, y):
        return ((x - x0) * k, (y - y0) * k)

    fonts = {}
    for it in items:
        kind = it["k"]
        fill = rgb(it["fill"]) + (255,) if it.get("fill") else None
        stroke = rgb(it["stroke"]) + (255,) if it.get("stroke") else None
        sw = it.get("sw", 0) * k
        if kind in ("circle", "ellipse"):
            rx, ry = (it["r"], it["r"]) if kind == "circle" else (it["rx"], it["ry"])
            (ax, ay), (bx, by) = P(it["cx"] - rx, it["cy"] - ry), P(it["cx"] + rx, it["cy"] + ry)
            if fill:
                dr.ellipse((ax, ay, bx, by), fill=fill)
            if stroke:
                h = sw / 2
                dr.ellipse((ax - h, ay - h, bx + h, by + h), outline=stroke, width=max(1, round(sw)))
        elif kind == "rect":
            (ax, ay), (bx, by) = P(it["x"], it["y"]), P(it["x"] + it["w"], it["y"] + it["h"])
            r = it.get("r", 0) * k
            if fill:
                dr.rounded_rectangle((ax, ay, bx, by), radius=r, fill=fill)
            if stroke:
                h = sw / 2
                dr.rounded_rectangle((ax - h, ay - h, bx + h, by + h), radius=r + h, outline=stroke, width=max(1, round(sw)))
        elif kind == "poly":
            pts = [P(x, y) for x, y in it["points"]]
            if fill:
                dr.polygon(pts, fill=fill)
            if stroke:
                dr.line(pts + [pts[0]], fill=stroke, width=max(1, round(sw)), joint="curve")
        elif kind == "line":
            dr.line([P(it["x1"], it["y1"]), P(it["x2"], it["y2"])], fill=stroke, width=max(1, round(sw)))
        elif kind == "text":
            size = max(1, round(it["size"] * k))
            key = (it["file"], size)
            if key not in fonts:
                fonts[key] = ImageFont.truetype(os.path.join(FONT_DIR, it["file"]), size)
            for ch, _, dx in it["glyphs"]:
                if ch.strip():
                    dr.text(P(it["x"] + dx, it["y"]), ch, font=fonts[key], fill=fill, anchor="ls")
        elif kind == "image":
            src = it["pil"].convert("RGBA")
            (ax, ay), (bx, by) = P(it["x"], it["y"]), P(it["x"] + it["w"], it["y"] + it["h"])
            bw, bh = bx - ax, by - ay
            sc = min(bw / src.width, bh / src.height)
            im = src.resize((max(1, round(src.width * sc)), max(1, round(src.height * sc))), Image.LANCZOS)
            img.alpha_composite(im, (round(ax + (bw - im.width) / 2), round(ay + (bh - im.height) / 2)))
    img = img.resize((W, H), Image.LANCZOS)
    img.save(path)
    return img


# --- the spec --------------------------------------------------------------------

def load_spec(raw, src_name):
    try:
        spec = json.loads(raw)
    except ValueError as e:
        fail(f"{src_name} is not valid JSON: {e}")
    if not isinstance(spec, dict):
        fail("the spec must be a JSON object")
    spec.pop("computed", None)
    name = spec.get("name")
    if name is not None:
        name = " ".join(str(name).split())
        if not name:
            name = None
        elif len(name) > 40:
            fail(f"name is {len(name)} characters; the lockup takes at most 40 - use the name people say")
    spec["name"] = name
    for key in ("about", "line"):
        v = " ".join(str(spec.get(key) or "").split())
        if not v:
            fail(f"{key} is required - " + ("what the business does, from the user" if key == "about"
                                            else "one sentence for the type specimen, from what the user said"))
        if key == "line" and len(v) > 110:
            fail(f"line is {len(v)} characters; keep it to one sentence under 110")
        spec[key] = v
    if spec.get("type") not in TYPE:
        fail(f"type must be one of {', '.join(TYPE)}, got {spec.get('type')!r}")
    colors = spec.get("colors")
    if not isinstance(colors, dict):
        fail("colors is required: primary, ink, surface and optionally accent")
    for role in list(colors):
        if role not in ROLES:
            fail(f"colors.{role} is not a role - use primary, ink, surface, accent")
    for role in ROLES:
        c = colors.get(role)
        if c is None:
            if role == "accent":
                continue
            fail(f"colors.{role} is missing")
        if isinstance(c, str):
            c = {"hex": c}
        c["hex"] = parse_hex(c.get("hex"), f"colors.{role}.hex")
        c["use"] = " ".join(str(c.get("use") or "").split())
        if not c["use"]:
            fail(f"colors.{role}.use is missing - one line on where this color goes")
        colors[role] = c
    if "accent" in colors and distance(colors["accent"]["hex"], colors["primary"]["hex"]) < 40:
        fail("colors.accent is nearly the same as primary - leave accent out instead")
    ink, surface = colors["ink"]["hex"], colors["surface"]["hex"]
    r = contrast(ink, surface)
    if r < 4.5:
        fail(f"colors.ink {ink} on colors.surface {surface} is {r:.2f}:1; body text needs 4.5:1 - "
             f"darken ink or lighten surface (never change primary to fix this)")
    voice = spec.get("voice") or []
    if not isinstance(voice, list) or len(voice) > 3:
        fail("voice is a list of up to 3 words")
    spec["voice"] = [" ".join(str(v).split()) for v in voice if str(v).strip()]
    wm = spec.get("wordmark") or {}
    case = wm.get("case", "as-is")
    if case not in ("as-is", "upper", "lower"):
        fail("wordmark.case must be as-is, upper or lower")
    tracking = float(wm.get("tracking", 0.0))
    if not -0.05 <= tracking <= 0.3:
        fail("wordmark.tracking must be between -0.05 and 0.3 (em)")
    color = wm.get("color", "ink")
    if color not in colors:
        fail(f"wordmark.color must be one of the roles in colors, got {color!r}")
    spec["wordmark"] = {"case": case, "tracking": tracking, "color": color}
    if spec.get("logo") and spec.get("mark"):
        fail("give either mark (draw a logo) or logo (the user's own file), not both")
    if not spec.get("logo") and not spec.get("mark") and not name:
        fail("a nameless kit needs a mark (or the user's own logo) - there is nothing else to draw")
    if spec.get("mark"):
        check_mark(spec["mark"], colors)
    return spec


def check_mark(mark, colors):
    if not isinstance(mark, list) or not 1 <= len(mark) <= MAX_SHAPES:
        fail(f"mark is a list of 1 to {MAX_SHAPES} shapes")
    for i, sh in enumerate(mark):
        where = f"mark[{i}]"
        t = sh.get("type")
        if t not in SHAPES:
            fail(f"{where}.type must be one of {', '.join(SHAPES)}, got {t!r}")
        for key in ("fill", "stroke"):
            v = sh.get(key)
            if v not in (None, "none") and v not in colors:
                fail(f"{where}.{key} must name a role in colors (or none), got {v!r} - never a hex")
        if t == "line" and sh.get("stroke") in (None, "none"):
            fail(f"{where} is a line and needs a stroke")
        if sh.get("stroke") not in (None, "none") and not sh.get("width"):
            fail(f"{where} has a stroke and needs a width")
        if sh.get("fill") in (None, "none") and sh.get("stroke") in (None, "none"):
            fail(f"{where} has neither fill nor stroke, so it draws nothing")
        need = {"circle": ("cx", "cy", "r"), "ellipse": ("cx", "cy", "rx", "ry"), "rect": ("x", "y", "w", "h"),
                "polygon": ("points",), "line": ("x1", "y1", "x2", "y2"), "letter": ("char", "cx", "cy", "size")}[t]
        for key in need:
            if key not in sh:
                fail(f"{where} ({t}) needs {', '.join(need)} - {key} is missing")
        if t == "letter":
            if len(str(sh["char"])) not in (1, 2, 3):
                fail(f"{where}.char is 1 to 3 characters")
            if sh.get("font", "heading") != "heading":
                fail(f"{where}.font must be heading - only the heading font is bundled, so letters in a mark use it")
        if t == "polygon" and (not isinstance(sh["points"], list) or len(sh["points"]) < 3):
            fail(f"{where}.points needs at least 3 [x, y] pairs")


def role_map(colors, variant):
    """Role -> hex for a logo variant."""
    p, ink, surf = colors["primary"]["hex"], colors["ink"]["hex"], colors["surface"]["hex"]
    acc = colors.get("accent", {}).get("hex")
    if variant == "full":
        m = {"primary": p, "ink": ink, "surface": surf}
        if acc:
            m["accent"] = acc
    elif variant == "mono":
        m = {"primary": ink, "ink": ink, "surface": surf, "accent": ink}
    else:  # reversed: drawn on ink. A primary that holds up on ink stays, and so do the
        # surface-colored details drawn on it; a primary that does not turns light, and
        # its surface details become knockouts in ink.
        keep = contrast(p, ink) >= 3
        m = {"primary": p if keep else surf, "ink": surf, "surface": surf if keep else ink,
             "accent": acc if acc and contrast(acc, ink) >= 3 else surf}
    return m


def mark_items(spec, cmap):
    head = TYPE[spec["type"]][0]
    body = TYPE[spec["type"]][1]
    items = []
    for i, sh in enumerate(spec["mark"]):
        fill = cmap.get(sh.get("fill")) if sh.get("fill") not in (None, "none") else None
        stroke = cmap.get(sh.get("stroke")) if sh.get("stroke") not in (None, "none") else None
        sw = float(sh.get("width") or 0)
        t = sh["type"]
        base = {"fill": fill, "stroke": stroke, "sw": sw}
        if t == "circle":
            items.append(dict(base, k="circle", cx=sh["cx"], cy=sh["cy"], r=sh["r"]))
        elif t == "ellipse":
            items.append(dict(base, k="ellipse", cx=sh["cx"], cy=sh["cy"], rx=sh["rx"], ry=sh["ry"]))
        elif t == "rect":
            items.append(dict(base, k="rect", x=sh["x"], y=sh["y"], w=sh["w"], h=sh["h"], r=sh.get("r", 0)))
        elif t == "polygon":
            items.append(dict(base, k="poly", points=[tuple(p) for p in sh["points"]]))
        elif t == "line":
            items.append(dict(base, k="line", fill=None, x1=sh["x1"], y1=sh["y1"], x2=sh["x2"], y2=sh["y2"]))
        else:
            fam, file = head[:2]
            f = font(file)
            check_glyphs(sh["char"], f, f"mark[{i}].char", fam)
            it = text_item(f, file, str(sh["char"]), sh["size"], 0, 0, fill or stroke)
            b = item_bbox(it)
            items.append(transform(it, 1, sh["cx"] - (b[0] + b[2]) / 2, sh["cy"] - (b[1] + b[3]) / 2))
        b = item_bbox(items[-1])
        if b[0] < -2 or b[1] < -2 or b[2] > 102 or b[3] > 102:
            fail(f"mark[{i}] reaches outside the 100 x 100 box ({', '.join(n(v) for v in b)}) - pull it in")
    return items


def wordmark_text(spec):
    name, case = spec["name"], spec["wordmark"]["case"]
    return name.upper() if case == "upper" else name.lower() if case == "lower" else name


def lockup_items(spec, cmap, mark):
    """Mark (scaled to height 100) beside the wordmark, cap height = half the mark."""
    fam, file = TYPE[spec["type"]][0][:2]
    f = font(file)
    text = wordmark_text(spec)
    check_glyphs(text, f, "name", fam)
    if mark:
        mb = union(item_bbox(i) for i in mark)
        s = 100 / (mb[3] - mb[1])
        m = [transform(i, s, -mb[0] * s, -mb[1] * s) for i in mark]
        mw = (mb[2] - mb[0]) * s
        cap = 50.0
        size = cap * f.upem / f.cap
        baseline = 50 + cap / 2
        word = text_item(f, file, text, size, mw + 30, baseline, cmap[spec["wordmark"]["color"]], spec["wordmark"]["tracking"])
        b = item_bbox(word)
        word = transform(word, 1, mw + 30 - b[0], 0)
        return m + [word]
    size = 100 * f.upem / f.cap
    return [text_item(f, file, text, size, 0, 100, cmap[spec["wordmark"]["color"]], spec["wordmark"]["tracking"])]


def monogram_items(spec, colors):
    """Icon for a wordmark-only logo: the first letter on a primary rounded square."""
    fam, file = TYPE[spec["type"]][0][:2]
    f = font(file)
    p = colors["primary"]["hex"]
    on = max((colors["surface"]["hex"], colors["ink"]["hex"]), key=lambda c: contrast(c, p))
    letter = wordmark_text(spec).strip()[0]
    sq = {"k": "rect", "x": 0, "y": 0, "w": 100, "h": 100, "r": 18, "fill": p, "stroke": None, "sw": 0}
    it = text_item(f, file, letter, 64, 0, 0, on)
    b = item_bbox(it)
    return [sq, transform(it, 1, 50 - (b[0] + b[2]) / 2, 50 - (b[1] + b[3]) / 2)]


# --- supplied logos ---------------------------------------------------------------

NAMED = {"white": "#FFFFFF", "black": "#000000"}
COLOR_RE = re.compile(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b|rgb\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)", re.I)
PAINT_RE = re.compile(r'((?:fill|stroke|stop-color)\s*[:=]\s*["\']?\s*)(#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b|'
                      r'rgb\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)|white\b|black\b)', re.I)


def norm_color(c):
    c = c.strip().lower()
    if c in NAMED:
        return NAMED[c]
    if c.startswith("rgb"):
        r, g, b = (int(v) for v in re.findall(r"\d+", c))
        return "#%02X%02X%02X" % (r, g, b)
    return parse_hex(c, "logo color")


def inspect_svg(text):
    uses = {}
    for m in PAINT_RE.finditer(text):
        h = norm_color(m.group(2))
        uses[h] = uses.get(h, 0) + 1
    blockers = [t for t in ("linearGradient", "radialGradient", "<pattern", "<image", "<filter", "<mask") if t in text]
    if not uses and not blockers:
        uses["#000000"] = 1   # SVG's default fill
    total = sum(uses.values()) or 1
    colors = [{"hex": h, "share": round(c / total, 2)} for h, c in sorted(uses.items(), key=lambda kv: -kv[1])]
    reason = None
    if blockers:
        reason = "uses " + ", ".join(b.strip("<") for b in blockers)
    elif len(uses) > 4:
        reason = f"has {len(uses)} colors"
    elif "currentColor" in text or "class=" in text and "<style" in text:
        reason = "styles colors through CSS classes" if "<style" in text else None
    return {"format": "svg", "colors": colors, "recolorable": reason is None, "why_not": reason}


def png_pixels(data):
    """Decode an 8/16-bit non-interlaced PNG with the standard library: (w, h, [(r,g,b,a)])."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    p, idat, plte, trns = 8, b"", None, None
    while p < len(data):
        length, typ = struct.unpack(">I4s", data[p:p + 8])
        chunk = data[p + 8:p + 8 + length]
        if typ == b"IHDR":
            w, h, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", chunk)
        elif typ == b"PLTE":
            plte = chunk
        elif typ == b"tRNS":
            trns = chunk
        elif typ == b"IDAT":
            idat += chunk
        p += 12 + length
    if interlace or depth not in (8, 16) and not (ctype == 3 and depth == 8):
        return None
    chans = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    bpp = chans * depth // 8
    raw = zlib.decompress(idat)
    stride = w * bpp
    prev = bytearray(stride)
    pixels = []
    o = 0
    for _ in range(h):
        ft = raw[o]
        line = bytearray(raw[o + 1:o + 1 + stride])
        o += 1 + stride
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if ft == 1:
                line[i] = (line[i] + a) & 255
            elif ft == 2:
                line[i] = (line[i] + b) & 255
            elif ft == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif ft == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if pa <= pb and pa <= pc else b if pb <= pc else c
                line[i] = (line[i] + pr) & 255
        prev = line
        step = depth // 8
        for x in range(w):
            px = [line[x * bpp + k * step] for k in range(chans)]
            if ctype == 0:
                pixels.append((px[0], px[0], px[0], 255))
            elif ctype == 2:
                pixels.append((px[0], px[1], px[2], 255))
            elif ctype == 3:
                i = px[0]
                al = trns[i] if trns and i < len(trns) else 255
                pixels.append((plte[3 * i], plte[3 * i + 1], plte[3 * i + 2], al))
            elif ctype == 4:
                pixels.append((px[0], px[0], px[0], px[1]))
            else:
                pixels.append(tuple(px))
    return w, h, pixels


def raster_colors(pixels, w, h):
    """Flat colors in a raster logo, largest first, with a solid background left out."""
    corners = [pixels[0], pixels[w - 1], pixels[(h - 1) * w], pixels[h * w - 1]]
    bg = None
    if all(c[3] >= 200 for c in corners) and max(math.dist(corners[0][:3], c[:3]) for c in corners) < 30:
        bg = corners[0][:3]
    counts = {}
    step = max(1, len(pixels) // 250000)
    for px in pixels[::step]:
        if px[3] < 200 or (bg and math.dist(bg, px[:3]) < 30):
            continue
        counts[px[:3]] = counts.get(px[:3], 0) + 1
    total = sum(counts.values()) or 1
    clusters = []
    for c, k in sorted(counts.items(), key=lambda kv: -kv[1]):
        for cl in clusters:
            if math.dist(cl["rgb"], c) < 30:
                cl["n"] += k
                break
        else:
            clusters.append({"rgb": c, "n": k})
    clusters.sort(key=lambda cl: -cl["n"])
    out = [{"hex": "#%02X%02X%02X" % cl["rgb"], "share": round(cl["n"] / total, 2)}
           for cl in clusters if cl["n"] / total >= 0.02][:6]
    flat = sum(o["share"] for o in out) >= 0.85
    return out, flat, ("#%02X%02X%02X" % bg if bg else None)


def inspect_logo(path):
    if not os.path.isfile(path):
        fail(f"logo file not found: {path}")
    ext = os.path.splitext(path)[1].lower()
    with open(path, "rb") as f:
        data = f.read()
    if ext == ".svg" or data.lstrip()[:5] in (b"<?xml", b"<svg ") or b"<svg" in data[:500]:
        info = inspect_svg(data.decode("utf-8", "replace"))
    else:
        dec = png_pixels(data)
        pixels = None
        if dec:
            w, h, pixels = dec
        elif have_pillow():
            from PIL import Image
            im = Image.open(path).convert("RGBA")
            im.thumbnail((600, 600))
            w, h, pixels = im.width, im.height, list(im.getdata())
        if pixels is None:
            return {"format": ext.lstrip(".") or "image", "colors": [], "recolorable": False,
                    "why_not": "this image cannot be read without Pillow - ask the user for their brand hex codes"}
        colors, flat, bg = raster_colors(pixels, w, h)
        info = {"format": "png" if data[:4] == b"\x89PNG" else ext.lstrip("."), "colors": colors,
                "recolorable": False, "why_not": "a raster logo is kept exactly as supplied",
                "size": [w, h]}
        if bg:
            info["background"] = bg
        if not flat:
            info["note"] = "many blended colors (a photo or gradient) - these are the closest flat matches"
    for c in info["colors"]:
        lum = luminance(c["hex"])
        c["tone"] = "near-white" if lum > 0.85 else "near-black" if lum < 0.02 else "color"
    return info


def recolor_svg(text, variant, colors):
    """Mono/reversed version of a supplied SVG: near-white parts stay light, the rest go to one color."""
    ink, surf = colors["ink"]["hex"], colors["surface"]["hex"]

    def sub(m):
        c = norm_color(m.group(2))
        light = luminance(c) > 0.85
        if variant == "mono":
            new = surf if light else ink
        else:
            new = ink if light else surf
        return m.group(1) + new
    out = PAINT_RE.sub(sub, text)
    if not PAINT_RE.search(text):   # default black fill
        out = re.sub(r"<svg\b", f'<svg fill="{ink if variant == "mono" else surf}"', out, count=1)
    return out


def svg_size(text):
    m = re.search(r'viewBox\s*=\s*["\']\s*([-\d.]+)[\s,]+([-\d.]+)[\s,]+([-\d.]+)[\s,]+([-\d.]+)', text)
    if m:
        return float(m.group(3)), float(m.group(4))
    w = re.search(r'\bwidth\s*=\s*["\']([\d.]+)', text)
    h = re.search(r'\bheight\s*=\s*["\']([\d.]+)', text)
    return (float(w.group(1)), float(h.group(1))) if w and h else (100.0, 100.0)


# A small SVG reader for flat logos: filled paths and basic shapes, group transforms,
# nonzero and evenodd fills. Anything else (gradients, strokes, text, masks, CSS
# classes) is reported as unsupported so the caller can say so instead of guessing.

NUM_RE = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
UNSUPPORTED = ("linearGradient", "radialGradient", "pattern", "mask", "clipPath", "filter", "image",
               "text", "use", "style", "foreignObject")


def mat_mul(a, b):
    return (a[0] * b[0] + a[2] * b[1], a[1] * b[0] + a[3] * b[1], a[0] * b[2] + a[2] * b[3],
            a[1] * b[2] + a[3] * b[3], a[0] * b[4] + a[2] * b[5] + a[4], a[1] * b[4] + a[3] * b[5] + a[5])


def parse_transform(t):
    m = (1, 0, 0, 1, 0, 0)
    for name, args in re.findall(r"(\w+)\s*\(([^)]*)\)", t or ""):
        v = [float(x) for x in NUM_RE.findall(args)]
        if name == "translate":
            k = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        elif name == "scale":
            k = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        elif name == "matrix" and len(v) == 6:
            k = tuple(v)
        elif name == "rotate":
            a = math.radians(v[0])
            k = (math.cos(a), math.sin(a), -math.sin(a), math.cos(a), 0, 0)
            if len(v) == 3:
                k = mat_mul(mat_mul((1, 0, 0, 1, v[1], v[2]), k), (1, 0, 0, 1, -v[1], -v[2]))
        else:
            raise ValueError(f"transform {name}")
        m = mat_mul(m, k)
    return m


def arc_points(x1, y1, rx, ry, phi, large, sweep, x2, y2):
    if rx == 0 or ry == 0:
        return [(x2, y2)]
    rx, ry = abs(rx), abs(ry)
    c, s = math.cos(math.radians(phi)), math.sin(math.radians(phi))
    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
    xp, yp = c * dx + s * dy, -s * dx + c * dy
    lam = xp * xp / (rx * rx) + yp * yp / (ry * ry)
    if lam > 1:
        rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
    num = rx * rx * ry * ry - rx * rx * yp * yp - ry * ry * xp * xp
    den = rx * rx * yp * yp + ry * ry * xp * xp
    co = math.sqrt(max(0, num / den)) if den else 0
    if large == sweep:
        co = -co
    cxp, cyp = co * rx * yp / ry, -co * ry * xp / rx
    cx, cy = c * cxp - s * cyp + (x1 + x2) / 2, s * cxp + c * cyp + (y1 + y2) / 2

    def ang(ux, uy, vx, vy):
        a = math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
        return a
    t1 = ang(1, 0, (xp - cxp) / rx, (yp - cyp) / ry)
    dt = ang((xp - cxp) / rx, (yp - cyp) / ry, (-xp - cxp) / rx, (-yp - cyp) / ry)
    if not sweep and dt > 0:
        dt -= 2 * math.pi
    elif sweep and dt < 0:
        dt += 2 * math.pi
    n = max(4, int(abs(dt) / (math.pi / 16)))
    pts = []
    for i in range(1, n + 1):
        t = t1 + dt * i / n
        x, y = rx * math.cos(t), ry * math.sin(t)
        pts.append((c * x - s * y + cx, s * x + c * y + cy))
    return pts


def path_polys(d):
    toks = re.findall(r"[MmLlHhVvCcSsQqTtAaZz]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", d)
    polys, cur, i = [], [], 0
    x = y = sx = sy = 0.0
    cmd, last_ctrl = None, None
    seg = 12

    def num():
        nonlocal i
        v = float(toks[i])
        i += 1
        return v
    while i < len(toks):
        if re.match(r"[A-Za-z]", toks[i]):
            cmd = toks[i]
            i += 1
        elif cmd is None:
            raise ValueError("path data")
        rel = cmd.islower()
        C = cmd.upper()
        ox, oy = (x, y) if rel else (0.0, 0.0)
        if C == "Z":
            if cur:
                polys.append(cur)
            cur, x, y, last_ctrl = [], sx, sy, None
            continue
        if C == "M":
            if cur:
                polys.append(cur)
            x, y = num() + ox, num() + oy
            sx, sy, cur = x, y, [(x, y)]
            cmd = "l" if rel else "L"
            last_ctrl = None
        elif C == "L":
            x, y = num() + ox, num() + oy
            cur.append((x, y))
            last_ctrl = None
        elif C == "H":
            x = num() + (x if rel else 0)
            cur.append((x, y))
            last_ctrl = None
        elif C == "V":
            y = num() + (y if rel else 0)
            cur.append((x, y))
            last_ctrl = None
        elif C in "CS":
            if C == "C":
                c1 = (num() + ox, num() + oy)
            else:
                c1 = (2 * x - last_ctrl[0], 2 * y - last_ctrl[1]) if last_ctrl and last_ctrl[2] == "C" else (x, y)
            c2 = (num() + ox, num() + oy)
            e = (num() + ox, num() + oy)
            for k in range(1, seg + 1):
                t = k / seg
                mt = 1 - t
                cur.append((mt ** 3 * x + 3 * mt * mt * t * c1[0] + 3 * mt * t * t * c2[0] + t ** 3 * e[0],
                            mt ** 3 * y + 3 * mt * mt * t * c1[1] + 3 * mt * t * t * c2[1] + t ** 3 * e[1]))
            last_ctrl = (c2[0], c2[1], "C")
            x, y = e
        elif C in "QT":
            if C == "Q":
                q = (num() + ox, num() + oy)
            else:
                q = (2 * x - last_ctrl[0], 2 * y - last_ctrl[1]) if last_ctrl and last_ctrl[2] == "Q" else (x, y)
            e = (num() + ox, num() + oy)
            for k in range(1, seg + 1):
                t = k / seg
                mt = 1 - t
                cur.append((mt * mt * x + 2 * mt * t * q[0] + t * t * e[0], mt * mt * y + 2 * mt * t * q[1] + t * t * e[1]))
            last_ctrl = (q[0], q[1], "Q")
            x, y = e
        elif C == "A":
            rx, ry, phi, large, sweep = num(), num(), num(), num(), num()
            e = (num() + ox, num() + oy)
            cur.extend(arc_points(x, y, rx, ry, phi, int(large), int(sweep), e[0], e[1]))
            x, y = e
            last_ctrl = None
    if cur:
        polys.append(cur)
    return [p for p in polys if len(p) >= 3]


def ellipse_poly(cx, cy, rx, ry, n=72):
    return [(cx + rx * math.cos(2 * math.pi * k / n), cy + ry * math.sin(2 * math.pi * k / n)) for k in range(n)]


def read_flat_svg(text):
    """[(polygons, hex, rule)] in viewBox units plus the viewBox, or (None, reason)."""
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        return None, f"is not well-formed XML ({e})"
    shapes = []

    def tag(el):
        return el.tag.split("}")[-1]

    def style(el):
        st = dict(re.findall(r"([\w-]+)\s*:\s*([^;]+)", el.get("style", "")))
        return {k: st.get(k, el.get(k)) for k in ("fill", "fill-rule", "stroke", "display", "opacity", "fill-opacity")}

    def walk(el, m, inh):
        t = tag(el)
        if t in UNSUPPORTED:
            raise ValueError(f"uses <{t}>")
        if t in ("defs", "title", "desc", "metadata"):
            return
        st = style(el)
        if st["display"] == "none":
            return
        cur = dict(inh)
        for k in ("fill", "fill-rule", "stroke"):
            if st[k] is not None:
                cur[k] = st[k].strip()
        if el.get("class"):
            raise ValueError("styles colors through CSS classes")
        m = mat_mul(m, parse_transform(el.get("transform"))) if el.get("transform") else m
        if cur.get("stroke") not in (None, "none"):
            raise ValueError("uses strokes")
        polys = None
        f = lambda k, d=0.0: float(NUM_RE.findall(el.get(k, str(d)) or str(d))[0])  # noqa: E731
        if t == "path":
            polys = path_polys(el.get("d", ""))
        elif t == "rect":
            x0, y0, w, h = f("x"), f("y"), f("width"), f("height")
            rx = f("rx", -1)
            ry = f("ry", -1)
            rx = ry if rx < 0 else rx
            ry = rx if ry < 0 else ry
            rx, ry = max(0.0, min(rx, w / 2)), max(0.0, min(ry, h / 2))
            if rx and ry:
                pts = []
                for cx, cy, a0 in ((x0 + w - rx, y0 + ry, -90), (x0 + w - rx, y0 + h - ry, 0),
                                   (x0 + rx, y0 + h - ry, 90), (x0 + rx, y0 + ry, 180)):
                    pts += [(cx + rx * math.cos(math.radians(a0 + 90 * k / 8)), cy + ry * math.sin(math.radians(a0 + 90 * k / 8))) for k in range(9)]
                polys = [pts]
            else:
                polys = [[(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)]]
        elif t == "circle":
            polys = [ellipse_poly(f("cx"), f("cy"), f("r"), f("r"))]
        elif t == "ellipse":
            polys = [ellipse_poly(f("cx"), f("cy"), f("rx"), f("ry"))]
        elif t in ("polygon", "polyline"):
            v = [float(x) for x in NUM_RE.findall(el.get("points", ""))]
            polys = [list(zip(v[::2], v[1::2]))]
        if polys is not None:
            fill = cur.get("fill", "#000000")
            if fill == "none":
                return
            if fill.startswith("url("):
                raise ValueError("uses gradient or pattern fills")
            c = fill.strip().lower()
            if not (c in NAMED or c.startswith("rgb(") or re.fullmatch(r"#[0-9a-f]{3}|#[0-9a-f]{6}", c)):
                raise ValueError(f"uses the color {fill!r}")
            hexc = norm_color(c)
            tp = [[(m[0] * px + m[2] * py + m[4], m[1] * px + m[3] * py + m[5]) for px, py in poly] for poly in polys]
            shapes.append((tp, hexc, cur.get("fill-rule", "nonzero")))
        for ch in el:
            walk(ch, m, cur)

    try:
        walk(root, (1, 0, 0, 1, 0, 0), {})
    except (ValueError, IndexError, ZeroDivisionError) as e:
        return None, str(e)
    vb = [float(v) for v in NUM_RE.findall(root.get("viewBox", ""))]
    if len(vb) != 4:
        w, h = svg_size(text)
        vb = [0, 0, w, h]
    return (shapes, vb), None


def fill_mask(polys, rule, W, H, sx, sy, ox, oy):
    """Scanline fill at one sample per pixel row centre; returns a Pillow 'L' mask."""
    from PIL import Image, ImageDraw
    mask = Image.new("L", (W, H), 0)
    dr = ImageDraw.Draw(mask)
    edges = []
    for poly in polys:
        pts = [((x - ox) * sx, (y - oy) * sy) for x, y in poly]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
            if y0 == y1:
                continue
            d = 1 if y1 > y0 else -1
            if y0 > y1:
                x0, y0, x1, y1 = x1, y1, x0, y0
            edges.append((y0, y1, x0, (x1 - x0) / (y1 - y0), d))
    if not edges:
        return mask
    edges.sort()
    ymin = max(0, int(min(e[0] for e in edges)))
    ymax = min(H - 1, int(max(e[1] for e in edges)) + 1)
    for row in range(ymin, ymax + 1):
        yc = row + 0.5
        xs = [(e[2] + (yc - e[0]) * e[3], e[4]) for e in edges if e[0] <= yc < e[1]]
        if not xs:
            continue
        xs.sort()
        wind = 0
        for k in range(len(xs) - 1):
            wind = wind + xs[k][1] if rule != "evenodd" else wind ^ 1
            if wind:
                a, b = round(xs[k][0]), round(xs[k + 1][0]) - 1
                if b >= a:
                    dr.line((a, row, b, row), fill=255)
    return mask


def raster_flat_svg(text, width, png_path):
    """Render a flat SVG to a transparent PNG with Pillow; returns (image, None) or (None, reason)."""
    from PIL import Image
    parsed, why = read_flat_svg(text)
    if parsed is None:
        return None, why
    shapes, (vx, vy, vw, vh) = parsed
    k = 3
    W, H = width * k, max(1, round(width * vh / vw)) * k
    sx, sy = W / vw, H / vh
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for polys, hexc, rule in shapes:
        mask = fill_mask(polys, rule, W, H, sx, sy, vx, vy)
        layer = Image.new("RGBA", (W, H), rgb(hexc) + (255,))
        img.paste(layer, (0, 0), mask)
    img = img.resize((W // k, H // k), Image.LANCZOS)
    img.save(png_path)
    return img, None


def rasterize_svg(svg_path, png_path, width):
    try:
        import cairosvg
        cairosvg.svg2png(url=svg_path, write_to=png_path, output_width=width)
        return True
    except Exception:
        pass
    if shutil.which("rsvg-convert"):
        r = subprocess.run(["rsvg-convert", "-w", str(width), "-o", png_path, svg_path], capture_output=True)
        return r.returncode == 0 and os.path.exists(png_path)
    return False


# --- the guide ---------------------------------------------------------------------

def font_face(fam, file, weight):
    with open(os.path.join(FONT_DIR, file), "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return (f"@font-face{{font-family:'{fam}';font-weight:{weight};font-style:normal;"
            f"src:url(data:font/ttf;base64,{b64}) format('truetype');}}")


def google_url(head, body):
    fams = []
    for fam, _, w, _, _ in (head, body):
        q = fam.replace(" ", "+")
        if fam == body[0]:
            fams.append(f"family={q}:wght@400;600")
        else:
            fams.append(f"family={q}:wght@{w}")
    if head[0] == body[0]:
        fams = fams[:1]
    return "https://fonts.googleapis.com/css2?" + "&".join(fams) + "&display=swap"


def inline_svg(svg):
    return re.sub(r"<title>.*?</title>", "", svg, count=1, flags=re.S).replace("<svg ", '<svg aria-hidden="true" ', 1)


def build_guide(spec, colors, logos, pairs, button):
    head, body = TYPE[spec["type"]]
    title = spec["name"] or spec["about"][:1].upper() + spec["about"][1:]
    e = html.escape
    p, ink, surf = colors["primary"]["hex"], colors["ink"]["hex"], colors["surface"]["hex"]
    swatches = []
    for role in ROLES:
        if role not in colors:
            continue
        h = colors[role]["hex"]
        on = max((surf, ink), key=lambda c: contrast(c, h))
        r, g, b = rgb(h)
        swatches.append(
            f'<div class="sw"><div class="chip" style="background:{h};color:{on}">'
            f'<b>{role.title()}</b><span>{h}</span></div>'
            f'<p class="meta">RGB {r} {g} {b}</p><p>{e(colors[role]["use"])}</p></div>')
    role_of = {colors[r]["hex"]: r.title() for r in ROLES if r in colors}
    tiles = []
    for fg, bg, ratio, label in pairs:
        tiles.append(f'<div class="pair"><div class="aa" style="background:{bg};color:{fg}">Aa</div>'
                     f'<p><b>{role_of[fg]}</b> on {role_of[bg].lower()}<br>{ratio:.1f}:1 · {label}</p></div>')
    logo_tiles = [f'<div class="lt" style="background:{surf}">{logos["full"]}<p>Primary</p></div>']
    if logos.get("reversed"):
        logo_tiles.append(f'<div class="lt" style="background:{ink}">{logos["reversed"]}<p style="color:{surf}">On ink</p></div>')
    if logos.get("mono"):
        logo_tiles.append(f'<div class="lt" style="background:{surf}">{logos["mono"]}<p>One color</p></div>')
    if logos.get("icon"):
        logo_tiles.append(f'<div class="lt sq" style="background:{surf}">{logos["icon"]}<p>Icon</p></div>')
    rules = [f"Keep clear space around the logo equal to {logos['clear']} on every side.",
             f"Never show the full logo smaller than {logos['min']}"
             + (" - use the icon below that." if logos.get("icon") else "."),
             "Never stretch, rotate, outline or recolor it outside these colors.",
             f"Buttons: {button}."]
    if luminance(p) > 0.5 and contrast(p, surf) < 3:
        rules.append(f"Primary is too light to read on surface - use it for fills and backgrounds, not text.")
    about = spec["about"][:1].upper() + spec["about"][1:]
    about += "" if about[-1] in ".!?" else "."
    voice = ""
    if spec["voice"]:
        voice = ('<section class="voice"><h2>Voice</h2><p class="words">'
                 + " · ".join(e(v) for v in spec["voice"]) + "</p></section>")
    faces = font_face(head[0], head[1], head[2])
    hs = f"'{head[0]}', {head[4]}"
    bs = f"'{body[0]}', {body[4]}"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="{e(google_url(head, body))}">
<title>{e(title)} brand guide</title>
<style>
{faces}
:root{{--primary:{p};--ink:{ink};--surface:{surf};--line:color-mix(in srgb,{ink} 18%,{surf});}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:{surf};color:{ink};font:15px/1.5 {bs};-webkit-print-color-adjust:exact;print-color-adjust:exact}}
main{{max-width:960px;margin:0 auto;padding:40px 24px 48px}}
h1,h2,.display{{font-family:{hs};font-weight:{head[2]};line-height:1.1}}
h1{{font-size:15px;letter-spacing:.12em;text-transform:uppercase;font-family:{bs};font-weight:400}}
h2{{font-size:22px;margin-bottom:12px}}
header{{display:flex;justify-content:space-between;align-items:center;gap:24px;padding-bottom:20px;border-bottom:2px solid {p}}}
header .lk svg{{height:64px;width:auto;max-width:100%;display:block}}
header .about{{max-width:300px;text-align:right}}
section{{padding-top:22px}}
.grid{{display:grid;gap:12px}}
.logos{{grid-template-columns:repeat(auto-fit,minmax(170px,1fr))}}
.lt{{border:1px solid var(--line);border-radius:8px;padding:22px 16px 10px;display:flex;flex-direction:column;align-items:center;gap:10px;min-height:120px;justify-content:space-between}}
.lt svg,.lt img{{max-height:52px;max-width:100%;width:auto;height:52px}}
.lt.sq svg,.lt.sq img{{height:52px;width:52px}}
.lt p{{font-size:12px}}
.rules{{margin-top:12px;padding-left:18px;font-size:14px}}
.colors{{grid-template-columns:repeat(auto-fit,minmax(170px,1fr))}}
.chip{{height:92px;border-radius:8px;padding:12px;display:flex;flex-direction:column;justify-content:space-between;border:1px solid var(--line)}}
.chip span{{font-variant-numeric:tabular-nums}}
.sw p{{font-size:13px;margin-top:4px}}
.sw .meta{{opacity:.75}}
.pairs{{grid-template-columns:repeat(auto-fit,minmax(130px,1fr));margin-top:14px}}
.aa{{font-family:{hs};font-size:28px;height:56px;display:flex;align-items:center;justify-content:center;border-radius:6px;border:1px solid var(--line)}}
.pair p{{font-size:12px;margin-top:4px}}
.type{{display:grid;grid-template-columns:1fr 1fr;gap:24px}}
.display{{font-size:30px;color:{p if contrast(p, surf) >= 3 else ink}}}
.spec{{font-size:13px;margin-top:6px}}
.words{{font-family:{hs};font-size:24px}}
footer{{margin-top:26px;padding-top:12px;border-top:1px solid var(--line);font-size:12px}}
footer a{{color:inherit}}
@media (max-width:640px){{header{{flex-direction:column;align-items:flex-start}}header .about{{text-align:left}}.type{{grid-template-columns:1fr}}}}
@page{{size:letter;margin:0}}
@media print{{main{{padding:0.4in;max-width:none}}body{{font-size:12px}}section{{padding-top:12px}}h2{{font-size:17px;margin-bottom:6px}}
.lt{{min-height:92px;padding:14px 10px 6px}}.lt svg,.lt img{{height:40px;max-height:40px}}.lt.sq svg{{width:40px}}
.chip{{height:62px;padding:8px}}.aa{{height:40px;font-size:22px}}.display{{font-size:22px}}.pairs{{margin-top:8px}}
.rules{{margin-top:6px;font-size:12px}}footer{{margin-top:12px}}header .lk svg{{height:48px}}}}
</style></head>
<body><main>
<header><div class="lk">{logos["full"]}</div><div class="about"><h1>Brand guide</h1><p>{e(spec["about"][:1].upper() + spec["about"][1:])}</p></div></header>
<section><h2>Logo</h2><div class="grid logos">{"".join(logo_tiles)}</div>
<ul class="rules">{"".join(f"<li>{e(r)}</li>" for r in rules)}</ul></section>
<section><h2>Color</h2><div class="grid colors">{"".join(swatches)}</div>
<div class="grid pairs">{"".join(tiles)}</div></section>
<section class="type"><div><h2>Type</h2><p class="display">{e(spec["line"])}</p>
<p class="spec">Headings: <b>{head[0]} {head[3]}</b> - 40 / 28 / 20px</p></div>
<div><h2>&nbsp;</h2><p style="font-size:18px">{e(about)}</p>
<p class="spec">Body: <b>{body[0]} {body[3]}</b> - 16px on 1.5 line height</p></div></section>
{voice}
<footer>Fonts: {head[0]}{"" if head[0] == body[0] else " and " + body[0]}, free from Google Fonts under the SIL Open Font License. Colors and fonts as CSS: <code>colors.css</code>.</footer>
</main></body></html>
"""


# --- build -----------------------------------------------------------------------

OWNED = ("brand-guide.html", "brand-board.svg", "brand-board.png", "colors.css", "brand.json")


def wrap(f, text, size, width, max_lines):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if f.layout(trial, size)[1] <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines if len(lines) <= max_lines else None


def build(spec, outdir, png_mode):
    colors = spec["colors"]
    head, body = TYPE[spec["type"]]
    # Only the heading font ships with the kit; everything the board sets in type uses it.
    # The body font is named in the guide and the CSS and loads from Google Fonts there.
    hf = bf = font(head[1])
    p, ink, surf = colors["primary"]["hex"], colors["ink"]["hex"], colors["surface"]["hex"]
    acc = colors.get("accent", {}).get("hex")
    notes = []
    pillow = png_mode != "none" and have_pillow()
    check_glyphs(spec["line"], hf, "line", head[0])
    check_glyphs(spec["about"], hf, "about", head[0])
    # Everything that can fail is checked before the output folder is touched.
    if spec.get("logo"):
        info = inspect_logo(spec["logo"])
        logo_colors = {c["hex"] for c in info["colors"]}
        if logo_colors and colors["primary"]["hex"] not in logo_colors:
            fail(f"colors.primary {colors['primary']['hex']} is not in the supplied logo - take it from "
                 f"--inspect: {', '.join(sorted(logo_colors))}")
    else:
        mk = mark_items(spec, role_map(colors, "full")) if spec.get("mark") else None
        if spec["name"]:
            lockup_items(spec, role_map(colors, "full"), mk)

    # Contrast: every pair, graded; only passing pairs are published.
    pairs = []
    cands = [(ink, surf), (p, surf), (surf, p), (ink, p), (surf, ink), (p, ink)]
    if acc:
        cands += [(acc, surf), (ink, acc), (surf, acc), (acc, ink)]
    seen = set()
    for fg, bg in cands:
        if (fg, bg) in seen or fg == bg:
            continue
        seen.add((fg, bg))
        r = contrast(fg, bg)
        if r >= 3:
            pairs.append((fg, bg, r, grade(r)))
    on_p = max((surf, ink), key=lambda c: contrast(c, p))
    if contrast(on_p, p) >= 4.5:
        button = f"{'surface' if on_p == surf else 'ink'} text on primary ({contrast(on_p, p):.1f}:1)"
        button_pair = {"background": p, "text": on_p}
    else:
        button = (f"surface text on ink ({contrast(surf, ink):.1f}:1) - no text color reaches 4.5:1 on "
                  f"primary, so primary is for graphics, not buttons")
        button_pair = {"background": ink, "text": surf}
        notes.append("primary cannot carry small text; buttons use ink")
    if contrast(p, surf) < 3:
        notes.append(f"primary is {contrast(p, surf):.2f}:1 on surface - it works as a fill or background, never as text or thin lines on the page")

    if os.path.isdir(outdir):
        for fname in OWNED:
            fp = os.path.join(outdir, fname)
            if os.path.isfile(fp):
                os.remove(fp)
        shutil.rmtree(os.path.join(outdir, "logo"), ignore_errors=True)
    os.makedirs(os.path.join(outdir, "logo"))
    L = lambda *a: os.path.join(outdir, "logo", *a)  # noqa: E731
    files = []
    logos = {}
    title = spec["name"] or spec["about"]

    # Logo files.
    if spec.get("logo"):
        src = spec["logo"]
        if not logo_colors:
            notes.append("the supplied logo's colors could not be read; palette taken from the spec as given")
        if info["format"] == "svg":
            text = open(src, encoding="utf-8", errors="replace").read()
            shutil.copyfile(src, L("logo.svg"))
            files.append("logo/logo.svg")
            w, h = svg_size(text)
            logos["full"] = inline_svg(text)
            href = "data:image/svg+xml;base64," + base64.b64encode(text.encode()).decode()
            logo_kind = "supplied-svg"
            if info["recolorable"]:
                for v in ("mono", "reversed"):
                    t = recolor_svg(text, v, colors)
                    with open(L(f"logo-{v}.svg"), "w", encoding="utf-8") as fh:
                        fh.write(t)
                    files.append(f"logo/logo-{v}.svg")
                    logos[v] = inline_svg(t)
            else:
                notes.append(f"no one-color or reversed versions: the supplied SVG {info['why_not']}")
            pil_img = None
            if pillow:
                why = None
                for v in ["logo"] + [f"logo-{x}" for x in ("mono", "reversed") if x in logos]:
                    with open(L(v + ".svg"), encoding="utf-8", errors="replace") as fh:
                        img, why = raster_flat_svg(fh.read(), 1600, L(v + ".png"))
                    if img is not None or rasterize_svg(L(v + ".svg"), L(v + ".png"), 1600):
                        files.append(f"logo/{v}.png")
                if os.path.exists(L("logo.png")):
                    from PIL import Image
                    pil_img = Image.open(L("logo.png"))
                else:
                    notes.append(f"the supplied SVG {why} and no SVG renderer is installed, so it has no PNG "
                                 f"and the board has no PNG preview")
        else:
            ext = os.path.splitext(src)[1].lower() or ".png"
            shutil.copyfile(src, L("logo" + ext))
            files.append("logo/logo" + ext)
            data = open(src, "rb").read()
            mime = "image/png" if data[:4] == b"\x89PNG" else "image/jpeg"
            href = f"data:{mime};base64," + base64.b64encode(data).decode()
            logos["full"] = f'<img src="{href}" alt="">'
            sz = info.get("size") or [400, 200]
            w, h = sz
            logo_kind = "supplied-raster"
            notes.append("a raster logo is kept exactly as supplied - no one-color, reversed or icon versions")
            pil_img = None
            if pillow:
                from PIL import Image
                pil_img = Image.open(src)
                w, h = pil_img.size
        logos["clear"] = "a quarter of the logo's height"
        logos["min"] = "120px wide on screen (1 inch in print)"
        board_logo = [{"k": "image", "href": href, "x": 0, "y": 0, "w": w, "h": h, "pil": pil_img}]
        reversed_logo = None
        if logos.get("reversed"):
            rtext = open(L("logo-reversed.svg"), encoding="utf-8").read()
            rpil = None
            if os.path.exists(L("logo-reversed.png")):
                from PIL import Image
                rpil = Image.open(L("logo-reversed.png"))
            reversed_logo = [{"k": "image", "x": 0, "y": 0, "w": w, "h": h, "pil": rpil,
                              "href": "data:image/svg+xml;base64," + base64.b64encode(rtext.encode()).decode()}]
        icon_items = None
    else:
        full = role_map(colors, "full")
        mark = mark_items(spec, full) if spec.get("mark") else None
        variants = {}
        for v in ("full", "mono", "reversed"):
            cm = role_map(colors, v)
            mk = mark_items(spec, cm) if mark else None
            variants[v] = lockup_items(spec, cm, mk) if spec["name"] else mk
        icon_variants = {}
        if spec["name"] and mark:
            for v in ("full", "mono", "reversed"):
                icon_variants[v] = mark_items(spec, role_map(colors, v))
        elif not spec["name"]:
            icon_variants = None          # the mark is the whole logo and already square
        else:
            icon_variants = {"full": monogram_items(spec, colors)}
        logo_kind = "drawn" if mark else "wordmark"
        for v, items in variants.items():
            b = union(item_bbox(i) for i in items)
            if not spec["name"]:
                b = square(b)
            pad = (b[3] - b[1]) * 0.04
            fn = "logo.svg" if v == "full" else f"logo-{v}.svg"
            svg = svg_doc(items, b, title + (" logo" if v == "full" else f" logo ({v})"), pad)
            with open(L(fn), "w", encoding="utf-8") as fh:
                fh.write(svg)
            files.append("logo/" + fn)
            logos[v] = inline_svg(svg)
            if pillow:
                render_png(items, b, 1600 if spec["name"] else 1024, L(fn[:-4] + ".png"), pad=pad)
                files.append("logo/" + fn[:-4] + ".png")
        icon_items = icon_variants["full"] if icon_variants else variants["full"]
        if icon_variants:
            ib = square(union(item_bbox(i) for i in icon_items))
            pad = (ib[3] - ib[1]) * 0.06
            svg = svg_doc(icon_items, ib, title + " icon", pad)
            with open(L("logo-icon.svg"), "w", encoding="utf-8") as fh:
                fh.write(svg)
            files.append("logo/logo-icon.svg")
            logos["icon"] = inline_svg(svg)
            if pillow:
                render_png(icon_items, ib, 1024, L("logo-icon.png"), pad=pad)
                files.append("logo/logo-icon.png")
        if pillow:
            from PIL import Image
            ib = square(union(item_bbox(i) for i in icon_items))
            big = render_png(icon_items, ib, 512, L("_icon.png"), pad=(ib[3] - ib[1]) * 0.04)
            os.remove(L("_icon.png"))
            big.resize((32, 32), Image.LANCZOS).save(L("favicon-32.png"))
            touch = Image.new("RGBA", (180, 180), rgb(surf) + (255,))
            inner = big.resize((144, 144), Image.LANCZOS)
            touch.alpha_composite(inner, (18, 18))
            touch.convert("RGB").save(L("apple-touch-icon.png"))
            files += ["logo/favicon-32.png", "logo/apple-touch-icon.png"]
        mh = 100
        logos["clear"] = "a quarter of the mark's height" if mark else "the height of the capital letters"
        logos["min"] = "120px wide on screen (1 inch in print)" if spec["name"] else "24px on screen"
        board_logo = variants["full"]
        reversed_logo = variants["reversed"]

    # Board: 1600 x 1000.
    W, H = 1600, 1000
    items = [{"k": "rect", "x": 0, "y": 0, "w": W, "h": H, "r": 0, "fill": surf, "stroke": None, "sw": 0}]
    sw_roles = [r for r in ROLES if r in colors]
    weights = {"primary": 0.4, "accent": 0.2, "ink": 0.2, "surface": 0.2}
    tot = sum(weights[r] for r in sw_roles)
    y = 0.0
    for role in ("primary", "accent", "ink", "surface"):
        if role not in colors:
            continue
        hgt = H * weights[role] / tot
        c = colors[role]["hex"]
        items.append({"k": "rect", "x": 1040, "y": y, "w": 560, "h": hgt, "r": 0, "fill": c, "stroke": None, "sw": 0})
        on = max((surf, ink), key=lambda x: contrast(x, c))
        items.append(text_item(hf, head[1], role.title(), 26, 1080, y + hgt - 54, on))
        items.append(text_item(hf, head[1], c, 22, 1080, y + hgt - 24, on))
        y += hgt
    items.append({"k": "line", "x1": 1040, "y1": H - H * weights["surface"] / tot, "x2": 1600,
                  "y2": H - H * weights["surface"] / tot, "stroke": blend(ink, surf, 0.18), "sw": 2})
    has_strip = reversed_logo is not None
    top_box = (80, 90, 960, 390 if has_strip else 470)
    items += place(board_logo, top_box, align="left")
    # Type specimen: the line as a headline in the heading font, what it does in the body font.
    hs, hl = 56, None
    while hs >= 32:
        hl = wrap(hf, spec["line"], hs, 880, 2)
        if hl:
            break
        hs -= 2
    hl = hl or wrap(hf, spec["line"], hs, 880, 3)
    ly = (470 if has_strip else 580) + hs * 0.8
    for ln in hl:
        items.append(text_item(hf, head[1], ln, hs, 80, ly, p if contrast(p, surf) >= 3 else ink))
        ly += hs * 1.15
    about = spec["about"][:1].upper() + spec["about"][1:]
    about += "" if about[-1] in ".!?" else "."
    bl = wrap(bf, about, 28, 880, 2) or [about]
    ly += 14
    for ln in bl:
        items.append(text_item(hf, head[1], ln, 28, 80, ly, ink))
        ly += 28 * 1.4
    items.append(text_item(hf, head[1], f"{head[0]} {head[3]}  /  {body[0]} {body[3]}", 20, 80, ly + 14,
                           ink))
    if has_strip:
        items.append({"k": "rect", "x": 0, "y": 820, "w": 1040, "h": 180, "r": 0, "fill": ink, "stroke": None, "sw": 0})
        items += place(reversed_logo, (80, 862, 700, 958), align="left")
    board_svg = svg_doc(items, (0, 0, W, H), f"{title} brand board")
    with open(os.path.join(outdir, "brand-board.svg"), "w", encoding="utf-8") as fh:
        fh.write(board_svg)
    files.append("brand-board.svg")
    preview = None
    board_ok = pillow and all(i.get("pil") is not None for i in items if i["k"] == "image")
    if board_ok:
        render_png(items, (0, 0, W, H), 1600, os.path.join(outdir, "brand-board.png"))
        files.append("brand-board.png")
        preview = os.path.join(outdir, "brand-board.png")

    # Guide, CSS, spec.
    with open(os.path.join(outdir, "brand-guide.html"), "w", encoding="utf-8") as fh:
        fh.write(build_guide(spec, colors, logos, pairs, button))
    files.append("brand-guide.html")
    css = [f"/* {title} - brand colors and fonts. Fonts are free on Google Fonts:",
           f"   @import url('{google_url(head, body)}'); */", ":root {"]
    for role in ROLES:
        if role in colors:
            css.append(f"  --brand-{role}: {colors[role]['hex']};")
    css.append(f"  --brand-button-bg: {button_pair['background']};")
    css.append(f"  --brand-button-text: {button_pair['text']};")
    css.append(f"  --brand-font-heading: '{head[0]}', {head[4]};")
    css.append(f"  --brand-font-body: '{body[0]}', {body[4]};")
    css.append("}")
    with open(os.path.join(outdir, "colors.css"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(css) + "\n")
    files.append("colors.css")
    computed = {
        "fonts": {"heading": f"{head[0]} {head[3]}", "body": f"{body[0]} {body[3]}",
                  "google_fonts": google_url(head, body)},
        "button": button_pair,
        "contrast": [{"text": fg, "on": bg, "ratio": round(r, 2), "use": g} for fg, bg, r, g in pairs],
    }
    saved = {k: v for k, v in spec.items() if k != "computed"}
    saved["computed"] = computed
    with open(os.path.join(outdir, "brand.json"), "w", encoding="utf-8") as fh:
        json.dump(saved, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    files.append("brand.json")

    zpath = outdir.rstrip("/") + ".zip"
    if os.path.exists(zpath):
        os.remove(zpath)
    root = os.path.basename(outdir.rstrip("/"))
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for fpath in files:
            z.write(os.path.join(outdir, fpath), f"{root}/{fpath}")
    return {
        "folder": os.path.abspath(outdir), "zip": os.path.abspath(zpath),
        "files": files, "preview": os.path.abspath(preview) if preview else None,
        "png": "pillow" if pillow else "none", "logo": logo_kind,
        "colors": {r: colors[r]["hex"] for r in ROLES if r in colors},
        "fonts": computed["fonts"], "button": button, "notes": notes,
    }


def square(b):
    w, h = b[2] - b[0], b[3] - b[1]
    s = max(w, h)
    cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    return (cx - s / 2, cy - s / 2, cx + s / 2, cy + s / 2)


def blend(a, b, t):
    ra, rb = rgb(a), rgb(b)
    return "#%02X%02X%02X" % tuple(round(x * t + y * (1 - t)) for x, y in zip(ra, rb))


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return
    if argv[0] == "--inspect":
        if len(argv) != 2:
            fail("usage: build_brand_kit.py --inspect <logo file>")
        print(json.dumps(inspect_logo(argv[1]), indent=2))
        return
    png_mode = "auto"
    if "--png" in argv:
        i = argv.index("--png")
        png_mode = argv[i + 1] if i + 1 < len(argv) else ""
        if png_mode not in ("auto", "none"):
            fail("--png is auto or none")
        argv = argv[:i] + argv[i + 2:]
    if len(argv) != 2:
        fail("usage: build_brand_kit.py <spec.json | -> <name-brand-kit>   (see --help)")
    src, outdir = argv
    raw = sys.stdin.read() if src == "-" else open(src, encoding="utf-8").read()
    spec = load_spec(raw, "stdin" if src == "-" else src)
    print(json.dumps(build(spec, outdir, png_mode), indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])
