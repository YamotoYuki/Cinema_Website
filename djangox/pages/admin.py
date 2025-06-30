from django.contrib import admin
from django.utils.html import format_html
from .models import Movie, Seat, Reservation, ShowSchedule

class ShowScheduleInline(admin.TabularInline):
    model = ShowSchedule
    extra = 1
    fields = ('date', 'start_time', 'end_time', 'screen', 'format')
    show_change_link = True

@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = ('title', 'genre', 'price', 'show_date', 'image_tag')
    inlines = [ShowScheduleInline]

    def image_tag(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="100" />'.format(obj.image.url))
        return "-"
    image_tag.short_description = '画像'

admin.site.register(Seat)
admin.site.register(Reservation)
