from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404
from django.views.generic import TemplateView

MOVIES = {
    'kimi-no-nawa': {
        'title': '君の名は',
        'poster_url': '/static/images/kimi_no_nawa.jpg',
        'genre': 'アニメ・ファンタジー',
        'duration': 106,
        'release_date': '2016-08-26',
        'description': '田舎に暮らす女子高生と東京の男子高校生が夢の中で入れ替わる──時空を超えた奇跡の物語。'
    },
    'spy-x-family': {
        'title': 'SPY×FAMILY CODE: White',
        'poster_url': '/static/images/spy_family.jpg',
        'genre': 'アクション・コメディ',
        'duration': 120,
        'release_date': '2023-12-22',
        'description': 'スパイの父、殺し屋の母、超能力の娘。仮初め家族の絆とスパイ任務が交差するドタバタ劇場版！'
    },
}

def purchase(request, movie_id):
    if movie_id not in MOVIES:
        raise Http404("映画が見つかりません。")
    movie = MOVIES[movie_id]
    return render(request, 'apps/purchase.html', {
        'movie_id': movie_id,
        'movie_title': movie['title'],
        'movie_poster_url': movie['poster_url'],
        'genre': movie['genre'],
        'duration': movie['duration'],
        'release_date': movie['release_date'],
        'description': movie['description'],
    })

def seat_select(request, movie_id):
    if movie_id not in MOVIES:
        raise Http404("映画が見つかりません。")

    reserved_seats = ['A5', 'A6', 'B10', 'C12'] 

    if request.method == 'POST':
        request.session['seat'] = request.POST.get('seat')
        return redirect('purchase_confirm', movie_id=movie_id)

    return render(request, 'apps/seat_select.html', {
        'movie_id': movie_id,
        'movie_title': MOVIES[movie_id]['title'],
        'reserved_seats': reserved_seats,
    })

def purchase_confirm(request, movie_id):
    if movie_id not in MOVIES:
        raise Http404("映画が見つかりません。")
    seat = request.session.get('seat')
    if request.method == 'POST':
        return redirect('purchase_complete')
    return render(request, 'apps/purchase_confirm.html', {
        'movie_id': movie_id,
        'movie_title': MOVIES[movie_id]['title'],
        'seat': seat,
    })

def purchase_complete(request):
    return render(request, 'apps/purchase_complete.html')


# その他ページ
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
    template_name = "apps/QR.html"

class TicketBuyPageView(TemplateView):
    template_name = "apps/TicketBuy.html"

class OnlinePageView(TemplateView):
    template_name = "apps/Online.html"
