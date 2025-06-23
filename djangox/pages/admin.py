from django.contrib import admin
from .models import Movie, Seat, Reservation
from django.utils.html import format_html

@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = ('title', 'genre', 'price', 'show_date', 'image_tag')

    def image_tag(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="100" />'.format(obj.image.url))
        return "-"
    image_tag.short_description = '画像'


admin.site.register(Seat)
admin.site.register(Reservation)
