from django.db import models

class Movie(models.Model):
    title = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.title

class Seat(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE)
    seat_code = models.CharField(max_length=5)
    is_reserved = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.seat_code} ({'予約済' if self.is_reserved else '空席'})"
