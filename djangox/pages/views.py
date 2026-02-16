from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView
from .models import Movie, Seat, Reservation, Notification, ChatMessage
from django.contrib.auth.decorators import login_required
from datetime import datetime, timedelta
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
from django.http import JsonResponse, HttpResponse
import json
from django.utils import timezone
from django.db.models import Count, Q
import re
from collections import Counter
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib import colors
import qrcode
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

User = get_user_model()

# 日本語フォントの登録
try:
    pdfmetrics.registerFont(UnicodeCIDFont('HeiseiMin-W3'))
    pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
    JAPANESE_FONT_AVAILABLE = True
except:
    JAPANESE_FONT_AVAILABLE = False


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
    
    # ShowScheduleモデルをインポート（既にインポートされている場合は不要）
    from .models import ShowSchedule
    
    today = datetime.today().date()
    weekdays = ['月', '火', '水', '木', '金', '土', '日']
    
    # 実際の上映スケジュールを取得（今日から7日間）
    schedules = ShowSchedule.objects.filter(
        movie=movie,
        date__gte=today,
        date__lte=today + timedelta(days=6)
    ).order_by('date', 'start_time')
    
    # 日付ごとにグループ化
    schedules_by_date = {}
    
    for schedule in schedules:
        date_str = schedule.date.strftime('%Y-%m-%d')
        
        if date_str not in schedules_by_date:
            schedules_by_date[date_str] = {
                'date': date_str,
                'label': f"{schedule.date.month}月{schedule.date.day}日（{weekdays[schedule.date.weekday()]}）",
                'weekday': weekdays[schedule.date.weekday()],
                'time_slots': []
            }
        
        # 時間帯の文字列を作成
        time_slot = f"{schedule.start_time.strftime('%H:%M')}～{schedule.end_time.strftime('%H:%M')}"
        
        schedules_by_date[date_str]['time_slots'].append({
            'time': time_slot,
            'screen': schedule.screen,
            'format': schedule.format if schedule.format else ''
        })
    
    # 辞書をリストに変換
    show_dates = list(schedules_by_date.values())
    
    # スケジュールが登録されていない場合は、デフォルトで7日間の日付のみ表示
    if not show_dates:
        for i in range(7):
            date = today + timedelta(days=i)
            
            # 公開予定の映画で公開日前の日付はスキップ
            if movie.status == 'coming_soon' and movie.release_date:
                if date < movie.release_date:
                    continue
            
            show_dates.append({
                'date': date.strftime('%Y-%m-%d'),
                'label': f"{date.month}月{date.day}日（{weekdays[date.weekday()]}）",
                'weekday': weekdays[date.weekday()],
                'time_slots': []  # スケジュール未登録
            })
    
    # 予約可否の判定
    can_reserve = True
    release_message = ""
    
    if movie.status == 'coming_soon':
        if movie.release_date:
            if movie.release_date > today:
                can_reserve = False
                days_until_release = (movie.release_date - today).days
                release_message = f"この映画は{movie.release_date.strftime('%Y年%m月%d日')}公開予定です（あと{days_until_release}日）"
        else:
            can_reserve = False
            release_message = "この映画の公開日は未定です"
    
    return render(request, 'apps/movie_detail.html', {
        'movie': movie,
        'show_dates': show_dates,
        'can_reserve': can_reserve,
        'release_message': release_message,
    })

@login_required
def seat_select(request, movie_id):
    selected_date = request.GET.get('date')
    time_slot = request.GET.get('time_slot')

    movie = get_object_or_404(Movie, pk=movie_id)
    
    # デバッグ情報（問題解決後に削除可能）
    print("=" * 50)
    print("seat_select - デバッグ情報")
    print(f"映画: {movie.title} (ID: {movie_id})")
    print(f"選択された日付: {selected_date}")
    print(f"選択された時間帯: {time_slot}")
    print(f"GET parameters: {request.GET}")
    print("=" * 50)
    
    # 公開予定映画のチェック
    if movie.status == 'coming_soon' and movie.release_date:
        if movie.release_date > datetime.today().date():
            messages.error(request, f"この映画は{movie.release_date.strftime('%Y年%m月%d日')}公開予定です。公開日以降にご予約ください。")
            return redirect('movie_detail', movie_id=movie.id)
    
    # 座席データを取得
    seats = Seat.objects.all()

    # 日付と時間帯のチェック
    if not selected_date or not time_slot:
        messages.error(request, "上映日または時間帯の情報がありません。映画詳細ページから再度選択してください。")
        print("エラー: 日付または時間帯が選択されていません")
        return redirect('movie_detail', movie_id=movie.id)
    
    # 公開予定映画の日付チェック
    if movie.status == 'coming_soon' and movie.release_date:
        try:
            selected_date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
            if selected_date_obj < movie.release_date:
                messages.error(request, f"公開日({movie.release_date.strftime('%Y年%m月%d日')})以降の日付を選択してください。")
                return redirect('movie_detail', movie_id=movie.id)
        except ValueError as e:
            messages.error(request, "日付の形式が正しくありません。")
            print(f"日付パースエラー: {e}")
            return redirect('movie_detail', movie_id=movie.id)

    # 上映時間の文字列を作成
    show_time_str = f"{selected_date} {time_slot}"
    print(f"上映時間文字列: {show_time_str}")

    # 予約済み座席を取得
    reserved_seats = Reservation.objects.filter(
        movie=movie,
        show_time=show_time_str
    ).values_list('seat__id', flat=True)

    reserved_seat_numbers = set(
        r.seat.seat_number for r in Reservation.objects.filter(
            movie=movie,
            show_time=show_time_str
        ).select_related('seat')
    )
    
    print(f"予約済み座席数: {len(reserved_seats)}")
    print(f"予約済み座席番号: {reserved_seat_numbers}")

    # 座席レイアウト
    rows = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']
    left_cols = [str(i) for i in range(1, 5)]
    center_cols = [str(i) for i in range(5, 17)]
    right_cols = [str(i) for i in range(17, 21)]
    wheelchair_seat_numbers = {'A5', 'A6', 'A15', 'A16'}

    # POST: 座席選択確定
    if request.method == 'POST':
        selected_seat_ids = request.POST.getlist('seats')
        
        print(f"選択された座席ID: {selected_seat_ids}")

        if not selected_seat_ids:
            messages.error(request, "座席を選択してください。")
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

        # セッションに保存
        request.session['selected_seats'] = selected_seat_ids
        request.session['selected_datetime'] = show_time_str
        request.session['movie_id'] = movie.id
        
        print(f"セッションに保存: seats={selected_seat_ids}, datetime={show_time_str}, movie={movie.id}")

        return redirect('purchase_confirm')

    # GET: 座席選択画面を表示
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
def my_reservations(request):
    reservations = Reservation.objects.filter(user=request.user).order_by('-reserved_at')
    return render(request, 'apps/my_reservations.html', {'reservations': reservations})


