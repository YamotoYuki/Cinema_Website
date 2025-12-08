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
from pages.models import UserProfile
from accounts.forms import CustomUserChangeForm  
from pages.forms import UserProfileForm
from django.db import IntegrityError
from django.http import JsonResponse
import json
from django.utils import timezone
from django.db.models import Count, Q
import re
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
    
    # 検索クエリがある場合
    if query:
        movies = Movie.objects.filter(title__icontains=query)
    else:
        # ステータスフィルター
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
        return redirect('home')
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

@login_required
def account_edit(request):
    user = request.user
    profile, _ = UserProfile.objects.get_or_create(user=user)

    if request.method == 'POST':
        user_form    = CustomUserChangeForm(request.POST, instance=user)
        profile_form = UserProfileForm(request.POST, request.FILES, instance=profile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, "アカウント情報を更新しました。")
            return redirect('account_edit')
        else:
            messages.error(request, "入力に誤りがあります。")
    else:
        user_form    = CustomUserChangeForm(instance=user)
        profile_form = UserProfileForm(instance=profile)

    return render(request, 'pages/account_edit.html', {
        'user_form':    user_form,
        'profile_form': profile_form,
    })


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
    else:
        instance.userprofile.save()

@login_required
def profile_select(request):
    user = request.user
    user_profile, created = UserProfile.objects.get_or_create(user=user)

    # すでにプロフィール登録済みならホームへリダイレクト
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

        # 登録完了フラグを更新
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
            
            # ユーザーメッセージを保存
            chat_message = ChatMessage.objects.create(
                user=request.user,
                message=user_message,
                is_user=True
            )
            
            # AI応答を生成（簡易版）
            ai_response = generate_ai_response(user_message, request.user)
            
            # AI応答を保存
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
    
    # 予約関連
    if '予約' in message_lower or '座席' in message_lower:
        response = handle_reservation_inquiry(user)
    
    # 特定の映画の空席確認
    elif '空席' in message_lower or '満席' in message_lower:
        response = handle_seat_availability(message, message_lower)
    
    # 映画情報
    elif '映画' in message_lower or '上映' in message_lower:
        response = handle_movie_info()
    
    # 料金・支払い
    elif '料金' in message_lower or '支払' in message_lower or '決済' in message_lower or '値段' in message_lower or '価格' in message_lower:
        response = handle_payment_info()
    
    # キャンセル
    elif 'キャンセル' in message_lower or '取消' in message_lower or '払い戻し' in message_lower:
        response = handle_cancellation_info()
    
    # 劇場情報
    elif '劇場' in message_lower or 'アクセス' in message_lower or '場所' in message_lower or '行き方' in message_lower or '駐車場' in message_lower:
        response = handle_theater_info()
    
    # 営業時間
    elif '営業' in message_lower or '営業時間' in message_lower or '開館' in message_lower or '閉館' in message_lower:
        response = handle_business_hours()
    
    # 会員特典
    elif '会員' in message_lower or 'ポイント' in message_lower or '特典' in message_lower:
        response = handle_membership_info(user)
    
    # 座席の種類
    elif '座席の種類' in message_lower or 'シート' in message_lower or 'プレミアム' in message_lower:
        response = handle_seat_types()
    
    # 持ち込み・飲食
    elif '持ち込み' in message_lower or '飲食' in message_lower or 'フード' in message_lower or 'ドリンク' in message_lower or 'メニュー' in message_lower or '売店' in message_lower:
        response = handle_food_info()
    
    # サービス・施設案内
    elif 'サービス' in message_lower or '施設' in message_lower or '設備' in message_lower:
        response = handle_service_info()
    
    # ラウンジ
    elif 'ラウンジ' in message_lower or 'wifi' in message_lower or 'wi-fi' in message_lower:
        response = handle_lounge_info()
    
    # キッズサービス
    elif 'キッズ' in message_lower or '子供' in message_lower or '子ども' in message_lower or 'こども' in message_lower or '赤ちゃん' in message_lower or '授乳' in message_lower or 'おむつ' in message_lower:
        response = handle_kids_service()
    
    # お問い合わせ
    elif 'お問い合わせ' in message_lower or '電話' in message_lower or '連絡先' in message_lower:
        response = handle_contact_info()
    
    # 挨拶
    elif 'こんにち' in message_lower or 'こんばん' in message_lower or 'おはよ' in message_lower or 'はじめまして' in message_lower or 'hello' in message_lower:
        response = handle_greeting(user)
    
    # ありがとう
    elif 'ありがとう' in message_lower or 'ありがと' in message_lower or 'サンキュー' in message_lower or 'thanks' in message_lower:
        response = handle_thanks()
    
    # デフォルト応答
    else:
        response = handle_default_response(user)
    
    return response


