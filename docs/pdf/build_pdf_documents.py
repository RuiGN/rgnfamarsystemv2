#!/usr/bin/env python3
"""Build polished PDF documents for RGN Farma System.

This generator intentionally avoids the previous generic Markdown converter for
these deliverables because the user needs tighter control: no cropped cover text,
no text over text, guaranteed embedded diagrams and the product logo on cover.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[2]
PDF_DIR = ROOT / 'docs' / 'pdf'
ASSETS_DIR = PDF_DIR / 'assets'
LOGO = ROOT / 'static' / 'vendor' / 'duralux' / 'images' / 'logo_farm_system.png'

COMPANY = 'RGN SYSTEMS TECNOLOGIA INOVA SIMPLES (I.S.)'
CNPJ = '67.956.492/0001-64'
ADDRESS = 'Rua Doutor Joao Marques, 60 — Ilha do Retiro — Recife/PE — CEP 50750-320'
DOC_DATE = '21/07/2026'

ACCENT = colors.HexColor('#0284C7')
ACCENT_DARK = colors.HexColor('#0F3B5F')
INK = colors.HexColor('#0F172A')
MUTED = colors.HexColor('#475569')
LINE = colors.HexColor('#CBD5E1')
LIGHT = colors.HexColor('#EFF6FF')
VERY_LIGHT = colors.HexColor('#F8FAFC')


@dataclass(frozen=True)
class DocumentSpec:
    source: Path
    output: Path
    title: str
    subtitle: str
    kind: str


def register_fonts() -> None:
    fonts = {
        'RGN-Sans': '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        'RGN-Sans-Bold': '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        'RGN-Mono': '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf',
    }
    for name, path in fonts.items():
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, path))


def make_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        'cover_title': ParagraphStyle(
            'cover_title',
            parent=base['Title'],
            fontName='RGN-Sans-Bold',
            fontSize=27,
            leading=32,
            textColor=colors.white,
            alignment=TA_CENTER,
            spaceAfter=8 * mm,
        ),
        'cover_subtitle': ParagraphStyle(
            'cover_subtitle',
            parent=base['BodyText'],
            fontName='RGN-Sans',
            fontSize=12,
            leading=17,
            textColor=colors.HexColor('#E0F2FE'),
            alignment=TA_CENTER,
            spaceAfter=8 * mm,
        ),
        'cover_meta': ParagraphStyle(
            'cover_meta',
            parent=base['BodyText'],
            fontName='RGN-Sans',
            fontSize=9.5,
            leading=13,
            textColor=colors.white,
            alignment=TA_CENTER,
        ),
        'h1': ParagraphStyle(
            'h1',
            parent=base['Heading1'],
            fontName='RGN-Sans-Bold',
            fontSize=20,
            leading=25,
            textColor=ACCENT_DARK,
            spaceBefore=8 * mm,
            spaceAfter=4 * mm,
            keepWithNext=True,
        ),
        'h2': ParagraphStyle(
            'h2',
            parent=base['Heading2'],
            fontName='RGN-Sans-Bold',
            fontSize=15,
            leading=20,
            textColor=ACCENT_DARK,
            spaceBefore=6 * mm,
            spaceAfter=3 * mm,
            keepWithNext=True,
        ),
        'h3': ParagraphStyle(
            'h3',
            parent=base['Heading3'],
            fontName='RGN-Sans-Bold',
            fontSize=12.2,
            leading=16,
            textColor=INK,
            spaceBefore=4 * mm,
            spaceAfter=2 * mm,
            keepWithNext=True,
        ),
        'body': ParagraphStyle(
            'body',
            parent=base['BodyText'],
            fontName='RGN-Sans',
            fontSize=9.4,
            leading=13.4,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=2.3 * mm,
            splitLongWords=True,
        ),
        'bullet': ParagraphStyle(
            'bullet',
            parent=base['BodyText'],
            fontName='RGN-Sans',
            fontSize=9.2,
            leading=12.7,
            leftIndent=5 * mm,
            firstLineIndent=0,
            bulletIndent=0,
            spaceAfter=1.2 * mm,
            textColor=INK,
            splitLongWords=True,
        ),
        'code': ParagraphStyle(
            'code',
            parent=base['Code'],
            fontName='RGN-Mono',
            fontSize=7.2,
            leading=9.2,
            backColor=colors.HexColor('#F1F5F9'),
            borderColor=LINE,
            borderWidth=0.4,
            borderPadding=5,
            textColor=colors.HexColor('#1E293B'),
            splitLongWords=True,
            spaceBefore=2 * mm,
            spaceAfter=3 * mm,
        ),
        'table_header': ParagraphStyle(
            'table_header',
            parent=base['BodyText'],
            fontName='RGN-Sans-Bold',
            fontSize=8,
            leading=10.5,
            textColor=colors.white,
            splitLongWords=True,
        ),
        'table_cell': ParagraphStyle(
            'table_cell',
            parent=base['BodyText'],
            fontName='RGN-Sans',
            fontSize=7.7,
            leading=10,
            textColor=INK,
            splitLongWords=True,
        ),
        'caption': ParagraphStyle(
            'caption',
            parent=base['BodyText'],
            fontName='RGN-Sans',
            fontSize=8,
            leading=10,
            textColor=MUTED,
            alignment=TA_CENTER,
            spaceAfter=4 * mm,
        ),
    }


def strip_frontmatter(markdown: str) -> str:
    if markdown.startswith('---'):
        parts = markdown.split('---', 2)
        if len(parts) == 3:
            return parts[2].lstrip()
    return markdown


def clean_inline(text: str) -> str:
    raw = text.strip()
    code_spans: list[str] = []

    def hold_code(match: re.Match[str]) -> str:
        code_spans.append(html.escape(match.group(1)))
        return f'@@CODE{len(code_spans) - 1}@@'

    raw = re.sub(r'`([^`]+)`', hold_code, raw)
    text = html.escape(raw)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
    # Avoid treating technical globs such as /api/* as emphasis.
    text = re.sub(r'(?<!/)\*([^*\s][^*]*?)\*', r'<i>\1</i>', text)
    for idx, code in enumerate(code_spans):
        text = text.replace(f'@@CODE{idx}@@', f"<font name='RGN-Mono'>{code}</font>")
    return text


def image_flowable(path: Path, max_width: float, max_height: float) -> Image:
    img = Image(str(path))
    ratio = min(max_width / img.imageWidth, max_height / img.imageHeight, 1.0)
    img.drawWidth = img.imageWidth * ratio
    img.drawHeight = img.imageHeight * ratio
    img.hAlign = 'CENTER'
    return img


def table_widths(rows: list[list[str]], available: float) -> list[float]:
    cols = max(len(r) for r in rows)
    if cols == 2:
        return [available * 0.27, available * 0.73]
    if cols == 3:
        return [available * 0.42, available * 0.23, available * 0.35]
    if cols == 4:
        return [available * 0.26, available * 0.18, available * 0.18, available * 0.38]
    return [available / cols] * cols


def parse_table(lines: list[str], styles: dict[str, ParagraphStyle], available: float) -> Table:
    rows: list[list[str]] = []
    for line in lines:
        values = [cell.strip() for cell in line.strip().strip('|').split('|')]
        if all(set(cell) <= {'-', ':', ' '} for cell in values):
            continue
        rows.append(values)
    cols = max(len(r) for r in rows)
    normalized = [r + [''] * (cols - len(r)) for r in rows]
    data = []
    for ri, row in enumerate(normalized):
        style = styles['table_header'] if ri == 0 else styles['table_cell']
        data.append([Paragraph(clean_inline(cell), style) for cell in row])
    table = Table(
        data, colWidths=table_widths(normalized, available), repeatRows=1, splitByRow=True
    )
    table.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, 0), ACCENT_DARK),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, VERY_LIGHT]),
                ('GRID', (0, 0), (-1, -1), 0.35, LINE),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def parse_markdown(
    markdown: str, styles: dict[str, ParagraphStyle], input_dir: Path, available: float
) -> list:
    md = strip_frontmatter(markdown)
    lines = md.splitlines()
    story: list = []
    para: list[str] = []
    code: list[str] = []
    in_code = False
    table_lines: list[str] = []
    skipped_first_h1 = False

    def flush_para() -> None:
        nonlocal para
        if para:
            story.append(Paragraph(clean_inline(' '.join(para)), styles['body']))
            para = []

    def flush_table() -> None:
        nonlocal table_lines
        if table_lines:
            flush_para()
            story.append(parse_table(table_lines, styles, available))
            story.append(Spacer(1, 3 * mm))
            table_lines = []

    for raw in lines + ['']:
        line = raw.rstrip()
        stripped = line.strip()

        if stripped.startswith('```'):
            flush_table()
            flush_para()
            if in_code:
                text = '<br/>'.join(
                    html.escape(code_line).replace(' ', '&nbsp;') for code_line in code
                )
                story.append(Paragraph(text, styles['code']))
                code = []
                in_code = False
            else:
                in_code = True
                code = []
            continue
        if in_code:
            code.append(line[:120])
            continue

        if stripped.startswith('|'):
            flush_para()
            table_lines.append(stripped)
            continue
        flush_table()

        image_match = re.match(r'!\[(.*?)\]\((.*?)\)', stripped)
        if image_match:
            flush_para()
            image_path = Path(image_match.group(2))
            if not image_path.is_absolute():
                image_path = input_dir / image_path
            if image_path.exists():
                story.append(Spacer(1, 2 * mm))
                story.append(image_flowable(image_path, available, 125 * mm))
                if image_match.group(1):
                    story.append(Paragraph(clean_inline(image_match.group(1)), styles['caption']))
            continue

        if not stripped:
            flush_para()
            continue

        if stripped in {'\\newpage', '---'}:
            flush_para()
            story.append(PageBreak())
            continue

        heading = re.match(r'^(#{1,4})\s+(.+)', stripped)
        if heading:
            flush_para()
            level = len(heading.group(1))
            title = heading.group(2).strip()
            if level == 1 and not skipped_first_h1:
                skipped_first_h1 = True
                continue
            if level == 1:
                story.append(Paragraph(clean_inline(title), styles['h1']))
            elif level == 2:
                story.append(Paragraph(clean_inline(title), styles['h1']))
            elif level == 3:
                story.append(Paragraph(clean_inline(title), styles['h2']))
            else:
                story.append(Paragraph(clean_inline(title), styles['h3']))
            continue

        bullet = re.match(r'^[-*]\s+(.+)', stripped)
        numbered = re.match(r'^\d+\.\s+(.+)', stripped)
        if bullet or numbered:
            flush_para()
            text = (bullet or numbered).group(1)
            marker = '•' if bullet else '•'
            story.append(Paragraph(f'{marker} {clean_inline(text)}', styles['bullet']))
            continue

        para.append(stripped)

    return story


def cover_story(spec: DocumentSpec, styles: dict[str, ParagraphStyle], available: float) -> list:
    logo = image_flowable(LOGO, available, 92 * mm)
    return [
        Spacer(1, 8 * mm),
        logo,
        Spacer(1, 10 * mm),
        Paragraph(clean_inline(spec.title), styles['cover_title']),
        Paragraph(clean_inline(spec.subtitle), styles['cover_subtitle']),
        Spacer(1, 9 * mm),
        Paragraph(clean_inline(f'{spec.kind} • versão 1.0 • {DOC_DATE}'), styles['cover_meta']),
        Spacer(1, 5 * mm),
        Paragraph(clean_inline(COMPANY), styles['cover_meta']),
        Paragraph(clean_inline(f'CNPJ: {CNPJ}'), styles['cover_meta']),
        Paragraph(clean_inline(ADDRESS), styles['cover_meta']),
        PageBreak(),
    ]


def draw_page(canvas, doc, spec: DocumentSpec) -> None:
    page_width, page_height = A4
    if canvas.getPageNumber() == 1:
        canvas.saveState()
        canvas.setFillColor(ACCENT_DARK)
        canvas.rect(0, 0, page_width, page_height, fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor('#08304F'))
        canvas.rect(0, 0, page_width, 42 * mm, fill=1, stroke=0)
        canvas.setStrokeColor(ACCENT)
        canvas.setLineWidth(2)
        canvas.line(24 * mm, 38 * mm, page_width - 24 * mm, 38 * mm)
        canvas.restoreState()
        return

    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(
        doc.leftMargin, page_height - 18 * mm, page_width - doc.rightMargin, page_height - 18 * mm
    )
    canvas.setFont('RGN-Sans-Bold', 8)
    canvas.setFillColor(ACCENT_DARK)
    canvas.drawString(doc.leftMargin, page_height - 15 * mm, 'RGN Farma System')
    canvas.setFont('RGN-Sans', 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(page_width - doc.rightMargin, page_height - 15 * mm, spec.kind)
    canvas.line(doc.leftMargin, 16 * mm, page_width - doc.rightMargin, 16 * mm)
    canvas.setFont('RGN-Sans', 7)
    canvas.drawString(doc.leftMargin, 10.5 * mm, COMPANY)
    canvas.drawRightString(
        page_width - doc.rightMargin, 10.5 * mm, f'Página {canvas.getPageNumber()}'
    )
    canvas.restoreState()


def build(spec: DocumentSpec) -> None:
    styles = make_styles()
    spec.output.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(spec.output),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=25 * mm,
        bottomMargin=23 * mm,
        title=spec.title,
        author=COMPANY,
    )
    story = cover_story(spec, styles, doc.width)
    content = parse_markdown(
        spec.source.read_text(encoding='utf-8'), styles, spec.source.parent, doc.width
    )
    story.extend(content)
    story.append(PageBreak())
    story.extend(back_cover(styles))
    doc.build(
        story,
        onFirstPage=lambda c, d: draw_page(c, d, spec),
        onLaterPages=lambda c, d: draw_page(c, d, spec),
    )


def back_cover(styles: dict[str, ParagraphStyle]) -> list:
    box_style = ParagraphStyle(
        'back',
        parent=styles['body'],
        alignment=TA_CENTER,
        fontSize=10,
        leading=14,
        textColor=INK,
    )
    return [
        Spacer(1, 42 * mm),
        image_flowable(LOGO, 120 * mm, 78 * mm),
        Spacer(1, 12 * mm),
        Paragraph(clean_inline(COMPANY), box_style),
        Paragraph(clean_inline(f'CNPJ: {CNPJ}'), box_style),
        Paragraph(clean_inline(ADDRESS), box_style),
        Spacer(1, 8 * mm),
        Paragraph(
            clean_inline(
                'Documento gerado para homologação, operação assistida e transferência de conhecimento do RGN Farma System.'
            ),
            box_style,
        ),
    ]


def main() -> None:
    register_fonts()
    specs: Iterable[DocumentSpec] = [
        DocumentSpec(
            source=PDF_DIR / 'especificacao_tecnica.md',
            output=PDF_DIR / 'especificacao_tecnica.pdf',
            title='RGN Farma System — Especificação Técnica',
            subtitle='Arquitetura, dockerização, segurança, permissões, integrações e critérios técnicos de homologação.',
            kind='Especificação técnica',
        ),
        DocumentSpec(
            source=PDF_DIR / 'manual_usuario.md',
            output=PDF_DIR / 'manual_usuario.pdf',
            title='RGN Farma System — Manual do Usuário',
            subtitle='Guia operacional para acesso, navegação, cadastros, fluxos, relatórios e boas práticas.',
            kind='Manual do usuário',
        ),
        DocumentSpec(
            source=PDF_DIR / 'especificacao_funcional.md',
            output=PDF_DIR / 'especificacao_funcional.pdf',
            title='RGN Farma System — Especificação Funcional',
            subtitle='Processos, módulos, perfis, regras de negócio, fluxos operacionais e critérios de aceite funcional.',
            kind='Especificação funcional',
        ),
    ]
    for spec in specs:
        build(spec)
        print(f'generated {spec.output}')


if __name__ == '__main__':
    main()
