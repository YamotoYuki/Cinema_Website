from django.db import models
from django.conf import settings
from decimal import Decimal

class Movie(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    show_date = models.DateField()
    genre = models.CharField(max_length=100, blank=True)
    price = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'))
    image = models.ImageField(upload_to='movie_images/', blank=True, null=True)
    duration = models.PositiveIntegerField(null=True, blank=True, help_text="上映時間（分）")
    theater = models.CharField(max_length=100, null=True, blank=True, help_text="シアター名")
    
    payment_method = models.CharField(max_length=50, blank=True, null=True)
    convenience_type = models.CharField(max_length=50, blank=True, null=True)


    def __str__(self):
        return self.title
    
class Seat(models.Model):
    seat_number = models.CharField(max_length=5)

    def __str__(self):
        return self.seat_number

class Reservation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE)
    seat = models.ForeignKey(Seat, on_delete=models.CASCADE)
    reserved_at = models.DateTimeField(auto_now_add=True)
    show_time = models.CharField(max_length=50, default='未設定')
    qr_code_image = models.ImageField(upload_to='qr_codes/', blank=True, null=True)

    # ここから追加
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
    )
    # ここまで追加

    class Meta:
        unique_together = ('movie', 'seat')


# ここに追加
class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"Notification for {self.user}: {self.message}"