def handle_reservation_inquiry(user):
    """予約状況の確認"""
    try:
        now = timezone.now()
        
        # show_timeがNoneでないものだけを取得
        future_reservations = Reservation.objects.filter(
            user=user, 
            show_time__isnull=False,
            show_time__gte=now
        ).select_related('movie', 'seat').order_by('show_time')[:5]
        
        past_reservations = Reservation.objects.filter(
            user=user,
            show_time__isnull=False,
            show_time__lt=now
        ).select_related('movie', 'seat').order_by('-show_time')[:3]
        
        if future_reservations or past_reservations:
            response = " ご予約状況\n\n"
            
            # 今後の予約
            if future_reservations:
                for r in future_reservations:
                    try:
                        # 基本情報の表示
                        response += f"\n {r.movie.title}\n"
                        
                        # 上映日時の取得と表示
                        show_time_value = None
                        try:
                            # show_timeフィールドを取得
                            show_time_value = getattr(r, 'show_time', None)
                            
                            if show_time_value and show_time_value is not None:
                                # datetimeオブジェクトかどうか確認
                                if hasattr(show_time_value, 'strftime'):
                                    response += f"    上映日時: {show_time_value.strftime('%Y年%m月%d日 %H:%M')}\n"
                                else:
                                    # 文字列の場合
                                    response += f"    上映日時: {show_time_value}\n"
                            else:
                                response += f"    上映日時: 未定\n"
                        except AttributeError:
                            response += f"    上映日時: 日時情報なし\n"
                        except Exception as e:
                            response += f"    上映日時: 取得エラー\n"
                        
                        # 座席情報
                        try:
                            if hasattr(r, 'seat') and r.seat:
                                response += f"    座席: {r.seat.seat_number}\n"
                            else:
                                response += f"    座席: 未割当\n"
                        except:
                            response += f"    座席: 情報なし\n"
                        
                        # シアター情報
                        try:
                            if hasattr(r, 'theater') and r.theater:
                                theater_name = r.theater.name
                                response += f"    シアター: {theater_name}\n"
                        except:
                            pass
                        
                        # 上映までの時間
                        try:
                            if show_time_value and hasattr(show_time_value, 'strftime'):
                                time_until = show_time_value - now
                                if time_until.days > 0:
                                    response += f"    あと{time_until.days}日\n"
                                elif time_until.total_seconds() > 0:
                                    hours = time_until.seconds // 3600
                                    minutes = (time_until.seconds % 3600) // 60
                                    if hours > 0:
                                        response += f"    あと{hours}時間{minutes}分\n"
                                    else:
                                        response += f"    あと{minutes}分\n"
                        except:
                            pass
                            
                    except Exception as e:
                        # 最悪の場合でも映画タイトルだけは表示
                        try:
                            response += f"\n {r.movie.title}\n"
                            response += f"   ℹ 詳細情報の取得に失敗しました\n"
                        except:
                            response += f"\n 予約情報\n"
                            response += f"   ℹ データエラー\n"
            
            # 過去の予約（視聴履歴）
            if past_reservations:
                response += "\n\n【視聴履歴（直近3件）】\n"
                for r in past_reservations:
                    response += f"\n {r.movie.title}\n"
                    # show_timeのNullチェック
                    if r.show_time:
                        try:
                            response += f"    視聴日: {r.show_time.strftime('%Y年%m月%d日')}\n"
                        except:
                            response += f"    視聴日: 情報取得エラー\n"
                    else:
                        response += f"    視聴日: 日付未定\n"
                    
                    # 座席情報も安全に取得
                    try:
                        response += f"    座席: {r.seat.seat_number}\n"
                    except:
                        response += f"    座席: 情報なし\n"
            
            response += "\n\n 詳細は「マイページ」からご確認いただけます。"
        else:
            response = "現在、ご予約はございません。\n\n"
            
            # 上映中・公開予定の映画を提案
            upcoming_movies = Movie.objects.filter(
                Q(status='now_showing') | Q(status='coming_soon')
            ).order_by('release_date')[:5]
            
            if upcoming_movies:
                response += "【上映中・公開予定の映画】\n"
                for movie in upcoming_movies:
                    try:
                        if movie.status == 'now_showing':
                            response += f"\n {movie.title} 上映中\n"
                            if movie.release_date:
                                response += f"    公開日: {movie.release_date.strftime('%Y年%m月%d日')}\n"
                            response += f"    ジャンル: {movie.genre if hasattr(movie, 'genre') else '未定'}\n"
                            response += f"   ⏱ 上映時間: {movie.duration}分\n" if hasattr(movie, 'duration') else ""
                        else:
                            response += f"\n {movie.title} 🆕公開予定\n"
                            if movie.release_date:
                                response += f"    公開予定日: {movie.release_date.strftime('%Y年%m月%d日')}\n"
                                try:
                                    days_until = (movie.release_date - now.date()).days
                                    response += f"    あと{days_until}日で公開\n"
                                except:
                                    pass
                    except Exception as e:
                        # 個別の映画でエラーが出ても続行
                        response += f"\n {movie.title}\n"
                        response += f"   ℹ 詳細情報準備中\n"
            
            response += "\n\n ぜひチケットをご購入ください！"
        
        return response
    except Exception as e:
        return f"申し訳ございません。予約情報の取得中にエラーが発生しました。\nマイページから直接ご確認いただくか、お問い合わせください。\n\nエラー詳細: {str(e)}"


def handle_seat_availability(message, message_lower):
    """特定の映画の空席確認"""
    try:
        # 映画タイトルを抽出
        movie_title = extract_movie_title(message)
        
        # 日付も抽出
        target_date = extract_date_from_message(message)
        
        # 人数も抽出
        num_people = extract_number_of_people(message)
        
        if movie_title:
            try:
                # 複数ヒットする可能性があるので、filter→firstを使用
                movies = Movie.objects.filter(title__icontains=movie_title)
                
                if not movies.exists():
                    return "申し訳ございません。該当する映画が見つかりませんでした。\n\n 映画タイトルをもう一度ご確認いただくか、上映中の映画一覧からお探しください。"
                
                # 複数ヒットした場合
                if movies.count() > 1:
                    response = f"「{movie_title}」に該当する映画が複数見つかりました。\n\n"
                    for idx, movie in enumerate(movies[:5], 1):
                        response += f"{idx}. {movie.title}\n"
                        if hasattr(movie, 'release_date') and movie.release_date:
                            response += f"   公開日: {movie.release_date.strftime('%Y年%m月%d日')}\n"
                    response += "\n 正確な映画タイトルで再度お尋ねください。"
                    return response
                
                # 1件のみヒット
                movie = movies.first()
                now = timezone.now()
                
                # 日付指定がある場合
                if target_date:
                    start_of_day = target_date.replace(hour=0, minute=0, second=0)
                    end_of_day = target_date.replace(hour=23, minute=59, second=59)
                    
                    # その日のスケジュールを取得
                    try:
                        schedules = MovieSchedule.objects.filter(
                            movie=movie,
                            show_time__gte=start_of_day,
                            show_time__lte=end_of_day
                        ).order_by('show_time')
                    except:
                        # MovieScheduleがない場合はReservationから推測
                        reservations = Reservation.objects.filter(
                            movie=movie,
                            show_time__gte=start_of_day,
                            show_time__lte=end_of_day
                        ).values('show_time').distinct()
                        
                        # 仮のスケジュールオブジェクトを作成
                        class FakeSchedule:
                            def __init__(self, show_time):
                                self.show_time = show_time
                                self.total_seats = 100
                        
                        schedules = [FakeSchedule(r['show_time']) for r in reservations]
                    
                    if schedules:
                        response = f"『{movie.title}』\n"
                        response += f"{target_date.strftime('%Y年%m月%d日(%a)')}の空席状況\n\n"
                        
                        has_available = False
                        for schedule in schedules:
                            reserved = Reservation.objects.filter(
                                movie=movie,
                                show_time=schedule.show_time
                            ).count()
                            total = getattr(schedule, 'total_seats', 100)
                            available = total - reserved
                            
                            # 人数指定がある場合
                            if num_people:
                                if available >= num_people:
                                    has_available = True
                                    status = f" {num_people}名様ご予約可能（残り{available}席）"
                                else:
                                    status = f" {num_people}名様不可（残り{available}席）"
                            else:
                                if available > 20:
                                    status = f"余裕あり（残り{available}席）"
                                    has_available = True
                                elif available > 5:
                                    status = f"残りわずか（残り{available}席）"
                                    has_available = True
                                elif available > 0:
                                    status = f"残り{available}席"
                                    has_available = True
                                else:
                                    status = "🈵 満席"
                            
                            response += f"{schedule.show_time.strftime('%H:%M')} {status}\n"
                        
                        # 人数指定がある場合の総括メッセージ
                        if num_people:
                            if has_available:
                                response += f"\n\n はい、{target_date.strftime('%m月%d日')}は{num_people}名様のご予約が可能な上映回がございます！"
                            else:
                                response += f"\n\n 申し訳ございません。{target_date.strftime('%m月%d日')}は{num_people}名様のご予約が難しい状況です。\n別の日程をご検討ください。"
                        else:
                            if has_available:
                                response += f"\n\n はい、{target_date.strftime('%m月%d日')}はまだ空席がございます！"
                            else:
                                response += f"\n\n 申し訳ございません。{target_date.strftime('%m月%d日')}は全ての上映回が満席です。"
                        
                        response += "\n\n ご予約は映画一覧ページからお願いいたします。"
                    else:
                        response = f"申し訳ございません。\n『{movie.title}』の{target_date.strftime('%Y年%m月%d日')}の上映スケジュールは\n現在公開されておりません。"
                
                # 日付指定なしの場合
                else:
                    try:
                        schedules = MovieSchedule.objects.filter(
                            movie=movie,
                            show_time__gte=now
                        ).order_by('show_time')[:10]
                    except:
                        # MovieScheduleがない場合
                        reservations = Reservation.objects.filter(
                            movie=movie,
                            show_time__gte=now
                        ).values('show_time').distinct().order_by('show_time')[:10]
                        
                        class FakeSchedule:
                            def __init__(self, show_time):
                                self.show_time = show_time
                                self.total_seats = 100
                        
                        schedules = [FakeSchedule(r['show_time']) for r in reservations]
                    
                    if schedules:
                        response = f"『{movie.title}』の空席状況\n\n"
                        if hasattr(movie, 'release_date') and movie.release_date:
                            try:
                                response += f"公開日: {movie.release_date.strftime('%Y年%m月%d日')}\n"
                            except:
                                pass
                        if hasattr(movie, 'duration') and movie.duration:
                            response += f"⏱上映時間: {movie.duration}分\n"
                        response += "\n"
                        
                        for schedule in schedules:
                            reserved = Reservation.objects.filter(
                                movie=movie,
                                show_time=schedule.show_time
                            ).count()
                            total = getattr(schedule, 'total_seats', 100)
                            available = total - reserved
                            
                            if available == 0:
                                status = "🈵 満席"
                            elif available <= 5:
                                status = f"残りわずか（{available}席）"
                            elif available <= 20:
                                status = f"残り{available}席"
                            else:
                                status = f"余裕あり（{available}席）"
                            
                            try:
                                response += f"{schedule.show_time.strftime('%m/%d(%a) %H:%M')} {status}\n"
                            except:
                                response += f"上映予定 {status}\n"
                        
                        response += "\n\n ご予約はお早めに！"
                    else:
                        response = f"『{movie.title}』の上映スケジュールが見つかりませんでした。\n\n"
                        response += "映画一覧ページで最新情報をご確認ください。"
                
                return response
                        
            except Exception as e:
                return f"空席情報の取得中にエラーが発生しました。\n\nエラー詳細: {str(e)}"
        else:
            response = "映画タイトルを教えていただけますか？\n\n"
            response += "例: 「鬼滅の刃はまだ席空いてますか？」\n"
            response += "例: 「12/25の鬼滅の刃を3人予約したいです」"
            return response
    except Exception as e:
        return f"空席情報の取得中にエラーが発生しました。\n\nエラー詳細: {str(e)}"


