from django.core.exceptions import PermissionDenied
from django.http import Http404

from base.ui.views import ResourceCreateView
from formulations.models import MasterFormula
from formulations.reuse import (
    VERSION_CONFLICT_MESSAGE,
    build_master_formula_reuse_form,
    component_reuse_initial,
    is_formula_version_conflict,
    master_formula_reuse_initial,
)
from masters.models import Product


class MasterFormulaReuseView(ResourceCreateView):
    source = None

    def dispatch(self, request, *args, **kwargs):
        resource = self.get_resource()
        if resource.model is not MasterFormula:
            raise Http404('Reaproveitamento disponível somente para fórmulas mestras.')
        if not resource.can_reuse(request.user):
            raise PermissionDenied('Usuário sem permissão para reaproveitar esta fórmula.')
        self.get_source()
        return super().dispatch(request, *args, **kwargs)

    def get_source(self):
        if self.source is None:
            try:
                self.source = (
                    self.get_queryset()
                    .select_related('product', 'batch_unit')
                    .prefetch_related('components')
                    .get(pk=self.kwargs['pk'])
                )
            except MasterFormula.DoesNotExist as exc:
                raise Http404('Fórmula de origem não encontrada.') from exc
        return self.source

    def get_form_class(self):
        return build_master_formula_reuse_form(self.get_resource())

    def get_form_initial(self):
        return master_formula_reuse_initial(self.get_source())

    def get_inline_initial(self):
        return {'components': component_reuse_initial(self.get_source())}

    def prepare_object_for_save(self, obj, *, action):
        del action
        Product.objects.select_for_update().only('pk').get(pk=obj.product_id)
        obj.code = ''
        obj.status = MasterFormula.Status.DRAFT
        obj.copied_from = self.get_source()
        obj.approved_by = None
        obj.approved_at = None
        return obj

    def handle_integrity_error(self, form, error):
        if not is_formula_version_conflict(error):
            return False
        form.add_error('version', VERSION_CONFLICT_MESSAGE)
        return True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['reuse_source'] = self.get_source()
        return context