@login_required
def cancel_reservation(request, reservation_id):
    """
    予約キャンセル処理（ポイント返還対応 - モーダル版）
    
    POST リクエストのみ受け付け（my_reservations.htmlのモーダルから呼ばれる）
    
    処理内容:
    1. 使用したポイントを返還
    2. 獲得したポイントを取り消し
    3. クーポン使用記録を削除
    4. 予約を削除
    5. 通知を作成
    """
    reservation = get_object_or_404(Reservation, id=reservation_id, user=request.user)
    
    if request.method == 'POST':
        movie_title = reservation.movie.title
        seat_number = reservation.seat.seat_number
        show_time = reservation.show_time
        
        # ========================================
        # ポイント処理
        # ========================================
        points_returned = 0
        points_deducted = 0
        
        try:
            # この予約に関連するポイント履歴を取得（最近10件）
            point_histories = PointHistory.objects.filter(
                user=request.user,
                reason__icontains=f'{movie_title}'
            ).order_by('-created_at')[:10]
            
            # -----------------------------------------
            # 1. 使用ポイントを返還
            # -----------------------------------------
            for history in point_histories:
                # マイナスのポイント = 使用したポイント
                if history.points < 0 and 'チケット購入' in history.reason and seat_number in history.reason:
                    used_points = abs(history.points)  # 絶対値を取得
                    
                    # ポイントを返還（add_points_to_user関数を使用）
                    add_points_to_user(
                        request.user, 
                        used_points, 
                        f"予約キャンセル返還: {movie_title}（{seat_number}）"
                    )
                    points_returned = used_points
                    break
            
            # -----------------------------------------
            # 2. 獲得ポイントを取り消し
            # -----------------------------------------
            for history in point_histories:
                # プラスのポイント = 獲得したポイント
                if history.points > 0 and 'チケット購入' in history.reason and seat_number in history.reason:
                    earned_points = history.points
                    current_points = calculate_user_points(request.user)
                    
                    # 保有ポイントから獲得分を減算
                    if current_points >= earned_points:
                        # 保有ポイントが十分にある場合
                        use_points(
                            request.user, 
                            earned_points, 
                            f"予約キャンセル取り消し: {movie_title}（{seat_number}）"
                        )
                        points_deducted = earned_points
                    elif current_points > 0:
                        # 保有ポイントが不足している場合は、保有分だけ減算
                        use_points(
                            request.user, 
                            current_points, 
                            f"予約キャンセル取り消し（一部）: {movie_title}（{seat_number}）"
                        )
                        points_deducted = current_points
                    break
                    
        except Exception as e:
            print(f"ポイント処理エラー: {str(e)}")
            import traceback
            traceback.print_exc()
        
        # ========================================
        # クーポン使用記録削除
        # ========================================
        try:
            UserCoupon.objects.filter(reservation=reservation).delete()
        except Exception as e:
            print(f"クーポン削除エラー: {str(e)}")
        
        # ========================================
        # チケット削除（テーブルが存在する場合のみ）
        # ========================================
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pages_ticket'")
                if cursor.fetchone():
                    if hasattr(reservation, 'tickets'):
                        reservation.tickets.all().delete()
        except Exception as e:
            print(f"チケット削除エラー: {str(e)}")
        
        # ========================================
        # 予約削除
        # ========================================
        reservation.delete()

        # ========================================
        # 通知作成
        # ========================================
        notification_msg = (
            f"映画「{movie_title}」の予約をキャンセルしました。\n"
            f"座席: {seat_number}\n"
            f"上映日時: {show_time}"
        )
        
        if points_returned > 0:
            notification_msg += f"\n✓ 使用ポイント返還: +{points_returned}pt"
        
        if points_deducted > 0:
            notification_msg += f"\n✓ 獲得ポイント取り消し: -{points_deducted}pt"
        
        Notification.objects.create(user=request.user, message=notification_msg)

        # ========================================
        # 成功メッセージ
        # ========================================
        success_msg = '予約をキャンセルしました。'
        
        if points_returned > 0:
            success_msg += f' 使用ポイント {points_returned}pt を返還しました。'
        
        if points_deducted > 0:
            success_msg += f' 獲得ポイント {points_deducted}pt を取り消しました。'
        
        messages.success(request, success_msg)
        return redirect('my_reservations')
    
    # GET リクエストの場合は予約一覧にリダイレクト
    return redirect('my_reservations')


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
    """AIレスポンス生成（Bootstrap Icons使用版）"""
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
    """予約状況の確認（Bootstrap Icons版）"""
    try:
        now = timezone.now()
        
        future_reservations = Reservation.objects.filter(
            user=user, 
            show_time__gte=now
        ).select_related('movie', 'seat').order_by('show_time')[:5]
        
        if future_reservations:
            response = "<i class='bi bi-clipboard-check'></i> <strong>ご予約状況</strong>\n\n"
            for r in future_reservations:
                response += f"<i class='bi bi-film'></i> {r.movie.title}\n"
                response += f"<i class='bi bi-calendar-event'></i> {r.show_time}\n"
                response += f"<i class='bi bi-ticket-perforated'></i> 座席: {r.seat.seat_number}\n\n"
            return response
        else:
            return "<i class='bi bi-info-circle'></i> 現在、ご予約はございません。"
    except Exception as e:
        return "<i class='bi bi-exclamation-triangle'></i> 予約情報の取得中にエラーが発生しました。"

def handle_seat_availability(message, message_lower):
    """空席情報（Bootstrap Icons版）"""
    return "<i class='bi bi-search'></i> 空席情報については映画一覧ページからご確認ください。"

def handle_movie_info():
    """映画情報（Bootstrap Icons版）"""
    return "<i class='bi bi-film'></i> 上映中の映画は映画一覧ページでご確認いただけます。"

def handle_payment_info():
    """料金・支払い情報（Bootstrap Icons版）"""
    response = "<i class='bi bi-credit-card'></i> <strong>お支払い方法・料金案内</strong>\n\n"
    response += "<strong>【お支払い方法】</strong>\n"
    response += "<i class='bi bi-cash-coin'></i> 現金\n"
    response += "<i class='bi bi-credit-card-2-front'></i> クレジットカード\n"
    response += "<i class='bi bi-phone'></i> 電子マネー（PayPay、メルペイ）\n"
    response += "<i class='bi bi-shop'></i> コンビニ払い\n"
    response += "<i class='bi bi-coin'></i> ポイント払い <span style='color: #22c55e;'>NEW</span>\n\n"
    response += "<strong>【料金】</strong>\n"
    response += "一般: <strong>¥1,900</strong>\n"
    response += "大学生・専門学生: <strong>¥1,500</strong>\n"
    response += "高校生以下: <strong>¥1,000</strong>\n"
    response += "シニア（60歳以上）: <strong>¥1,200</strong>\n"
    response += "障がい者割引: <strong>¥1,000</strong>\n\n"
    response += "<strong>【ポイント払いについて】</strong>\n"
    response += "<i class='bi bi-check-circle'></i> 保有ポイントで直接お支払い可能\n"
    response += "<i class='bi bi-check-circle'></i> 1pt = ¥1として利用\n"
    response += "<i class='bi bi-info-circle'></i> ポイント払いの場合、新たなポイント獲得はありません\n"
    return response

