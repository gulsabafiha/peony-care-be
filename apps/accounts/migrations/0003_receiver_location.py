from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_auto_approve_restaurants"),
    ]

    operations = [
        migrations.AddField(
            model_name="receiverprofile",
            name="latitude",
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="receiverprofile",
            name="longitude",
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="receiverprofile",
            name="browse_radius_km",
            field=models.FloatField(default=5.0),
        ),
    ]
