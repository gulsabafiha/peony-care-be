from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="notificationsettings",
            name="alert_no_show",
            field=models.BooleanField(default=True),
        ),
    ]