def handle_cancellation_info():
    """キャンセル情報（Bootstrap Icons版）"""
    response = "<i class='bi bi-x-circle'></i> <strong>予約キャンセルについて</strong>\n\n"
    response += "<strong>【キャンセル方法】</strong>\n"
    response += "マイページ <i class='bi bi-arrow-right'></i> 予約一覧 <i class='bi bi-arrow-right'></i> キャンセルボタン\n\n"
    response += "<strong>【注意事項】</strong>\n"
    response += "<i class='bi bi-exclamation-triangle'></i> 使用したポイントは返還されます\n"
    response += "<i class='bi bi-exclamation-triangle'></i> 獲得したポイントは取り消されます\n"
    response += "<i class='bi bi-clock'></i> 上映開始1時間前までキャンセル可能\n"
    return response

def handle_theater_info():
    """劇場情報（Bootstrap Icons版）"""
    response = "<i class='bi bi-building'></i> <strong>HAL CINEMA アクセス情報</strong>\n\n"
    response += "<strong>【所在地】</strong>\n"
    response += "<i class='bi bi-geo-alt-fill'></i> 愛知県名古屋市中村区名駅4丁目27-1\n"
    response += "HAL名古屋内\n\n"
    response += "<strong>【アクセス】</strong>\n"
    response += "<i class='bi bi-train-front'></i> JR名古屋駅から徒歩3分\n"
    return response

def handle_business_hours():
    """営業時間（Bootstrap Icons版）"""
    response = "<i class='bi bi-clock-history'></i> <strong>営業時間</strong>\n\n"
    response += "<i class='bi bi-calendar-week'></i> 平日: 9:00 ~ 23:00\n"
    response += "<i class='bi bi-calendar-day'></i> 土日祝: 8:30 ~ 23:30\n\n"
    response += "<i class='bi bi-check-circle'></i> 年中無休\n"
    return response

def handle_membership_info(user):
    """会員情報（Bootstrap Icons版）"""
    points = calculate_user_points(user)
    response = f"<i class='bi bi-person-circle'></i> <strong>{user.username}様の会員情報</strong>\n\n"
    response += f"<i class='bi bi-coin'></i> 現在のポイント: <strong style='color: #667eea;'>{points}pt</strong>\n\n"
    response += "<strong>【特典】</strong>\n"
    response += "<i class='bi bi-gift'></i> 予約ごとに100pt獲得\n"
    response += "<i class='bi bi-ticket-perforated'></i> 1,000ptで無料鑑賞\n"
    return response

def handle_greeting(user):
    """挨拶（Bootstrap Icons版）"""
    from datetime import datetime
    hour = datetime.now().hour
    
    if 5 <= hour < 11:
        greeting = "おはようございます"
        icon = "<i class='bi bi-sunrise'></i>"
    elif 11 <= hour < 18:
        greeting = "こんにちは"
        icon = "<i class='bi bi-sun'></i>"
    else:
        greeting = "こんばんは"
        icon = "<i class='bi bi-moon-stars'></i>"
    
    response = f"{icon} {greeting}、{user.username}様！\n"
    response += "<i class='bi bi-robot'></i> HAL CINEMA サポートAIです。\n\n"
    response += "<i class='bi bi-chat-dots'></i> ご質問をお気軽にどうぞ！"
    return response

def handle_thanks():
    """お礼の返答（Bootstrap Icons版）"""
    return "<i class='bi bi-emoji-smile'></i> どういたしまして！\n<i class='bi bi-film'></i> 素敵な映画体験をお楽しみください。"

def handle_default_response(user):
    """デフォルトレスポンス（Bootstrap Icons版）"""
    response = f"<i class='bi bi-person-circle'></i> {user.username}様、ご質問ありがとうございます。\n\n"
    response += "<strong>以下のご質問にお答えできます：</strong>\n"
    response += "<i class='bi bi-calendar-check'></i> 予約確認\n"
    response += "<i class='bi bi-film'></i> 上映情報\n"
    response += "<i class='bi bi-credit-card'></i> 料金案内\n"
    response += "<i class='bi bi-building'></i> 劇場案内\n"
    response += "<i class='bi bi-coin'></i> ポイント確認\n"
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
def purchase_confirm(request):
    """購入確認画面（クーポン・ポイント併用払い完全対応）"""
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
    
    # ユーザーの現在のポイントを取得
    user_points = calculate_user_points(request.user)
    
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
        
        # ★★★ 修正ポイント：payment_methodに関わらずpoints_to_useを取得 ★★★
        points_to_use = int(request.POST.get('points_to_use', 0))
        
        # 元の金額
        original_price = float(total_price)
        final_price = original_price
        discount_amount = 0
        used_coupon = None
        
        # クーポン適用処理
        if coupon_id:
            try:
                coupon = Coupon.objects.get(id=coupon_id)
                
                if UserCoupon.objects.filter(user=request.user, coupon=coupon).exists():
                    messages.error(request, "このクーポンは既に使用済みです。")
                    return redirect('purchase_confirm')
                
                now = timezone.now()
                if not coupon.is_active or coupon.start_date > now or coupon.expiry_date < now:
                    messages.error(request, "このクーポンは現在利用できません。")
                    return redirect('purchase_confirm')
                
                if original_price < coupon.min_purchase:
                    messages.error(request, f"このクーポンは¥{coupon.min_purchase}以上のご購入で利用可能です。")
                    return redirect('purchase_confirm')
                
                # 割引計算
                if coupon.discount_type == 'percentage':
                    discount_amount = (original_price * coupon.discount_value) / 100
                    final_price = original_price - discount_amount
                elif coupon.discount_type == 'fixed':
                    discount_amount = float(coupon.discount_value)
                    final_price = max(0, original_price - discount_amount)
                elif coupon.discount_type == 'free':
                    discount_amount = original_price
                    final_price = 0
                
                used_coupon = coupon
            except Coupon.DoesNotExist:
                messages.warning(request, "無効なクーポンです。")
        
        # ★★★ ポイント使用処理（ポイント併用払い対応） ★★★
        cash_amount = final_price  # 初期値は全額現金払い
        
        if points_to_use > 0:
            user_points = calculate_user_points(request.user)
            
            # ポイント使用量のバリデーション
            if points_to_use > user_points:
                messages.error(request, f"ポイントが不足しています。使用指定: {points_to_use}pt / 所持: {user_points}pt")
                return redirect('purchase_confirm')
            
            if points_to_use > int(final_price):
                messages.error(request, f"使用ポイント数が支払い金額を超えています。")
                return redirect('purchase_confirm')
            
            # ★★★ ポイントを消費（use_points関数を呼び出す） ★★★
            if not use_points(request.user, points_to_use, f"映画「{movie.title}」のチケット購入（座席: {', '.join(seat_numbers)}）"):
                messages.error(request, "ポイントの使用に失敗しました。")
                return redirect('purchase_confirm')
            
            # ポイント使用後の支払い金額
            cash_amount = final_price - points_to_use

        # 予約作成（各座席ごと）
        created_reservations = []
        
        for seat in seats:
            if not Reservation.objects.filter(movie=movie, seat=seat, show_time=selected_datetime).exists():
                # ポイント併用払いの場合
                if points_to_use > 0:
                    actual_payment = cash_amount / len(seats) if cash_amount > 0 else 0
                    points_per_seat = points_to_use / len(seats)
                else:
                    actual_payment = final_price / len(seats) if final_price > 0 else 0
                    points_per_seat = 0
                
                reservation = Reservation.objects.create(
                    user=request.user,
                    movie=movie,
                    seat=seat,
                    show_time=selected_datetime,
                    payment_method=payment_method,
                    convenience_type=convenience_type,
                    original_price=float(movie.price),
                    discount_amount=discount_amount / len(seats) if discount_amount > 0 else 0,
                    final_price=actual_payment,
                    applied_coupon=used_coupon
                )
                generate_qr_code(reservation)
                created_reservations.append(reservation)
                
                # ★★★ ポイント付与（全額ポイント払い以外の場合） ★★★
                # 現金支払いがある場合のみポイント付与
                if cash_amount > 0:
                    points_earned = 100
                    add_points_to_user(request.user, points_earned, f"映画「{movie.title}」のチケット購入（座席: {seat.seat_number}）")
                
                # 通知作成（最初の予約のみ）
                if len(created_reservations) == 1:
                    notification_msg = (
                        f"映画「{movie.title}」のチケットを購入しました。\n"
                        f"座席: {', '.join(seat_numbers)}\n"
                        f"上映日時: {selected_datetime}\n"
                    )
                    
                    if points_to_use > 0:
                        if cash_amount > 0:
                            notification_msg += f"支払方法: ポイント併用払い\n"
                            notification_msg += f"使用ポイント: {points_to_use}pt\n"
                            notification_msg += f"現金支払い: ¥{int(cash_amount):,}"
                        else:
                            notification_msg += f"支払方法: 全額ポイント払い\n"
                            notification_msg += f"使用ポイント: {points_to_use}pt"
                    else:
                        notification_msg += f"支払方法: {payment_method}\n"
                    
                    if used_coupon:
                        notification_msg += f"\nクーポン適用: {used_coupon.title} (-¥{int(discount_amount):,})"
                    
                    if points_to_use > 0 and cash_amount > 0:
                        notification_msg += f"\n合計: ¥{int(cash_amount):,}"
                    else:
                        notification_msg += f"\n合計: ¥{int(final_price):,}"
                    
                    # 現金支払いがある場合のみポイント獲得を通知
                    if cash_amount > 0:
                        notification_msg += f"\n{100 * len(seats)}ポイント獲得！"
                    
                    Notification.objects.create(
                        user=request.user,
                        message=notification_msg
                    )
        
        # クーポン使用記録
        if used_coupon and created_reservations:
            try:
                UserCoupon.objects.create(
                    user=request.user,
                    coupon=used_coupon,
                    reservation=created_reservations[0]
                )
                used_coupon.used_count += 1
                used_coupon.save()
            except IntegrityError:
                messages.error(request, "クーポンは既に使用済みです。")

        # セッションに保存して購入完了画面へ
        if created_reservations:
            request.session['last_reservation_id'] = created_reservations[0].id
            request.session['seat_numbers'] = seat_numbers
            request.session['total_price'] = float(cash_amount) if points_to_use > 0 else float(final_price)
            request.session['payment_method'] = payment_method
            request.session['points_used'] = points_to_use
        
        # セッションの座席情報をクリア
        request.session.pop('selected_seats', None)
        request.session.pop('selected_datetime', None)
        request.session.pop('movie_id', None)
        
        if points_to_use > 0:
            if cash_amount > 0:
                messages.success(request, f'ポイントと現金でチケットを購入しました！（{points_to_use}pt使用 + ¥{int(cash_amount):,}）')
            else:
                messages.success(request, f'全額ポイントでチケットを購入しました！（{points_to_use}pt使用）')
        else:
            messages.success(request, 'チケットの購入が完了しました！')
        
        return redirect('purchase_complete')

    return render(request, 'apps/purchase_confirm.html', {
        'movie': movie,
        'selected_seat_numbers': seat_numbers,
        'selected_seat_count': len(seats),
        'total_price': total_price,
        'selected_seat_ids': selected_seat_ids,
        'selected_datetime': selected_datetime,
        'available_coupons': available_coupons,
        'user_points': user_points,
    })

