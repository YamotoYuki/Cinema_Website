from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView
from .models import Movie, Seat, Reservation, Notification, ChatMessage
from django.contrib.auth.decorators import login_required
from datetime import datetime, timedelta
import qrcode
from io import BytesIO
from django.core.files.base import ContentFile
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from pages.models import UserProfile, Coupon, UserCoupon, PointHistory
from accounts.forms import CustomUserChangeForm  
from pages.forms import UserProfileForm
from django.db import IntegrityError
from django.http import JsonResponse
import json
from django.utils import timezone
from django.db.models import Count, Q
import re
from collections import Counter

User = get_user_model()


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
    status_filter = request.GET.get('status', 'all')
    
    if query:
        movies = Movie.objects.filter(title__icontains=query)
    else:
        if status_filter == 'now_showing':
            movies = Movie.objects.filter(status='now_showing')
        elif status_filter == 'coming_soon':
            movies = Movie.objects.filter(status='coming_soon')
        else:
            movies = Movie.objects.all()
    
    return render(request, 'apps/movie_list.html', {
        'movies': movies,
        'query': query,
        'current_status': status_filter,
    })

def movie_detail(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)
    weekdays = ['月', '火', '水', '木', '金', '土', '日']
    show_dates = []
    
    if movie.status == 'coming_soon' and movie.release_date:
        start_date = movie.release_date
        for i in range(7):
            date = start_date + timedelta(days=i)
            if date >= datetime.today().date():
                show_dates.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'label': f"{date.month}月{date.day}日（{weekdays[date.weekday()]}）",
                    'weekday': weekdays[date.weekday()]
                })
    else:
        for i in range(7):
            date = datetime.today() + timedelta(days=i)
            show_dates.append({
                'date': date.strftime('%Y-%m-%d'),
                'label': f"{date.month}月{date.day}日（{weekdays[date.weekday()]}）",
                'weekday': weekdays[date.weekday()]
            })
    
    can_reserve = True
    release_message = ""
    
    if movie.status == 'coming_soon':
        if movie.release_date:
            if movie.release_date > datetime.today().date():
                can_reserve = False
                days_until_release = (movie.release_date - datetime.today().date()).days
                release_message = f"この映画は{movie.release_date.strftime('%Y年%m月%d日')}公開予定です（あと{days_until_release}日）"
        else:
            can_reserve = False
            release_message = "この映画の公開日は未定です"
    
    return render(request, 'apps/movie_detail.html', {
        'movie': movie,
        'show_dates': show_dates,
        'time_slots': ["09:00～11:00", "11:00～13:00", "13:00～15:00", "15:00～17:00", "17:00～19:00", "19:00～21:00", "21:00～23:00"],
        'can_reserve': can_reserve,
        'release_message': release_message,
    })

