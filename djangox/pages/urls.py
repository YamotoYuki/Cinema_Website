from django.urls import path
from . import views
from .views import (
    HomePageView,
    AboutPageView,
    TheaterPageView,
    TicketPageView,
    ServicePageView,
    AccessPageView,
    FAQPageView,
    QRPageView,
    TicketBuyPageView,
    OnlinePageView,
    
)

urlpatterns = [
    path("", HomePageView.as_view(), name="home"),
    path("About/", AboutPageView.as_view(), name="about"),
    path("Theater/", TheaterPageView.as_view(), name="theater"),
    path("Ticket/", TicketPageView.as_view(), name="ticket"),
    path("Service/", ServicePageView.as_view(), name="service"),
    path("Access/", AccessPageView.as_view(), name="access"),
    path("FAQ/", FAQPageView.as_view(), name="faq"),
    path("QR/", QRPageView.as_view(), name="QR"),
    path("TicketBuy/", TicketBuyPageView.as_view(), name="TicketBuy"),
    path("Online/", OnlinePageView.as_view(), name="Online"), 
    path('purchase/<str:movie_id>/', views.purchase, name='purchase'),
    path('seat_select/<str:movie_id>/', views.seat_select, name='seat_select'),
    path('purchase_confirm/<str:movie_id>/', views.purchase_confirm, name='purchase_confirm'),
    path('purchase_complete/', views.purchase_complete, name='purchase_complete'),
]

