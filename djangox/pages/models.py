from django.db import models
from django.conf import settings
from decimal import Decimal

class Movie(models.Model):
    STATUS_CHOICES = [
        ('now_showing', '上映中'),
        ('coming_soon', '公開予定'),
    ]
    
    title = models.CharField(max_length=200, verbose_name='タイトル')
    description = models.TextField(verbose_name='説明')
    show_date = models.DateField(verbose_name='上映日')
    genre = models.CharField(max_length=100, blank=True, verbose_name='ジャンル')
    price = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'), verbose_name='料金')
    image = models.ImageField(upload_to='movie_images/', blank=True, null=True, verbose_name='画像')
    duration = models.PositiveIntegerField(null=True, blank=True, help_text="上映時間（分）", verbose_name='上映時間')
    theater = models.CharField(max_length=100, null=True, blank=True, help_text="シアター名", verbose_name='シアター')
    
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='now_showing',
        verbose_name='上映ステータス'
    )
    release_date = models.DateField(
        null=True, 
        blank=True,
        verbose_name='公開日',
        help_text='公開予定日（coming_soonの場合に設定）'
    )
    
    payment_method = models.CharField(max_length=50, blank=True, null=True, verbose_name='支払い方法')
    convenience_type = models.CharField(max_length=50, blank=True, null=True, verbose_name='コンビニ種類')

    class Meta:
        ordering = ['status', '-show_date']
        verbose_name = '映画'
        verbose_name_plural = '映画'

    def __str__(self):
        return self.title
    
class Seat(models.Model):
    seat_number = models.CharField(max_length=5, verbose_name='座席番号')

    class Meta:
        verbose_name = '座席'
        verbose_name_plural = '座席'

    def __str__(self):
        return self.seat_number

class Reservation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='ユーザー')
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, verbose_name='映画')
    seat = models.ForeignKey(Seat, on_delete=models.CASCADE, verbose_name='座席')
    reserved_at = models.DateTimeField(auto_now_add=True, verbose_name='予約日時')
    show_time = models.CharField(max_length=50, verbose_name='上映時間')
    qr_code_image = models.ImageField(upload_to='qr_codes/', blank=True, null=True, verbose_name='QRコード')

    PAYMENT_METHOD_CHOICES = [
        ('cash', '現金'),
        ('credit_card', 'クレジットカード'),
        ('paypal', 'PayPal'),
        ('merpay', 'メルペイ'),
        ('paypay', 'PayPay'),
        ('convenience_store', 'コンビニ払い'),
    ]
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default='cash',
        verbose_name='支払い方法'
    )

    CONVENIENCE_TYPE_CHOICES = [
        ('7eleven', 'セブンイレブン'),
        ('famima', 'ファミリーマート'),
        ('daily', 'デイリーヤマザキ'),
        ('ministop', 'ミニストップ'),
        ('lawson', 'ローソン'),
    ]
    convenience_type = models.CharField(
        max_length=20,
        choices=CONVENIENCE_TYPE_CHOICES,
        blank=True,
        null=True,
        verbose_name='コンビニ種類'
    )

    class Meta:
        unique_together = ('movie', 'seat', 'show_time')
        verbose_name = '予約'
        verbose_name_plural = '予約'
        ordering = ['-reserved_at']

    def __str__(self):
        return f"{self.user.username} - {self.movie.title}"

class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='ユーザー')
    message = models.CharField(max_length=255, verbose_name='メッセージ')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='作成日時')
    is_read = models.BooleanField(default=False, verbose_name='既読')

    class Meta:
        verbose_name = '通知'
        verbose_name_plural = '通知'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username}への通知: {self.message}"

class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='ユーザー')
    phone_number = models.CharField(max_length=15, blank=True, verbose_name='電話番号')
    profile_image = models.ImageField(upload_to='profile_images/', blank=True, null=True, verbose_name='プロフィール画像')
    is_completed = models.BooleanField(default=False, verbose_name='プロフィール完了')

    class Meta:
        verbose_name = 'ユーザープロフィール'
        verbose_name_plural = 'ユーザープロフィール'

    def __str__(self):
        return self.user.username

