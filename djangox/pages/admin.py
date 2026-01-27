from django.contrib import admin
from django.utils.html import format_html
from django import forms
from django.contrib import messages
from django.shortcuts import render
from django.contrib.admin import SimpleListFilter
from pages.models import Contact
from django.conf import settings
import requests
from .models import Ticket
import json

from .models import (
    Movie, Seat, Reservation, Notification, ShowSchedule, 
    UserProfile, ChatMessage, PointHistory, Coupon, UserCoupon
)

# 管理画面のヘッダーとタイトルを日本語化
admin.site.site_header = "Cinema Website 管理画面"
admin.site.site_title = "Cinema 管理"
admin.site.index_title = "ダッシュボード"

# =====================================
# ShowSchedule Inline（MovieAdminより前に定義）
# =====================================

class ShowScheduleInline(admin.TabularInline):
    """映画詳細画面で上映スケジュールを編集できるようにする"""
    model = ShowSchedule
    extra = 1
    fields = ['date', 'start_time', 'end_time', 'screen', 'format']
    ordering = ['date', 'start_time']

# =====================================
# ShowSchedule（独立した管理画面）
# =====================================

@admin.register(ShowSchedule)
class ShowScheduleAdmin(admin.ModelAdmin):
    list_display = ['movie', 'date', 'start_time', 'end_time', 'screen', 'format']
    list_filter = ['date', 'screen', 'movie']
    search_fields = ['movie__title']
    date_hierarchy = 'date'
    ordering = ['date', 'start_time']
    
    fieldsets = (
        ('基本情報', {
            'fields': ('movie', 'date')
        }),
        ('上映時間', {
            'fields': ('start_time', 'end_time')
        }),
        ('その他', {
            'fields': ('screen', 'format')
        }),
    )

# =====================================
# Movie関連
# =====================================

