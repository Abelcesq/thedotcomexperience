from .models import Connection, Message


def community_counts(request):
    """Unread messages + pending connection requests, for the nav badges."""
    if not request.user.is_authenticated:
        return {}
    return {
        "unread_messages": Message.objects.filter(recipient=request.user, read_at__isnull=True).count(),
        "pending_requests": Connection.objects.filter(
            addressee=request.user, status=Connection.Status.PENDING).count(),
    }