class ShowSchedule(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='schedules', verbose_name='映画')
    date = models.DateField(verbose_name='上映日')
    start_time = models.TimeField(verbose_name='開始時間')
    end_time = models.TimeField(verbose_name='終了時間')
    screen = models.IntegerField(verbose_name='スクリーン')
    format = models.CharField(max_length=50, blank=True, verbose_name='上映形式')

    class Meta:
        verbose_name = '上映スケジュール'
        verbose_name_plural = '上映スケジュール'
        ordering = ['date', 'start_time']

    def __str__(self):
        return f"{self.movie.title} | {self.date} {self.start_time} - {self.end_time} (スクリーン{self.screen})"
    
class ChatMessage(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='ユーザー')
    message = models.TextField(verbose_name='メッセージ')
    response = models.TextField(verbose_name='AI応答', blank=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='作成日時')
    is_user = models.BooleanField(default=True, verbose_name='ユーザーメッセージ')

    class Meta:
        ordering = ['created_at']
        verbose_name = 'チャットメッセージ'
        verbose_name_plural = 'チャットメッセージ'

    def __str__(self):
        return f"{self.user.username} - {self.created_at}"
    
    
from django.db import models
from django.conf import settings
from django.utils import timezone

# settings.AUTH_USER_MODELを使用してUserモデルを参照

class UserProfile(models.Model):
    """ユーザープロフィール拡張"""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='ユーザー'
    )
    profile_image = models.ImageField(
        upload_to='profile_images/',
        blank=True,
        null=True,
        verbose_name='プロフィール画像'
    )
    birth_date = models.DateField(
        blank=True,
        null=True,
        verbose_name='生年月日'
    )
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name='電話番号'
    )
    points = models.IntegerField(
        default=0,
        verbose_name='ポイント'
    )
    membership_level = models.CharField(
        max_length=20,
        choices=[
            ('standard', 'スタンダード'),
            ('gold', 'ゴールド'),
            ('platinum', 'プラチナ'),
        ],
        default='standard',
        verbose_name='会員レベル'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='作成日時'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新日時'
    )

    class Meta:
        verbose_name = 'ユーザープロフィール'
        verbose_name_plural = 'ユーザープロフィール'

    def __str__(self):
        return f"{self.user.username}のプロフィール"

    def add_points(self, points, reason=""):
        """ポイントを追加"""
        self.points += points
        self.save()
        
        # ポイント履歴を作成
        PointHistory.objects.create(
            user=self.user,
            points=points,
            reason=reason,
            balance_after=self.points
        )
        
        # 会員レベルを更新
        self.update_membership_level()

    def use_points(self, points, reason=""):
        """ポイントを使用"""
        if self.points >= points:
            self.points -= points
            self.save()
            
            # ポイント履歴を作成
            PointHistory.objects.create(
                user=self.user,
                points=-points,
                reason=reason,
                balance_after=self.points
            )
            return True
        return False

    def update_membership_level(self):
        """ポイントに基づいて会員レベルを更新"""
        if self.points >= 5000:
            self.membership_level = 'platinum'
        elif self.points >= 2000:
            self.membership_level = 'gold'
        else:
            self.membership_level = 'standard'
        self.save()


