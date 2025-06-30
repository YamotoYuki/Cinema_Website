from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views
from .views import RulePageView, PolicyPageView, InquiryPageView, GuidePageView


urlpatterns = [
    path("", views.home_page, name="home"),
    path("Theater/", views.theater_page, name="theater"),
    path("Ticket/", views.ticket_page, name="ticket"),
    path("Service/", views.service_page, name="service"),
    path("rule/", RulePageView.as_view(), name="rule"),
    path("policy/", PolicyPageView.as_view(), name="policy"),   
    path("inquiry/", InquiryPageView.as_view(), name="inquiry"),
    path("guide/", GuidePageView.as_view(), name="guide"),
    path("Access/", views.access_page, name="access"),
    path("FAQ/", views.faq_page, name="faq"),
    path("QR/", views.qr_page, name="QR"),
    path("TicketBuy/", views.ticket_buy_page, name="TicketBuy"),
    path("Online/", views.online_page, name="Online"),
    path('movielist/', views.movie_list, name='movie_list'),
    path('movie/<int:movie_id>/', views.movie_detail, name='movie_detail'),
    path('movie/<int:movie_id>/seats/', views.seat_select, name='seat_select'),
    path('confirm/', views.purchase_confirm, name='purchase_confirm'),
    path('complete/', views.purchase_complete, name='purchase_complete'),
    path('my_reservations/', views.my_reservations, name='my_reservations'),
    path('reservation/<int:reservation_id>/cancel/', views.cancel_reservation, name='cancel_reservation'),
    path('account/edit/', views.account_edit, name='account_edit'),
    path('account/delete/', views.account_delete, name='account_delete'),
    path('notifications/', views.notifications_list, name='notifications_list'),
    path('notifications/read/<int:notification_id>/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/delete/<int:notification_id>/', views.delete_notification, name='delete_notification'),
    path('notifications/delete_all/', views.delete_all_notifications, name='delete_all_notifications'),
    path('payment/', views.payment_input, name='payment_input'),
    path('profile/select/', views.profile_select, name='profile_select'),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
