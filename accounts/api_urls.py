from django.urls import path

from accounts.views import CurrentUserAPIView


app_name = 'accounts_api'

urlpatterns = [
    path('me/', CurrentUserAPIView.as_view(), name='me'),
]
