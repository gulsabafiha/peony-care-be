from collections import defaultdict

import phonenumbers
from django.db import migrations


PHONE_REGION = "SG"


def _to_e164(phone: str) -> str | None:
    if not phone:
        return None
    try:
        parsed = phonenumbers.parse(str(phone).strip(), PHONE_REGION)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(parsed):
        return None
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def _normalize_user_phones(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    grouped: dict[str, list] = defaultdict(list)

    for user in User.objects.all().order_by("-is_active", "created_at"):
        normalized = _to_e164(user.phone_e164)
        if normalized is None:
            continue
        grouped[normalized].append(user)

    for normalized, users in grouped.items():
        keeper = users[0]
        if keeper.phone_e164 != normalized:
            keeper.phone_e164 = normalized
            keeper.save(update_fields=["phone_e164"])
        for duplicate in users[1:]:
            duplicate.delete()


def _normalize_phone_field(apps, schema_editor, model_name: str):
    Model = apps.get_model("accounts", model_name)
    for row in Model.objects.all():
        normalized = _to_e164(row.phone_e164)
        if normalized and row.phone_e164 != normalized:
            row.phone_e164 = normalized
            row.save(update_fields=["phone_e164"])


def normalize_phone_numbers(apps, schema_editor):
    _normalize_user_phones(apps, schema_editor)
    _normalize_phone_field(apps, schema_editor, "OtpChallenge")
    _normalize_phone_field(apps, schema_editor, "ReceiverDataExport")


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0007_receiver_data_export_phone"),
    ]

    operations = [
        migrations.RunPython(normalize_phone_numbers, migrations.RunPython.noop),
    ]
