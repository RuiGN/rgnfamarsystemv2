from typing import Any

from base.automatic_fields import automatic_generated_fields


class AutomaticGeneratedFieldsAdminMixin:
    def get_readonly_fields(self, request, obj=None):
        inherited = tuple(super().get_readonly_fields(request, obj))
        generated = automatic_generated_fields(self.model)
        return tuple(dict.fromkeys((*inherited, *generated)))


class ImmutableAuditAdminMixin:
    model: Any
    actions = None

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields) + tuple(
            field.name for field in self.model._meta.many_to_many
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
