from django.db import migrations, models
from django.utils import timezone


def approve_existing_restaurants(apps, schema_editor):
    RestaurantProfile = apps.get_model("accounts", "RestaurantProfile")
    RestaurantProfile.objects.filter(is_approved=False).update(
        is_approved=True,
        approved_at=timezone.now(),
    )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="restaurantprofile",
            name="is_approved",
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(approve_existing_restaurants, migrations.RunPython.noop),
    ]
