# Generated manually — replace claim-scoped reviews with restaurant-scoped reviews.

import django.core.validators
import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0012_rename_restaurant__purge_a_7c2e1a_idx_restaurant__purge_a_84e4e7_idx_and_more"),
        ("claims", "0005_claim_reviews"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.DeleteModel(name="ClaimReview"),
        migrations.CreateModel(
            name="RestaurantReview",
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
                (
                    "rating",
                    models.PositiveSmallIntegerField(
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(5),
                        ]
                    ),
                ),
                ("comment", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "receiver",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="restaurant_reviews",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "restaurant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reviews",
                        to="accounts.restaurantprofile",
                    ),
                ),
                (
                    "tags",
                    models.ManyToManyField(
                        blank=True,
                        related_name="reviews",
                        to="claims.reviewtagoption",
                    ),
                ),
            ],
            options={
                "db_table": "restaurant_reviews",
            },
        ),
        migrations.AddIndex(
            model_name="restaurantreview",
            index=models.Index(
                fields=["restaurant", "-created_at"],
                name="restaurant__restaur_1d5199_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="restaurantreview",
            index=models.Index(
                fields=["receiver", "-created_at"],
                name="restaurant__receive_80e478_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="restaurantreview",
            constraint=models.UniqueConstraint(
                fields=("receiver", "restaurant"),
                name="uniq_receiver_restaurant_review",
            ),
        ),
    ]
