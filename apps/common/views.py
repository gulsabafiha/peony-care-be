from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET


@require_GET
def health_check(request):
    return JsonResponse(
        {
            "status": "success",
            "data": {"service": "peony-care-be", "healthy": True},
            "error": None,
            "timestamp": timezone.now().isoformat(),
        }
    )
