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
