#!/usr/bin/env python
"""Render a simple Markdown recap into a Word .docx file.

This helper intentionally uses only the Python standard library so the
us-market-daily-recap skill can produce Word files even when python-docx is
not installed. It supports headings, paragraphs, bullet/numbered lines,
Markdown tables, and local image tags like:

![caption](D:/codex/path/chart.png)
"""

from __future__ import annotations

import argparse
import datetime as _dt
import html
import mimetypes
import pathlib
import re
import struct
import zipfile


NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
}

STOCK_TERMS = sorted(
    {
        # Individual companies and single-stock tickers only.
        # Do not include indices, ETFs, sectors, or basket codes here.
        "Nvidia",
        "NVDA",
        "OpenAI",
        "Micron",
        "MU",
        "SanDisk",
        "SNDK",
        "AMD",
        "Applied Materials",
        "AMAT",
        "ASML",
        "SK Hynix",
        "Samsung",
        "Corning",
        "GLW",
        "Dell",
        "DELL",
        "Marvell",
        "MRVL",
        "Intel",
        "INTC",
        "Apple",
        "AAPL",
        "Microsoft",
        "MSFT",
        "Alphabet",
        "GOOGL",
        "GOOG",
        "Amazon",
        "AMZN",
        "Meta",
        "META",
        "Oracle",
        "ORCL",
        "Salesforce",
        "CRM",
        "IBM",
        "ServiceNow",
        "NOW",
        "Workday",
        "WDAY",
        "Intuit",
        "INTU",
        "Atlassian",
        "TEAM",
        "Infosys",
        "INFY",
        "Wipro",
        "WIT",
        "Cognizant",
        "CTSH",
        "Palo Alto",
        "PANW",
        "CrowdStrike",
        "CRWD",
        "Cisco",
        "CSCO",
        "Fortinet",
        "FTNT",
        "Lumentum",
        "LITE",
        "Coherent",
        "COHR",
        "Western Digital",
        "WDC",
        "Seagate",
        "STX",
        "Digital Realty",
        "DLR",
        "Equinix",
        "EQIX",
        "CoreWeave",
        "CRWV",
        # Meme, retail momentum, and speculative growth.
        "GameStop",
        "GME",
        "AMC",
        "Opendoor",
        "OPEN",
        "Reddit",
        "RDDT",
        "MicroStrategy",
        "Strategy",
        "MSTR",
        "Coinbase",
        "COIN",
        "Nike",
        "NKE",
        "Wendy's",
        "WEN",
        "Rocket Lab",
        "RKLB",
        # Non-tech.
        "Coca-Cola",
        "KO",
        "Unilever",
        "UL",
        "Walmart",
        "WMT",
        "PepsiCo",
        "PEP",
        "Procter & Gamble",
        "PG",
        "Royal Caribbean",
        "RCL",
        "Home Depot",
        "HD",
        "McDonald's",
        "MCD",
        "Tesla",
        "TSLA",
        "LVMH",
        "Hermes",
        "Richemont",
        "Tapestry",
        "TPR",
        "Ralph Lauren",
        "RL",
        "Estee Lauder",
        "EL",
        "Capri",
        "CPRI",
        "PayPal",
        "PYPL",
        "Visa",
        "American Express",
        "AXP",
        "Boeing",
        "BA",
        "Illinois Tool Works",
        "ITW",
        "UPS",
        "Exxon",
        "XOM",
        "Chevron",
        "CVX",
        "ConocoPhillips",
        "COP",
        "SLB",
        "Sherwin-Williams",
        "SHW",
        "Freeport-McMoRan",
        "FCX",
        "Newmont",
        "NEM",
        "Amgen",
        "AMGN",
        "Johnson & Johnson",
        "JNJ",
        "IQVIA",
        "IQV",
        "Tenet",
        "THC",
        "Bristol Myers",
        "BMY",
        # Common earnings/mover anchors that frequently appear in daily recaps.
        "Vertiv",
        "VRT",
        "KLA",
        "KLAC",
        "Garmin",
        "GRMN",
        "GE HealthCare",
        "GEHC",
        "SoFi",
        "SOFI",
        "Hims & Hers",
        "HIMS",
        "Humana",
        "HUM",
        "Procter & Gamble",
        "P&G",
        "Caterpillar",
        "CAT",
        "Goldman Sachs",
        "GS",
        "Visa",
        "V",
        "Ford",
        "F",
        "Qualcomm",
        "QCOM",
        "Starbucks",
        "SBUX",
        "Fortinet",
        "FTNT",
        "Snowflake",
        "SNOW",
        "Datadog",
        "DDOG",
        "Warner Bros. Discovery",
        "Warner Bros",
        "WBD",
        "Honeywell",
        "HON",
        "Honeywell Aerospace",
        "Molson Coors",
        "TAP",
        "HubSpot",
        "HUBS",
        "Figma",
        "FIG",
        "Duolingo",
        "DUOL",
        "Robinhood",
        "HOOD",
        "Woodward",
        "WWD",
        "Teva",
        "TEVA",
        "Kering",
        "PPRUY",
        "Amazon",
        "BlackBerry",
        "BB",
        "Roblox",
        "RBLX",
        "AXT",
        "AXTI",
        "USA Rare Earth",
        "USAR",
        "Alibaba",
        "BABA",
        "Mastercard",
        "MA",
        "Adidas",
        "ADDYY",
        "MarketAxess",
        "MKTX",
        "Intercontinental Exchange",
        "ICE",
        "Chipotle",
        "CMG",
        "Yum Brands",
        "YUM",
        "Shell",
        "SHEL",
        "AB InBev",
        "BUD",
        "Guardant Health",
        "GH",
        "Illumina",
        "ILMN",
        "Veracyte",
        "VCYT",
        "Eli Lilly",
        "LLY",
        "Lam Research",
        "LRCX",
        "Broadcom",
        "AVGO",
        "Adobe",
        "ADBE",
        "Applovin",
        "APP",
        "Applied Optoelectronics",
        "AAOI",
        "IREN",
        "Coinbase",
        "COIN",
        "Novo Nordisk",
        "NVO",
        "Luckin Coffee",
        "LKNCY",
        "XPeng",
        "XPEV",
        "Corsair",
        "CRSR",
        "Shopify",
        "SHOP",
        "Merck",
        "MRK",
        "Pfizer",
        "PFE",
        "Transocean",
        "RIG",
        "eBay",
        "EBAY",
        "United States Antimony",
        "UAMY",
        "Moderna",
        "MRNA",
        "Exxon Mobil",
        "ExxonMobil",
        "First Solar",
        "FSLR",
        "Dexcom",
        "DXCM",
        "Monolithic Power",
        "MPWR",
        "One Stop Systems",
        "OSS",
        "Palantir",
        "PLTR",
        "Snap",
        "SNAP",
        "SELLAS",
        "SLS",
        "Backblaze",
        "BLZE",
        "Sterling Construction",
        "STRL",
        "DraftKings",
        "DKNG",
        "Better Home",
        "BETR",
        "Spotify",
        "SPOT",
        "Alnylam",
        "ALNY",
        "Pinterest",
        "PINS",
        "Toast",
        "TOST",
        "Circle Internet",
        "CRCL",
        "Fastly",
        "FSLY",
        "Axon",
        "AXON",
        "Centrus Energy",
        "LEU",
        "FTAI Aviation",
        "FTAI",
        "SpaceX",
        "SPCE",
        "AstraZeneca",
        "AZN",
        "Marriott",
        "MAR",
        "Tyson Foods",
        "TSN",
        "Newell Brands",
        "NWL",
        "Ferguson",
        "FERG",
        "Circle",
        "Caterpillar",
        "McDonald's",
        "MCD",
        "Zeta Global",
        "ZETA",
        "Digital Turbine",
        "APPS",
        "Kratos Defense",
        "Kratos",
        "KTOS",
        "Amprius",
        "AMPX",
        "Lucid",
        "LCID",
        "Verizon",
        "VZ",
        "AT&T",
        "Upstart",
        "UPST",
        "Astera Labs",
        "ALAB",
        "Innodata",
        "INOD",
        "SpaceX",
        "SPCX",
        "Bed Bath & Beyond",
        "BBBY",
        "Cipher Mining",
        "CIFR",
        "T-Mobile",
        "TMUS",
        "TransMedics",
        "TMDX",
        "Uber",
        "UBER",
        "Carnival",
        "CCL",
        "Northrop Grumman",
        "NOC",
        "Serve Robotics",
        "SERV",
        "BP",
        "HSBC",
        "Prologis",
        "PLD",
        "Segro",
        "Zebra Technologies",
        "ZBRA",
        "Paymentus",
        "PAY",
        "Datadog",
        "DDOG",
        "Disney",
        "DIS",
        "Shake Shack",
        "SHAK",
        "Flutter",
        "FLUT",
        "Arista Networks",
        "ANET",
        "CVS Health",
        "CVS",
        "Insulet",
        "PODD",
        "Booking",
        "BKNG",
        "SolarEdge",
        "SEDG",
        "Shopify",
        "Falkland Oil",
        "Falklands Oil",
        "FALKL",
        "Glencore",
        "GLEN",
        "Honda",
        "Toy Story",
    },
    key=len,
    reverse=True,
)
STOCK_RE = re.compile(
    r"(?<![A-Za-z0-9&./'-])(" + "|".join(re.escape(term) for term in STOCK_TERMS) + r")(?![A-Za-z0-9&./'-])"
)


