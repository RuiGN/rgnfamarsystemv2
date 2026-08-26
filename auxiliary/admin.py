from django.contrib import admin
from base.admin_mixins import AutomaticGeneratedFieldsAdminMixin
from auxiliary.models import (
    BackupRun,
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
    list_display = ('id', 'name')
    search_fields = ('name',)


@admin.register(StateProvince)
class StateProvinceAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'country')
    search_fields = ('name', 'country__name')
    list_filter = ('country',)


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'state')
    search_fields = ('name', 'state__name')
    list_filter = ('state',)


@admin.register(Currency)
class CurrencyAdmin(AuxiliaryCatalogAdmin):
    list_display = ('code', 'name', 'numeric_code', 'symbol', 'decimal_places', 'is_active')


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


@admin.register(BackupRun)
class BackupRunAdmin(admin.ModelAdmin):
    list_display = (
        'run_number',
        'kind',
        'status',
        'size_bytes',
        'drive_file_id',
        'started_at',
        'finished_at',
        'duration_seconds',
        'triggered_by',
    )
    list_filter = ('status', 'kind', 'triggered_by', 'encrypted', 'encryption_key_id')
    search_fields = ('run_number', 'source_path', 'sha256', 'drive_file_id', 'drive_file_name')
    readonly_fields = (
        'run_number',
        'created_at',
        'updated_at',
        'started_at',
        'finished_at',
        'duration_seconds',
        'drive_file_id',
        'drive_web_view_link',
        'drive_md5_checksum',
    )
    ordering = ('-started_at',)
