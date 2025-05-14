from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse

# シンプルなログイン必須ページ（テスト用）
@login_required
def secret_page(request):
    return HttpResponse("ログイン成功！このページはログインユーザーだけが見られます。")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("secret/", secret_page, name="secret"),
    path("", lambda request: redirect("secret")),
]
