from django.urls import path

from .views import HomePageView, AboutPageView

urlpatterns = [
    path("", HomePageView.as_view(), name="home"),
    path("about/", AboutPageView.as_view(), name="about"),
    path("theater/", AboutPageView.as_view(), name="theater"),
    path("ticket/", AboutPageView.as_view(), name="ticket"),
    path("service/", AboutPageView.as_view(), name="service"),
    path("access/", AboutPageView.as_view(), name="access"),
    path("faq/", AboutPageView.as_view(), name="faq"),
]