def handle_reservation_request(message, message_lower):
    """予約リクエストの処理"""
    try:
        movie_title = extract_movie_title(message)
        target_date = extract_date_from_message(message)
        num_people = extract_number_of_people(message)
        
        response = "ご予約のお手続きについて\n\n"
        
        if movie_title:
            response += f"【ご希望内容】\n"
            response += f"作品: {movie_title}\n"
            
            if target_date:
                response += f"日付: {target_date.strftime('%Y年%m月%d日(%a)')}\n"
            
            if num_people:
                response += f"人数: {num_people}名様\n"
            
            response += "\n"
            
            # 空席確認
            if movie_title and target_date:
                # 該当する映画を検索
                try:
                    movies = Movie.objects.filter(title__icontains=movie_title)
                    
                    if movies.exists():
                        if movies.count() > 1:
                            response += "該当する映画が複数あります：\n"
                            for idx, m in enumerate(movies[:3], 1):
                                response += f"{idx}. {m.title}\n"
                            response += "\n正確な映画タイトルをお聞かせください。\n\n"
                        else:
                            movie = movies.first()
                            now = timezone.now()
                            start_of_day = target_date.replace(hour=0, minute=0, second=0)
                            end_of_day = target_date.replace(hour=23, minute=59, second=59)
                            
                            # スケジュール確認
                            try:
                                schedules = MovieSchedule.objects.filter(
                                    movie=movie,
                                    show_time__gte=start_of_day,
                                    show_time__lte=end_of_day
                                ).order_by('show_time')
                            except:
                                # MovieScheduleがない場合
                                reservations = Reservation.objects.filter(
                                    movie=movie,
                                    show_time__gte=start_of_day,
                                    show_time__lte=end_of_day
                                ).values('show_time').distinct()
                                
                                class FakeSchedule:
                                    def __init__(self, show_time):
                                        self.show_time = show_time
                                        self.total_seats = 100
                                
                                schedules = [FakeSchedule(r['show_time']) for r in reservations]
                            
                            if schedules:
                                has_available = False
                                response += f"{target_date.strftime('%m月%d日')}の空席状況：\n\n"
                                
                                for schedule in schedules[:5]:  # 最大5つ表示
                                    reserved = Reservation.objects.filter(
                                        movie=movie,
                                        show_time=schedule.show_time
                                    ).count()
                                    total = getattr(schedule, 'total_seats', 100)
                                    available = total - reserved
                                    
                                    if num_people:
                                        if available >= num_people:
                                            has_available = True
                                            status = f"ご予約可能（残り{available}席）"
                                        else:
                                            status = f"不可（残り{available}席）"
                                    else:
                                        if available > 0:
                                            has_available = True
                                            status = f"○ 残り{available}席"
                                        else:
                                            status = "× 満席"
                                    
                                    try:
                                        response += f"{schedule.show_time.strftime('%H:%M')} {status}\n"
                                    except:
                                        response += f"上映予定 {status}\n"
                                
                                response += "\n"
                                
                                if has_available:
                                    if num_people:
                                        response += f"はい、{num_people}名様のご予約が可能です！\n\n"
                                    else:
                                        response += f"はい、ご予約可能な上映回がございます！\n\n"
                                else:
                                    if num_people:
                                        response += f"申し訳ございません。{num_people}名様のご予約が難しい状況です。\n\n"
                                    else:
                                        response += f"申し訳ございません。全ての上映回が満席です。\n\n"
                            else:
                                response += f"{target_date.strftime('%m月%d日')}の上映スケジュールは\n現在公開されておりません。\n\n"
                    else:
                        response += f"『{movie_title}』が見つかりませんでした。\n"
                        response += "映画タイトルをご確認ください。\n\n"
                except Exception as e:
                    response += f"空席確認中にエラーが発生しました。\n\n"
            
            response += "【予約方法】\n"
            response += "映画一覧ページから作品を選択\n"
            response += "上映日時を選択\n"
            response += "3️お好きな座席を選択\n"
            response += "お支払い方法を選択して完了\n\n"
            response += "オンライン予約なら24時間いつでもOK！"
        else:
            response += "ご予約をご希望の映画タイトルを教えていただけますか？\n\n"
            response += "例: 「鬼滅の刃を12/25に3人予約したいです」"
        
        return response
    except Exception as e:
        return f"予約リクエストの処理中にエラーが発生しました。\n\nエラー: {str(e)}"