def x(text: str) -> str:
    return html.escape(text, quote=True)


def strip_links(text: str) -> str:
    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)


def run(text: str, bold: bool = False, underline: bool = False, highlight: bool = False, code: bool = False) -> str:
    props = []
    if bold:
        props.append("<w:b/>")
    if underline:
        props.append('<w:u w:val="single"/>')
    if highlight:
        props.append('<w:highlight w:val="yellow"/>')
    if code:
        props.append('<w:shd w:val="clear" w:color="auto" w:fill="EDEDED"/>')
    rpr = f"<w:rPr>{''.join(props)}</w:rPr>" if props else ""
    return f"<w:r>{rpr}<w:t xml:space=\"preserve\">{x(text)}</w:t></w:r>"


def stock_shaded_runs(text: str, default_bold: bool = False, shade_stocks: bool = True) -> str:
    if not shade_stocks:
        return run(text, bold=default_bold)
    out = []
    pos = 0
    for match in STOCK_RE.finditer(text):
        if match.start() > pos:
            out.append(run(text[pos : match.start()], bold=default_bold))
        out.append(run(match.group(0), bold=default_bold, code=True))
        pos = match.end()
    if pos < len(text):
        out.append(run(text[pos:], bold=default_bold))
    return "".join(out)


def inline_runs(text: str, default_bold: bool = False, shade_stocks: bool = True) -> str:
    text = strip_links(text.strip())
    token_re = re.compile(r"(==[^=]+==|__[^_]+__|\*\*[^*]+\*\*|`[^`]+`)")
    out = []
    pos = 0
    for match in token_re.finditer(text):
        if match.start() > pos:
            out.append(stock_shaded_runs(text[pos : match.start()], default_bold=default_bold, shade_stocks=shade_stocks))
        token = match.group(0)
        if token.startswith("=="):
            out.append(run(token[2:-2], bold=default_bold, highlight=True))
        elif token.startswith("__"):
            out.append(run(token[2:-2], bold=default_bold, underline=True))
        elif token.startswith("**"):
            out.append(run(token[2:-2], bold=True))
        elif token.startswith("`"):
            out.append(run(token[1:-1], bold=default_bold, code=True))
        pos = match.end()
    if pos < len(text):
        out.append(stock_shaded_runs(text[pos:], default_bold=default_bold, shade_stocks=shade_stocks))
    return "".join(out) or run("")


