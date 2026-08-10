from django.shortcuts import render
from django.views.decorators.http import require_GET


@require_GET
def privacy_policy(request):
    return render(request, "legal/privacy.html", {"page_title": "Privacy Policy"})


@require_GET
def terms_of_service(request):
    return render(request, "legal/terms.html", {"page_title": "Terms of Use"})
