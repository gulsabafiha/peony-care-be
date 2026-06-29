from django.db import migrations, models


def copy_phone_from_user(apps, schema_editor):
    ReceiverDataExport = apps.get_model("accounts", "ReceiverDataExport")
    for export in ReceiverDataExport.objects.select_related("user").iterator():
        export.phone_e164 = export.user.phone_e164
        export.save(update_fields=["phone_e164"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0006_receiver_data_export"),
    ]

    operations = [
        migrations.AddField(
            model_name="receiverdataexport",
            name="phone_e164",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.RunPython(copy_phone_from_user, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="receiverdataexport",
            name="phone_e164",
            field=models.CharField(max_length=20),
        ),
        migrations.RemoveField(
            model_name="receiverdataexport",
            name="email",
        ),
    ]
