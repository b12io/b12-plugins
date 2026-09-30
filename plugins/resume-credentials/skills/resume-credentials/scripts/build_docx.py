#!/usr/bin/env python3
"""Build a resume or capability statement .docx from a JSON content file.

    python3 build_docx.py content.json output.docx
    python3 build_docx.py - output.docx  <<'JSON' ... JSON      (content on stdin)
    python3 build_docx.py --help                                (this text)

Standard library only. Any text written as [like this] is styled as an amber
placeholder, so the content file never needs formatting markup. The package is
validated after it is written; on any problem the script exits non-zero.

Content file shape (every section key is optional except "type"):

{
  "palette": {"ink": "17212B", "brand": "155E75", "muted": "52606D"},
  "header": {"name": "[name]", "headline": "Senior Infrastructure Engineer",
             "contact": ["[email]", "[phone]"], "band": false},
  "sections": [
    {"type": "paragraph", "title": "Profile", "text": "..."},
    {"type": "roles", "title": "Experience",
     "items": [{"title": "...", "org": "...", "dates": "[dates]", "bullets": ["..."]}]},
    {"type": "groups", "title": "Skills", "rows": [["Label", "a · b · c"]]},
    {"type": "bullets", "title": "Differentiators", "items": ["..."]},
    {"type": "columns",
     "left":  {"title": "Core competencies", "items": ["..."]},
     "right": {"title": "Past performance",
               "entries": [{"heading": "...", "detail": "..."}]}},
    {"type": "fields", "title": "Corporate data", "fields": [["UEI", "[UEI]"]]},
    {"type": "footer", "text": "[name] · [email] · [phone]"}
  ]
}

"header.band": true draws the name on a solid brand-coloured band (capability
statements); false gives a plain header (resumes).

Every palette colour is darkened, if needed, until text in it clears 4.5:1 on
white. The final values are printed — use those in the reply and the B12 link.
"""
import json
import math
import re
import sys
import zipfile
import xml.dom.minidom

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
AMBER, AMBER_FILL = "8A6D1F", "FFF6DA"
FONT = '<w:rFonts w:ascii="Georgia" w:hAnsi="Georgia" w:cs="Georgia"/>'
TEXT_WIDTH = 10800          # twips: Letter 12240 minus two 720 margins
LINE_BUDGET = 100           # characters per line at 10.5pt Georgia, measured
PAGE_LINES = 51             # 720pt / 14.07pt per line, measured


def esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def lum(h):
    def ch(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def darken_for_white(h):
    """Darken a colour until white text on it clears 4.5:1."""
    k = 1.0
    while True:
        c = "".join(f"{max(0, round(int(h[i:i + 2], 16) * k)):02X}" for i in (0, 2, 4))
        if (1.05) / (lum(c) + 0.05) >= 4.5 or k <= 0:
            return c
        k -= 0.01


class Doc:
    def __init__(self, palette):
        # darken_for_white(c) makes white-on-c clear 4.5:1, which is the same ratio as c-on-white
        self.ink = darken_for_white(palette.get("ink", "17212B").lstrip("#").upper())
        self.brand = darken_for_white(palette.get("brand", "155E75").lstrip("#").upper())
        self.muted = darken_for_white(palette.get("muted", "52606D").lstrip("#").upper())
        self.body = []
        self.lines = 0.0

    # -- runs and paragraphs -------------------------------------------------
    def runs(self, text, sz=10.5, col=None, bold=False, caps=False):
        col = col or self.ink
        out = []
        for part in re.split(r"(\[[^\]]+\])", text):
            if not part:
                continue
            ph = part.startswith("[") and part.endswith("]")
            # CT_RPr element order is fixed by the schema; Word rejects it out of order
            rpr = FONT
            if bold:
                rpr += "<w:b/>"
            if caps:
                rpr += "<w:caps/>"
            rpr += f'<w:color w:val="{AMBER if ph else col}"/>'
            if caps:
                rpr += '<w:spacing w:val="24"/>'
            rpr += f'<w:sz w:val="{round(sz * 2)}"/>'
            if ph:
                rpr += f'<w:shd w:val="clear" w:color="auto" w:fill="{AMBER_FILL}"/>'
            out.append(f'<w:r><w:rPr>{rpr}</w:rPr><w:t xml:space="preserve">{esc(part)}</w:t></w:r>')
        return "".join(out)

    def para(self, inner, before=0, after=60, bullet=False, rule=False, tab=False,
             shade=None, indent=None, text_len=0, keep_next=False):
        # CT_PPr element order is fixed by the schema; Word rejects it out of order
        ppr = ""
        if keep_next:
            ppr += "<w:keepNext/>"
        if bullet:
            ppr += '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>'
        if rule:
            ppr += f'<w:pBdr><w:bottom w:val="single" w:sz="6" w:space="2" w:color="{self.brand}"/></w:pBdr>'
        if shade:
            ppr += f'<w:shd w:val="clear" w:color="auto" w:fill="{shade}"/>'
        if tab:
            ppr += f'<w:tabs><w:tab w:val="right" w:pos="{TEXT_WIDTH}"/></w:tabs>'
        ppr += f'<w:spacing w:before="{before}" w:after="{after}" w:line="276" w:lineRule="auto"/>'
        if indent:
            ppr += f'<w:ind w:left="{indent}" w:right="{indent}"/>'
        self.lines += max(1, math.ceil(text_len / LINE_BUDGET)) + (before + after) / 280
        return f"<w:p><w:pPr>{ppr}</w:pPr>{inner}</w:p>"

    def heading(self, title):
        self.body.append(self.para(self.runs(title, 9.5, self.brand, bold=True, caps=True),
                                   before=180, after=80, rule=True, text_len=len(title),
                                   keep_next=True))

    # -- blocks --------------------------------------------------------------
    def header(self, h):
        name, headline = h.get("name", "[name]"), h.get("headline", "")
        contact = "  ·  ".join(h.get("contact", []))
        if h.get("band"):
            self.band([(name, 20, True)] + ([(headline, 10.5, False)] if headline else []))
            if contact:
                self.body.append(self.para(self.runs(contact, 9.5, self.muted), after=60,
                                           text_len=len(contact)))
        else:
            self.body.append(self.para(self.runs(name, 22, self.ink, bold=True), after=20, text_len=40))
            if headline:
                self.body.append(self.para(self.runs(headline, 11.5, self.brand, bold=True),
                                           after=30, text_len=len(headline)))
            if contact:
                self.body.append(self.para(self.runs(contact, 9.5, self.muted), after=60,
                                           text_len=len(contact)))

    def paragraph(self, s):
        self.heading(s["title"])
        self.body.append(self.para(self.runs(s["text"]), after=40, text_len=len(s["text"])))

    def roles(self, s):
        self.heading(s["title"])
        for it in s["items"]:
            head = self.runs(it["title"], bold=True)
            if it.get("org"):
                head += self.runs("  ·  " + it["org"])
            if it.get("dates"):
                head += '<w:r><w:tab/></w:r>' + self.runs(it["dates"], 9.5, self.muted)
            self.body.append(self.para(head, before=80, after=30, tab=True, keep_next=True,
                                       text_len=len(it["title"]) + len(it.get("org", ""))))
            for b in it.get("bullets", []):
                self.body.append(self.para(self.runs(b), after=30, bullet=True, text_len=len(b) + 4))

    def groups(self, s):
        self.heading(s["title"])
        for label, text in s["rows"]:
            self.body.append(self.para(self.runs(label + ": ", bold=True) + self.runs(text),
                                       after=40, text_len=len(label) + len(text) + 2))

    def bullets(self, s):
        self.heading(s["title"])
        for b in s["items"]:
            self.body.append(self.para(self.runs(b), after=30, bullet=True, text_len=len(b) + 4))

    def _cell(self, inner, width, fill=None):
        shd = f'<w:shd w:val="clear" w:color="auto" w:fill="{fill}"/>' if fill else ""
        return f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>{shd}</w:tcPr>{inner}</w:tc>'

    def band(self, paragraphs, pad=160):
        """A full-width block of white text on the brand colour, as a shaded one-cell table."""
        fill = darken_for_white(self.brand)
        inner = "".join(self.para(self.runs(t, sz, "FFFFFF", bold=b), before=pad if i == 0 else 0,
                                  after=pad if i == len(paragraphs) - 1 else 20, indent=pad,
                                  text_len=len(t))
                        for i, (t, sz, b) in enumerate(paragraphs))
        self.body.append(self._table(f"<w:tr>{self._cell(inner, TEXT_WIDTH, fill)}</w:tr>", [TEXT_WIDTH]))
        self.body.append(self.para("", after=40))

    def _table(self, rows_xml, widths):
        grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in widths)
        return (f'<w:tbl><w:tblPr><w:tblW w:w="{sum(widths)}" w:type="dxa"/>'
                '<w:tblBorders><w:top w:val="nil"/><w:left w:val="nil"/><w:bottom w:val="nil"/>'
                '<w:right w:val="nil"/><w:insideH w:val="nil"/><w:insideV w:val="nil"/></w:tblBorders>'
                '<w:tblLayout w:type="fixed"/>'
                '<w:tblCellMar><w:left w:w="0" w:type="dxa"/><w:right w:w="200" w:type="dxa"/></w:tblCellMar>'
                f'</w:tblPr><w:tblGrid>{grid}</w:tblGrid>{rows_xml}</w:tbl>')

    def columns(self, s):
        half = TEXT_WIDTH // 2
        saved = self.lines

        def col_xml(c):
            parts = [self.para(self.runs(c["title"], 9.5, self.brand, bold=True, caps=True),
                               before=180, after=80, rule=True, text_len=len(c["title"]))]
            for b in c.get("items", []):
                parts.append(self.para(self.runs(b), after=30, bullet=True, text_len=(len(b) + 4) * 2))
            for e in c.get("entries", []):
                parts.append(self.para(self.runs(e["heading"], bold=True), after=0,
                                       text_len=len(e["heading"]) * 2))
                parts.append(self.para(self.runs(e.get("detail", ""), 9.5, self.muted), after=80,
                                       text_len=len(e.get("detail", "")) * 2))
            return "".join(parts)

        self.lines = 0
        left = col_xml(s["left"])
        left_lines = self.lines
        self.lines = 0
        right = col_xml(s["right"])
        self.lines = saved + max(left_lines, self.lines)
        row = f"<w:tr>{self._cell(left, half)}{self._cell(right, half)}</w:tr>"
        self.body.append(self._table(row, [half, half]))
        self.body.append(self.para("", after=0))

    def fields(self, s):
        self.heading(s["title"])
        third = TEXT_WIDTH // 3
        items = list(s["fields"])
        rows = []
        for i in range(0, len(items), 3):
            cells = []
            for label, value in items[i:i + 3] + [["", ""]] * (3 - len(items[i:i + 3])):
                inner = (self.para(self.runs(label, 8, self.muted, bold=True, caps=True), after=0) +
                         self.para(self.runs(value, 10), after=80))
                cells.append(self._cell(inner, third))
            rows.append("<w:tr>" + "".join(cells) + "</w:tr>")
        self.lines += math.ceil(len(items) / 3) * 1.2
        self.body.append(self._table("".join(rows), [third] * 3))
        self.body.append(self.para("", after=0))

    def footer(self, s):
        self.body.append(self.para("", before=120, after=0))
        self.band([(s["text"], 9.5, False)], pad=100)

    # -- package -------------------------------------------------------------
    def save(self, path):
        sect = ('<w:sectPr><w:pgSz w:w="12240" w:h="15840"/>'
                '<w:pgMar w:top="720" w:right="720" w:bottom="720" w:left="720" '
                'w:header="360" w:footer="360" w:gutter="0"/></w:sectPr>')
        doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
               f'<w:document {W}><w:body>{"".join(self.body)}{sect}</w:body></w:document>')
        ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
              '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
              '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
              '<Default Extension="xml" ContentType="application/xml"/>'
              '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
              '<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>'
              '</Types>')
        rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
                '</Relationships>')
        drels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                 '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>'
                 '</Relationships>')
        num = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
               f'<w:numbering {W}><w:abstractNum w:abstractNumId="0"><w:lvl w:ilvl="0">'
               '<w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="•"/><w:lvlJc w:val="left"/>'
               '<w:pPr><w:ind w:left="300" w:hanging="200"/></w:pPr>'
               f'<w:rPr>{FONT}<w:color w:val="{self.brand}"/></w:rPr></w:lvl></w:abstractNum>'
               '<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num></w:numbering>')
        parts = {"[Content_Types].xml": ct, "_rels/.rels": rels, "word/document.xml": doc,
                 "word/_rels/document.xml.rels": drels, "word/numbering.xml": num}
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            for name, data in parts.items():
                z.writestr(name, data)
        return parts


