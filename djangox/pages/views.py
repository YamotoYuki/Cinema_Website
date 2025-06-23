from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView
from .models import Movie, Seat, Reservation
from django.contrib.auth.decorators import login_required
from datetime import datetime, timedelta
import qrcode
from io import BytesIO
from django.core.files.base import ContentFile

def generate_qr_code(reservation):
    qr_data = f"予約ID:{reservation.id}\n映画:{reservation.movie.title}\n座席:{reservation.seat.seat_number}\n日時:{reservation.movie.show_time}"
    qr = qrcode.make(qr_data)
    buffer = BytesIO()
    qr.save(buffer, format='PNG')
    file_name = f'qr_{reservation.id}.png'
    reservation.qr_code_image.save(file_name, ContentFile(buffer.getvalue()))
    reservation.save()

def movie_list(request):
    query = request.GET.get('q')
    if query:
        movies = Movie.objects.filter(title__icontains=query)
    else:
        movies = Movie.objects.all()
    return render(request, 'apps/movie_list.html', {
        'movies': movies,
        'query': query,
    })


def movie_detail(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)
    weekdays = ['月', '火', '水', '木', '金', '土', '日']
    show_dates = []
    for i in range(7):
        date = datetime.today() + timedelta(days=i)
        show_dates.append({
            'date': date.strftime('%Y-%m-%d'),
            'label': f"{date.month}月{date.day}日（{weekdays[date.weekday()]}）",
            'weekday': weekdays[date.weekday()]
        })
    return render(request, 'apps/movie_detail.html', {
        'movie': movie,
        'show_dates': show_dates,
        'time_slots': ["13:00～15:00", "16:00～18:00", "19:00～21:00"]
    })

@login_required
def seat_select(request, movie_id):
    selected_date = request.GET.get('date') 
    time_slot = request.GET.get('time_slot')        
    movie = get_object_or_404(Movie, pk=movie_id)
    seats = Seat.objects.all()
    reserved_seats = Reservation.objects.filter(movie=movie).values_list('seat__id', flat=True)

    rows = ['A','B','C','D','E','F','G','H','I','J']
    left_cols = [str(i) for i in range(1,5)]
    center_cols = [str(i) for i in range(5,17)]
    right_cols = [str(i) for i in range(17,21)]

    reservations = Reservation.objects.filter(movie=movie)
    reserved_seat_numbers = set(r.seat.seat_number for r in reservations)
    wheelchair_seat_numbers = {'A5', 'A6', 'A15', 'A16'}

    if request.method == 'POST':
        selected_seat_ids = request.POST.getlist('seats')
        request.session['selected_seats'] = selected_seat_ids
        request.session['selected_datetime'] = f'{selected_date} {time_slot}'
        for seat_id in selected_seat_ids:
            seat = Seat.objects.get(id=seat_id)
            if not Reservation.objects.filter(movie=movie, seat=seat).exists():
                reservation = Reservation.objects.create(
                    user=request.user,
                    movie=movie,
                    seat=seat,
                    show_time=f'{selected_date} {time_slot}'
                )
                generate_qr_code(reservation)
        return redirect('purchase_confirm')

    return render(request, 'apps/seat_select.html', {
        'movie': movie,
        'seats': seats,
        'reserved_seats': reserved_seats,
        'rows': rows,
        'left_cols': left_cols,
        'center_cols': center_cols,
        'right_cols': right_cols,
        'reserved_seat_numbers': reserved_seat_numbers,
        'wheelchair_seat_numbers': wheelchair_seat_numbers,
    })

def generate_qr_code(reservation):
    qr_data = (
        f"予約ID:{reservation.id}\n"
        f"映画:{reservation.movie.title}\n"
        f"座席:{reservation.seat.seat_number}\n"
        f"上映日時:{reservation.show_time}"
    )
    qr = qrcode.make(qr_data)
    buffer = BytesIO()
    qr.save(buffer, format='PNG')
    file_name = f'qr_{reservation.id}.png'
    reservation.qr_code_image.save(file_name, ContentFile(buffer.getvalue()))
    reservation.save()

@login_required
def purchase_confirm(request):
    selected_seat_ids = request.session.get('selected_seats', [])
    selected_datetime = request.session.get('selected_datetime', None)  # ← ★ここを追加★

    if not selected_seat_ids:
        return redirect('movie_list')

    seats = Seat.objects.filter(id__in=selected_seat_ids)
    if not seats.exists():
        return redirect('movie_list')

    movie = seats.first().reservation_set.last().movie if seats.first().reservation_set.exists() else None
    if not movie:
        latest_reservation = Reservation.objects.filter(user=request.user).order_by('-reserved_at').first()
        movie = latest_reservation.movie if latest_reservation else None

    total_price = movie.price * len(seats) if movie else 0
    seat_numbers = [seat.seat_number for seat in seats]

    return render(request, 'apps/purchase_confirm.html', {
        'movie': movie,
        'selected_seat_numbers': seat_numbers,
        'selected_seat_count': len(seats),
        'total_price': total_price,
        'selected_seat_ids': selected_seat_ids,
        'selected_datetime': selected_datetime
    })


@login_required
def purchase_complete(request):
    selected_seat_ids = request.session.pop('selected_seats', [])
    seats = Seat.objects.filter(id__in=selected_seat_ids)
    movie = seats.first().reservation_set.last().movie if seats and seats.first().reservation_set.exists() else None
    seat_numbers = [seat.seat_number for seat in seats]
    total_price = movie.price * len(seats) if movie else 0
    return render(request, 'apps/purchase_complete.html', {
        'movie': movie,
        'selected_seat_numbers': seat_numbers,
        'total_price': total_price
    })

@login_required
def my_reservations(request):
    reservations = Reservation.objects.filter(user=request.user).order_by('-reserved_at')
    return render(request, 'apps/my_reservations.html', {'reservations': reservations})

@login_required
def cancel_reservation(request, reservation_id):
    reservation = get_object_or_404(Reservation, id=reservation_id, user=request.user)
    if request.method == 'POST':
        reservation.delete()
        return redirect('my_reservations')
    return render(request, 'apps/cancel_reservation_confirm.html', {'reservation': reservation})

@login_required
def home_page(request):
    return render(request, 'pages/home.html')

@login_required
def about_page(request):
    return render(request, 'pages/about.html')

@login_required
def theater_page(request):
    return render(request, 'pages/theater.html')

@login_required
def ticket_page(request):
    return render(request, 'pages/ticket.html')

@login_required
def service_page(request):
    return render(request, 'pages/service.html')

@login_required
def access_page(request):
    return render(request, 'pages/access.html')

@login_required
def faq_page(request):
    return render(request, 'pages/faq.html')

@login_required
def qr_page(request):
    return render(request, 'apps/QR.html')

@login_required
def ticket_buy_page(request):
    return render(request, 'apps/TicketBuy.html')

@login_required
def online_page(request):
    return render(request, 'apps/Online.html')