@login_required
def seat_select(request, movie_id):
    selected_date = request.GET.get('date')
    time_slot = request.GET.get('time_slot')

    movie = get_object_or_404(Movie, pk=movie_id)
    
    if movie.status == 'coming_soon' and movie.release_date:
        if movie.release_date > datetime.today().date():
            messages.error(request, f"この映画は{movie.release_date.strftime('%Y年%m月%d日')}公開予定です。公開日以降にご予約ください。")
            return redirect('movie_detail', movie_id=movie.id)
    
    seats = Seat.objects.all()

    if not selected_date or not time_slot:
        messages.error(request, "上映日または時間帯の情報がありません。")
        return redirect('movie_detail', movie_id=movie.id)
    
    if movie.status == 'coming_soon' and movie.release_date:
        selected_date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
        if selected_date_obj < movie.release_date:
            messages.error(request, f"公開日({movie.release_date.strftime('%Y年%m月%d日')})以降の日付を選択してください。")
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
    
    now = timezone.now()
    available_coupons = Coupon.objects.filter(
        is_active=True,
        start_date__lte=now,
        expiry_date__gte=now,
        min_purchase__lte=total_price
    ).exclude(
        id__in=UserCoupon.objects.filter(user=request.user).values_list('coupon_id', flat=True)
    )

    if request.method == 'POST':
        payment_method = request.POST.get('payment_method', 'cash')
        convenience_type = request.POST.get('convenience_type') if payment_method == 'convenience_store' else None
        coupon_id = request.POST.get('coupon_id')
        
        final_price = total_price
        used_coupon = None
        
        if coupon_id:
            try:
                coupon = Coupon.objects.get(id=coupon_id)
                
                # 重要：クーポンが既に使用されているかチェック
                if UserCoupon.objects.filter(user=request.user, coupon=coupon).exists():
                    messages.error(request, "このクーポンは既に使用済みです。")
                    return redirect('purchase_confirm')
                
                # クーポンが利用可能かチェック
                now = timezone.now()
                if not coupon.is_active or coupon.start_date > now or coupon.expiry_date < now:
                    messages.error(request, "このクーポンは現在利用できません。")
                    return redirect('purchase_confirm')
                
                if total_price < coupon.min_purchase:
                    messages.error(request, f"このクーポンは¥{coupon.min_purchase}以上のご購入で利用可能です。")
                    return redirect('purchase_confirm')
                
                # 割引計算
                if coupon.discount_type == 'percentage':
                    discount = (total_price * coupon.discount_value) / 100
                    final_price = total_price - discount
                elif coupon.discount_type == 'fixed':
                    final_price = max(0, total_price - coupon.discount_value)
                elif coupon.discount_type == 'free':
                    final_price = 0
                
                used_coupon = coupon
            except Coupon.DoesNotExist:
                messages.warning(request, "無効なクーポンです。")

        for seat in seats:
            if not Reservation.objects.filter(movie=movie, seat=seat, show_time=selected_datetime).exists():
                reservation = Reservation.objects.create(
                    user=request.user,
                    movie=movie,
                    seat=seat,
                    show_time=selected_datetime,
                    payment_method=payment_method,
                    convenience_type=convenience_type,
                    final_price=final_price  # 割引後の金額を保存
                )
                generate_qr_code(reservation)
                
                # クーポン使用記録（重要：ここで1回だけ作成）
                if used_coupon:
                    try:
                        UserCoupon.objects.create(
                            user=request.user,
                            coupon=used_coupon,
                            used_at=timezone.now(),
                            reservation=reservation
                        )
                    except IntegrityError:
                        # unique_togetherで重複エラーが出た場合
                        messages.error(request, "クーポンは既に使用済みです。")
                        reservation.delete()
                        continue
                
                # ポイント付与
                points_earned = 100
                add_points_to_user(request.user, points_earned, f"映画「{movie.title}」のチケット購入（座席: {seat.seat_number}）")

                Notification.objects.create(
                    user=request.user,
                    message=(
                        f"映画「{movie.title}」のチケットを購入しました。"
                        f"座席: {seat.seat_number}、上映日時: {selected_datetime}、"
                        f"支払方法: {payment_method} {convenience_type or ''}"
                        f"{f'、クーポン適用: {used_coupon.code} (割引後: ¥{int(final_price)})' if used_coupon else ''}"
                        f"、{points_earned}ポイント獲得！"
                    )
                )

        request.session.pop('selected_seats', None)
        request.session.pop('selected_datetime', None)
        request.session.pop('movie_id', None)
        
        messages.success(request, 'チケットの購入が完了しました！')
        return redirect('my_reservations')

    return render(request, 'apps/purchase_confirm.html', {
        'movie': movie,
        'selected_seat_numbers': seat_numbers,
        'selected_seat_count': len(seats),
        'total_price': total_price,
        'selected_seat_ids': selected_seat_ids,
        'selected_datetime': selected_datetime,
        'available_coupons': available_coupons,
    })

