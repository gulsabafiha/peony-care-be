"""Lightweight email helpers (console backend by default — no Celery)."""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def send_restaurant_data_export_email(
    *,
    to_email: str,
    restaurant_name: str,
    download_url: str,
) -> bool:
    """Send a secure download link. Returns True if dispatch succeeded."""
    if not to_email or not str(to_email).strip():
        logger.warning(
            "[Udufood Export Email] skipped — no business email for %s",
            restaurant_name,
        )
        return False

    subject = "Your Udufood data export is ready"
    body = (
        f"Hello {restaurant_name},\n\n"
        "Your Udufood business data export is ready.\n\n"
        f"Secure download link:\n{download_url}\n\n"
        "If you did not request this export, contact support@udufood.com.\n\n"
        "— Udufood"
    )
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "support@udufood.com"),
            recipient_list=[to_email.strip()],
            fail_silently=False,
        )
        logger.info("[Udufood Export Email] sent to %s", to_email)
        return True
    except Exception:
        logger.exception("[Udufood Export Email] failed for %s", to_email)
        return False
