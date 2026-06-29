from rest_framework import serializers

from apps.common.choices import CreditPreference


class DonorProfileSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    display_name = serializers.CharField()
    contact_email = serializers.EmailField(allow_blank=True)
    photo_url = serializers.URLField(allow_null=True, required=False)
    credit_preference = serializers.CharField()
    total_meals_sponsored = serializers.IntegerField()
    total_amount_donated_sgd = serializers.CharField()
    phone = serializers.CharField(required=False)


class DonorProfileUpdateSerializer(serializers.Serializer):
    display_name = serializers.CharField(max_length=100, required=False)
    contact_email = serializers.EmailField(required=False, allow_blank=True)
    photo_url = serializers.URLField(required=False, allow_blank=True)


class CreditPreferenceSerializer(serializers.Serializer):
    credit_preference = serializers.ChoiceField(choices=CreditPreference.choices)


class DonorDashboardSerializer(serializers.Serializer):
    total_meals_sponsored = serializers.IntegerField()
    total_amount_donated_sgd = serializers.CharField()
    lives_impacted = serializers.IntegerField()
    recent_donations = serializers.ListField(child=serializers.DictField(), required=False)


class DonorHistoryItemSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=["MEAL", "MONEY"])
    id = serializers.UUIDField()
    restaurant_id = serializers.UUIDField(required=False)
    restaurant_name = serializers.CharField(allow_null=True, required=False)
    amount_sgd = serializers.CharField()
    reference_code = serializers.CharField(required=False)
    is_anonymous = serializers.BooleanField(required=False)
    status = serializers.CharField()
    food_item_id = serializers.UUIDField(allow_null=True, required=False)
    items = serializers.ListField(child=serializers.DictField(), required=False)
    transfer_marked_at = serializers.DateTimeField(allow_null=True, required=False)
    confirmed_at = serializers.DateTimeField(allow_null=True, required=False)
    created_at = serializers.DateTimeField()


class DonorImpactMonthlySerializer(serializers.Serializer):
    month = serializers.CharField()
    meals = serializers.IntegerField()
    amount_sgd = serializers.CharField()


class DonorImpactSerializer(serializers.Serializer):
    total_meals_sponsored = serializers.IntegerField()
    total_amount_donated_sgd = serializers.CharField()
    lives_impacted = serializers.IntegerField()
    monthly = DonorImpactMonthlySerializer(many=True)


class RestaurantBrowseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    address = serializers.CharField()
    postal_code = serializers.CharField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    photo_url = serializers.URLField(allow_null=True, required=False)
    is_verified = serializers.BooleanField()
    menu_item_count = serializers.IntegerField()


class RestaurantMenuItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    price_sgd = serializers.CharField()
    photo_url = serializers.URLField(allow_null=True, required=False)
    is_available = serializers.BooleanField()
    sort_order = serializers.IntegerField()


class RestaurantMenuSerializer(serializers.Serializer):
    restaurant_id = serializers.UUIDField()
    restaurant_name = serializers.CharField()
    menu_items = RestaurantMenuItemSerializer(many=True)


class MealOrderItemInputSerializer(serializers.Serializer):
    menu_item_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)


class CreateMealOrderSerializer(serializers.Serializer):
    restaurant_id = serializers.UUIDField()
    items = MealOrderItemInputSerializer(many=True, min_length=1)
    pickup_start = serializers.DateTimeField()
    pickup_end = serializers.DateTimeField()
    credit_preference = serializers.ChoiceField(
        choices=CreditPreference.choices,
        required=False,
    )


class CreateMoneyDonationSerializer(serializers.Serializer):
    amount_sgd = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=1)
    is_anonymous = serializers.BooleanField(required=False, default=False)


class MealOrderResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    restaurant_id = serializers.UUIDField()
    restaurant_name = serializers.CharField()
    total_amount_sgd = serializers.CharField()
    credit_preference = serializers.CharField()
    status = serializers.CharField()
    food_item = serializers.DictField()
    items = serializers.ListField(child=serializers.DictField())
    created_at = serializers.DateTimeField()


class MoneyDonationResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    amount_sgd = serializers.CharField()
    reference_code = serializers.CharField()
    is_anonymous = serializers.BooleanField()
    status = serializers.CharField()
    paynow = serializers.DictField()
    created_at = serializers.DateTimeField()


class MoneyDonationTransferSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    amount_sgd = serializers.CharField()
    reference_code = serializers.CharField()
    status = serializers.CharField()
    transfer_marked_at = serializers.DateTimeField()
