from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from accounts.models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    ordering = ('username',)
    list_display = (
        'username',
        'email',
        'first_name',
        'last_name',
        'avatar',
        'is_staff',
        'is_active',
    )
    list_filter = ('is_staff', 'is_superuser', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    readonly_fields = (
        'created_at',
        'updated_at',
        'last_login',
        'date_joined',
    )
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Dados pessoais', {'fields': ('email', 'first_name', 'last_name', 'avatar')}),
        (
            'Permissões',
            {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')},
        ),
        (
            'Datas importantes',
            {'fields': ('last_login', 'date_joined', 'created_at', 'updated_at')},
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': (
                    'username',
                    'email',
                    'password1',
                    'password2',
                    'is_staff',
                    'is_active',
                ),
            },
        ),
    )
