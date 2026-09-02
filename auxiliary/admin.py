from django.contrib import admin
from base.admin_mixins import AutomaticGeneratedFieldsAdminMixin
from auxiliary.models import (
    BusinessArea,
    BusinessProcess,
    CatalogType,
    CatalogValue,
    City,
    CommercialTerm,
    Country,
    Currency,
    Department,
    ImpactLevel,
    OrganizationalRole,
    StateProvince,
    SystemModel,
    SystemModule,
)


class AuxiliaryCatalogAdmin(admin.ModelAdmin):
    list_display: tuple[str, ...] = ('code', 'name', 'is_active')
    list_filter: tuple[str, ...] = ('is_active',)
    search_fields: tuple[str, ...] = ('code', 'name', 'description')


@admin.register(BusinessArea)
class BusinessAreaAdmin(AutomaticGeneratedFieldsAdminMixin, AuxiliaryCatalogAdmin):
    pass


@admin.register(BusinessProcess)
class BusinessProcessAdmin(AutomaticGeneratedFieldsAdminMixin, AuxiliaryCatalogAdmin):
    list_display = ('code', 'name', 'area', 'is_active')
    list_filter = ('area', 'is_active')


@admin.register(Department)
class DepartmentAdmin(AutomaticGeneratedFieldsAdminMixin, AuxiliaryCatalogAdmin):
    list_display = ('code', 'name', 'area', 'is_active')
    list_filter = ('area', 'is_active')


@admin.register(OrganizationalRole)
class OrganizationalRoleAdmin(AutomaticGeneratedFieldsAdminMixin, AuxiliaryCatalogAdmin):
    pass


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'iso_alpha2', 'iso_alpha3', 'numeric_code')
    search_fields = ('name', 'iso_alpha2', 'iso_alpha3', 'numeric_code')


@admin.register(StateProvince)
class StateProvinceAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'abbreviation', 'ibge_code', 'country')
    search_fields = ('name', 'abbreviation', 'ibge_code', 'country__name')
    list_filter = ('country',)


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'ibge_code', 'state')
    search_fields = ('name', 'ibge_code', 'state__name')
    list_filter = ('state',)


@admin.register(Currency)
class CurrencyAdmin(AuxiliaryCatalogAdmin):
    list_display = (
        'code',
        'name',
        'numeric_code',
        'symbol',
        'decimal_places',
        'minor_unit_applicable',
        'is_active',
    )


@admin.register(CommercialTerm)
class CommercialTermAdmin(AutomaticGeneratedFieldsAdminMixin, AuxiliaryCatalogAdmin):
    list_display = ('code', 'name', 'term_type', 'days', 'is_active')
    list_filter = ('term_type', 'is_active')


@admin.register(SystemModule)
class SystemModuleAdmin(AutomaticGeneratedFieldsAdminMixin, AuxiliaryCatalogAdmin):
    list_display = ('code', 'name', 'app_label', 'menu_label', 'is_active')


@admin.register(SystemModel)
class SystemModelAdmin(AutomaticGeneratedFieldsAdminMixin, AuxiliaryCatalogAdmin):
    list_display = ('code', 'name', 'module', 'app_label', 'model_name', 'is_active')
    list_filter = ('module', 'is_active')


@admin.register(ImpactLevel)
class ImpactLevelAdmin(AutomaticGeneratedFieldsAdminMixin, AuxiliaryCatalogAdmin):
    list_display = ('code', 'name', 'level_type', 'weight', 'color', 'is_active')
    list_filter = ('level_type', 'is_active')


@admin.register(CatalogType)
class CatalogTypeAdmin(AutomaticGeneratedFieldsAdminMixin, AuxiliaryCatalogAdmin):
    list_display = ('code', 'name', 'target_field', 'is_active')


@admin.register(CatalogValue)
class CatalogValueAdmin(AutomaticGeneratedFieldsAdminMixin, AuxiliaryCatalogAdmin):
    list_display = ('code', 'name', 'catalog_type', 'value', 'order', 'is_active')
    list_filter = ('catalog_type', 'is_active')
