"""Daily caps on the calls the site's own key pays for."""
from datetime import date

from django.core.cache import cache


def _visitor(request):
    if request.user.is_authenticated:
        return f"user-{request.user.pk}"
    # Behind Heroku's router the visitor's address is the first one in X-Forwarded-For.
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return "ip-" + (forwarded.split(",")[0].strip() or request.META.get("REMOTE_ADDR", "unknown"))


def spend_one(request, name, per_visitor, overall):
    """Count one call to the site's key against today's caps; False when either cap is already reached."""
    today = date.today().isoformat()
    counters = [(f"{name}:{today}:all", overall), (f"{name}:{today}:{_visitor(request)}", per_visitor)]
    if any(cache.get(key, 0) >= limit for key, limit in counters):
        return False
    for key, _ in counters:
        cache.add(key, 0, 60 * 60 * 26)
        cache.incr(key)
    return True
