from django.urls import path

from accounts.views import EmailLogoutView, UserAvatarUpdateView, UsernameLoginView


app_name = 'accounts'

urlpatterns = [
    path('login/', UsernameLoginView.as_view(), name='login'),
    path('avatar/', UserAvatarUpdateView.as_view(), name='avatar'),
    path('logout/', EmailLogoutView.as_view(), name='logout'),
]
