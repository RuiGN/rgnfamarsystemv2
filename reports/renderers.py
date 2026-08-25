import csv
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from html import escape
from io import BytesIO, StringIO

from django.core.exceptions import ValidationError
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from reports.contracts import ReportColumn, ReportDataset, ReportRow


CSV_BOM = b'\xef\xbb\xbf'
CSV_MIME_TYPE = 'text/csv; charset=utf-8'
XLSX_MIME_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
PDF_MIME_TYPE = 'application/pdf'
SUPPORTED_FORMATS = frozenset({'csv', 'xlsx', 'pdf'})
FORMULA_SIGILS = ('=', '+', '-', '@')
XLSX_TEXT_LIMIT = 32_767
ILLEGAL_CONTROL_PATTERN = re.compile(
    '[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\ud800-\udfff\ufffe\uffff]'
)


@dataclass(frozen=True, slots=True)
class RenderedReport:
    content: bytes
    mime_type: str
    extension: str


def _unsupported_cell() -> ValidationError:
    return ValidationError({'rows': 'O relatório contém um valor de célula não suportado.'})


def _sanitize_text(value: str) -> str:
    normalized_newlines = value.replace('\r\n', '\n').replace('\r', '\n')
    return ILLEGAL_CONTROL_PATTERN.sub('', normalized_newlines)


def _cell(value: object) -> str:
    if value is None:
        return ''
    if type(value) is datetime:
        return value.isoformat()
    if type(value) is date:
        return value.isoformat()
    if type(value) is Decimal:
        return f'{value:.4f}'
    if type(value) is bool:
        return 'True' if value else 'False'
    if type(value) is int or type(value) is float:
        return str(value)
    if type(value) is str:
        return _sanitize_text(value)
    raise _unsupported_cell()


def _spreadsheet_cell(value: object) -> str:
    rendered = _cell(value)
    if type(value) is str and rendered.lstrip().startswith(FORMULA_SIGILS):
        return f"'{rendered}"
    return rendered


def _xlsx_cell(value: object) -> str:
    rendered = _spreadsheet_cell(value)
    if len(rendered) > XLSX_TEXT_LIMIT:
        raise ValidationError(
            {'content': 'O relatório contém uma célula que excede o limite do XLSX.'}
        )
    return rendered


def _spreadsheet_header(column: ReportColumn) -> str:
    return _spreadsheet_cell(column.label)


def _xlsx_header(column: ReportColumn) -> str:
    return _xlsx_cell(column.label)


def _row_values(
    row: ReportRow,
    columns: tuple[ReportColumn, ...],
    *,
    spreadsheet_safe: bool,
) -> list[str]:
    convert = _spreadsheet_cell if spreadsheet_safe else _cell
    return [convert(row.get(column.key)) for column in columns]


def _render_csv(dataset: ReportDataset) -> RenderedReport:
    stream = StringIO(newline='')
    writer = csv.writer(stream, delimiter=';', lineterminator='\r\n')
    writer.writerow([_spreadsheet_header(column) for column in dataset.columns])
    for row in dataset.rows:
        writer.writerow(_row_values(row, dataset.columns, spreadsheet_safe=True))
    return RenderedReport(
        content=CSV_BOM + stream.getvalue().encode('utf-8'),
        mime_type=CSV_MIME_TYPE,
        extension='csv',
    )


def _render_xlsx(dataset: ReportDataset) -> RenderedReport:
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet(title='Relatório')
    stream = BytesIO()
    try:
        sheet.append([_xlsx_header(column) for column in dataset.columns])
        for row in dataset.rows:
            sheet.append([_xlsx_cell(row.get(column.key)) for column in dataset.columns])
        workbook.save(stream)
    except Exception:
        sheet.close()
        raise
    finally:
        workbook.close()
    return RenderedReport(
        content=stream.getvalue(),
        mime_type=XLSX_MIME_TYPE,
        extension='xlsx',
    )


def _paragraph(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(text), style)


def _render_pdf(dataset: ReportDataset) -> RenderedReport:
    if type(dataset.title) is not str:
        raise ValidationError({'title': 'O relatório possui um título inválido.'})

    title_style = ParagraphStyle(
        'ReportTitle',
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=14,
        alignment=TA_LEFT,
        wordWrap='CJK',
        splitLongWords=True,
        spaceAfter=6,
    )
    header_style = ParagraphStyle(
        'ReportHeader',
        fontName='Helvetica-Bold',
        fontSize=6,
        leading=7,
        textColor=colors.white,
        alignment=TA_LEFT,
        wordWrap='CJK',
        splitLongWords=True,
    )
    cell_style = ParagraphStyle(
        'ReportCell',
        fontName='Helvetica',
        fontSize=6,
        leading=7,
        alignment=TA_LEFT,
        wordWrap='CJK',
        splitLongWords=True,
    )

    header: list[Paragraph] = []
    for column in dataset.columns:
        header.append(_paragraph(_sanitize_text(column.label), header_style))

    matrix: list[list[Paragraph]] = [header]
    for row in dataset.rows:
        matrix.append(
            [
                _paragraph(value, cell_style)
                for value in _row_values(row, dataset.columns, spreadsheet_safe=False)
            ]
        )

    page_size = landscape(A4)
    margin = 24
    available_width = page_size[0] - (2 * margin)
    column_width = available_width / len(dataset.columns)
    table = Table(
        matrix,
        colWidths=[column_width] * len(dataset.columns),
        repeatRows=1,
        splitByRow=1,
        splitInRow=1,
        hAlign='LEFT',
    )
    table.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#243447')),
                ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]
        )
    )

    stream = BytesIO()
    document = SimpleDocTemplate(
        stream,
        pagesize=page_size,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=margin,
        title=_sanitize_text(dataset.title),
    )
    document.build(
        [
            _paragraph(_sanitize_text(dataset.title), title_style),
            Spacer(1, 4),
            table,
        ]
    )
    return RenderedReport(
        content=stream.getvalue(),
        mime_type=PDF_MIME_TYPE,
        extension='pdf',
    )


def _validate_columns(columns: tuple[ReportColumn, ...]) -> None:
    keys: set[str] = set()
    for column in columns:
        if type(column.key) is not str or column.key == '' or type(column.label) is not str:
            raise ValidationError({'columns': 'O relatório contém uma coluna inválida.'})
        if column.key in keys:
            raise ValidationError({'columns': 'O relatório contém uma coluna inválida.'})
        keys.add(column.key)


def render_report(dataset: ReportDataset, export_format: object) -> RenderedReport:
    if type(export_format) is not str or export_format not in SUPPORTED_FORMATS:
        raise ValidationError({'export_format': 'Formato de exportação não suportado.'})
    if not dataset.columns:
        raise ValidationError({'columns': 'O relatório deve possuir ao menos uma coluna.'})
    _validate_columns(dataset.columns)

    if export_format == 'csv':
        return _render_csv(dataset)
    if export_format == 'xlsx':
        return _render_xlsx(dataset)
    return _render_pdf(dataset)