def handle_coming_soon_movies():
    """公開予定の映画リスト"""
    try:
        now = timezone.now()
        
        # 公開予定の映画を取得
        try:
            coming_movies = Movie.objects.filter(
                status='coming_soon'
            ).order_by('release_date')[:10]
        except:
            # statusフィールドがない場合
            coming_movies = Movie.objects.filter(
                release_date__gt=now.date()
            ).order_by('release_date')[:10]
        
        if coming_movies:
            response = "公開予定の映画\n\n"
            
            for idx, movie in enumerate(coming_movies, 1):
                try:
                    response += f"{idx}.{movie.title}\n"
                    
                    if hasattr(movie, 'release_date') and movie.release_date:
                        response += f"公開予定日: {movie.release_date.strftime('%Y年%m月%d日(%a)')}\n"
                        
                        # 公開までの日数
                        try:
                            days_until = (movie.release_date - now.date()).days
                            if days_until > 0:
                                response += f"あと{days_until}日で公開！\n"
                            elif days_until == 0:
                                response += f"本日公開！\n"
                        except:
                            pass
                    
                    if hasattr(movie, 'genre') and movie.genre:
                        response += f"ジャンル: {movie.genre}\n"
                    
                    if hasattr(movie, 'duration') and movie.duration:
                        response += f"上映時間: {movie.duration}分\n"
                    
                    if hasattr(movie, 'description') and movie.description:
                        desc = movie.description[:60] + "..." if len(movie.description) > 60 else movie.description
                        response += f"{desc}\n"
                    
                    response += "\n"
                except Exception as e:
                    continue
            
            response += "詳細は映画一覧ページでご確認いただけます。\n"
            response += "公開をお楽しみに！"
        else:
            response = "現在、公開予定の映画情報はございません。\n\n"
            response += "最新情報は随時更新されますので、\n"
            response += "定期的にチェックしてください！"
        
        return response
    except Exception as e:
        return f"公開予定映画の取得中にエラーが発生しました。\n\nエラー: {str(e)}"


def extract_date_from_message(message):
    """メッセージから日付を抽出"""
    try:
        from datetime import datetime, timedelta
        import re
        
        # 日付パターンを抽出
        patterns = [
            (r'(\d{4})[/-年](\d{1,2})[/-月](\d{1,2})', 
             lambda m: datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))),
            (r'(\d{1,2})[/-月](\d{1,2})', 
             lambda m: datetime(datetime.now().year, int(m.group(1)), int(m.group(2)))),
            (r'今日', lambda m: datetime.now()),
            (r'明日', lambda m: datetime.now() + timedelta(days=1)),
            (r'明後日|あさって', lambda m: datetime.now() + timedelta(days=2)),
        ]
        
        for pattern, date_func in patterns:
            match = re.search(pattern, message)
            if match:
                return date_func(match)
        
        return None
    except:
        return None


def extract_number_of_people(message):
    """メッセージから人数を抽出"""
    try:
        import re
        
        # 人数パターン
        patterns = [
            r'(\d+)人',
            r'(\d+)名',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message)
            if match:
                return int(match.group(1))
        
        return None
    except:
        return None


def handle_movie_info():
    """映画情報"""
    try:
        # statusフィールドの有無を確認
        try:
            now_showing = Movie.objects.filter(status='now_showing').count()
            coming_soon = Movie.objects.filter(status='coming_soon').count()
        except:
            # statusフィールドがない場合は全件取得
            now_showing = Movie.objects.all().count()
            coming_soon = 0
        
        response = f"映画情報\n\n"
        
        if now_showing > 0:
            response += f"上映中: {now_showing}作品\n"
        if coming_soon > 0:
            response += f"🆕 公開予定: {coming_soon}作品\n"
        
        if now_showing == 0 and coming_soon == 0:
            response += "現在、登録されている映画情報はございません。\n"
        
        response += "\n"
        
        # 人気作品TOP3（エラーハンドリング強化）
        try:
            if hasattr(Movie.objects.first(), 'popularity'):
                popular_movies = Movie.objects.filter(status='now_showing').order_by('-popularity')[:3]
            else:
                # popularityフィールドがない場合は最新作品を表示
                popular_movies = Movie.objects.all().order_by('-id')[:3]
            
            if popular_movies:
                response += "！注目作品！\n"
                for idx, movie in enumerate(popular_movies, 1):
                    try:
                        response += f"{idx}. {movie.title}\n"
                    except:
                        continue
                response += "\n"
        except Exception as e:
            pass
        
        response += "映画一覧ページから詳細をご確認いただけます。お好みの作品をお探しください！"
        return response
    except Exception as e:
        return f"映画情報を取得できませんでした。映画一覧ページをご確認ください。\n\nエラー: {str(e)}"


def handle_payment_info():
    """料金・支払い情報"""
    response = "お支払い方法・料金案内\n\n"
    response += "【お支払い方法】\n"
    response += "現金\n"
    response += "クレジットカード（VISA / MasterCard / JCB / AMEX / Diners）\n"
    response += "電子マネー\n"
    response += "  ・PayPay\n"
    response += "  ・メルペイ\n"
    response += "  ・Paypal\n"
    response += "コンビニ払い\n"
    response += "  ・セブンイレブン\n"
    response += "  ・ファミリーマート\n"
    response += "  ・ローソン\n"
    response += "  ・デイリーヤマザキ\n\n"
    response += "【料金案内】\n"
    response += "一般: ¥1,900\n"
    response += "大学生・専門学生: ¥1,500（学生証提示必須）\n"
    response += "高校生: ¥1,000（学生証提示必須）\n"
    response += "中学生以下: ¥1,000\n"
    response += "シニア（60歳以上）: ¥1,200（年齢確認書類提示）\n"
    response += "障がい者割引: ¥1,000（手帳提示、同伴者1名まで同額）\n\n"
    response += "【特別料金】\n"
    response += "レイトショー（20:00以降）: ¥1,400\n"
    response += "モーニングショー（平日朝10時まで）: ¥1,400\n"
    response += "ペア割引（2名様）: ¥3,400\n"
    response += "ファミリー割引（3名様以上）: お一人様¥1,500\n\n"
    response += "会員様は更にお得な割引がございます！"
    return response


def handle_cancellation_info():
    """キャンセル情報"""
    response = "予約キャンセルについて\n\n"
    response += "【キャンセル方法】\n"
    response += "マイページ → 予約一覧 → キャンセルしたい予約を選択\n\n"
    response += "【キャンセル可能期限】\n"
    response += "上映開始時刻の1時間前まで\n\n"
    response += "【払い戻しについて】\n"
    response += "クレジットカード決済: 3~5営業日で返金\n"
    response += "現金・電子マネー: 劇場窓口で返金\n"
    response += "コンビニ払い: お支払い前ならキャンセル料なし\n\n"
    response += "【注意事項】\n"
    response += "上映開始1時間を切った後のキャンセルは不可\n"
    response += "特別興行（イベント上映等）はキャンセル不可の場合あり\n\n"
    response += "お早めのお手続きをお願いいたします。"
    return response