# Child order inside w:pPr / w:rPr / w:tcPr is fixed by the WordprocessingML schema.
# Pages, Google Docs and Quick Look tolerate it out of order; Word does not.
SCHEMA_ORDER = {
    "pPr": ["pStyle", "keepNext", "keepLines", "pageBreakBefore", "framePr", "widowControl",
            "numPr", "suppressLineNumbers", "pBdr", "shd", "tabs", "suppressAutoHyphens",
            "kinsoku", "wordWrap", "overflowPunct", "topLinePunct", "autoSpaceDE", "autoSpaceDN",
            "bidi", "adjustRightInd", "snapToGrid", "spacing", "ind", "contextualSpacing",
            "mirrorIndents", "suppressOverlap", "jc"],
    "rPr": ["rStyle", "rFonts", "b", "bCs", "i", "iCs", "caps", "smallCaps", "strike", "dstrike",
            "outline", "shadow", "emboss", "imprint", "noProof", "snapToGrid", "vanish",
            "webHidden", "color", "spacing", "w", "kern", "position", "sz", "szCs", "highlight",
            "u", "effect", "bdr", "shd"],
    "tcPr": ["cnfStyle", "tcW", "gridSpan", "hMerge", "vMerge", "tcBorders", "shd", "noWrap",
             "tcMar", "textDirection", "tcFitText", "vAlign", "hideMark"],
}


