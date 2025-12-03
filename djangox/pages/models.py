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