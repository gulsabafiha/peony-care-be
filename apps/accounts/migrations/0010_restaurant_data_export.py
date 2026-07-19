import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0009_restaurant_detail_profile_gaps"),
    ]

    operations = [
        migrations.CreateModel(
            name="RestaurantDataExport",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("phone_e164", models.CharField(max_length=20)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("COMPLETED", "Completed"),
                            ("FAILED", "Failed"),
                        ],
                        default="PENDING",
                        max_length=20,
                    ),
                ),
                ("file_path", models.CharField(blank=True, max_length=500)),
                ("requested_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="restaurant_data_exports",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "restaurant_data_exports",
                "ordering": ["-requested_at"],
                "indexes": [
                    models.Index(
                        fields=["user", "requested_at"],
                        name="restaurant__user_id_e8c1a2_idx",
                    )
                ],
            },
        ),
    ]