def handle_theater_info():
    """劇場情報"""
    response = "HAL CINEMA アクセス情報\n\n"
    response += "【所在地】\n"
    response += "〒450-0002\n"
    response += "愛知県名古屋市中村区名駅4丁目27-1\n"
    response += "HAL名古屋 総合校舎スパイラルタワーズ内\n\n"
    response += "【電車でのアクセス】\n"
    response += "JR「名古屋駅」桜通口から徒歩3分\n"
    response += "地下鉄東山線・桜通線「名古屋駅」8番出口直結\n"
    response += "名鉄・近鉄「名古屋駅」から徒歩5分\n\n"
    response += "【お車でのアクセス】\n"
    response += "名古屋高速都心環状線「錦橋出口」より約5分\n"
    response += "提携駐車場あり（3時間まで無料）\n"
    response += "   ・タイムズ名駅4丁目（120台）\n"
    response += "   ・名鉄協商パーキング（80台）\n\n"
    response += "【館内設備】\n"
    response += "スクリーン数: 8スクリーン\n"
    response += "総座席数: 1,200席\n"
    response += "バリアフリー対応\n"
    response += "売店・カフェあり\n"
    response += "無料Wi-Fi完備\n\n"
    response += "ご来場の際はお気をつけてお越しください！"
    return response


def handle_business_hours():
    """営業時間"""
    response = "営業時間のご案内\n\n"
    response += "【通常営業】\n"
    response += "平日: 9:00 ~ 23:00\n"
    response += "土日祝: 8:30 ~ 23:30\n\n"
    response += "【チケット窓口】\n"
    response += "営業開始30分前から営業終了まで\n\n"
    response += "【売店】\n"
    response += "各上映開始30分前から営業\n\n"
    response += "【定休日】\n"
    response += "年中無休（設備点検日を除く）\n\n"
    response += "最新の営業情報は公式サイトをご確認ください。"
    return response


def handle_membership_info(user):
    """会員特典"""
    response = f"会員特典のご案内\n\n"
    response += f"こんにちは、{user.username}様！\n\n"
    response += "【会員特典】\n"
    response += "毎回100ポイント獲得\n"
    response += "1,000ポイントで1回無料鑑賞\n"
    response += "誕生月は1,100円で鑑賞可能\n"
    response += "会員限定試写会へご招待\n"
    response += "オンライン予約手数料無料\n"
    response += "ポップコーン・ドリンク割引\n\n"
    response += "【現在のポイント】\n"
    
    # ポイント情報を取得（仮）
    try:
        points = getattr(user, 'points', 0)
        response += f"{points}ポイント\n\n"
        if points >= 1000:
            response += "無料鑑賞チケットと交換できます！\n\n"
    except:
        response += "ポイント情報はマイページでご確認ください\n\n"
    
    response += "詳細はマイページからご確認いただけます。"
    return response


def handle_seat_types():
    """座席の種類"""
    response = "座席タイプのご案内\n\n"
    response += "【スタンダードシート】\n"
    response += "通常料金でご利用いただける座席\n"
    response += "幅: 50cm / リクライニング角度: 15度\n\n"
    response += "【プレミアムシート】（+¥500）\n"
    response += "ゆったりとした広めの座席\n"
    response += "幅: 60cm / リクライニング角度: 25度\n"
    response += "ドリンクホルダー・サイドテーブル付き\n\n"
    response += "【ペアシート】（+¥800/2名）\n"
    response += "カップル・ご夫婦におすすめ\n"
    response += "肘掛けなしのソファタイプ\n\n"
    response += "【車椅子席】\n"
    response += "バリアフリー対応\n"
    response += "介助者1名様まで同席可能\n\n"
    response += "座席は予約時に選択できます！"
    return response


def handle_food_info():
    """飲食・持ち込み情報"""
    response = "飲食・持ち込みについて\n\n"
    response += "【館内売店メニュー】\n\n"
    response += "ポップコーン\n"
    response += "  ・塩味: S ¥400 / M ¥500 / L ¥600\n"
    response += "  ・キャラメル: S ¥450 / M ¥550 / L ¥650\n"
    response += "  ・ハーフ&ハーフ: M ¥600 / L ¥700\n\n"
    response += "ドリンク\n"
    response += "  ・コーラ/ジンジャーエール: S ¥300 / M ¥400 / L ¥500\n"
    response += "  ・オレンジ/メロンソーダ: S ¥300 / M ¥400 / L ¥500\n"
    response += "  ・アイスコーヒー/ティー: M ¥400 / L ¥500\n\n"
    response += "フード\n"
    response += "  ・ホットドッグ: ¥500\n"
    response += "  ・ナチョス&チーズ: ¥600\n"
    response += "  ・チキンナゲット(5個): ¥450\n\n"
    response += "スイーツ\n"
    response += "  ・アイスクリーム: ¥350\n"
    response += "  ・限定コラボスイーツ: ¥800\n\n"
    response += "【お得なセット】\n"
    response += "レギュラーセット: ¥800（通常¥900）\n"
    response += "   ポップコーン(M) + ドリンク(M)\n"
    response += "ラージセット: ¥1,000（通常¥1,100）\n"
    response += "   ポップコーン(L) + ドリンク(L)\n\n"
    response += "【キッズメニュー】\n"
    response += "ポップコーン(S): ¥250\n"
    response += "ジュース: ¥200\n"
    response += "キッズランチボックス: ¥500\n\n"
    response += "【持ち込みについて】\n"
    response += "ペットボトル飲料\n"
    response += "密閉容器に入った軽食\n"
    response += "においの強い食べ物\n"
    response += "アルコール類\n"
    response += "熱い食べ物\n\n"
    response += "【お願い】\n"
    response += "・音の出る包装はお控えください\n"
    response += "・ゴミは各自お持ち帰りください\n\n"
    response += "マナーを守って楽しくご鑑賞ください！"
    return response


def handle_contact_info():
    """お問い合わせ情報"""
    response = "お問い合わせ先\n\n"
    response += "【電話】\n"
    response += " 00-1234-5678\n"
    response += "受付時間: 9:00~23:00（年中無休）\n\n"
    response += "【メール】\n"
    response += "info@halcinema.jp\n"
    response += "※24時間受付（返信は営業時間内）\n\n"
    response += "【公式SNS】\n"
    response += "Twitter: @HAL_CINEMA\n"
    response += "Instagram: @halcinema_official\n"
    response += "Facebook: HAL CINEMA名古屋\n\n"
    response += "【よくある質問】\n"
    response += "公式サイトのFAQページもご活用ください\n\n"
    response += "お気軽にお問い合わせください！"
    return response


