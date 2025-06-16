from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404
from django.views.generic import TemplateView
from accounts.forms import PaymentForm

MOVIES = {
    'kimi-no-nawa': {
        'title': '君の名は',
        'poster_url': '/static/images/kimi_no_nawa.jpg',
        'genre': 'アニメ・ファンタジー',
        'duration': 106,
        'release_date': '2016-08-26',
        'description': '田舎に暮らす女子高生と東京の男子高校生が夢の中で入れ替わる──時空を超えた奇跡の物語。',
        'showtime': '2025年6月21日（土） 19:00〜',
        'price': 1500,
        'theater_name': 'TOHOシネマズ新宿'
    },
    'spy-x-family': {
        'title': 'SPY×FAMILY CODE: White',
        'poster_url': '/static/images/spy_x_family.jpg',
        'genre': 'アクション・コメディ',
        'duration': 120,
        'release_date': '2023-12-22',
        'description': 'スパイの父、殺し屋の母、超能力の娘。仮初め家族の絆とスパイ任務が交差するドタバタ劇場版！',
        'showtime': '2025年6月22日（日） 14:30〜',
        'price': 1600,
        'theater_name': '109シネマズ川崎'
    },
    'kimetsu': {
        'title': '鬼滅の刃 無限列車編',
        'poster_url': '/static/images/kimetsu.jpg',
        'genre': 'アクション・ファンタジー',
        'duration': 117,
        'release_date': '2020-10-16',
        'description': '鬼殺隊の炭治郎たちが、無限列車で次々と失踪する人々の謎を追う。圧巻の作画と感動のドラマ。',
        'showtime': '2025年6月23日（月） 18:00〜',
        'price': 1500,
        'theater_name': 'ユナイテッド・シネマ豊洲'
    },
    'gintama': {
        'title': '銀魂 ザ・ファイナル',
        'poster_url': '/static/images/gintama.jpg',
        'genre': 'アクション・コメディ',
        'duration': 104,
        'release_date': '2021-01-08',
        'description': '銀時たち万事屋の最後の戦い。ギャグと感動、アクションが融合した劇場版最終章。',
        'showtime': '2025年6月24日（火） 20:00〜',
        'price': 1400,
        'theater_name': 'MOVIXさいたま'
    },
    'suzume': {
        'title': 'すずめの戸締まり',
        'poster_url': '/static/images/suzume.jpg',
        'genre': 'アニメ・ファンタジー',
        'duration': 122,
        'release_date': '2022-11-11',
        'description': '少女・すずめが扉を閉じて災いを防ぐ──不思議な旅を描く成長と絆の物語。',
        'showtime': '2025年6月25日（水） 13:00〜',
        'price': 1600,
        'theater_name': 'TOHOシネマズ池袋'
    },
    'yurucamp': {
        'title': 'ゆるキャン△',
        'poster_url': '/static/images/yurucamp.jpg',
        'genre': '日常・癒し',
        'duration': 96,
        'release_date': '2022-07-01',
        'description': '大人になったリンたちがキャンプ場を作るために奮闘する、未来の物語。',
        'showtime': '2025年6月26日（木） 11:30〜',
        'price': 1300,
        'theater_name': 'イオンシネマ幕張新都心'
    },
    'onepiece-film-red': {
        'title': 'OnePiece Film Red',
        'poster_url': '/static/images/onepiece.jpg',
        'genre': 'アクション・冒険',
        'duration': 115,
        'release_date': '2022-08-06',
        'description': '歌姫ウタとルフィの運命、そしてシャンクスとの過去が明かされる音楽冒険劇。',
        'showtime': '2025年6月27日（金） 19:30〜',
        'price': 1700,
        'theater_name': 'TOHOシネマズ日比谷'
    },
    'kuroko-winter-cup': {
        'title': 'くろこのバスケ ウィンターカップ総集編',
        'poster_url': '/static/images/kuroko.jpg',
        'genre': 'スポーツ・青春',
        'duration': 89,
        'release_date': '2016-09-03',
        'description': 'キセキの世代が激突！最後の奇跡を描く劇場版バスケットアニメ。',
        'showtime': '2025年6月28日（土） 16:00〜',
        'price': 1400,
        'theater_name': '109シネマズ二子玉川'
    },
    'mahouka-hoshi': {
        'title': '魔法科高校の劣等生 星を呼ぶ少女',
        'poster_url': '/static/images/mahouka.jpg',
        'genre': 'SF・魔法',
        'duration': 90,
        'release_date': '2017-06-17',
        'description': '司波兄妹が南の島で謎の少女と出会い、魔法戦闘へ巻き込まれる。',
        'showtime': '2025年6月29日（日） 12:45〜',
        'price': 1500,
        'theater_name': 'T・ジョイPRINCE品川'
    },
    'heroaca': {
        'title': '僕のヒーローアカデミア THE MOVIE',
        'poster_url': '/static/images/hiroaka.jpg',
        'genre': 'アクション・ヒーロー',
        'duration': 98,
        'release_date': '2021-08-06',
        'description': '世界を救うため、出久たちが新たな仲間とともに敵に立ち向かう。',
        'showtime': '2025年6月30日（月） 15:00〜',
        'price': 1600,
        'theater_name': 'ユナイテッド・シネマお台場'
    },
    'sao-progressive': {
        'title': '劇場版 ソードアート・オンライン プログレッシブ 星なき夜のアリア',
        'poster_url': '/static/images/sao.jpg',
        'genre': 'アニメ・SF',
        'duration': 97,
        'release_date': '2021-10-30',
        'description': 'アスナ視点で描かれる、SAO第1層攻略の新たな物語。',
        'showtime': '2025年7月1日（火） 18:30〜',
        'price': 1500,
        'theater_name': 'MOVIX京都'
    },
    'tenki-no-ko': {
        'title': '天気の子',
        'poster_url': '/static/images/tenki_no_ko.jpg',
        'genre': 'アニメ・ファンタジー',
        'duration': 112,
        'release_date': '2019-07-19',
        'description': '天候を操る少女と少年の出会いが、運命を変えていく青春ファンタジー。',
        'showtime': '2025年7月2日（水） 17:15〜',
        'price': 1500,
        'theater_name': 'シネマサンシャイン池袋'
    },
    'koe-no-katachi': {
        'title': '聲の形',
        'poster_url': '/static/images/koe_no_katachi.jpg',
        'genre': '青春・ヒューマンドラマ',
        'duration': 129,
        'release_date': '2016-09-17',
        'description': '耳が聞こえない少女と、かつて彼女をいじめた少年の再会と贖罪の物語。',
        'showtime': '2025年7月3日（木） 13:30〜',
        'price': 1400,
        'theater_name': '立川シネマシティ'
    },
    'tensura': {
        'title': '劇場版 転生したらスライムだった件',
        'poster_url': '/static/images/tensura.jpg',
        'genre': '異世界・ファンタジー',
        'duration': 108,
        'release_date': '2022-11-25',
        'description': 'サラリーマンが異世界でスライムに転生！国づくりと仲間の絆を描く冒険譚。',
        'showtime': '2025年7月4日（金） 14:15〜',
        'price': 1600,
        'theater_name': 'TOHOシネマズ渋谷'
    },
    'overlord': {
        'title': '劇場版 オーバーロード',
        'poster_url': '/static/images/overlord.jpg',
        'genre': 'ダークファンタジー',
        'duration': 103,
        'release_date': '2017-02-25',
        'description': 'ゲーム世界に取り残された最強アンデッドが世界を支配していくダークファンタジー。',
        'showtime': '2025年7月5日（土） 20:00〜',
        'price': 1500,
        'theater_name': '池袋HUMAXシネマズ'
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
        'showtime': movie['showtime'],         
        'price': movie['price'],               
        'theater_name': movie['theater_name'], 
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
    movie = MOVIES[movie_id]

    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            payment_method = form.cleaned_data['payment_method']
            # 支払い方法をセッションやDBに保存する処理を書くことも可能
            request.session['payment_method'] = payment_method
            return redirect('purchase_complete')  # 購入完了ページへリダイレクト
    else:
        # 初期表示はセッションに保存された支払い方法があればそれをセット
        initial = {}
        if 'payment_method' in request.session:
            initial['payment_method'] = request.session['payment_method']
        form = PaymentForm(initial=initial)

    return render(request, 'apps/purchase_confirm.html', {
        'movie_id': movie_id,
        'movie_title': movie['title'],
        'seat': seat,
        'showtime': movie['showtime'],
        'price': movie['price'],
        'theater_name': movie['theater_name'],
        'form': form,
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
