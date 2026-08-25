from masters.models import BusinessPartner
from django import forms
from base.ui.forms import _apply_widget_metadata


class F(forms.ModelForm):
    class Meta:
        model = BusinessPartner
        fields = ['qualification_valid_until']


f = F()
field = f.fields['qualification_valid_until']
_apply_widget_metadata('qualification_valid_until', field)
print('Icon:', getattr(field, 'rgn_icon', None))
print('Attrs:', field.widget.attrs)
print('Type:', type(field.widget))