class PointHistory(models.Model):
    """ポイント履歴"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='point_histories',
        verbose_name='ユーザー'
    )
    points = models.IntegerField(verbose_name='ポイント増減')
    reason = models.CharField(
        max_length=200,
        verbose_name='理由'
    )
    balance_after = models.IntegerField(
        verbose_name='変更後残高'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='作成日時'
    )

    class Meta:
        verbose_name = 'ポイント履歴'
        verbose_name_plural = 'ポイント履歴'
        ordering = ['-created_at']

    def __str__(self):
        sign = '+' if self.points > 0 else ''
        return f"{self.user.username}: {sign}{self.points}pt - {self.reason}"


class Coupon(models.Model):
    """クーポン"""
    code = models.CharField(
        max_length=20,
        unique=True,
        verbose_name='クーポンコード'
    )
    title = models.CharField(
        max_length=100,
        verbose_name='タイトル'
    )
    description = models.TextField(
        verbose_name='説明'
    )
    discount_type = models.CharField(
        max_length=20,
        choices=[
            ('percentage', 'パーセント割引'),
            ('fixed', '定額割引'),
            ('free', '無料'),
        ],
        default='fixed',
        verbose_name='割引タイプ'
    )
    discount_value = models.IntegerField(
        verbose_name='割引値'
    )
    min_purchase = models.IntegerField(
        default=0,
        verbose_name='最小購入金額'
    )
    max_uses = models.IntegerField(
        default=1,
        verbose_name='最大使用回数'
    )
    used_count = models.IntegerField(
        default=0,
        verbose_name='使用回数'
    )
    start_date = models.DateTimeField(
        verbose_name='開始日時'
    )
    expiry_date = models.DateTimeField(
        verbose_name='終了日時'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='有効'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='作成日時'
    )

    class Meta:
        verbose_name = 'クーポン'
        verbose_name_plural = 'クーポン'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.code} - {self.title}"

    def is_valid(self):
        """クーポンが有効かチェック"""
        now = timezone.now()
        return (
            self.is_active and
            self.start_date <= now <= self.expiry_date and
            self.used_count < self.max_uses
        )

    def can_use(self, user):
        """ユーザーが使用できるかチェック"""
        if not self.is_valid():
            return False
        
        # すでに使用しているかチェック
        used = UserCoupon.objects.filter(
            user=user,
            coupon=self
        ).exists()
        
        return not used

    def use(self, user):
        """クーポンを使用"""
        if self.can_use(user):
            self.used_count += 1
            self.save()
            
            # 使用履歴を作成
            UserCoupon.objects.create(
                user=user,
                coupon=self
            )
            return True
        return False


class UserCoupon(models.Model):
    """ユーザーのクーポン使用履歴"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='used_coupons',
        verbose_name='ユーザー'
    )
    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.CASCADE,
        related_name='users',
        verbose_name='クーポン'
    )
    used_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='使用日時'
    )
    reservation = models.ForeignKey(
        'Reservation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='予約'
    )

    class Meta:
        verbose_name = 'ユーザークーポン'
        verbose_name_plural = 'ユーザークーポン'
        ordering = ['-used_at']
        unique_together = ['user', 'coupon']

    def __str__(self):
        return f"{self.user.username} - {self.coupon.code}"


# シグナルの設定
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

User = get_user_model()

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """ユーザー作成時にUserProfileを自動作成"""
    if created:
        UserProfile.objects.get_or_create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """ユーザー保存時にUserProfileも保存"""
    if hasattr(instance, 'userprofile'):
        try:
            instance.userprofile.save()
        except UserProfile.DoesNotExist:
            UserProfile.objects.create(user=instance)


# 予約完了時にポイントを付与するシグナル
# Reservationモデルがある場合のみ使用
try:
    from .models import Reservation  # 同じファイル内にある場合
    
    @receiver(post_save, sender=Reservation)
    def add_points_on_reservation(sender, instance, created, **kwargs):
        """予約作成時にポイントを付与"""
        if created:
            try:
                profile, created = UserProfile.objects.get_or_create(user=instance.user)
                profile.add_points(100, f'予約: {instance.movie.title}')
            except Exception as e:
                print(f"ポイント付与エラー: {str(e)}")
except ImportError:
    # Reservationモデルが別ファイルにある場合は、そのファイルでシグナルを設定
    pass