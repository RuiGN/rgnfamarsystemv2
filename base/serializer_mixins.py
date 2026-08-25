"""Contratos de tipagem compartilhados por mixins de serializers DRF."""

from typing import Any


class ModelSerializerContractMixin:
    """Declara atributos fornecidos pelo ``ModelSerializer`` na classe final."""

    instance: Any
    Meta: Any
