from django.contrib import admin
from django.utils.html import format_html
from .models import Movie, Seat, Reservation, Notification, ShowSchedule

class ShowScheduleInline(admin.TabularInline):
    model = ShowSchedule
    extra = 1
    fields = ('date', 'start_time', 'end_time', 'screen', 'format')
    show_change_link = True

@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = ['title', 'status', 'release_date', 'show_date', 'genre', 'price']
    list_filter = ['status', 'genre', 'show_date']
    search_fields = ['title', 'description']
    list_editable = ['status']  # 一覧画面で直接編集可能
    date_hierarchy = 'show_date'
    
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
    )

admin.site.register(Seat)
admin.site.register(Reservation)