def para(text: str = "", style: str | None = None, bold: bool = False, shade_stocks: bool = True) -> str:
    ppr = f"<w:pPr><w:pStyle w:val=\"{style}\"/></w:pPr>" if style else ""
    return f"<w:p>{ppr}{inline_runs(text, default_bold=bold, shade_stocks=shade_stocks)}</w:p>"


def table(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    col_width = max(900, int(9300 / max(len(rows[0]), 1)))
    grid = "".join(f"<w:gridCol w:w=\"{col_width}\"/>" for _ in rows[0])
    body = [f"<w:tbl><w:tblPr><w:tblStyle w:val=\"TableGrid\"/><w:tblW w:w=\"0\" w:type=\"auto\"/></w:tblPr><w:tblGrid>{grid}</w:tblGrid>"]
    for ridx, row in enumerate(rows):
        body.append("<w:tr>")
        for cell in row:
            cell_text = cell.strip()
            shading = "<w:shd w:fill=\"D9EAF7\"/>" if ridx == 0 else ""
            body.append(
                "<w:tc><w:tcPr>"
                f"<w:tcW w:w=\"{col_width}\" w:type=\"dxa\"/>"
                f"{shading}"
                "</w:tcPr>"
                f"{para(cell_text, shade_stocks=False)}"
                "</w:tc>"
            )
        body.append("</w:tr>")
    body.append("</w:tbl>")
    return "".join(body)


def png_size(data: bytes) -> tuple[int, int] | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        return struct.unpack(">II", data[16:24])
    return None


def jpeg_size(data: bytes) -> tuple[int, int] | None:
    if not data.startswith(b"\xff\xd8"):
        return None
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        i += 2
        if marker in {0xD8, 0xD9}:
            continue
        if i + 2 > len(data):
            break
        length = struct.unpack(">H", data[i : i + 2])[0]
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            if i + 7 <= len(data):
                height = struct.unpack(">H", data[i + 3 : i + 5])[0]
                width = struct.unpack(">H", data[i + 5 : i + 7])[0]
                return width, height
        i += length
    return None


def image_size(path: pathlib.Path) -> tuple[int, int]:
    data = path.read_bytes()
    return png_size(data) or jpeg_size(data) or (1200, 800)


def image_paragraph(rid: str, image_name: str, width_px: int, height_px: int, caption: str) -> str:
    max_width_emu = 6_000_000
    ratio = height_px / max(width_px, 1)
    cx = max_width_emu
    cy = int(cx * ratio)
    descr = x(caption or image_name)
    return f"""
<w:p>
  <w:r>
    <w:drawing>
      <wp:inline distT="0" distB="0" distL="0" distR="0">
        <wp:extent cx="{cx}" cy="{cy}"/>
        <wp:docPr id="1" name="{x(image_name)}" descr="{descr}"/>
        <a:graphic xmlns:a="{NS['a']}">
          <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
            <pic:pic xmlns:pic="{NS['pic']}">
              <pic:nvPicPr><pic:cNvPr id="0" name="{x(image_name)}"/><pic:cNvPicPr/></pic:nvPicPr>
              <pic:blipFill><a:blip r:embed="{rid}" xmlns:r="{NS['r']}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>
              <pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>
            </pic:pic>
          </a:graphicData>
        </a:graphic>
      </wp:inline>
    </w:drawing>
  </w:r>
</w:p>
"""


def parse_table(lines: list[str], start: int) -> tuple[str, int] | None:
    if start + 1 >= len(lines):
        return None
    if not (lines[start].lstrip().startswith("|") and lines[start + 1].lstrip().startswith("|")):
        return None
    sep = lines[start + 1]
    if not re.fullmatch(r"\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*", sep):
        return None
    rows = []
    i = start
    while i < len(lines) and lines[i].lstrip().startswith("|"):
        if i != start + 1:
            row = [c.strip() for c in lines[i].strip().strip("|").split("|")]
            rows.append(row)
        i += 1
    return table(rows), i


def render_markdown(markdown: str, base_dir: pathlib.Path) -> tuple[str, list[tuple[pathlib.Path, str, str]]]:
    lines = markdown.splitlines()
    chunks: list[str] = []
    images: list[tuple[pathlib.Path, str, str]] = []
    i = 0
    image_re = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            i += 1
            continue
        parsed = parse_table(lines, i)
        if parsed:
            tbl, i = parsed
            chunks.append(tbl)
            continue
        img_match = image_re.search(line)
        if img_match:
            caption, raw_path = img_match.group(1), img_match.group(2).strip()
            img_path = pathlib.Path(raw_path)
            if not img_path.is_absolute():
                img_path = base_dir / img_path
            if img_path.exists():
                rid = f"rIdImg{len(images) + 1}"
                images.append((img_path, rid, caption))
                w, h = image_size(img_path)
                chunks.append(image_paragraph(rid, img_path.name, w, h, caption))
                if caption:
                    chunks.append(para(f"Source/Caption: {caption}", style="Caption"))
            else:
                chunks.append(para(f"[Missing image: {raw_path}] {caption}"))
            i += 1
            continue
        if line.startswith("### "):
            chunks.append(para(line[4:], style="Heading3"))
        elif line.startswith("## "):
            chunks.append(para(line[3:], style="Heading2"))
        elif line.startswith("# "):
            chunks.append(para(line[2:], style="Heading1"))
        elif line.lstrip().startswith("- "):
            chunks.append(para("- " + line.lstrip()[2:], style="ListParagraph"))
        elif re.match(r"\s*\d+\.\s+", line):
            chunks.append(para(line.strip(), style="ListParagraph"))
        else:
            chunks.append(para(line))
        i += 1
    return "\n".join(chunks), images


def content_types(images: list[tuple[pathlib.Path, str, str]]) -> str:
    defaults = {
        "rels": "application/vnd.openxmlformats-package.relationships+xml",
        "xml": "application/xml",
    }
    for path, _, _ in images:
        ext = path.suffix.lower().lstrip(".")
        if ext:
            defaults[ext] = mimetypes.types_map.get(path.suffix.lower(), "application/octet-stream")
    items = [f'<Default Extension="{x(ext)}" ContentType="{x(ct)}"/>' for ext, ct in defaults.items()]
    items.append('<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>')
    items.append('<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>')
    items.append('<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>')
    items.append('<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>')
    return f'<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">{"".join(items)}</Types>'


def root_rels() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""


def document_rels(images: list[tuple[pathlib.Path, str, str]]) -> str:
    rels = ['<Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>']
    for idx, (path, rid, _) in enumerate(images, start=1):
        rels.append(f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image{idx}{x(path.suffix.lower())}"/>')
    return f'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{"".join(rels)}</Relationships>'


def styles_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:pPr><w:spacing w:after="140" w:line="330" w:lineRule="auto"/></w:pPr><w:rPr><w:sz w:val="21"/><w:szCs w:val="21"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:before="260" w:after="160" w:line="330" w:lineRule="auto"/></w:pPr><w:rPr><w:b/><w:sz w:val="32"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:before="220" w:after="130" w:line="330" w:lineRule="auto"/></w:pPr><w:rPr><w:b/><w:sz w:val="26"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:before="180" w:after="100" w:line="330" w:lineRule="auto"/></w:pPr><w:rPr><w:b/><w:sz w:val="23"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Caption"><w:name w:val="caption"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="100" w:line="300" w:lineRule="auto"/></w:pPr><w:rPr><w:i/><w:sz w:val="18"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/><w:basedOn w:val="Normal"/><w:pPr><w:ind w:left="360"/><w:spacing w:after="100" w:line="330" w:lineRule="auto"/></w:pPr></w:style>
  <w:style w:type="table" w:styleId="TableGrid"><w:name w:val="Table Grid"/><w:tblPr><w:tblBorders><w:top w:val="single" w:sz="4" w:color="BFBFBF"/><w:left w:val="single" w:sz="4" w:color="BFBFBF"/><w:bottom w:val="single" w:sz="4" w:color="BFBFBF"/><w:right w:val="single" w:sz="4" w:color="BFBFBF"/><w:insideH w:val="single" w:sz="4" w:color="BFBFBF"/><w:insideV w:val="single" w:sz="4" w:color="BFBFBF"/></w:tblBorders></w:tblPr></w:style>
</w:styles>"""


def document_xml(body: str) -> str:
    namespaces = " ".join(f'xmlns:{k}="{v}"' for k, v in NS.items())
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document {namespaces}>
  <w:body>
    {body}
    <w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="850" w:right="850" w:bottom="850" w:left="850" w:header="708" w:footer="708" w:gutter="0"/></w:sectPr>
  </w:body>
</w:document>"""


def core_xml(title: str) -> str:
    now = _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>{x(title)}</dc:title>
  <dc:creator>Codex</dc:creator>
  <cp:lastModifiedBy>Codex</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>
</cp:coreProperties>"""


def app_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Codex</Application>
</Properties>"""


def write_docx(markdown_path: pathlib.Path, output_path: pathlib.Path, title: str | None) -> None:
    markdown = markdown_path.read_text(encoding="utf-8")
    body, images = render_markdown(markdown, markdown_path.parent)
    title = title or markdown_path.stem
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types(images))
        zf.writestr("_rels/.rels", root_rels())
        zf.writestr("word/document.xml", document_xml(body))
        zf.writestr("word/_rels/document.xml.rels", document_rels(images))
        zf.writestr("word/styles.xml", styles_xml())
        zf.writestr("docProps/core.xml", core_xml(title))
        zf.writestr("docProps/app.xml", app_xml())
        for idx, (path, _, _) in enumerate(images, start=1):
            zf.write(path, f"word/media/image{idx}{path.suffix.lower()}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_md", type=pathlib.Path)
    parser.add_argument("output_docx", type=pathlib.Path)
    parser.add_argument("--title", default=None)
    args = parser.parse_args()
    write_docx(args.input_md, args.output_docx, args.title)


if __name__ == "__main__":
    main()