@login_required
def purchase_complete(request):
    """購入完了画面"""
    last_reservation_id = request.session.get('last_reservation_id')
    seat_numbers = request.session.get('seat_numbers', [])
    total_price = request.session.get('total_price', 0)
    
    if not last_reservation_id:
        messages.error(request, "予約情報が見つかりません。")
        return redirect('my_reservations')
    
    try:
        reservation = Reservation.objects.get(id=last_reservation_id, user=request.user)
        movie = reservation.movie
        
        # 同じ上映時間の全予約を取得
        all_reservations = Reservation.objects.filter(
            user=request.user,
            movie=movie,
            show_time=reservation.show_time
        ).select_related('seat', 'applied_coupon')
        
        return render(request, 'apps/purchase_complete.html', {
            'movie': movie,
            'reservation': reservation,
            'selected_seat_numbers': seat_numbers,
            'total_price': total_price,
            'all_reservations': all_reservations,
        })
    except Reservation.DoesNotExist:
        messages.error(request, "予約が見つかりません。")
        return redirect('my_reservations')


@login_required
def download_ticket_pdf(request, reservation_id):
    """QRコード確実表示版チケットPDF（クーポン情報対応）"""
    try:
        reservation = get_object_or_404(Reservation, id=reservation_id, user=request.user)
        
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # ===== 背景グラデーション =====
        p.setFillColor(colors.HexColor('#0d5a4a'))
        p.rect(0, 0, width, height, fill=1, stroke=0)
        
        for i in range(150):
            progress = i / 150
            r = int(13 + (10 - 13) * progress)
            g = int(90 + (74 - 90) * progress)
            b = int(74 + (60 - 74) * progress)
            p.setFillColor(colors.HexColor(f'#{r:02x}{g:02x}{b:02x}'))
            y_pos = height - (i * height / 150)
            p.rect(0, y_pos, width, height / 150 + 1, fill=1, stroke=0)
        
        # ===== タイトル =====
        p.setFillColor(colors.HexColor('#ffd700'))
        p.setFont('Helvetica-Bold', 48)
        p.drawCentredString(width/2, height - 40*mm, 'HAL CINEMA')
        
        p.setFillColor(colors.white)
        if JAPANESE_FONT_AVAILABLE:
            p.setFont('HeiseiKakuGo-W5', 16)
            p.drawCentredString(width/2, height - 50*mm, '映画チケット')
        else:
            p.setFont('Helvetica-Bold', 16)
            p.drawCentredString(width/2, height - 50*mm, 'MOVIE TICKET')
        
        # 装飾ライン
        p.setStrokeColor(colors.HexColor('#ffd700'))
        p.setLineWidth(3)
        p.line(30*mm, height - 58*mm, width - 30*mm, height - 58*mm)
        
        # ===== 白いボックス =====
        box_left = 25*mm
        box_top = height - 75*mm
        box_width = width - 50*mm
        box_height = 150*mm
        
        p.setFillColor(colors.white)
        p.roundRect(box_left, box_top - box_height, box_width, box_height, 10, fill=1, stroke=0)
        
        # ===== 左側：映画情報 =====
        left_x = box_left + 12*mm
        info_y = box_top - 15*mm
        
        if JAPANESE_FONT_AVAILABLE:
            # 映画タイトル
            p.setFillColor(colors.HexColor('#0a4d3c'))
            p.setFont('HeiseiKakuGo-W5', 9)
            p.drawString(left_x, info_y, '映画タイトル')
            
            p.setFillColor(colors.black)
            p.setFont('HeiseiMin-W3', 11)
            info_y -= 7*mm
            p.drawString(left_x, info_y, reservation.movie.title[:25])
            
            # 上映日時
            info_y -= 13*mm
            p.setFillColor(colors.HexColor('#0a4d3c'))
            p.setFont('HeiseiKakuGo-W5', 9)
            p.drawString(left_x, info_y, '上映日時')
            
            p.setFillColor(colors.black)
            p.setFont('HeiseiMin-W3', 9)
            info_y -= 6*mm
            p.drawString(left_x, info_y, str(reservation.show_time))
            
            # スクリーン
            info_y -= 13*mm
            p.setFillColor(colors.HexColor('#0a4d3c'))
            p.setFont('HeiseiKakuGo-W5', 9)
            p.drawString(left_x, info_y, 'スクリーン')
            
            p.setFillColor(colors.black)
            p.setFont('HeiseiMin-W3', 9)
            info_y -= 6*mm
            theater = reservation.movie.theater or 'Screen 1'
            p.drawString(left_x, info_y, theater)
            
            # 座席番号
            info_y -= 15*mm
            p.setFillColor(colors.HexColor('#0a4d3c'))
            p.setFont('HeiseiKakuGo-W5', 9)
            p.drawString(left_x, info_y, '座席番号')
            
            # 座席番号ボックス
            info_y -= 16*mm
            p.setFillColor(colors.HexColor('#ffe4a0'))
            p.roundRect(left_x, info_y, 34*mm, 14*mm, 5, fill=1, stroke=0)
            
            p.setFillColor(colors.HexColor('#0a4d3c'))
            p.setFont('Helvetica-Bold', 24)
            p.drawCentredString(left_x + 17*mm, info_y + 2.5*mm, reservation.seat.seat_number)
            
            # 料金セクション
            info_y -= 18*mm
            p.setStrokeColor(colors.HexColor('#cccccc'))
            p.setLineWidth(1)
            p.line(left_x, info_y, left_x + 50*mm, info_y)
            
            info_y -= 9*mm
            
            # クーポン適用チェック
            has_coupon = (hasattr(reservation, 'applied_coupon') and 
                         reservation.applied_coupon and 
                         hasattr(reservation, 'discount_amount') and 
                         reservation.discount_amount > 0)
            
            if has_coupon:
                # 元の金額
                p.setFillColor(colors.HexColor('#0a4d3c'))
                p.setFont('HeiseiKakuGo-W5', 8)
                p.drawString(left_x, info_y, '元の金額')
                
                p.setFillColor(colors.HexColor('#999999'))
                p.setFont('HeiseiKakuGo-W5', 12)
                original_price = int(reservation.original_price) if hasattr(reservation, 'original_price') else int(reservation.movie.price)
                p.drawRightString(left_x + 50*mm, info_y, f'¥{original_price:,}')
                
                # 取り消し線（テキストの真ん中に配置）
                p.setStrokeColor(colors.HexColor('#999999'))
                p.setLineWidth(1)
                text_width = p.stringWidth(f'¥{original_price:,}', 'HeiseiKakuGo-W5', 12)
                # フォントサイズ12の真ん中
                line_y = info_y + 1*mm
                p.line(left_x + 50*mm - text_width, line_y, left_x + 50*mm, line_y)
                
                # クーポン割引
                info_y -= 7*mm
                p.setFillColor(colors.HexColor('#ef4444'))
                p.setFont('HeiseiKakuGo-W5', 8)
                coupon_name = reservation.applied_coupon.title[:15] if len(reservation.applied_coupon.title) > 15 else reservation.applied_coupon.title
                p.drawString(left_x, info_y, f'割引 ({coupon_name})')
                
                p.setFont('HeiseiKakuGo-W5', 12)
                discount = int(reservation.discount_amount)
                p.drawRightString(left_x + 50*mm, info_y, f'-¥{discount:,}')
                
                # お支払い金額
                info_y -= 9*mm
                p.setFillColor(colors.HexColor('#0a4d3c'))
                p.setFont('HeiseiKakuGo-W5', 10)
                p.drawString(left_x, info_y, 'お支払い金額')
                
                p.setFillColor(colors.HexColor('#22c55e'))
                p.setFont('HeiseiKakuGo-W5', 17)
                final_price = int(reservation.final_price)
                p.drawRightString(left_x + 50*mm, info_y, f'¥{final_price:,}')
                
                # クーポン適用バッジ
                info_y -= 10*mm
                badge_width = 45*mm
                badge_height = 6*mm
                p.setFillColor(colors.HexColor('#667eea'))
                p.roundRect(left_x, info_y, badge_width, badge_height, 3, fill=1, stroke=0)
                
                p.setFillColor(colors.white)
                p.setFont('HeiseiKakuGo-W5', 8)
                # バッジの高さ6mmの中心は info_y + 3mm、フォントサイズ8の調整で -1mm
                p.drawCentredString(left_x + badge_width/2, info_y + 2*mm, 'クーポン適用済み')
                
            else:
                # クーポンなしの場合
                p.setFillColor(colors.HexColor('#0a4d3c'))
                p.setFont('HeiseiKakuGo-W5', 10)
                p.drawString(left_x, info_y, 'ご利用金額')
                
                if hasattr(reservation, 'final_price') and reservation.final_price > 0:
                    display_price = int(reservation.final_price)
                else:
                    display_price = int(reservation.movie.price)
                
                p.setFillColor(colors.HexColor('#d4af37'))
                p.setFont('HeiseiKakuGo-W5', 17)
                p.drawRightString(left_x + 50*mm, info_y, f'¥{display_price:,}')
            
        else:
            # English version with coupon support
            p.setFillColor(colors.HexColor('#0a4d3c'))
            p.setFont('Helvetica-Bold', 9)
            p.drawString(left_x, info_y, 'MOVIE')
            
            p.setFillColor(colors.black)
            p.setFont('Helvetica', 11)
            info_y -= 7*mm
            p.drawString(left_x, info_y, reservation.movie.title[:25])
            
            info_y -= 13*mm
            p.setFillColor(colors.HexColor('#0a4d3c'))
            p.setFont('Helvetica-Bold', 9)
            p.drawString(left_x, info_y, 'DATE & TIME')
            
            p.setFillColor(colors.black)
            p.setFont('Helvetica', 9)
            info_y -= 6*mm
            p.drawString(left_x, info_y, str(reservation.show_time))
            
            info_y -= 13*mm
            p.setFillColor(colors.HexColor('#0a4d3c'))
            p.setFont('Helvetica-Bold', 9)
            p.drawString(left_x, info_y, 'SCREEN')
            
            p.setFillColor(colors.black)
            p.setFont('Helvetica', 9)
            info_y -= 6*mm
            theater = reservation.movie.theater or 'Screen 1'
            p.drawString(left_x, info_y, theater)
            
            info_y -= 15*mm
            p.setFillColor(colors.HexColor('#0a4d3c'))
            p.setFont('Helvetica-Bold', 9)
            p.drawString(left_x, info_y, 'SEAT NUMBER')
            
            info_y -= 16*mm
            p.setFillColor(colors.HexColor('#ffe4a0'))
            p.roundRect(left_x, info_y, 34*mm, 14*mm, 5, fill=1, stroke=0)
            
            p.setFillColor(colors.HexColor('#0a4d3c'))
            p.setFont('Helvetica-Bold', 24)
            p.drawCentredString(left_x + 17*mm, info_y + 2.5*mm, reservation.seat.seat_number)
            
            info_y -= 18*mm
            p.setStrokeColor(colors.HexColor('#cccccc'))
            p.setLineWidth(1)
            p.line(left_x, info_y, left_x + 50*mm, info_y)
            
            info_y -= 12*mm
            
            # Coupon check
            has_coupon = (hasattr(reservation, 'applied_coupon') and 
                         reservation.applied_coupon and 
                         hasattr(reservation, 'discount_amount') and 
                         reservation.discount_amount > 0)
            
            if has_coupon:
                # Detail box
                detail_box_y = info_y - 2*mm
                detail_box_height = 32*mm
                
                p.setFillColor(colors.HexColor('#f9fafb'))
                p.roundRect(left_x, detail_box_y - detail_box_height, 50*mm, detail_box_height, 5, fill=1, stroke=0)
                
                detail_y = detail_box_y - 6*mm
                
                # Original amount
                p.setFillColor(colors.HexColor('#6b7280'))
                p.setFont('Helvetica', 8)
                p.drawString(left_x + 3*mm, detail_y, 'Original')
                
                p.setFillColor(colors.HexColor('#9ca3af'))
                p.setFont('Helvetica-Bold', 11)
                original_price = int(reservation.original_price) if hasattr(reservation, 'original_price') else int(reservation.movie.price)
                p.drawRightString(left_x + 47*mm, detail_y, f'JPY {original_price:,}')
                
                # Strike-through（テキストの真ん中に配置）
                p.setStrokeColor(colors.HexColor('#9ca3af'))
                p.setLineWidth(1)
                text_width = p.stringWidth(f'JPY {original_price:,}', 'Helvetica-Bold', 11)
                # フォントサイズ11の真ん中
                line_y = detail_y + 0.5*mm
                p.line(left_x + 47*mm - text_width, line_y, left_x + 47*mm, line_y)
                
                # Discount
                detail_y -= 8*mm
                p.setFillColor(colors.HexColor('#dc2626'))
                p.setFont('Helvetica', 8)
                coupon_name = reservation.applied_coupon.title[:10]
                p.drawString(left_x + 3*mm, detail_y, f'Discount ({coupon_name})')
                
                p.setFillColor(colors.HexColor('#dc2626'))
                p.setFont('Helvetica-Bold', 11)
                discount = int(reservation.discount_amount)
                p.drawRightString(left_x + 47*mm, detail_y, f'-JPY {discount:,}')
                
                # Divider
                detail_y -= 6*mm
                p.setStrokeColor(colors.HexColor('#e5e7eb'))
                p.setLineWidth(1)
                p.line(left_x + 3*mm, detail_y, left_x + 47*mm, detail_y)
                
                # Final amount
                detail_y -= 9*mm
                p.setFillColor(colors.HexColor('#059669'))
                p.setFont('Helvetica-Bold', 9)
                p.drawString(left_x + 3*mm, detail_y, 'Total')
                
                p.setFillColor(colors.HexColor('#059669'))
                p.setFont('Helvetica-Bold', 16)
                final_price = int(reservation.final_price)
                p.drawRightString(left_x + 47*mm, detail_y - 1*mm, f'JPY {final_price:,}')
                
                # Coupon badge
                info_y = detail_box_y - detail_box_height - 5*mm
                badge_width = 50*mm
                badge_height = 7*mm
                
                p.setFillColor(colors.HexColor('#8b5cf6'))
                p.roundRect(left_x, info_y, badge_width, badge_height, 3, fill=1, stroke=0)
                
                p.setFillColor(colors.white)
                p.setFont('Helvetica-Bold', 8)
                # バッジの高さ7mmの中心は info_y + 3.5mm、フォントサイズ8の調整で -1mm
                p.drawCentredString(left_x + badge_width/2, info_y + 2.5*mm, '✓ COUPON APPLIED')
                
            else:
                # No coupon
                p.setFillColor(colors.HexColor('#0a4d3c'))
                p.setFont('Helvetica-Bold', 10)
                p.drawString(left_x, info_y, 'AMOUNT')
                
                if hasattr(reservation, 'final_price') and reservation.final_price > 0:
                    display_price = int(reservation.final_price)
                else:
                    display_price = int(reservation.movie.price)
                
                p.setFillColor(colors.HexColor('#d4af37'))
                p.setFont('Helvetica-Bold', 17)
                p.drawRightString(left_x + 50*mm, info_y, f'JPY {display_price:,}')
        
        # ===== 右側:QRコード =====
        qr_size = 42*mm
        qr_x = box_left + box_width - qr_size - 10*mm
        qr_y = box_top - qr_size - 15*mm
        
        try:
            # 既存のQRコード画像を使用
            if reservation.qr_code_image:
                from django.core.files.storage import default_storage
                import os
                
                qr_path = reservation.qr_code_image.path
                
                if os.path.exists(qr_path):
                    p.drawImage(qr_path, qr_x, qr_y, qr_size, qr_size, preserveAspectRatio=True, mask='auto')
                    print(f"既存QRコード使用成功: {qr_path}")
                else:
                    raise FileNotFoundError("QR code file not found")
            else:
                raise AttributeError("No QR code image")
                
        except (AttributeError, FileNotFoundError) as e:
            print(f"既存QRコードなし、新規生成します: {e}")
            
            try:
                import qrcode
                from PIL import Image
                
                qr_data = f"HAL CINEMA TICKET #{reservation.id}"
                
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_M,
                    box_size=10,
                    border=2,
                )
                qr.add_data(qr_data)
                qr.make(fit=True)
                
                qr_img = qr.make_image(fill_color="black", back_color="white")
                
                qr_buffer = BytesIO()
                qr_img.save(qr_buffer, format='PNG')
                qr_buffer.seek(0)
                
                from reportlab.lib.utils import ImageReader
                img_reader = ImageReader(qr_buffer)
                
                p.drawImage(img_reader, qr_x, qr_y, qr_size, qr_size, 
                           preserveAspectRatio=True, mask='auto')
                
                print(f"QRコード新規生成成功: {qr_data}")
                
            except Exception as qr_err:
                print(f"QRコード生成エラー: {qr_err}")
                import traceback
                traceback.print_exc()
                
                p.setFillColor(colors.HexColor('#cccccc'))
                p.rect(qr_x, qr_y, qr_size, qr_size, fill=1, stroke=1)
                p.setFillColor(colors.black)
                p.setFont('Helvetica-Bold', 10)
                p.drawCentredString(qr_x + qr_size/2, qr_y + qr_size/2 + 5*mm, 'QR CODE')
                p.setFont('Helvetica', 8)
                p.drawCentredString(qr_x + qr_size/2, qr_y + qr_size/2 - 5*mm, f'ID: {reservation.id}')
        
        # QRコード説明
        p.setFillColor(colors.HexColor('#0a4d3c'))
        if JAPANESE_FONT_AVAILABLE:
            p.setFont('HeiseiMin-W3', 7)
            p.drawCentredString(qr_x + qr_size/2, qr_y - 4*mm, '入場時にご提示ください')
        else:
            p.setFont('Helvetica', 6)
            p.drawCentredString(qr_x + qr_size/2, qr_y - 4*mm, 'Show at entrance')
        
        # ===== フッター =====
        footer_y = 28*mm
        p.setFillColor(colors.white)
        
        if JAPANESE_FONT_AVAILABLE:
            p.setFont('HeiseiMin-W3', 8)
            p.drawCentredString(width/2, footer_y, f'予約番号: {reservation.id}')
            p.setFont('HeiseiMin-W3', 7)
            p.drawCentredString(width/2, footer_y - 5*mm, f'ご購入者: {request.user.username}')
            p.drawCentredString(width/2, footer_y - 10*mm, 'HAL CINEMA をご利用いただきありがとうございます')
        else:
            p.setFont('Helvetica', 8)
            p.drawCentredString(width/2, footer_y, f'Reservation ID: {reservation.id}')
            p.setFont('Helvetica', 7)
            p.drawCentredString(width/2, footer_y - 5*mm, f'Customer: {request.user.username}')
            p.drawCentredString(width/2, footer_y - 10*mm, 'Thank you for choosing HAL CINEMA')
        
        p.showPage()
        p.save()
        
        buffer.seek(0)
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="HAL_CINEMA_Ticket_{reservation.id}.pdf"'
        
        return response
        
    except Exception as e:
        print(f"チケットPDF生成エラー: {str(e)}")
        import traceback
        traceback.print_exc()
        messages.error(request, f"チケットのダウンロード中にエラーが発生しました: {str(e)}")
        return redirect('my_reservations')

