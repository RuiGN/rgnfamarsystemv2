from django.http import JsonResponse
from django.shortcuts import redirect, render


def health_check(request):
    return JsonResponse({'status': 'ok'})


def home(request):
    if not request.user.is_authenticated:
        return redirect('accounts:login')
    return render(request, 'dashboard/home.html')


def permission_denied(request, exception=None):
    return render(request, 'app/permission_denied.html', {'exception': exception}, status=403)
