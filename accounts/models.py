from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone


def default_membership_invitation_expiry():
    """Compatibility shim for historical invitation migrations."""
    return timezone.now() + timedelta(hours=72)


def normalize_login_name(value: str) -> str:
    """Return the canonical spacing used by human-readable login names."""
    return ' '.join(str(value or '').split())


def user_avatar_path(instance, filename):
    suffix = Path(filename).suffix.lower() or '.png'
    user_reference = instance.pk or uuid4().hex
    return f'avatars/user-{user_reference}{suffix}'


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, username, email, password, **extra_fields):
        username = normalize_login_name(username)
        if not username:
            raise ValueError('O nome do usuário é obrigatório.')
        if not email:
            raise ValueError('O email é obrigatório.')

        email = self.normalize_email(str(email).strip())
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(username, email, password, **extra_fields)

    def create_superuser(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superusuário deve ter is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superusuário deve ter is_superuser=True.')

        return self._create_user(username, email, password, **extra_fields)


class User(AbstractUser):
    username = models.CharField('nome do usuário', max_length=150, unique=True)
    email = models.EmailField('email', unique=True)
    avatar = models.ImageField('avatar', upload_to=user_avatar_path, blank=True)
    created_at = models.DateTimeField('criado em', auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField('atualizado em', auto_now=True)

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    objects = UserManager()

    class Meta:
        ordering = ['username']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['is_active']),
        ]
        constraints = [
            models.UniqueConstraint(
                Lower('username'),
                name='accounts_user_username_ci_unique',
            ),
        ]
        verbose_name = 'usuário'
        verbose_name_plural = 'usuários'

    def clean(self):
        super().clean()
        self.username = normalize_login_name(self.username)
        self.email = self.__class__.objects.normalize_email(str(self.email or '').strip())

    def save(self, *args, **kwargs):
        self.username = normalize_login_name(self.username)
        self.email = self.__class__.objects.normalize_email(str(self.email or '').strip())
        return super().save(*args, **kwargs)

    @property
    def avatar_url(self):
        if not self.avatar:
            return ''
        try:
            return self.avatar.url
        except ValueError:
            return ''

    def __str__(self):
        return self.username
