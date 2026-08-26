from django import forms

from accounts.models import User


class UserAvatarForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('avatar',)
        widgets = {
            'avatar': forms.ClearableFileInput(
                attrs={
                    'class': 'form-control',
                    'accept': 'image/*',
                    'capture': 'user',
                }
            )
        }

    def clean_avatar(self):
        avatar = self.cleaned_data.get('avatar')
        if not avatar:
            return avatar

        if avatar.size > 2 * 1024 * 1024:
            raise forms.ValidationError('O avatar deve ter no máximo 2 MB.')

        content_type = getattr(avatar, 'content_type', '')
        if content_type and content_type not in {'image/png', 'image/jpeg', 'image/webp'}:
            raise forms.ValidationError('Envie uma imagem PNG, JPEG ou WebP.')

        return avatar