@login_required
def download_receipt_pdf(request, reservation_id):
    """領収書PDF生成（クーポン対応版）"""
    try:
        reservation = get_object_or_404(Reservation, id=reservation_id, user=request.user)
        
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # ===== ヘッダー部分 =====
        p.setFillColor(colors.HexColor('#0a4d3c'))
        p.rect(0, height - 60*mm, width, 60*mm, fill=1, stroke=0)
        
        p.setFillColor(colors.HexColor('#ffd700'))
        p.setFont('Helvetica-Bold', 42)
        p.drawCentredString(width/2, height - 35*mm, 'HAL CINEMA')
        
        p.setFillColor(colors.white)
        if JAPANESE_FONT_AVAILABLE:
            p.setFont('HeiseiKakuGo-W5', 24)
            p.drawCentredString(width/2, height - 50*mm, '領収書')
        else:
            p.setFont('Helvetica-Bold', 24)
            p.drawCentredString(width/2, height - 50*mm, 'RECEIPT')
        
        # ===== 宛名・発行日 =====
        content_start_y = height - 75*mm
        
        if JAPANESE_FONT_AVAILABLE:
            p.setFillColor(colors.black)
            p.setFont('HeiseiMin-W3', 12)
            p.drawString(40*mm, content_start_y, f'{request.user.username} 様')
            
            p.setFont('HeiseiMin-W3', 10)
            from datetime import datetime
            issue_date = datetime.now().strftime('%Y年%m月%d日')
            p.drawRightString(width - 40*mm, content_start_y, f'発行日: {issue_date}')
        else:
            p.setFillColor(colors.black)
            p.setFont('Helvetica', 12)
            p.drawString(40*mm, content_start_y, f'To: {request.user.username}')
            
            p.setFont('Helvetica', 10)
            from datetime import datetime
            issue_date = datetime.now().strftime('%Y/%m/%d')
            p.drawRightString(width - 40*mm, content_start_y, f'Issue Date: {issue_date}')
        
        # ===== 金額ボックス =====
        amount_y = content_start_y - 30*mm  # 25mm から 30mm に変更して少し下げる
        
        # クーポン適用チェック
        has_coupon = (hasattr(reservation, 'applied_coupon') and 
                     reservation.applied_coupon and 
                     hasattr(reservation, 'discount_amount') and 
                     reservation.discount_amount > 0)
        
        if has_coupon:
            final_price = int(reservation.final_price)
        else:
            if hasattr(reservation, 'final_price') and reservation.final_price > 0:
                final_price = int(reservation.final_price)
            else:
                final_price = int(reservation.movie.price)
        
        # 金額ボックス描画（中央配置）
        box_height = 20*mm
        box_bottom = amount_y - 10*mm
        box_center_y = box_bottom + (box_height / 2)  # ボックスの中心Y座標を計算
        
        p.setFillColor(colors.HexColor('#f0f0f0'))
        p.roundRect(40*mm, box_bottom, width - 80*mm, box_height, 5, fill=1, stroke=0)
        
        p.setFillColor(colors.black)
        if JAPANESE_FONT_AVAILABLE:
            # 「合計金額:」のフォントサイズ14pt → ベースライン調整は約-5mm
            p.setFont('HeiseiKakuGo-W5', 14)
            p.drawString(50*mm, box_center_y - 2*mm, '合計金額:')
            
            # 金額のフォントサイズ24pt → ベースライン調整は約-8mm
            p.setFont('HeiseiKakuGo-W5', 24)
            p.drawRightString(width - 50*mm, box_center_y - 4*mm, f'¥{final_price:,}')
        else:
            p.setFont('Helvetica-Bold', 14)
            p.drawString(50*mm, box_center_y - 2*mm, 'Total Amount:')
            p.setFont('Helvetica-Bold', 24)
            p.drawRightString(width - 50*mm, box_center_y - 4*mm, f'JPY {final_price:,}')
        
        # ===== 明細テーブル =====
        table_y = amount_y - 35*mm
        
        # テーブルヘッダー
        p.setFillColor(colors.HexColor('#0a4d3c'))
        p.rect(40*mm, table_y, width - 80*mm, 10*mm, fill=1, stroke=0)
        
        p.setFillColor(colors.white)
        if JAPANESE_FONT_AVAILABLE:
            p.setFont('HeiseiKakuGo-W5', 10)
            p.drawString(45*mm, table_y + 3*mm, '項目')
            p.drawRightString(width - 45*mm, table_y + 3*mm, '金額')
        else:
            p.setFont('Helvetica-Bold', 10)
            p.drawString(45*mm, table_y + 3*mm, 'Item')
            p.drawRightString(width - 45*mm, table_y + 3*mm, 'Amount')
        
        # テーブル内容
        row_y = table_y - 10*mm
        row_height = 8*mm
        
        p.setFillColor(colors.black)
        
        if JAPANESE_FONT_AVAILABLE:
            # 映画チケット
            p.setFont('HeiseiMin-W3', 9)
            p.drawString(45*mm, row_y + 2*mm, f'映画チケット: {reservation.movie.title[:20]}')
            
            if has_coupon:
                original_price = int(reservation.original_price) if hasattr(reservation, 'original_price') else int(reservation.movie.price)
                p.setFont('HeiseiMin-W3', 9)
                p.drawRightString(width - 45*mm, row_y + 2*mm, f'¥{original_price:,}')
                
                # 罫線
                p.setStrokeColor(colors.HexColor('#cccccc'))
                p.setLineWidth(0.5)
                row_y -= row_height
                p.line(40*mm, row_y + row_height, width - 40*mm, row_y + row_height)
                
                # クーポン割引行
                p.setFillColor(colors.HexColor('#ef4444'))
                p.setFont('HeiseiMin-W3', 9)
                coupon_title = reservation.applied_coupon.title[:20]
                p.drawString(45*mm, row_y + 2*mm, f'クーポン割引: {coupon_title}')
                p.drawRightString(width - 45*mm, row_y + 2*mm, f'-¥{int(reservation.discount_amount):,}')
                
                # 罫線
                row_y -= row_height
                p.line(40*mm, row_y + row_height, width - 40*mm, row_y + row_height)
                
                # クーポンバッジ
                row_y -= 2*mm
                badge_width = 50*mm
                badge_height = 7*mm
                badge_x = (width - badge_width) / 2
                
                p.setFillColor(colors.HexColor('#667eea'))
                p.roundRect(badge_x, row_y, badge_width, badge_height, 3, fill=1, stroke=0)
                
                p.setFillColor(colors.white)
                p.setFont('HeiseiKakuGo-W5', 9)
                # バッジの高さ7mmの中心は row_y + 3.5mm、フォントサイズ9の調整で -1mm
                p.drawCentredString(width/2, row_y + 2.5*mm, 'クーポン適用済み')
                
                row_y -= row_height + 3*mm
                
            else:
                p.setFont('HeiseiMin-W3', 9)
                p.drawRightString(width - 45*mm, row_y + 2*mm, f'¥{final_price:,}')
                
                # 罫線
                p.setStrokeColor(colors.HexColor('#cccccc'))
                p.setLineWidth(0.5)
                row_y -= row_height
                p.line(40*mm, row_y + row_height, width - 40*mm, row_y + row_height)
            
            # 座席情報
            p.setFillColor(colors.HexColor('#666666'))
            p.setFont('HeiseiMin-W3', 8)
            p.drawString(45*mm, row_y + 2*mm, f'座席: {reservation.seat.seat_number}')
            p.drawString(45*mm, row_y - 3*mm, f'上映日時: {reservation.show_time}')
            
        else:
            # English version
            p.setFont('Helvetica', 9)
            p.drawString(45*mm, row_y + 2*mm, f'Movie Ticket: {reservation.movie.title[:20]}')
            
            if has_coupon:
                original_price = int(reservation.original_price) if hasattr(reservation, 'original_price') else int(reservation.movie.price)
                p.setFont('Helvetica', 9)
                p.drawRightString(width - 45*mm, row_y + 2*mm, f'JPY {original_price:,}')
                
                p.setStrokeColor(colors.HexColor('#cccccc'))
                p.setLineWidth(0.5)
                row_y -= row_height
                p.line(40*mm, row_y + row_height, width - 40*mm, row_y + row_height)
                
                # Discount row
                p.setFillColor(colors.HexColor('#ef4444'))
                p.setFont('Helvetica', 9)
                coupon_title = reservation.applied_coupon.title[:18]
                p.drawString(45*mm, row_y + 2*mm, f'Coupon Discount: {coupon_title}')
                p.drawRightString(width - 45*mm, row_y + 2*mm, f'-JPY {int(reservation.discount_amount):,}')
                
                row_y -= row_height
                p.line(40*mm, row_y + row_height, width - 40*mm, row_y + row_height)
                
                # Coupon badge
                row_y -= 2*mm
                badge_width = 50*mm
                badge_height = 7*mm
                badge_x = (width - badge_width) / 2
                
                p.setFillColor(colors.HexColor('#667eea'))
                p.roundRect(badge_x, row_y, badge_width, badge_height, 3, fill=1, stroke=0)
                
                p.setFillColor(colors.white)
                p.setFont('Helvetica-Bold', 9)
                # バッジの高さ7mmの中心は row_y + 3.5mm、フォントサイズ9の調整で -1mm
                p.drawCentredString(width/2, row_y + 2.5*mm, 'COUPON APPLIED')
                
                row_y -= row_height + 3*mm
                
            else:
                p.setFont('Helvetica', 9)
                p.drawRightString(width - 45*mm, row_y + 2*mm, f'JPY {final_price:,}')
                
                p.setStrokeColor(colors.HexColor('#cccccc'))
                p.setLineWidth(0.5)
                row_y -= row_height
                p.line(40*mm, row_y + row_height, width - 40*mm, row_y + row_height)
            
            # Seat info
            p.setFillColor(colors.HexColor('#666666'))
            p.setFont('Helvetica', 8)
            p.drawString(45*mm, row_y + 2*mm, f'Seat: {reservation.seat.seat_number}')
            p.drawString(45*mm, row_y - 3*mm, f'Show Time: {reservation.show_time}')
        
        # ===== 合計ライン =====
        total_y = row_y - 15*mm
        p.setStrokeColor(colors.black)
        p.setLineWidth(2)
        p.line(40*mm, total_y, width - 40*mm, total_y)
        
        total_y -= 10*mm
        p.setFillColor(colors.black)
        if JAPANESE_FONT_AVAILABLE:
            p.setFont('HeiseiKakuGo-W5', 12)
            p.drawString(45*mm, total_y, '合計')
            p.setFont('HeiseiKakuGo-W5', 16)
            p.drawRightString(width - 45*mm, total_y, f'¥{final_price:,}')
        else:
            p.setFont('Helvetica-Bold', 12)
            p.drawString(45*mm, total_y, 'Total')
            p.setFont('Helvetica-Bold', 16)
            p.drawRightString(width - 45*mm, total_y, f'JPY {final_price:,}')
        
        # ===== フッター =====
        footer_y = 60*mm  # 50mm から 60mm に変更
        
        p.setFillColor(colors.HexColor('#0a4d3c'))
        p.rect(0, 0, width, 70*mm, fill=1, stroke=0)  # 50mm から 70mm に増やす
        
        p.setFillColor(colors.white)
        if JAPANESE_FONT_AVAILABLE:
            p.setFont('HeiseiMin-W3', 9)
            p.drawCentredString(width/2, footer_y - 5*mm, 'HAL CINEMA')
            p.setFont('HeiseiMin-W3', 8)
            p.drawCentredString(width/2, footer_y - 12*mm, '〒123-4567 東京都渋谷区○○1-2-3')
            p.drawCentredString(width/2, footer_y - 18*mm, 'TEL: 03-1234-5678')
            p.drawCentredString(width/2, footer_y - 24*mm, f'予約番号: {reservation.id}')
        else:
            p.setFont('Helvetica', 9)
            p.drawCentredString(width/2, footer_y - 5*mm, 'HAL CINEMA')
            p.setFont('Helvetica', 8)
            p.drawCentredString(width/2, footer_y - 12*mm, '1-2-3 Shibuya, Tokyo 123-4567')
            p.drawCentredString(width/2, footer_y - 18*mm, 'TEL: 03-1234-5678')
            p.drawCentredString(width/2, footer_y - 24*mm, f'Reservation ID: {reservation.id}')
        
        p.showPage()
        p.save()
        
        buffer.seek(0)
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="HAL_CINEMA_Receipt_{reservation.id}.pdf"'
        
        return response
        
    except Exception as e:
        print(f"領収書PDF生成エラー: {str(e)}")
        import traceback
        traceback.print_exc()
        messages.error(request, f"領収書のダウンロード中にエラーが発生しました: {str(e)}")
        return redirect('my_reservations')

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

