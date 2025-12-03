from django.contrib import admin
from django.utils.html import format_html
from .models import Movie, Seat, Reservation, Notification, ShowSchedule, UserProfile, ChatMessage

# 管理画面のヘッダーとタイトルを日本語化
admin.site.site_header = "Cinema Website 管理画面"
admin.site.site_title = "Cinema 管理"
admin.site.index_title = "ダッシュボード"

class ShowScheduleInline(admin.TabularInline):
    model = ShowSchedule
    extra = 1
    fields = ('date', 'start_time', 'end_time', 'screen', 'format')
    show_change_link = True
    verbose_name = "上映スケジュール"
    verbose_name_plural = "上映スケジュール"

@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = ['title', 'status', 'release_date', 'show_date', 'genre', 'price', 'image_tag']
    list_filter = ['status', 'genre', 'show_date']
    search_fields = ['title', 'description']
    list_editable = ['status']
    date_hierarchy = 'show_date'
    inlines = [ShowScheduleInline]
    
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
    
    def image_tag(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="100" />'.format(obj.image.url))
        return "-"
    image_tag.short_description = '画像'

@admin.register(Seat)
class SeatAdmin(admin.ModelAdmin):
    list_display = ['seat_number']
    search_fields = ['seat_number']

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

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'message', 'created_at', 'is_read']
    list_filter = ['is_read', 'created_at']
    search_fields = ['user__username', 'message']
    date_hierarchy = 'created_at'
    list_editable = ['is_read']

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone_number', 'is_completed']
    list_filter = ['is_completed']
    search_fields = ['user__username', 'phone_number']
    list_editable = ['is_completed']

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