from django.db import migrations, models


def backfill_series_ids(apps, schema_editor):
    FoodItem = apps.get_model("donations", "FoodItem")
    for food in FoodItem.objects.filter(
        recurrence_type__in=["DAILY", "CUSTOM"],
        recurrence_series_id__isnull=True,
    ).iterator():
        food.recurrence_series_id = food.id
        food.save(update_fields=["recurrence_series_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("donations", "0006_menu_photos"),
    ]

    operations = [
        migrations.AddField(
            model_name="fooditem",
            name="recurrence_series_id",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
        migrations.RunPython(backfill_series_ids, migrations.RunPython.noop),
    ]