def handle_service_info():
    """サービス・施設案内"""
    response = "施設・サービスのご案内\n\n"
    response += "【館内サービス】\n"
    response += "売店・フードコーナー\n"
    response += "   ポップコーン、ドリンク、ホットドッグなど充実のメニュー\n\n"
    response += "ラウンジスペース\n"
    response += "   無料Wi-Fi、充電スポット、カフェコーナー完備\n\n"
    response += "キッズ向けサービス\n"
    response += "   チャイルドシート、授乳室、キッズプレイエリア\n\n"
    response += "【その他のサービス】\n"
    response += "モバイルオーダー対応\n"
    response += "誕生日特典\n"
    response += "会員ポイント制度\n"
    response += "友達紹介キャンペーン\n\n"
    response += "詳しくは各サービスについてお尋ねください！\n"
    response += "例: 「ラウンジについて」「キッズサービスは？」"
    return response


def handle_lounge_info():
    """ラウンジ情報"""
    response = "ラウンジサービスのご案内\n\n"
    response += "【快適なラウンジ空間】\n"
    response += "上映前後のひとときをゆったりお過ごしいただけます。\n\n"
    response += "【設備・サービス】\n\n"
    response += "無料Wi-Fi\n"
    response += "  高速インターネットが無料。パスワード不要で簡単接続！\n\n"
    response += "充電スポット\n"
    response += "  電源コンセント・USBポート完備\n"
    response += "  USB-C、Lightning両対応\n\n"
    response += "カフェコーナー\n"
    response += "  エスプレッソ: ¥300\n"
    response += "  カプチーノ: ¥400\n"
    response += "  カフェラテ: ¥400\n\n"
    response += "映画雑誌・書籍コーナー\n"
    response += "  最新の映画雑誌を自由に閲覧可能\n\n"
    response += "快適な空調システム\n"
    response += "  季節を問わず快適な温度を維持\n\n"
    response += "多様な座席タイプ\n"
    response += "  ソファ席、テーブル席、カウンター席\n\n"
    response += "【ロケーション】\n"
    response += "2階ロビー: メインラウンジ（50席）\n"
    response += "3階: プレミアムラウンジ（会員専用・20席）\n\n"
    response += "【営業時間】\n"
    response += "平日: 10:00 - 23:00\n"
    response += "土日祝: 9:00 - 24:00\n\n"
    response += "プレミアム会員の方は3階ラウンジで\n"
    response += "   無料ドリンクサービスもご利用いただけます！"
    return response


def handle_kids_service():
    """キッズサービス情報"""
    response = "キッズ向けサービスのご案内\n\n"
    response += "お子様連れのお客様も安心してお楽しみいただけます。\n\n"
    response += "【サービス一覧】\n\n"
    response += "チャイルドシート（無料貸出）\n"
    response += "  座面を高くするクッション\n"
    response += "  対象: 身長100cm〜130cm\n\n"
    response += "チャイルドヘッドホン（無料貸出）\n"
    response += "  音量調整機能付き\n"
    response += "  対象: 3歳〜10歳\n"
    response += "  ※数に限りあり。事前予約推奨\n\n"
    response += "授乳室・おむつ交換室\n"
    response += "  場所: 2階ロビー（完全個室）\n"
    response += "  設備: おむつ交換台、調乳用温水器、ソファ\n"
    response += "  営業時間中いつでも利用可能\n\n"
    response += "キッズトイレ\n"
    response += "  低い便器、補助便座、踏み台完備\n"
    response += "  各フロアのトイレ内に設置\n\n"
    response += "キッズプレイエリア\n"
    response += "  場所: 2階ロビー\n"
    response += "  設備: 滑り台、ボールプール、絵本コーナー\n"
    response += "  対象: 2歳〜6歳（保護者同伴必須）\n\n"
    response += "キッズメニュー\n"
    response += "  ポップコーン(S): ¥250\n"
    response += "  ジュース: ¥200\n"
    response += "  キッズランチボックス: ¥500\n\n"
    response += "【ママズシアター】\n"
    response += "開催: 毎月第2・第4木曜日 午前中\n"
    response += "赤ちゃん連れでも安心して楽しめる特別上映\n\n"
    response += "特徴:\n"
    response += "  ・場内を少し明るめに設定\n"
    response += "  ・音量をやや控えめに設定\n"
    response += "  ・泣いてしまってもOK\n"
    response += "  ・ベビーカー置き場完備（10台分）\n"
    response += "  ・途中退出・再入場自由\n\n"
    response += "【ご注意事項】\n"
    response += "  作品により年齢制限あり\n"
    response += "  周りのお客様へのご配慮をお願いします\n"
    response += "  館内では必ず保護者が付き添いください\n\n"
    response += "  おすすめ: 平日午前中や休日初回上映は\n"
    response += "  比較的空いており、お子様連れでも快適です！"
    return response


def handle_greeting(user):
    """挨拶"""
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
    response += "映画のご予約、上映情報、劇場案内など、\n"
    response += "どのようなことでもお気軽にお尋ねください。\n\n"
    response += "「予約確認」「上映中の映画」「料金」などと\n"
    response += "お声がけいただくとスムーズです！"
    return response


def handle_thanks():
    """お礼への返答"""
    response = "どういたしまして！\n\n"
    response += "他にご不明な点がございましたら、\n"
    response += "いつでもお声がけください。\n\n"
    response += "素敵な映画体験をお楽しみくださいませ。"
    return response


def handle_default_response(user):
    """デフォルト応答"""
    response = f"{user.username}様、ご質問ありがとうございます。\n\n"
    response += "以下のようなご質問にお答えできます：\n\n"
    response += "ご予約関連\n"
    response += "  ・予約確認\n"
    response += "  ・空席状況\n"
    response += "  ・キャンセル方法\n\n"
    response += "映画情報\n"
    response += "  ・上映中の作品\n"
    response += "  ・公開予定\n"
    response += "  ・上映スケジュール\n"
    response += "  ・おすすめ映画\n\n"
    response += "料金・お支払い\n"
    response += "  ・料金案内\n"
    response += "  ・支払い方法\n"
    response += "  ・割引情報\n"
    response += "  ・キャンペーン\n\n"
    response += "劇場案内\n"
    response += "  ・アクセス方法\n"
    response += "  ・営業時間\n"
    response += "  ・館内設備\n\n"
    response += "サービス・施設\n"
    response += "  ・売店メニュー\n"
    response += "  ・ラウンジ\n"
    response += "  ・キッズサービス\n\n"
    response += "会員特典\n"
    response += "  ・ポイント確認\n"
    response += "  ・特典内容\n\n"
    response += "お困りのことがございましたら、\n"
    response += "具体的にお聞かせください！"
    return response


def extract_movie_title(message):
    """メッセージから映画タイトルを抽出する簡易関数"""
    # 「」や『』で囲まれたタイトルを抽出
    patterns = [
        r'[「『](.+?)[」』]',  # 「タイトル」『タイトル』
        r'「(.+?)」',
        r'『(.+?)』',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, message)
        if match:
            return match.group(1)
    
    # 括弧がない場合、「の空席」「は満席」などのパターンから抽出
    keywords = ['の空席', 'は満席', 'の満席', 'の予約', 'を予約', 'が見たい', 'の上映']
    for keyword in keywords:
        if keyword in message:
            parts = message.split(keyword)
            if len(parts) > 0:
                # 最後の単語を取得
                candidate = parts[0].strip().split()[-1] if parts[0].strip() else None
                if candidate and len(candidate) > 1:
                    return candidate
    
    return None


