import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0010_restaurant_data_export"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="restaurantdataexport",
            new_name="restaurant__user_id_a1eda7_idx",
            old_name="restaurant__user_id_e8c1a2_idx",
        ),
        migrations.AddField(
            model_name="restaurantdataexport",
            name="email",
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AddField(
            model_name="restaurantdataexport",
            name="email_sent",
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name="RestaurantLegalRetention",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("former_user_id", models.UUIDField()),
                ("former_restaurant_id", models.UUIDField()),
                ("phone_e164", models.CharField(max_length=20)),
                ("uen", models.CharField(max_length=20)),
                ("business_name", models.CharField(max_length=200)),
                ("contact_name", models.CharField(blank=True, max_length=100)),
                ("contact_email", models.EmailField(blank=True, max_length=254)),
                ("contact_phone", models.CharField(blank=True, max_length=20)),
                ("deleted_at", models.DateTimeField()),
                ("purge_after", models.DateTimeField()),
                ("purged_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "db_table": "restaurant_legal_retentions",
                "ordering": ["-deleted_at"],
            },
        ),
        migrations.CreateModel(
            name="RestaurantPayoutRetention",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("former_meal_order_id", models.UUIDField()),
                ("former_restaurant_id", models.UUIDField()),
                ("restaurant_uen", models.CharField(max_length=20)),
                ("restaurant_name", models.CharField(max_length=200)),
                ("donor_label", models.CharField(blank=True, max_length=200)),
                ("total_amount_sgd", models.DecimalField(decimal_places=2, max_digits=10)),
                ("credit_preference", models.CharField(blank=True, max_length=20)),
                ("status", models.CharField(max_length=20)),
                ("ordered_at", models.DateTimeField()),
                ("items", models.JSONField(blank=True, default=list)),
                ("retained_until", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "legal_retention",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payouts",
                        to="accounts.restaurantlegalretention",
                    ),
                ),
            ],
            options={
                "db_table": "restaurant_payout_retentions",
                "ordering": ["-ordered_at"],
            },
        ),
        migrations.AddIndex(
            model_name="restaurantlegalretention",
            index=models.Index(fields=["purge_after"], name="restaurant__purge_a_7c2e1a_idx"),
        ),
        migrations.AddIndex(
            model_name="restaurantlegalretention",
            index=models.Index(fields=["uen"], name="restaurant__uen_8f1b2c_idx"),
        ),
        migrations.AddIndex(
            model_name="restaurantpayoutretention",
            index=models.Index(fields=["retained_until"], name="restaurant__retaine_3a9d4e_idx"),
        ),
        migrations.AddIndex(
            model_name="restaurantpayoutretention",
            index=models.Index(
                fields=["former_restaurant_id"], name="restaurant__former__5b6c7d_idx"
            ),
        ),
    ]
