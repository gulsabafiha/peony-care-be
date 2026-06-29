import uuid

import django.db.models.deletion
from django.db import migrations, models


DEFAULT_REPORT_REASONS = [
    ("unsafe-or-spoiled", "Food was unsafe or spoiled", 1),
    ("misleading-listing", "Listing is misleading", 2),
    ("restaurant-closed", "Restaurant was closed or absent", 3),
    ("rude-behaviour", "Rude or inappropriate behaviour", 4),
    ("asked-to-pay", "Asked me to pay for the food", 5),
    ("other", "Something else", 6),
]

LEGACY_REASON_CODE_MAP = {
    "UNSAFE_OR_SPOILED": "unsafe-or-spoiled",
    "MISLEADING_LISTING": "misleading-listing",
    "RESTAURANT_CLOSED": "restaurant-closed",
    "RUDE_BEHAVIOUR": "rude-behaviour",
    "ASKED_TO_PAY": "asked-to-pay",
    "OTHER": "other",
}


def seed_report_reasons(apps, schema_editor):
    FoodReportReasonOption = apps.get_model("donations", "FoodReportReasonOption")
    for code, label, sort_order in DEFAULT_REPORT_REASONS:
        FoodReportReasonOption.objects.get_or_create(
            code=code,
            defaults={"label": label, "sort_order": sort_order, "is_active": True},
        )


def link_existing_reports(apps, schema_editor):
    FoodReport = apps.get_model("donations", "FoodReport")
    FoodReportReasonOption = apps.get_model("donations", "FoodReportReasonOption")

    for report in FoodReport.objects.all():
        legacy_code = report.reason
        option_code = LEGACY_REASON_CODE_MAP.get(legacy_code, "other")
        option = FoodReportReasonOption.objects.get(code=option_code)
        report.reason_option_id = option.id
        report.save(update_fields=["reason_option_id"])


class Migration(migrations.Migration):
    dependencies = [
        ("donations", "0002_food_report"),
    ]

    operations = [
        migrations.CreateModel(
            name="FoodReportReasonOption",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("code", models.SlugField(max_length=50, unique=True)),
                ("label", models.CharField(max_length=200)),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.IntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "food_report_reason_options",
                "ordering": ["sort_order", "label"],
            },
        ),
        migrations.RunPython(seed_report_reasons, migrations.RunPython.noop),
        migrations.AddField(
            model_name="foodreport",
            name="reason_option",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="reports",
                to="donations.foodreportreasonoption",
            ),
        ),
        migrations.RunPython(link_existing_reports, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="foodreport",
            name="reason",
        ),
        migrations.AlterField(
            model_name="foodreport",
            name="reason_option",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="reports",
                to="donations.foodreportreasonoption",
            ),
        ),
    ]