def check_order(dom):
    for tag, order in SCHEMA_ORDER.items():
        for el in dom.getElementsByTagName("w:" + tag):
            kids = [k.tagName[2:] for k in el.childNodes if k.nodeType == k.ELEMENT_NODE]
            idx = [order.index(k) for k in kids if k in order]
            assert idx == sorted(idx), f"w:{tag} children out of schema order: {kids}"


def validate(path):
    z = zipfile.ZipFile(path)
    assert z.testzip() is None, "corrupt zip"
    for part in ("[Content_Types].xml", "_rels/.rels", "word/document.xml",
                 "word/_rels/document.xml.rels", "word/numbering.xml"):
        assert part in z.namelist(), f"missing part {part}"
        xml.dom.minidom.parseString(z.read(part))
    ct = z.read("[Content_Types].xml")
    assert b"/word/document.xml" in ct and b"/word/numbering.xml" in ct, "missing content-type override"
    doc = z.read("word/document.xml").decode("utf-8")
    check_order(xml.dom.minidom.parseString(doc))
    check_order(xml.dom.minidom.parseString(z.read("word/numbering.xml")))
    assert doc.count("<w:t ") == doc.count('w:ascii="Georgia"'), "a text run lacks the Georgia font"
    return re.sub(r"<[^>]+>", " ", doc)


SECTION_TYPES = ("paragraph", "roles", "groups", "bullets", "columns", "fields", "footer")


def main():
    if len(sys.argv) == 2 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return
    if len(sys.argv) != 3:
        sys.exit("usage: build_docx.py content.json|- output.docx   (--help for the content format)")
    src = sys.stdin if sys.argv[1] == "-" else open(sys.argv[1], encoding="utf-8")
    spec = json.load(src)
    d = Doc(spec.get("palette", {}))
    d.header(spec.get("header", {}))
    for s in spec.get("sections", []):
        kind = s.get("type")
        if kind not in SECTION_TYPES:
            raise ValueError(f"unknown section type {kind!r}; use one of {', '.join(SECTION_TYPES)}")
        getattr(d, kind)(s)
    d.save(sys.argv[2])
    text = validate(sys.argv[2])
    words = len(text.split())
    pages = d.lines / PAGE_LINES
    print(f"wrote {sys.argv[2]} · {words} words · ~{d.lines:.0f} of {PAGE_LINES} lines per page "
          f"(modelled ~{pages:.2f} pages) · palette ink #{d.ink} brand #{d.brand} muted #{d.muted} "
          f"· package valid")


if __name__ == "__main__":
    try:
        main()
    except KeyError as e:
        sys.exit(f"build failed: a section is missing the field {e} (run --help for the content format)")
    except (AssertionError, ValueError, json.JSONDecodeError) as e:
        sys.exit(f"build failed: {e}")
