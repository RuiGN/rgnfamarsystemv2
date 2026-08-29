from django.core.exceptions import PermissionDenied
from django.http import Http404

from base.ui.views import ResourceCreateView
from formulations.models import MasterFormula
from formulations.reuse import (
    build_master_formula_reuse_form,
    component_reuse_initial,
    master_formula_reuse_initial,
)


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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['reuse_source'] = self.get_source()
        return context
