from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import re
from xml.etree.ElementTree import ParseError

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException


MAX_NFE_XML_SIZE = 10 * 1024 * 1024
CENT = Decimal('0.01')


class NfeImportError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class NfeItemData:
    product_code: str
    description: str
    quantity: Decimal
    unit_code: str
    unit_price: Decimal
    product_total: Decimal
    tax_amount: Decimal
    lot_number: str
    manufacturing_date: date | None
    expiry_date: date | None


@dataclass(frozen=True, slots=True)
class NfeData:
    access_key: str
    number: str
    series: str
    issue_date: date
    model: str
    authorization_status: str
    supplier_document: str
    supplier_name: str
    destination_document: str
    product_total: Decimal
    items: tuple[NfeItemData, ...]
    xml_sha256: str
    raw_xml: bytes


def _local_name(tag):
    return str(tag).rsplit('}', 1)[-1]


def _first(element, name):
    return next((child for child in element.iter() if _local_name(child.tag) == name), None)


def _all(element, name):
    return tuple(child for child in element.iter() if _local_name(child.tag) == name)


def _text(element, name, *, required=True):
    child = _first(element, name)
    value = (child.text or '').strip() if child is not None else ''
    if required and not value:
        raise NfeImportError(f'O XML da NF-e não informa {name}.')
    return value


def _decimal(element, name, *, positive=False, default=None):
    raw = _text(element, name, required=default is None)
    if not raw and default is not None:
        return default
    try:
        value = Decimal(raw)
    except (InvalidOperation, TypeError, ValueError) as error:
        raise NfeImportError(f'O campo {name} deve conter um número válido.') from error
    if not value.is_finite():
        raise NfeImportError(f'O campo {name} deve conter um número finito.')
    if value < 0 or (positive and value <= 0):
        comparison = 'maior que zero' if positive else 'não negativo'
        raise NfeImportError(f'O campo {name} deve ser {comparison}.')
    return value


def _date(element, name):
    raw = _text(element, name, required=False)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except (TypeError, ValueError) as error:
        raise NfeImportError(f'O campo {name} deve conter uma data ISO válida.') from error


def _document(element):
    value = _text(element, 'CNPJ', required=False) or _text(element, 'CPF', required=False)
    digits = re.sub(r'\D', '', value)
    if not digits:
        raise NfeImportError('O XML da NF-e não informa o documento da parte.')
    return digits


def _raw_xml(xml_content):
    if hasattr(xml_content, 'read'):
        xml_content = xml_content.read()
    if isinstance(xml_content, str):
        xml_content = xml_content.encode('utf-8')
    if not isinstance(xml_content, (bytes, bytearray, memoryview)):
        raise NfeImportError('Informe o conteúdo XML da NF-e em bytes.')
    raw_xml = bytes(xml_content)
    if not raw_xml:
        raise NfeImportError('O arquivo XML da NF-e está vazio.')
    if len(raw_xml) > MAX_NFE_XML_SIZE:
        raise NfeImportError('O XML da NF-e não pode exceder 10 MiB.')
    upper_xml = raw_xml.upper()
    if b'<!DOCTYPE' in upper_xml or b'<!ENTITY' in upper_xml:
        raise NfeImportError('O XML da NF-e não pode conter DOCTYPE ou ENTITY.')
    return raw_xml


def _parse_item(det):
    product = _first(det, 'prod')
    if product is None:
        raise NfeImportError('Um item da NF-e não contém o grupo prod.')
    tracking = _first(product, 'rastro')
    manufacturing_date = _date(tracking, 'dFab') if tracking is not None else None
    expiry_date = _date(tracking, 'dVal') if tracking is not None else None
    if manufacturing_date and expiry_date and manufacturing_date > expiry_date:
        raise NfeImportError('A fabricação do lote não pode ser posterior à validade.')
    tax_group = _first(det, 'imposto')
    tax_amount = (
        _decimal(tax_group, 'vTotTrib', default=Decimal('0.00'))
        if tax_group is not None
        else Decimal('0.00')
    )
    return NfeItemData(
        product_code=_text(product, 'cProd'),
        description=_text(product, 'xProd'),
        quantity=_decimal(product, 'qCom', positive=True),
        unit_code=_text(product, 'uCom'),
        unit_price=_decimal(product, 'vUnCom'),
        product_total=_decimal(product, 'vProd'),
        tax_amount=tax_amount,
        lot_number=_text(tracking, 'nLote', required=False) if tracking is not None else '',
        manufacturing_date=manufacturing_date,
        expiry_date=expiry_date,
    )


def parse_nfe_xml(xml_content):
    raw_xml = _raw_xml(xml_content)
    try:
        root = ElementTree.fromstring(raw_xml)
    except (DefusedXmlException, ParseError, ValueError) as error:
        raise NfeImportError('O arquivo informado não contém um XML NF-e válido.') from error
    if _local_name(root.tag) != 'nfeProc':
        raise NfeImportError('O XML deve usar a estrutura autorizada nfeProc.')

    inf_nfe = _first(root, 'infNFe')
    inf_prot = _first(root, 'infProt')
    if inf_nfe is None or inf_prot is None:
        raise NfeImportError('O XML não contém os grupos obrigatórios da NF-e autorizada.')

    model = _text(inf_nfe, 'mod')
    if model != '55':
        raise NfeImportError('A importação aceita somente NF-e modelo 55.')
    authorization_status = _text(inf_prot, 'cStat')
    if authorization_status != '100':
        raise NfeImportError('A NF-e precisa estar autorizada com cStat 100.')
    access_key = _text(inf_prot, 'chNFe')
    if re.fullmatch(r'\d{44}', access_key) is None:
        raise NfeImportError('A chave de acesso da NF-e deve conter exatamente 44 dígitos.')
    if inf_nfe.attrib.get('Id') != f'NFe{access_key}':
        raise NfeImportError('A chave autorizada diverge do identificador infNFe.')

    ide = _first(inf_nfe, 'ide')
    supplier = _first(inf_nfe, 'emit')
    destination = _first(inf_nfe, 'dest')
    total_group = _first(inf_nfe, 'ICMSTot')
    if None in (ide, supplier, destination, total_group):
        raise NfeImportError('O XML não contém cabeçalho, partes e total obrigatórios.')

    issue_date = _date(ide, 'dhEmi')
    if issue_date is None:
        raise NfeImportError('O XML da NF-e não informa a data de emissão.')
    items = tuple(_parse_item(det) for det in _all(inf_nfe, 'det'))
    if not items:
        raise NfeImportError('A NF-e precisa conter ao menos um item.')
    product_total = _decimal(total_group, 'vProd')
    items_total = sum((item.product_total for item in items), Decimal('0.00')).quantize(CENT)
    if items_total != product_total.quantize(CENT):
        raise NfeImportError('O total dos itens diverge do total de produtos da NF-e.')

    return NfeData(
        access_key=access_key,
        number=_text(ide, 'nNF'),
        series=_text(ide, 'serie'),
        issue_date=issue_date,
        model=model,
        authorization_status=authorization_status,
        supplier_document=_document(supplier),
        supplier_name=_text(supplier, 'xNome'),
        destination_document=_document(destination),
        product_total=product_total,
        items=items,
        xml_sha256=hashlib.sha256(raw_xml).hexdigest(),
        raw_xml=raw_xml,
    )
