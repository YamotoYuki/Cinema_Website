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

    class Meta:
        unique_together = ('movie', 'seat') 
