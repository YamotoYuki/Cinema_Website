from django.views.generic import TemplateView

class HomePageView(TemplateView):
    template_name = "pages/home.html"

class AboutPageView(TemplateView):
    template_name = "pages/about.html"

class TheaterPageView(TemplateView):
    template_name = "pages/theater.html"

class TicketPageView(TemplateView):
    template_name = "pages/ticket.html"

class ServicePageView(TemplateView):
    template_name = "pages/service.html"

class AccessPageView(TemplateView):
    template_name = "pages/access.html"

class FAQPageView(TemplateView):
    template_name = "pages/faq.html"
    
class QRPageView(TemplateView):
    template_name = "pages/QR.html"
    
class TicketBuyPageView(TemplateView):
    template_name = "pages/TicketBuy.html"
    
class OnlinePageView(TemplateView):
    template_name = "pages/Online.html"
