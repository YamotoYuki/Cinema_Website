from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView
from .models import Movie, Seat, Reservation, Notification
from django.contrib.auth.decorators import login_required
from datetime import datetime, timedelta
import qrcode
from io import BytesIO
from django.core.files.base import ContentFile
from django.contrib import messages
from django.views.decorators.http import require_POST

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

def movie_list(request):
    query = request.GET.get('q')
    movies = Movie.objects.filter(title__icontains=query) if query else Movie.objects.all()
    return render(request, 'apps/movie_list.html', {'movies': movies, 'query': query})

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
        'time_slots': ["09:00～11:00", "11:00～13:00", "13:00～15:00", "15:00～17:00", "17:00～19:00", "19:00～21:00", "21:00～23:00"]
    })

@login_required
def seat_select(request, movie_id):
    selected_date = request.GET.get('date')  # '2025-06-26'
    time_slot = request.GET.get('time_slot')  # '13:00〜15:00'

    movie = get_object_or_404(Movie, pk=movie_id)
    seats = Seat.objects.all()

    if not selected_date or not time_slot:
        messages.error(request, "上映日または時間帯の情報がありません。")
        return redirect('movie_detail', movie_id=movie.id)

    show_time_str = f"{selected_date} {time_slot}"

    reserved_seats = Reservation.objects.filter(
        movie=movie,
        show_time=show_time_str
    ).values_list('seat__id', flat=True)

    reserved_seat_numbers = set(
        r.seat.seat_number for r in Reservation.objects.filter(
            movie=movie,
            show_time=show_time_str
        )
    )

    rows = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']
    left_cols = [str(i) for i in range(1, 5)]
    center_cols = [str(i) for i in range(5, 17)]
    right_cols = [str(i) for i in range(17, 21)]
    wheelchair_seat_numbers = {'A5', 'A6', 'A15', 'A16'}

    if request.method == 'POST':
        selected_seat_ids = request.POST.getlist('seats')

        request.session['selected_seats'] = selected_seat_ids
        request.session['selected_datetime'] = show_time_str
        request.session['movie_id'] = movie.id

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
        'selected_date': selected_date,
        'time_slot': time_slot,
    })


@login_required
def purchase_confirm(request):
    selected_seat_ids = request.session.get('selected_seats', [])
    selected_datetime = request.session.get('selected_datetime')
    movie_id = request.session.get('movie_id')

    if not selected_seat_ids or not selected_datetime or not movie_id:
        messages.error(request, "選択された座席または日時の情報がありません。")
        return redirect('movie_list')

    seats = Seat.objects.filter(id__in=selected_seat_ids)
    seat_numbers = [seat.seat_number for seat in seats]

    movie = get_object_or_404(Movie, id=movie_id)

    total_price = movie.price * len(seats)

    if request.method == 'POST':
        payment_method = request.POST.get('payment_method', 'cash')
        convenience_type = request.POST.get('convenience_type') if payment_method == 'convenience_store' else None

        for seat in seats:
            if not Reservation.objects.filter(movie=movie, seat=seat, show_time=selected_datetime).exists():
                reservation = Reservation.objects.create(
                    user=request.user,
                    movie=movie,
                    seat=seat,
                    show_time=selected_datetime,
                    payment_method=payment_method,
                    convenience_type=convenience_type
                )
                generate_qr_code(reservation)

                Notification.objects.create(
                    user=request.user,
                    message=(
                        f"映画「{movie.title}」のチケットを購入しました。"
                        f"座席: {seat.seat_number}、上映日時: {selected_datetime}、"
                        f"支払方法: {payment_method} {convenience_type or ''}"
                    )
                )

        request.session.pop('selected_seats', None)
        
@login_required
def purchase_confirm(request):
    selected_seat_ids = request.session.get('selected_seats', [])
    selected_datetime = request.session.get('selected_datetime')
    movie_id = request.session.get('movie_id')

    if not selected_seat_ids or not selected_datetime or not movie_id:
        messages.error(request, "選択された座席または日時の情報がありません。")
        return redirect('movie_list')

    seats = Seat.objects.filter(id__in=selected_seat_ids)
    seat_numbers = [seat.seat_number for seat in seats]
    movie = get_object_or_404(Movie, id=movie_id)
    total_price = movie.price * len(seats)

    return render(request, 'apps/purchase_confirm.html', {
        'movie': movie,
        'selected_seat_numbers': seat_numbers,
        'selected_seat_count': len(seats),
        'total_price': total_price,
        'selected_seat_ids': selected_seat_ids,
        'selected_datetime': selected_datetime,
    })
    
