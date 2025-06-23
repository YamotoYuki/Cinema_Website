from .models import Notification

def unread_notifications_processor(request):
    if request.user.is_authenticated:
        unread = Notification.objects.filter(user=request.user, is_read=False)
        return {
            'unread_notifications': unread,
            'unread_count': unread.count()
        }
    return {}
