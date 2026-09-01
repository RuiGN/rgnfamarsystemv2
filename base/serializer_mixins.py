"""Contratos de tipagem compartilhados por mixins de serializers DRF."""

from typing import Any


class ModelSerializerContractMixin:
    """Declara atributos fornecidos pelo ``ModelSerializer`` na classe final."""

    instance: Any
    Meta: Any

    def get_fields(self):
        fields = getattr(super(), 'get_fields')()
        from base.automatic_fields import automatic_generated_fields

        for field_name in automatic_generated_fields(self.Meta.model):
            if field_name in fields:
                fields[field_name].read_only = True
        return fields
