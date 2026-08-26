import socket
import unicodedata
from datetime import date, datetime

from django.utils import timezone

from integrations.models import LabelPrinterSettings
from inventory.models import StockLot


PRINTER_TIMEOUT_SECONDS = 5


class LabelPrinterError(RuntimeError):
    pass


class LabelPrinterConfigurationError(LabelPrinterError):
    pass


class LabelPrinterConnectionError(LabelPrinterError):
    pass


class LabelDataError(LabelPrinterError):
    pass


def _printer_text(value, *, limit=48):
    text = unicodedata.normalize('NFKD', str(value or ''))
    ascii_text = text.encode('ascii', 'ignore').decode('ascii')
    printable_text = ''.join(
        character if 32 <= ord(character) <= 126 else ' ' for character in ascii_text
    )
    safe_text = ' '.join(printable_text.split()).replace('"', "'")
    return safe_text[:limit]


def _date_text(value: date | None):
    return value.strftime('%d/%m/%Y') if value else ''


def _signature_text(user, printed_at: datetime):
    name = str(user.get_full_name() or '').strip() or user.get_username()
    local_time = timezone.localtime(printed_at)
    timestamp = f'{local_time:%d/%m/%Y %H:%M}'
    name_limit = max(1, 48 - len(timestamp) - 1)
    return f'{_printer_text(name, limit=name_limit)} {timestamp}'


def render_lot_label_tspl(
    lot: StockLot,
    user,
    *,
    width_mm=40,
    height_mm=30,
    printed_at=None,
):
    if not lot.lot_number:
        raise LabelDataError('O lote não possui número para impressão.')
    if not lot.expiry_date:
        raise LabelDataError('O lote não possui validade para impressão.')
    if int(width_mm) <= 0 or int(height_mm) <= 0:
        raise LabelDataError('As dimensões da etiqueta devem ser positivas.')
    printed_at = printed_at or timezone.now()
    product = _printer_text(f'{lot.product.code} - {lot.product.description}')
    lot_number = _printer_text(lot.lot_number)
    expiry = _date_text(lot.expiry_date)
    signature = _signature_text(user, printed_at)
    lines = [
        f'SIZE {int(width_mm)} mm,{int(height_mm)} mm',
        'GAP 2 mm,0 mm',
        'DIRECTION 1',
        'CLS',
        f'TEXT 24,18,"0",0,1,1,"PRODUTO: {product}"',
        f'TEXT 24,52,"0",0,1,1,"LOTE: {lot_number}"',
        f'TEXT 24,86,"0",0,1,1,"VALIDADE: {expiry}"',
        f'TEXT 24,120,"0",0,1,1,"ASS: {signature}"',
        'PRINT 1,1',
    ]
    return '\n'.join(lines) + '\n'


def _active_printer_settings():
    return LabelPrinterSettings.objects.filter(is_active=True).first()


def print_lot_label(lot: StockLot, user):
    printer = _active_printer_settings()
    if printer is None:
        raise LabelPrinterConfigurationError(
            'Configure uma impressora ativa no módulo Integrações.'
        )
    payload = render_lot_label_tspl(
        lot,
        user,
        width_mm=printer.width_mm,
        height_mm=printer.height_mm,
    )
    try:
        with socket.create_connection(
            (printer.host, printer.port), timeout=PRINTER_TIMEOUT_SECONDS
        ) as connection:
            connection.sendall(payload.encode('ascii'))
    except (OSError, TimeoutError) as error:
        raise LabelPrinterConnectionError(
            'Não foi possível conectar à impressora de etiquetas pela VPN.'
        ) from error
    return {
        'printer_name': printer.name,
        'printer_host': printer.host,
        'printer_port': printer.port,
        'product_code': lot.product.code,
        'lot_number': lot.lot_number,
        'expiry_date': lot.expiry_date.isoformat(),
    }