@login_required
def my_reservations(request):
    reservations = Reservation.objects.filter(user=request.user).order_by('-reserved_at')
    return render(request, 'apps/my_reservations.html', {'reservations': reservations})

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
            
            # ポイント付与
            points_earned = 100
            add_points_to_user(request.user, points_earned, f"映画「{movie.title}」のチケット購入（座席: {seat.seat_number}）")
            
            Notification.objects.create(
                user=request.user,
                message=(
                    f"映画「{movie.title}」のチケットを購入しました。"
                    f"座席: {seat.seat_number}、上映日時: {selected_datetime}、"
                    f"支払方法: {payment_method} {convenience_type or ''}"
                    f"、{points_earned}ポイント獲得！"
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
def cancel_reservation(request, reservation_id):
    reservation = get_object_or_404(Reservation, id=reservation_id, user=request.user)
    if request.method == 'POST':
        movie_title = reservation.movie.title
        seat_number = reservation.seat.seat_number
        show_time = reservation.show_time
        
        # ポイント減算処理
        points_to_deduct = 100
        
        try:
            if hasattr(request.user, 'userprofile') and hasattr(request.user.userprofile, 'points'):
                current_points = request.user.userprofile.points
                if current_points >= points_to_deduct:
                    use_points(request.user, points_to_deduct, f"予約キャンセル: 映画「{movie_title}」（座席: {seat_number}）")
                else:
                    if current_points > 0:
                        use_points(request.user, current_points, f"予約キャンセル: 映画「{movie_title}」（座席: {seat_number}）")
        except Exception as e:
            print(f"ポイント減算エラー: {str(e)}")
        
        # クーポンの使用記録も削除
        try:
            UserCoupon.objects.filter(reservation=reservation).delete()
        except Exception as e:
            print(f"クーポン削除エラー: {str(e)}")
        
        reservation.delete()

        Notification.objects.create(
            user=request.user,
            message=f"映画「{movie_title}」の予約をキャンセルしました。座席: {seat_number}、上映日時: {show_time}、{points_to_deduct}ポイント減算"
        )

        messages.success(request, '予約をキャンセルし、ポイントを減算しました。')
        return redirect('my_reservations')
    return render(request, 'apps/cancel_reservation_confirm.html', {'reservation': reservation})


@login_required
def account_edit(request):
    user = request.user
    profile, _ = UserProfile.objects.get_or_create(user=user)

    if request.method == 'POST':
        user_form = CustomUserChangeForm(request.POST, instance=user)
        profile_form = UserProfileForm(request.POST, request.FILES, instance=profile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, "アカウント情報を更新しました。")
            return redirect('account_edit')
        else:
            messages.error(request, "入力に誤りがあります。")
    else:
        user_form = CustomUserChangeForm(instance=user)
        profile_form = UserProfileForm(instance=profile)

    return render(request, 'pages/account_edit.html', {
        'user_form': user_form,
        'profile_form': profile_form,
    })

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

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        # get_or_createを使用して、既に存在する場合は作成しない
        UserProfile.objects.get_or_create(user=instance)
    else:
        # 更新時は、プロファイルが存在する場合のみ保存
        if hasattr(instance, 'userprofile'):
            instance.userprofile.save()
            
@login_required
def profile_select(request):
    user = request.user
    user_profile, created = UserProfile.objects.get_or_create(user=user)

    if user_profile.is_completed:
        return redirect('home')

    if request.method == 'POST':
        new_username = request.POST.get('username', '').strip()
        if new_username and new_username != user.username:
            from accounts.models import CustomUser
            if CustomUser.objects.filter(username=new_username).exclude(pk=user.pk).exists():
                messages.error(request, "そのユーザー名は既に使われています。")
                return render(request, 'pages/profile_select.html')

            user.username = new_username
            try:
                user.save()
            except IntegrityError:
                messages.error(request, "ユーザー名保存時にエラーが発生しました。")
                return render(request, 'pages/profile_select.html')

        user_profile.phone_number = request.POST.get('phone_number', '')
        if 'profile_image' in request.FILES:
            user_profile.profile_image = request.FILES['profile_image']

        user_profile.is_completed = True
        user_profile.save()

        return redirect('home')

    return render(request, 'pages/profile_select.html')

@login_required
def ai_support(request):
    """AIサポートページ"""
    messages = ChatMessage.objects.filter(user=request.user).order_by('created_at')
    return render(request, 'apps/ai_support.html', {
        'messages': messages,
        'hide_floating_chat': True
    })

@login_required
def ai_chat(request):
    """AIチャットAPI"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '').strip()
            
            if not user_message:
                return JsonResponse({'error': 'メッセージが空です'}, status=400)
            
            chat_message = ChatMessage.objects.create(
                user=request.user,
                message=user_message,
                is_user=True
            )
            
            ai_response = generate_ai_response(user_message, request.user)
            
            ai_message = ChatMessage.objects.create(
                user=request.user,
                message=ai_response,
                is_user=False
            )
            
            return JsonResponse({
                'success': True,
                'user_message': user_message,
                'ai_response': ai_response,
                'timestamp': ai_message.created_at.strftime('%Y-%m-%d %H:%M:%S')
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'POSTリクエストのみ対応'}, status=405)


def generate_ai_response(message, user):
    message_lower = message.lower()
    response = ""
    
    if '予約' in message_lower or '座席' in message_lower:
        response = handle_reservation_inquiry(user)
    elif '空席' in message_lower or '満席' in message_lower:
        response = handle_seat_availability(message, message_lower)
    elif '映画' in message_lower or '上映' in message_lower:
        response = handle_movie_info()
    elif '料金' in message_lower or '支払' in message_lower or '決済' in message_lower:
        response = handle_payment_info()
    elif 'キャンセル' in message_lower or '取消' in message_lower:
        response = handle_cancellation_info()
    elif '劇場' in message_lower or 'アクセス' in message_lower:
        response = handle_theater_info()
    elif '営業' in message_lower or '営業時間' in message_lower:
        response = handle_business_hours()
    elif '会員' in message_lower or 'ポイント' in message_lower:
        response = handle_membership_info(user)
    elif 'こんにち' in message_lower or 'こんばん' in message_lower or 'おはよ' in message_lower:
        response = handle_greeting(user)
    elif 'ありがとう' in message_lower or 'ありがと' in message_lower:
        response = handle_thanks()
    else:
        response = handle_default_response(user)
    
    return response

def handle_reservation_inquiry(user):
    try:
        now = timezone.now()
        
        future_reservations = Reservation.objects.filter(
            user=user, 
            show_time__gte=now
        ).select_related('movie', 'seat').order_by('show_time')[:5]
        
        if future_reservations:
            response = "📋 ご予約状況\n\n"
            for r in future_reservations:
                response += f"🎬 {r.movie.title}\n"
                response += f"📅 {r.show_time}\n"
                response += f"💺 座席: {r.seat.seat_number}\n\n"
            return response
        else:
            return "現在、ご予約はございません。"
    except Exception as e:
        return f"予約情報の取得中にエラーが発生しました。"

def handle_seat_availability(message, message_lower):
    return "空席情報については映画一覧ページからご確認ください。"

def handle_movie_info():
    return "上映中の映画は映画一覧ページでご確認いただけます。"

def handle_payment_info():
    response = "💳 お支払い方法・料金案内\n\n"
    response += "【お支払い方法】\n"
    response += "・現金\n"
    response += "・クレジットカード\n"
    response += "・電子マネー\n"
    response += "・コンビニ払い\n\n"
    response += "【料金】\n"
    response += "一般: ¥1,900\n"
    response += "学生: ¥1,500\n"
    return response

def handle_cancellation_info():
    response = "🔄 予約キャンセルについて\n\n"
    response += "【キャンセル方法】\n"
    response += "マイページ → 予約一覧 → キャンセルボタン\n\n"
    response += "【注意】\n"
    response += "・キャンセル時、獲得ポイントが減算されます\n"
    response += "・上映開始1時間前までキャンセル可能\n"
    return response

def handle_theater_info():
    response = "🏢 HAL CINEMA アクセス情報\n\n"
    response += "【所在地】\n"
    response += "愛知県名古屋市中村区名駅4丁目27-1\n"
    response += "HAL名古屋内\n\n"
    response += "【アクセス】\n"
    response += "JR名古屋駅から徒歩3分\n"
    return response

def handle_business_hours():
    response = "⏰ 営業時間\n\n"
    response += "平日: 9:00 ~ 23:00\n"
    response += "土日祝: 8:30 ~ 23:30\n\n"
    response += "年中無休\n"
    return response

def handle_membership_info(user):
    points = calculate_user_points(user)
    response = f"👤 {user.username}様の会員情報\n\n"
    response += f"💰 現在のポイント: {points}pt\n\n"
    response += "【特典】\n"
    response += "・予約ごとに100pt獲得\n"
    response += "・1,000ptで無料鑑賞\n"
    return response

def handle_greeting(user):
    from datetime import datetime
    hour = datetime.now().hour
    
    if 5 <= hour < 11:
        greeting = "おはようございます"
    elif 11 <= hour < 18:
        greeting = "こんにちは"
    else:
        greeting = "こんばんは"
    
    response = f"{greeting}、{user.username}様！\n"
    response += "HAL CINEMA サポートAIです。\n\n"
    response += "ご質問をお気軽にどうぞ！"
    return response

def handle_thanks():
    return "どういたしまして！\n素敵な映画体験をお楽しみください。"

def handle_default_response(user):
    response = f"{user.username}様、ご質問ありがとうございます。\n\n"
    response += "以下のご質問にお答えできます：\n"
    response += "・予約確認\n"
    response += "・上映情報\n"
    response += "・料金案内\n"
    response += "・劇場案内\n"
    response += "・ポイント確認\n"
    return response

@login_required
def clear_chat_history(request):
    if request.method == 'POST':
        ChatMessage.objects.filter(user=request.user).delete()
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'POSTリクエストのみ対応'}, status=405)

@login_required
def my_profile(request):
    user = request.user
    now = timezone.now()
    
    try:
        total_reservations = Reservation.objects.filter(user=user).count()
        watched_movies = Reservation.objects.filter(user=user, show_time__lt=now).count()
        upcoming_reservations = Reservation.objects.filter(user=user, show_time__gte=now).count()
    except:
        total_reservations = 0
        watched_movies = 0
        upcoming_reservations = 0
    
    user_points = calculate_user_points(user)
    membership_level = get_membership_level(user_points)
    points_to_next_level = get_points_to_next_level(user_points, membership_level)
    progress_percentage = calculate_progress_percentage(user_points, membership_level)
    membership_days = (now.date() - user.date_joined.date()).days
    
    # お気に入りジャンルを取得
    favorite_genre = "未設定"
    try:
        reservations = Reservation.objects.filter(
            user=user,
            show_time__lt=now
        ).select_related('movie')
        
        genres = []
        for res in reservations:
            if hasattr(res.movie, 'genre') and res.movie.genre:
                genres.append(res.movie.genre)
        
        if genres:
            genre_counts = Counter(genres)
            favorite_genre = genre_counts.most_common(1)[0][0]
    except Exception as e:
        print(f"お気に入りジャンル取得エラー: {str(e)}")
    
    # ジャンル統計
    genre_stats = []
    try:
        if genres:
            total = len(genres)
            genre_counts = Counter(genres)
            
            for genre, count in genre_counts.most_common(5):
                percentage = (count / total) * 100
                genre_stats.append({
                    'name': genre,
                    'count': count,
                    'percentage': round(percentage, 1)
                })
    except Exception as e:
        print(f"ジャンル統計取得エラー: {str(e)}")
    
    # 最近のアクティビティ
    recent_activities = []
    try:
        # 最近の予約（今後30日以内）
        upcoming = Reservation.objects.filter(
            user=user,
            show_time__gte=now,
            show_time__lte=now + timedelta(days=30)
        ).select_related('movie').order_by('show_time')[:3]
        
        for res in upcoming:
            recent_activities.append({
                'type': 'reservation',
                'title': f'「{res.movie.title}」を予約しました',
                'date': res.reserved_at if hasattr(res, 'reserved_at') else res.show_time
            })
        
        # 最近視聴した映画（過去30日以内）
        watched = Reservation.objects.filter(
            user=user,
            show_time__lt=now,
            show_time__gte=now - timedelta(days=30)
        ).select_related('movie').order_by('-show_time')[:3]
        
        for res in watched:
            recent_activities.append({
                'type': 'watched',
                'title': f'「{res.movie.title}」を視聴しました',
                'date': res.show_time
            })
        
        # 日付でソート
        recent_activities.sort(key=lambda x: x['date'], reverse=True)
        recent_activities = recent_activities[:5]
    except Exception as e:
        print(f"アクティビティ取得エラー: {str(e)}")
    
    context = {
        'total_reservations': total_reservations,
        'watched_movies': watched_movies,
        'upcoming_reservations': upcoming_reservations,
        'user_points': user_points,
        'membership_level': membership_level,
        'points_to_next_level': points_to_next_level,
        'progress_percentage': progress_percentage,
        'membership_days': membership_days,
        'favorite_genre': favorite_genre,
        'genre_stats': genre_stats,
        'recent_activities': recent_activities,
    }
    
    return render(request, 'my_profile.html', context)


def calculate_user_points(user):
    try:
        if hasattr(user, 'userprofile') and hasattr(user.userprofile, 'points'):
            return user.userprofile.points
        return 0
    except:
        return 0


def get_membership_level(points):
    if points >= 5000:
        return 'platinum'
    elif points >= 2000:
        return 'gold'
    else:
        return 'standard'


def get_points_to_next_level(points, current_level):
    if current_level == 'standard':
        return max(0, 2000 - points)
    elif current_level == 'gold':
        return max(0, 5000 - points)
    else:
        return 0


def calculate_progress_percentage(points, level):
    if level == 'standard':
        return min(100, (points / 2000) * 100)
    elif level == 'gold':
        progress = ((points - 2000) / 3000) * 100
        return min(100, max(0, progress))
    else:
        return 100


def add_points_to_user(user, points, reason=""):
    try:
        if hasattr(user, 'userprofile'):
            profile = user.userprofile
            
            if not hasattr(profile, 'points'):
                profile.points = 0
            
            profile.points += points
            profile.save()
            
            try:
                PointHistory.objects.create(
                    user=user,
                    points=points,
                    reason=reason,
                    balance_after=profile.points
                )
            except:
                pass
            
            return True
    except Exception as e:
        print(f"ポイント付与エラー: {str(e)}")
        return False


def use_points(user, points, reason=""):
    try:
        if hasattr(user, 'userprofile'):
            profile = user.userprofile
            
            if hasattr(profile, 'points') and profile.points >= points:
                profile.points -= points
                profile.save()
                
                try:
                    PointHistory.objects.create(
                        user=user,
                        points=-points,
                        reason=reason,
                        balance_after=profile.points
                    )
                except:
                    pass
                
                return True
            else:
                return False
    except Exception as e:
        print(f"ポイント使用エラー: {str(e)}")
        return False


@login_required
def point_history(request):
    try:
        history = PointHistory.objects.filter(
            user=request.user
        ).order_by('-created_at')[:50]
    except:
        history = []
    
    context = {
        'point_history': history,
        'current_points': calculate_user_points(request.user)
    }
    
    return render(request, 'point_history.html', context)


@login_required
def my_coupons(request):
    now = timezone.now()
    
    available_coupons = Coupon.objects.filter(
        is_active=True,
        start_date__lte=now,
        expiry_date__gte=now
    ).exclude(
        id__in=UserCoupon.objects.filter(user=request.user).values_list('coupon_id', flat=True)
    )
    
    used_coupons = UserCoupon.objects.filter(user=request.user).select_related('coupon')
    
    return render(request, 'apps/my_coupons.html', {
        'available_coupons': available_coupons,
        'used_coupons': used_coupons
    })

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

@login_required
def notice_foodmenu(request):
    return render(request, "notices/notice_foodmenu.html")

@login_required
def notice_dolby(request):
    return render(request, "notices/notice_dolby.html")

@login_required
def notice_phone(request):
    return render(request, "notices/notice_phone.html")

@login_required
def notice_parkir(request):
    return render(request, "notices/notice_parkir.html")

@login_required
def notice_newyear(request):
    return render(request, "notices/notice_newyear.html")

@login_required
def notice_lobby(request):
    return render(request, "notices/notice_lobby.html")

class IndexPageView(TemplateView):
    template_name = "pages/index.html"
 
class RulePageView(TemplateView):
    template_name = "pages/rule.html"
    
class PolicyPageView(TemplateView):
    template_name = "pages/policy.html"
    
from pages.models import Contact

def inquiry_page(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        message = request.POST.get('message', '').strip()
        
        if not name or not email or not message:
            messages.error(request, '全ての項目を入力してください。')
            return render(request, 'pages/inquiry.html')
        
        Contact.objects.create(
            name=name,
            email=email,
            message=message
        )
        
        messages.success(request, 'お問い合わせを送信しました。ご連絡ありがとうございます。')
        return redirect('inquiry')
    
    return render(request, 'pages/inquiry.html')
    
class GuidePageView(TemplateView):
    template_name = "pages/guide.html"