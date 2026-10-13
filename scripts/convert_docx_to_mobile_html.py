#!/usr/bin/env python3
"""Convert the generated Word report into a self-contained mobile HTML page."""

from __future__ import annotations

import argparse
import base64
import html
import mimetypes
from pathlib import Path

from docx.document import Document as DocumentType
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx import Document


def iter_blocks(parent):
    if isinstance(parent, DocumentType):
        element = parent.element.body
    elif isinstance(parent, _Cell):
        element = parent._tc
    else:
        raise TypeError(type(parent))
    for child in element.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)


def image_data_uri(document, run) -> list[str]:
    result = []
    for blip in run._element.xpath('.//a:blip'):
        rel_id = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
        if not rel_id:
            continue
        part = document.part.related_parts.get(rel_id)
        if part is None:
            continue
        content_type = getattr(part, 'content_type', None) or mimetypes.guess_type(str(part.partname))[0] or 'image/png'
        encoded = base64.b64encode(part.blob).decode('ascii')
        result.append(f'<img src="data:{html.escape(content_type)};base64,{encoded}" loading="lazy" alt="报告图表">')
    return result


def render_paragraph(document, paragraph) -> str:
    chunks = []
    for run in paragraph.runs:
        text = html.escape(run.text or '').replace('\n', '<br>')
        if text:
            if run.bold:
                text = f'<strong>{text}</strong>'
            if run.italic:
                text = f'<em>{text}</em>'
            chunks.append(text)
        chunks.extend(image_data_uri(document, run))
    if not chunks and paragraph.text:
        chunks.append(html.escape(paragraph.text))
    return ''.join(chunks).strip()


def paragraph_tag(paragraph, content: str) -> str:
    if not content:
        return ''
    style = paragraph.style.name if paragraph.style else ''
    if style == 'Title' or style.startswith('Title'):
        return f'<h1>{content}</h1>'
    for level in (1, 2, 3, 4, 5, 6):
        if style.startswith(f'Heading {level}'):
            return f'<h{min(level + 1, 6)}>{content}</h{min(level + 1, 6)}>'
    if 'Caption' in style or content.startswith('图：'):
        return f'<p class="caption">{content}</p>'
    if '<img ' in content:
        return f'<figure>{content}</figure>'
    return f'<p>{content}</p>'


def render_cell(document, cell) -> str:
    parts = []
    for block in iter_blocks(cell):
        if isinstance(block, Paragraph):
            content = render_paragraph(document, block)
            if content:
                parts.append(content)
    return '<br>'.join(parts)


def render_table(document, table) -> str:
    rows = []
    for row_index, row in enumerate(table.rows):
        cells = []
        for cell in row.cells:
            tag = 'th' if row_index == 0 else 'td'
            cells.append(f'<{tag}>{render_cell(document, cell)}</{tag}>')
        rows.append('<tr>' + ''.join(cells) + '</tr>')
    return '<div class="table-wrap"><table>' + ''.join(rows) + '</table></div>'


def convert(input_path: Path, output_path: Path) -> None:
    document = Document(str(input_path))
    blocks = []
    for block in iter_blocks(document):
        if isinstance(block, Paragraph):
            rendered = paragraph_tag(block, render_paragraph(document, block))
        else:
            rendered = render_table(document, block)
        if rendered:
            blocks.append(rendered)
    body = '\n'.join(blocks)
    title = html.escape(input_path.stem.replace('_', ' '))
    page = f'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{ color-scheme: light; --ink:#17202a; --muted:#64748b; --line:#d8dee8; --blue:#1f4e78; --soft:#f4f7fa; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:#eef2f6; color:var(--ink); font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",Arial,sans-serif; line-height:1.65; }}
    main {{ max-width:980px; margin:0 auto; padding:18px 14px 42px; background:#fff; min-height:100vh; }}
    h1 {{ font-size:clamp(23px,5vw,36px); line-height:1.25; margin:0 0 18px; color:#111827; }}
    h2 {{ font-size:clamp(19px,4vw,26px); line-height:1.35; margin:30px 0 10px; color:var(--blue); border-bottom:2px solid #dbe7f1; padding-bottom:6px; }}
    h3,h4,h5,h6 {{ color:var(--blue); margin:22px 0 8px; line-height:1.4; }}
    p {{ margin:8px 0 12px; font-size:16px; }}
    figure {{ margin:16px 0 8px; text-align:center; overflow-x:auto; }}
    figure img {{ display:block; max-width:100%; height:auto; margin:0 auto; }}
    .caption {{ color:var(--muted); font-size:13px; font-style:italic; margin-top:2px; }}
    .table-wrap {{ width:100%; overflow-x:auto; margin:14px 0 18px; border:1px solid var(--line); }}
    table {{ border-collapse:collapse; width:100%; min-width:620px; font-size:13px; }}
    th {{ background:var(--blue); color:#fff; font-weight:700; text-align:left; }}
    th,td {{ border:1px solid var(--line); padding:7px 8px; vertical-align:top; }}
    tr:nth-child(even) td {{ background:var(--soft); }}
    img {{ max-width:100%; }}
    strong {{ color:#111827; }}
    @media (min-width:700px) {{ main {{ padding:28px 42px 54px; }} p {{ font-size:17px; }} }}
  </style>
</head>
<body><main>{body}</main></body>
</html>
'''
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(page, encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    convert(args.input, args.output)
    print(args.output)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