# ============================================
# 追加機能: レコメンデーション機能
# ============================================

def handle_recommendation(user, message_lower):
    """映画レコメンデーション"""
    try:
        # ユーザーの視聴履歴から好みを分析
        past_reservations = Reservation.objects.filter(
            user=user
        ).select_related('movie').order_by('-show_time')[:10]
        
        if past_reservations:
            # 視聴したジャンルを集計
            watched_genres = []
            for r in past_reservations:
                if hasattr(r.movie, 'genre'):
                    watched_genres.append(r.movie.genre)
            
            # 最も多いジャンル
            if watched_genres:
                from collections import Counter
                most_common_genre = Counter(watched_genres).most_common(1)[0][0]
                
                # 同じジャンルの未視聴作品を推薦
                watched_movie_ids = [r.movie.id for r in past_reservations]
                recommendations = Movie.objects.filter(
                    genre=most_common_genre,
                    status='now_showing'
                ).exclude(id__in=watched_movie_ids)[:3]
                
                if recommendations:
                    response = f"{user.username}様へのおすすめ映画\n\n"
                    response += f"あなたがよく観る「{most_common_genre}」ジャンルから\n"
                    response += "おすすめをご紹介します！\n\n"
                    
                    for idx, movie in enumerate(recommendations, 1):
                        response += f"{idx}.{movie.title}\n"
                        response += f"公開日: {movie.release_date.strftime('%Y年%m月%d日')}\n"
                        if hasattr(movie, 'rating'):
                            response += f"評価: {movie.rating}/5.0\n"
                        if hasattr(movie, 'description'):
                            desc = movie.description[:50] + "..." if len(movie.description) > 50 else movie.description
                            response += f"{desc}\n"
                        response += "\n"
                    
                    return response
        
        # 視聴履歴がない場合は人気作品を推薦
        popular_movies = Movie.objects.filter(
            status='now_showing'
        ).order_by('-popularity')[:5]
        
        if popular_movies:
            response = "今週の人気作品\n\n"
            for idx, movie in enumerate(popular_movies, 1):
                response += f"{idx}. {movie.title}\n"
                if hasattr(movie, 'genre'):
                    response += f"{movie.genre}\n"
                if hasattr(movie, 'rating'):
                    response += f"   ⭐ {movie.rating}/5.0\n"
                response += "\n"
            
            return response
        
        return "現在上映中の作品をご確認ください。"
        
    except Exception as e:
        return f"おすすめ情報の取得中にエラーが発生しました。\n{str(e)}"


# ============================================
# 追加機能: 日付指定での上映確認
# ============================================

def handle_schedule_by_date(message):
    """特定日付の上映スケジュール確認"""
    try:
        from datetime import datetime, timedelta
        import re
        
        # 日付パターンを抽出
        date_patterns = [
            (r'(\d{1,2})月(\d{1,2})日', lambda m: datetime(datetime.now().year, int(m.group(1)), int(m.group(2)))),
            (r'今日', lambda m: datetime.now()),
            (r'明日', lambda m: datetime.now() + timedelta(days=1)),
            (r'明後日|あさって', lambda m: datetime.now() + timedelta(days=2)),
            (r'来週', lambda m: datetime.now() + timedelta(days=7)),
        ]
        
        target_date = None
        for pattern, date_func in date_patterns:
            match = re.search(pattern, message)
            if match:
                target_date = date_func(match)
                break
        
        if not target_date:
            return "日付を指定してください。\n例: 「明日の上映スケジュール」「12月25日の上映」"
        
        # その日の上映スケジュールを取得
        start_of_day = target_date.replace(hour=0, minute=0, second=0)
        end_of_day = target_date.replace(hour=23, minute=59, second=59)
        
        schedules = MovieSchedule.objects.filter(
            show_time__gte=start_of_day,
            show_time__lte=end_of_day
        ).select_related('movie').order_by('show_time')
        
        if schedules:
            response = f"{target_date.strftime('%Y年%m月%d日(%a)')}の上映スケジュール\n\n"
            
            current_movie = None
            for schedule in schedules:
                if current_movie != schedule.movie.title:
                    current_movie = schedule.movie.title
                    response += f"\n{schedule.movie.title}\n"
                
                # 空席状況
                reserved = Reservation.objects.filter(
                    movie=schedule.movie,
                    show_time=schedule.show_time
                ).count()
                total = getattr(schedule, 'total_seats', 100)
                available = total - reserved
                
                seat_status = "○" if available > 20 else "△" if available > 5 else "×" if available > 0 else "✕"
                
                response += f"  {schedule.show_time.strftime('%H:%M')} {seat_status} "
                if hasattr(schedule, 'theater'):
                    response += f"[{schedule.theater.name}]"
                response += "\n"
            
            response += "\n\n○:余裕 △:残少 ×:残僅少 ✕:満席"
            return response
        else:
            return f"{target_date.strftime('%Y年%m月%d日')}の上映スケジュールは\nまだ公開されていません。"
    
    except Exception as e:
        return f"スケジュール取得中にエラーが発生しました。\n{str(e)}"


# ============================================
# 追加機能: ジャンル検索
# ============================================

def handle_genre_search(message_lower):
    """ジャンルで映画を検索"""
    try:
        genre_keywords = {
            'アクション': ['アクション', 'action'],
            'コメディ': ['コメディ', 'comedy', '笑える', '面白い'],
            'ホラー': ['ホラー', 'horror', '怖い', 'ホラー'],
            'ロマンス': ['ロマンス', 'romance', '恋愛', 'ラブ'],
            'SF': ['sf', 'サイエンスフィクション', 'sci-fi'],
            'ドキュメンタリー': ['ドキュメンタリー', 'documentary', '実話'],
            'アニメ': ['アニメ', 'anime', 'アニメーション'],
            'ファンタジー': ['ファンタジー', 'fantasy', '冒険'],
            'スリラー': ['スリラー', 'thriller', 'サスペンス'],
            'ドラマ': ['ドラマ', 'drama', '感動'],
        }
        
        detected_genre = None
        for genre, keywords in genre_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                detected_genre = genre
                break
        
        if not detected_genre:
            response = "ジャンルを指定してください。\n\n"
            response += "【対応ジャンル】\n"
            for genre in genre_keywords.keys():
                response += f"・{genre}\n"
            return response
        
        # ジャンルで映画を検索
        movies = Movie.objects.filter(
            genre__icontains=detected_genre,
            status='now_showing'
        )[:5]
        
        if movies:
            response = f"{detected_genre}ジャンルの上映中作品\n\n"
            for movie in movies:
                response += f"{movie.title}\n"
                if hasattr(movie, 'rating'):
                    response += f"評価: {movie.rating}/5.0\n"
                if hasattr(movie, 'duration'):
                    response += f"{movie.duration}分\n"
                if hasattr(movie, 'description'):
                    desc = movie.description[:60] + "..." if len(movie.description) > 60 else movie.description
                    response += f"{desc}\n"
                response += "\n"
            
            return response
        else:
            return f"申し訳ございません。現在{detected_genre}ジャンルの\n上映作品はございません。"
    
    except Exception as e:
        return f"ジャンル検索中にエラーが発生しました。\n{str(e)}"