@login_required
@require_POST
def purchase_complete(request):
    selected_seat_ids = request.POST.getlist('seats')
    selected_datetime = request.session.get('selected_datetime')
    movie_id = request.POST.get('movie_id')
    movie = get_object_or_404(Movie, id=movie_id)
    seats = Seat.objects.filter(id__in=selected_seat_ids)

    payment_method = request.POST.get('payment_method', 'cash')
    convenience_type = request.POST.get('convenience_type') if payment_method == 'convenience_store' else None

    seat_numbers = []
    for seat in seats:
        if not Reservation.objects.filter(movie=movie, seat=seat, show_time=selected_datetime).exists():
            reservation = Reservation.objects.create(
                user=request.user,
                movie=movie,
                seat=seat,
                show_time=selected_datetime,
                payment_method=payment_method,
                convenience_type=convenience_type
            )
            generate_qr_code(reservation)
            Notification.objects.create(
                user=request.user,
                message=(
                    f"映画「{movie.title}」のチケットを購入しました。"
                    f"座席: {seat.seat_number}、上映日時: {selected_datetime}、"
                    f"支払方法: {payment_method} {convenience_type or ''}"
                )
            )
            seat_numbers.append(seat.seat_number)

    total_price = movie.price * len(seat_numbers)

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
        movie_title = reservation.movie.title
        seat_number = reservation.seat.seat_number
        show_time = reservation.show_time
        
        reservation.delete()

        Notification.objects.create(
            user=request.user,
            message=f"映画「{movie_title}」の予約をキャンセルしました。座席: {seat_number}、上映日時: {show_time}"
        )

        messages.success(request, '予約をキャンセルし、通知を送信しました。')
        return redirect('my_reservations')
    return render(request, 'apps/cancel_reservation_confirm.html', {'reservation': reservation})


@login_required
def account_edit(request):
    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = request.POST.get('email', user.email)
        password = request.POST.get('password')
        if password:
            user.set_password(password)
        user.save()
        messages.success(request, 'アカウント情報を更新しました。')
        return redirect('account_edit')
    return render(request, 'pages/account_edit.html')

@login_required
def account_delete(request):
    if request.method == 'POST':
        user = request.user
        user.delete()
        messages.success(request, 'アカウントを削除しました。')
        return redirect('home')
    return render(request, 'pages/account_delete_confirm.html')

@login_required
def notifications_list(request):
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'apps/notifications_list.html', {
        'notifications': notifications
    })

@login_required
def mark_notification_read(request, notification_id):
    notification = Notification.objects.filter(id=notification_id, user=request.user).first()
    if notification and not notification.is_read:
        notification.is_read = True
        notification.save()
    return redirect('notifications_list')

def unread_notifications_processor(request):
    if request.user.is_authenticated:
        unread = Notification.objects.filter(user=request.user, is_read=False)
        return {
            'unread_notifications': unread,
            'unread_count': unread.count()
        }
    return {}

@login_required
@require_POST
def delete_notification(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.delete()
    return redirect('notifications_list')

@login_required
def delete_all_notifications(request):
    Notification.objects.filter(user=request.user).delete()
    return redirect('notifications_list')

@login_required
def payment_input(request):
    selected_seat_ids = request.session.get('selected_seats', [])
    selected_datetime = request.session.get('selected_datetime')

    if not selected_seat_ids or not selected_datetime:
        return redirect('movie_list')

    seats = Seat.objects.filter(id__in=selected_seat_ids)
    movie = seats.first().reservation_set.last().movie if seats and seats.first().reservation_set.exists() else None

    return render(request, 'apps/payment_input.html', {
        'movie': movie,
        'selected_seat_ids': selected_seat_ids,
        'selected_datetime': selected_datetime
    })
    
    from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from .forms import ProfileEditForm

@login_required
def account_edit(request):
    user = request.user
    if request.method == 'POST':
        form = ProfileEditForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            return redirect('account_edit') 
    else:
        form = ProfileEditForm(instance=user)
    return render(request, 'pages/account_edit.html', {'form': form})



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

class IndexPageView(TemplateView):
    template_name = "pages/index.html"
 
class RulePageView(TemplateView):
    template_name = "pages/rule.html"
    
class PolicyPageView(TemplateView):
    template_name = "pages/policy.html"
    
class InquiryPageView(TemplateView):
    template_name = "pages/inquiry.html"
    
class GuidePageView(TemplateView):
    template_name = "pages/guide.html"