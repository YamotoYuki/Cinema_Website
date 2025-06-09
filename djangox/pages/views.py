from django.views.generic import TemplateView
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404
from django.http import Http404

# 仮の映画辞書
MOVIES = {
    'kimi-no-nawa': '君の名は',
    'spy-x-family': 'SPY×FAMILY CODE: White',
    # 他のIDも同様に追加
}

def purchase(request, movie_id):
    if movie_id not in MOVIES:
        raise Http404("映画が見つかりません。")
    return render(request, 'pages/purchase.html', {'movie_id': movie_id, 'movie_title': MOVIES[movie_id]})

def seat_select(request, movie_id):
    if movie_id not in MOVIES:
        raise Http404("映画が見つかりません。")
    if request.method == 'POST':
        # 座席選択情報を一時的にセッションに保存
        request.session['seat'] = request.POST.get('seat')
        return redirect('purchase_confirm', movie_id=movie_id)
    return render(request, 'pages/seat_select.html', {'movie_id': movie_id, 'movie_title': MOVIES[movie_id]})

def purchase_confirm(request, movie_id):
    if movie_id not in MOVIES:
        raise Http404("映画が見つかりません。")
    seat = request.session.get('seat')
    if request.method == 'POST':
        return redirect('purchase_complete')
    return render(request, 'pages/purchase_confirm.html', {
        'movie_id': movie_id,
        'movie_title': MOVIES[movie_id],
        'seat': seat,
    })

def purchase_complete(request):
    return render(request, 'pages/purchase_complete.html')


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