# ============================================
# 追加機能: 評価・レビュー情報
# ============================================

def handle_movie_reviews(movie_title):
    """映画のレビュー・評価情報"""
    try:
        movie = Movie.objects.get(title__icontains=movie_title)
        
        response = f"⭐ 『{movie.title}』の評価\n\n"
        
        # 平均評価
        if hasattr(movie, 'rating'):
            response += f"総合評価: {movie.rating}/5.0\n"
        
        # レビュー件数
        if hasattr(movie, 'review_count'):
            response += f"レビュー数: {movie.review_count}件\n\n"
        
        # 最新レビュー（Reviewモデルがある場合）
        try:
            reviews = Review.objects.filter(movie=movie).order_by('-created_at')[:3]
            if reviews:
                response += "【最新レビュー】\n\n"
                for review in reviews:
                    response += f"{review.user.username}\n"
                    response += f"{review.rating}/5.0\n"
                    comment = review.comment[:80] + "..." if len(review.comment) > 80 else review.comment
                    response += f"{comment}\n\n"
        except:
            pass
        
        response += "詳細なレビューは作品ページでご確認いただけます。"
        return response
        
    except Movie.DoesNotExist:
        return "該当する映画が見つかりませんでした。"
    except Exception as e:
        return f"レビュー情報の取得中にエラーが発生しました。\n{str(e)}"

def handle_campaign_info():
    """キャンペーン・クーポン情報"""
    from datetime import datetime
    
    response = "開催中のキャンペーン\n\n"
    
    # 現在の日付から自動判定
    now = datetime.now()
    day_of_week = now.weekday()  # 0:月曜 6:日曜
    
    response += "【定期キャンペーン】\n\n"
    
    if day_of_week == 0:  # 月曜日
        response += "ムービーマンデー\n"
        response += "毎週月曜日は全作品¥1,200！\n\n"
    
    if day_of_week == 2:  # 水曜日
        response += "レディースデー\n"
        response += "女性の方は¥1,200でご鑑賞いただけます！\n\n"
    
    if now.day == 1:  # 毎月1日
        response += "ファーストデー\n"
        response += "毎月1日は誰でも¥1,200！\n\n"
    
    if 20 <= now.day <= 25:  # 20日〜25日
        response += "シネマポイントウィーク\n"
        response += "ポイント2倍進呈中！\n\n"
    
    response += "【期間限定キャンペーン】\n\n"
    response += "ウィンターキャンペーン\n"
    response += "2024年12月1日〜2025年1月31日\n"
    response += "対象作品が¥1,500で鑑賞可能！\n\n"
    
    response += "友達紹介キャンペーン\n"
    response += "お友達を紹介すると両方に500ポイントプレゼント！\n\n"
    
    response += "最新情報は公式サイト・アプリでチェック！"
    
    return response

def process_chatbot_message_enhanced(user, message):
    """
    拡張版チャットボットメッセージ処理
    """
    message_lower = message.lower()
    response = ""
    
    # 予約関連
    if '予約' in message_lower or '座席' in message_lower:
        response = handle_reservation_inquiry(user)
    
    # 特定の映画の空席確認
    elif '空席' in message_lower or '満席' in message_lower:
        response = handle_seat_availability(message, message_lower)
    
    # 日付指定の上映スケジュール
    elif any(word in message_lower for word in ['今日', '明日', '明後日', 'あさって', '月', '日']):
        if any(word in message_lower for word in ['上映', 'スケジュール', '時間']):
            response = handle_schedule_by_date(message)
        else:
            response = handle_movie_info()
    
    # おすすめ・レコメンド
    elif 'おすすめ' in message_lower or 'レコメンド' in message_lower or 'オススメ' in message_lower:
        response = handle_recommendation(user, message_lower)
    
    # ジャンル検索
    elif 'ジャンル' in message_lower or any(word in message_lower for word in ['アクション', 'コメディ', 'ホラー', 'sf']):
        response = handle_genre_search(message_lower)
    
    # レビュー・評価
    elif 'レビュー' in message_lower or '評価' in message_lower or '口コミ' in message_lower:
        movie_title = extract_movie_title(message)
        if movie_title:
            response = handle_movie_reviews(movie_title)
        else:
            response = "映画タイトルを教えてください。\n例: 「○○○の評価を教えて」"
    
    # キャンペーン・クーポン
    elif 'キャンペーン' in message_lower or 'クーポン' in message_lower or '割引' in message_lower or 'セール' in message_lower:
        response = handle_campaign_info()
    
    # 映画情報
    elif '映画' in message_lower or '上映' in message_lower:
        response = handle_movie_info()
    
    # 料金・支払い
    elif '料金' in message_lower or '支払' in message_lower or '決済' in message_lower or '値段' in message_lower or '価格' in message_lower:
        response = handle_payment_info()
    
    # キャンセル
    elif 'キャンセル' in message_lower or '取消' in message_lower or '払い戻し' in message_lower:
        response = handle_cancellation_info()
    
    # 劇場情報
    elif '劇場' in message_lower or 'アクセス' in message_lower or '場所' in message_lower or '行き方' in message_lower or '駐車場' in message_lower:
        response = handle_theater_info()
    
    # 営業時間
    elif '営業' in message_lower or '営業時間' in message_lower or '開館' in message_lower or '閉館' in message_lower:
        response = handle_business_hours()
    
    # 会員特典
    elif '会員' in message_lower or 'ポイント' in message_lower or '特典' in message_lower:
        response = handle_membership_info(user)
    
    # 座席の種類
    elif '座席の種類' in message_lower or 'シート' in message_lower or 'プレミアム' in message_lower:
        response = handle_seat_types()
    
    # 持ち込み・飲食
    elif '持ち込み' in message_lower or '飲食' in message_lower or 'フード' in message_lower or 'ドリンク' in message_lower:
        response = handle_food_info()
    
    # お問い合わせ
    elif 'お問い合わせ' in message_lower or '電話' in message_lower or '連絡先' in message_lower:
        response = handle_contact_info()
    
    # 挨拶
    elif 'こんにち' in message_lower or 'こんばん' in message_lower or 'おはよ' in message_lower or 'はじめまして' in message_lower or 'hello' in message_lower:
        response = handle_greeting(user)
    
    # ありがとう
    elif 'ありがとう' in message_lower or 'ありがと' in message_lower or 'サンキュー' in message_lower or 'thanks' in message_lower:
        response = handle_thanks()
    
    # デフォルト応答
    else:
        response = handle_default_response(user)
    
    return response

@login_required
def clear_chat_history(request):
    """チャット履歴をクリア"""
    if request.method == 'POST':
        ChatMessage.objects.filter(user=request.user).delete()
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'POSTリクエストのみ対応'}, status=405)

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
    
class InquiryPageView(TemplateView):
    template_name = "pages/inquiry.html"
    
class GuidePageView(TemplateView):
    template_name = "pages/guide.html"