class MovieAdminForm(forms.ModelForm):
    """映画登録フォーム（AI自動入力機能付き）"""
    auto_generate = forms.BooleanField(
        required=False, 
        initial=False,
        label='AI自動入力を使用',
        help_text='映画タイトルを入力後、このチェックを入れて保存すると自動的に情報を入力します'
    )
    
    class Meta:
        model = Movie
        fields = '__all__'
        widgets = {
            'description': forms.Textarea(attrs={'rows': 6, 'cols': 80}),
        }


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    form = MovieAdminForm
    list_display = ['title', 'status', 'release_date', 'show_date', 'genre', 'price', 'image_tag']
    list_filter = ['status', 'genre', 'show_date']
    search_fields = ['title', 'description']
    list_editable = ['status']
    date_hierarchy = 'show_date'
    inlines = [ShowScheduleInline]  # これでShowScheduleInlineが使えます
    
    fieldsets = (
        ('基本情報', {
            'fields': ('title', 'description', 'genre', 'image')
        }),
        ('上映情報', {
            'fields': ('status', 'release_date', 'show_date', 'duration', 'theater')
        }),
        ('料金', {
            'fields': ('price',)
        }),
        ('AI自動入力', {
            'fields': ('auto_generate',),
            'classes': ('collapse',),
            'description': 'タイトルだけ入力してこのチェックを入れると、自動的に説明文やジャンルを生成します'
        }),
    )
    
    def image_tag(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="100" />'.format(obj.image.url))
        return "-"
    image_tag.short_description = '画像'
    
    def save_model(self, request, obj, form, change):
        """保存時に映画情報を自動入力（TMDb API - 無料）"""
        if form.cleaned_data.get('auto_generate') and obj.title:
            try:
                # TMDb API Key
                TMDB_API_KEY = '161e2d17545a30906bfacfab70d7c68d'
                
                # 映画を検索
                search_url = "https://api.themoviedb.org/3/search/movie"
                params = {
                    'api_key': TMDB_API_KEY,
                    'query': obj.title,
                    'language': 'ja-JP'
                }
                
                response = requests.get(search_url, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data['results']:
                        movie = data['results'][0]
                        updated_fields = []
                        
                        # 説明文を取得
                        if not obj.description and movie.get('overview'):
                            obj.description = movie['overview']
                            updated_fields.append('説明文')
                        
                        # ポスター画像を取得してダウンロード
                        if not obj.image and movie.get('poster_path'):
                            try:
                                import urllib.request
                                from django.core.files import File
                                import tempfile
                                import os
                                
                                poster_url = f"https://image.tmdb.org/t/p/w500{movie['poster_path']}"
                                
                                # 一時ファイルを作成
                                fd, temp_path = tempfile.mkstemp(suffix='.jpg')
                                os.close(fd)
                                
                                try:
                                    # 画像をダウンロード
                                    urllib.request.urlretrieve(poster_url, temp_path)
                                    
                                    # ファイル名を生成（安全な文字列に変換）
                                    safe_title = "".join(c for c in obj.title if c.isalnum() or c in (' ', '_')).rstrip()
                                    file_name = f"{safe_title.replace(' ', '_')}_poster.jpg"
                                    
                                    # Djangoのファイルとして保存
                                    with open(temp_path, 'rb') as f:
                                        obj.image.save(file_name, File(f), save=False)
                                    
                                    updated_fields.append('画像')
                                finally:
                                    # 一時ファイルを削除
                                    if os.path.exists(temp_path):
                                        os.remove(temp_path)
                                        
                            except Exception as img_error:
                                messages.warning(request, f'画像のダウンロードに失敗しました: {str(img_error)}')
                        
                        # 詳細情報を取得
                        movie_id = movie['id']
                        detail_url = f"https://api.themoviedb.org/3/movie/{movie_id}"
                        detail_params = {
                            'api_key': TMDB_API_KEY,
                            'language': 'ja-JP'
                        }
                        
                        detail_response = requests.get(detail_url, params=detail_params)
                        
                        if detail_response.status_code == 200:
                            detail = detail_response.json()
                            
                            # 上映時間
                            if not obj.duration and detail.get('runtime'):
                                obj.duration = detail['runtime']
                                updated_fields.append('上映時間')
                            
                            # ジャンル
                            if not obj.genre and detail.get('genres'):
                                obj.genre = detail['genres'][0]['name']
                                updated_fields.append('ジャンル')
                        
                        # デフォルト値を設定
                        if not obj.price:
                            obj.price = 1800
                            updated_fields.append('料金（デフォルト値）')
                        
                        if not obj.theater:
                            obj.theater = 'シアター1'
                            updated_fields.append('シアター（デフォルト値）')
                        
                        if updated_fields:
                            messages.success(
                                request,
                                f'TMDb APIから自動入力が完了しました（{", ".join(updated_fields)}）'
                            )
                        else:
                            messages.info(
                                request,
                                '全ての項目が既に入力されているため、自動入力はスキップされました。'
                            )
                    else:
                        messages.warning(
                            request,
                            f'「{obj.title}」の情報が見つかりませんでした。手動で入力してください。'
                        )
                else:
                    messages.error(request, f'API呼び出しエラー: {response.status_code}')
                    
            except requests.RequestException as e:
                messages.error(request, f'ネットワークエラー: {str(e)}')
            except Exception as e:
                messages.error(request, f'エラー: {str(e)}')
        
        super().save_model(request, obj, form, change)


# =====================================
# Seat
# =====================================

@admin.register(Seat)
class SeatAdmin(admin.ModelAdmin):
    list_display = ['seat_number']
    search_fields = ['seat_number']


# =====================================
# Reservation
# =====================================

@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ['user', 'movie', 'seat', 'reserved_at', 'show_time', 'payment_method']
    list_filter = ['payment_method', 'reserved_at']
    search_fields = ['user__username', 'movie__title', 'seat__seat_number']
    date_hierarchy = 'reserved_at'
    readonly_fields = ['reserved_at', 'qr_code_image']
    
    fieldsets = (
        ('予約情報', {
            'fields': ('user', 'movie', 'seat', 'show_time', 'reserved_at')
        }),
        ('支払い情報', {
            'fields': ('payment_method', 'convenience_type')
        }),
        ('QRコード', {
            'fields': ('qr_code_image',)
        }),
    )


# =====================================
# Notification
# =====================================

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'message', 'created_at', 'is_read']
    list_filter = ['is_read', 'created_at']
    search_fields = ['user__username', 'message']
    date_hierarchy = 'created_at'
    list_editable = ['is_read']


# =====================================
# ChatMessage
# =====================================

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['user', 'message_preview', 'is_user', 'created_at']
    list_filter = ['is_user', 'created_at']
    search_fields = ['user__username', 'message', 'response']
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at']
    
    def message_preview(self, obj):
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message
    message_preview.short_description = 'メッセージ'


# =====================================
# カスタムフィルター
# =====================================

class PointRangeFilter(SimpleListFilter):
    """ポイント範囲でフィルタ"""
    title = 'ポイント範囲'
    parameter_name = 'point_range'
    
    def lookups(self, request, model_admin):
        return (
            ('0-500', '0-500pt'),
            ('501-1000', '501-1,000pt'),
            ('1001-2000', '1,001-2,000pt'),
            ('2001-5000', '2,001-5,000pt'),
            ('5001+', '5,001pt以上'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == '0-500':
            return queryset.filter(points__lte=500)
        elif self.value() == '501-1000':
            return queryset.filter(points__gt=500, points__lte=1000)
        elif self.value() == '1001-2000':
            return queryset.filter(points__gt=1000, points__lte=2000)
        elif self.value() == '2001-5000':
            return queryset.filter(points__gt=2000, points__lte=5000)
        elif self.value() == '5001+':
            return queryset.filter(points__gt=5000)
        return queryset


# =====================================
# UserProfile
# =====================================

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """ユーザープロフィール管理"""
    list_display = [
        'user',
        'points',
        'membership_level',
        'phone_number',
        'birth_date',
        'created_at'
    ]
    list_filter = [
        'membership_level',
        PointRangeFilter,
        'created_at'
    ]
    search_fields = [
        'user__username',
        'user__email',
        'phone_number'
    ]
    readonly_fields = [
        'created_at',
        'updated_at'
    ]
    
    fieldsets = (
        ('ユーザー情報', {
            'fields': ('user', 'profile_image')
        }),
        ('個人情報', {
            'fields': ('birth_date', 'phone_number')
        }),
        ('ポイント・会員情報', {
            'fields': ('points', 'membership_level')
        }),
        ('日時情報', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['add_bonus_points']
    
    def get_queryset(self, request):
        """効率的なクエリ"""
        qs = super().get_queryset(request)
        return qs.select_related('user')
    
    def add_bonus_points(self, request, queryset):
        """選択したユーザーにボーナスポイントを付与"""
        class BonusPointsForm(forms.Form):
            points = forms.IntegerField(
                label='付与ポイント',
                min_value=1,
                help_text='付与するポイント数を入力してください'
            )
            reason = forms.CharField(
                label='理由',
                max_length=200,
                widget=forms.TextInput(attrs={'size': '60'}),
                help_text='ポイント付与の理由を入力してください'
            )
        
        if 'apply' in request.POST:
            form = BonusPointsForm(request.POST)
            if form.is_valid():
                points = form.cleaned_data['points']
                reason = form.cleaned_data['reason']
                
                count = 0
                for profile in queryset:
                    profile.add_points(points, reason)
                    count += 1
                
                self.message_user(
                    request,
                    f'{count}名のユーザーに{points}ポイントを付与しました。',
                    messages.SUCCESS
                )
                return None
        else:
            form = BonusPointsForm()
        
        context = {
            'form': form,
            'profiles': queryset,
            'opts': self.model._meta,
            'title': 'ボーナスポイント付与',
        }
        
        return render(request, 'admin/add_bonus_points.html', context)
    
    add_bonus_points.short_description = '選択したユーザーにボーナスポイントを付与'


# =====================================
# PointHistory
# =====================================

@admin.register(PointHistory)
class PointHistoryAdmin(admin.ModelAdmin):
    """ポイント履歴管理"""
    list_display = [
        'user',
        'points_display',
        'reason',
        'balance_after',
        'created_at'
    ]
    list_filter = [
        'created_at',
    ]
    search_fields = [
        'user__username',
        'reason'
    ]
    readonly_fields = [
        'user',
        'points',
        'reason',
        'balance_after',
        'created_at'
    ]
    date_hierarchy = 'created_at'
    
    def get_queryset(self, request):
        """効率的なクエリ"""
        qs = super().get_queryset(request)
        return qs.select_related('user')
    
    def points_display(self, obj):
        """ポイントの表示（+/-付き）"""
        if obj.points > 0:
            return f'+{obj.points}pt'
        return f'{obj.points}pt'
    points_display.short_description = 'ポイント増減'
    
    def has_add_permission(self, request):
        """追加権限なし（プログラムから自動生成）"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """変更権限なし（履歴は変更不可）"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """削除権限なし（履歴は削除不可）"""
        return False


# =====================================
# Coupon
# =====================================

@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    """クーポン管理"""
    list_display = [
        'code',
        'title',
        'discount_display',
        'usage_display',
        'is_active',
        'validity_period'
    ]
    list_filter = [
        'discount_type',
        'is_active',
        'start_date',
        'expiry_date'
    ]
    search_fields = [
        'code',
        'title',
        'description'
    ]
    readonly_fields = [
        'used_count',
        'created_at'
    ]
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('基本情報', {
            'fields': ('code', 'title', 'description', 'is_active')
        }),
        ('割引設定', {
            'fields': ('discount_type', 'discount_value', 'min_purchase')
        }),
        ('使用制限', {
            'fields': ('max_uses', 'used_count')
        }),
        ('有効期間', {
            'fields': ('start_date', 'expiry_date')
        }),
        ('システム情報', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['activate_coupons', 'deactivate_coupons']
    
    def discount_display(self, obj):
        """割引額の表示"""
        if obj.discount_type == 'percentage':
            return f'{obj.discount_value}% OFF'
        elif obj.discount_type == 'fixed':
            return f'¥{obj.discount_value} OFF'
        elif obj.discount_type == 'free':
            return '無料'
        return str(obj.discount_value)
    discount_display.short_description = '割引内容'
    
    def usage_display(self, obj):
        """使用状況の表示"""
        return f'{obj.used_count} / {obj.max_uses}'
    usage_display.short_description = '使用状況'
    
    def validity_period(self, obj):
        """有効期間の表示"""
        return f'{obj.start_date.strftime("%Y/%m/%d")} 〜 {obj.expiry_date.strftime("%Y/%m/%d")}'
    validity_period.short_description = '有効期間'
    
    def activate_coupons(self, request, queryset):
        """クーポンを有効化"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated}件のクーポンを有効化しました。')
    activate_coupons.short_description = '選択したクーポンを有効化'
    
    def deactivate_coupons(self, request, queryset):
        """クーポンを無効化"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated}件のクーポンを無効化しました。')
    deactivate_coupons.short_description = '選択したクーポンを無効化'


# =====================================
# UserCoupon
# =====================================

@admin.register(UserCoupon)
class UserCouponAdmin(admin.ModelAdmin):
    """ユーザークーポン使用履歴管理"""
    list_display = [
        'user',
        'coupon_code',
        'coupon_title',
        'used_at',
        'reservation'
    ]
    list_filter = [
        'used_at',
    ]
    search_fields = [
        'user__username',
        'coupon__code',
        'coupon__title'
    ]
    readonly_fields = [
        'user',
        'coupon',
        'used_at',
        'reservation'
    ]
    date_hierarchy = 'used_at'
    
    def get_queryset(self, request):
        """効率的なクエリ"""
        qs = super().get_queryset(request)
        return qs.select_related('user', 'coupon', 'reservation')
    
    def coupon_code(self, obj):
        """クーポンコードの表示"""
        return obj.coupon.code
    coupon_code.short_description = 'クーポンコード'
    
    def coupon_title(self, obj):
        """クーポンタイトルの表示"""
        return obj.coupon.title
    coupon_title.short_description = 'クーポン名'
    
    def has_add_permission(self, request):
        """追加権限なし（使用時に自動生成）"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """変更権限なし（使用履歴は変更不可）"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """削除権限あり（誤使用の場合のみ）"""
        return request.user.is_superuser

# =====================================
# Contact
# =====================================

@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'created_at', 'is_read')
    list_filter = ('is_read', 'created_at')
    search_fields = ('name', 'email', 'message')
    readonly_fields = ('created_at',)
    list_editable = ('is_read',)
    
    fieldsets = (
        ('送信者情報', {
            'fields': ('name', 'email')
        }),
        ('お問い合わせ内容', {
            'fields': ('message',)
        }),
        ('管理情報', {
            'fields': ('is_read', 'created_at')
        }),
    )

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('ticket_number', 'reservation', 'ticket_type', 'price', 'issued_at', 'is_used')
    list_filter = ('ticket_type', 'is_used', 'issued_at')
    search_fields = ('ticket_number', 'reservation__user__username', 'reservation__movie__title')
    readonly_fields = ('ticket_number', 'issued_at')