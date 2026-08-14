from django.db import migrations, models
from django.utils import timezone as dj_timezone


CATEGORY_MAP = {
    "BREAD": "BREAD_BAKERY",
    "SNACKS": "PACKAGED",
}


def remap_categories_and_day_windows(apps, schema_editor):
    FoodItem = apps.get_model("donations", "FoodItem")
    for old, new in CATEGORY_MAP.items():
        FoodItem.objects.filter(category=old).update(category=new)

    from apps.common.timezone_utils import day_bounds_in, timezone_for_restaurant

    now = dj_timezone.now()
    for food in FoodItem.objects.select_related("restaurant").iterator():
        restaurant = food.restaurant
        tz = timezone_for_restaurant(restaurant)
        day = food.pickup_start.astimezone(tz).date()
        start, end = day_bounds_in(day, tz=tz)
        update_fields = ["pickup_start", "pickup_end"]
        food.pickup_start = start
        food.pickup_end = end
        if food.list_status == "ACTIVE" and end <= now:
            food.list_status = "PAST"
            food.closed_at = now
            update_fields.extend(["list_status", "closed_at"])
            if food.quantity_available > 0:
                food.status = "EXPIRED"
                food.closed_reason = "EXPIRED"
                update_fields.extend(["status", "closed_reason"])
            elif not food.closed_reason:
                food.closed_reason = "FULLY_CLAIMED"
                update_fields.append("closed_reason")
        food.save(update_fields=update_fields)


def noop_reverse(apps, schema_editor):
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("donations", "0007_fooditem_recurrence_series"),
    ]

    operations = [
        migrations.AlterField(
            model_name="fooditem",
            name="category",
            field=models.CharField(
                choices=[
                    ("COOKED_MEAL", "Cooked meal"),
                    ("RICE", "Rice"),
                    ("NOODLES", "Noodles"),
                    ("BREAD_BAKERY", "Bread & bakery"),
                    ("VEGETABLES", "Vegetables"),
                    ("FRUITS", "Fruits"),
                    ("PROTEIN", "Meat & protein"),
                    ("SOUP", "Soup"),
                    ("DESSERT", "Dessert"),
                    ("DRINKS", "Drinks"),
                    ("PACKAGED", "Packaged food"),
                    ("OTHER", "Other"),
                ],
                max_length=32,
            ),
        ),
        migrations.RunPython(remap_categories_and_day_windows, noop_reverse),
    ]
