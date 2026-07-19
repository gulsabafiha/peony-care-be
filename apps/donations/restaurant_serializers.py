from rest_framework import serializers

from apps.common.choices import FoodCategory, RecurrenceType


class CreateDonationSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    category = serializers.ChoiceField(choices=FoodCategory.choices)
    unit = serializers.CharField(max_length=20, required=False, default="pack")
    photo_url = serializers.URLField(required=False, allow_blank=True, default="")
    quantity = serializers.IntegerField(min_value=1)
    pickup_start = serializers.DateTimeField()
    pickup_end = serializers.DateTimeField()
    recurrence_type = serializers.ChoiceField(
        choices=RecurrenceType.choices,
        required=False,
        default=RecurrenceType.NONE,
    )
    recurrence_days = serializers.ListField(
        child=serializers.IntegerField(min_value=0, max_value=6),
        required=False,
        default=list,
    )


class UpdateDonationSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    category = serializers.ChoiceField(choices=FoodCategory.choices, required=False)
    unit = serializers.CharField(max_length=20, required=False)
    photo_url = serializers.URLField(required=False, allow_blank=True)
    quantity = serializers.IntegerField(min_value=1, required=False)
    pickup_start = serializers.DateTimeField(required=False)
    pickup_end = serializers.DateTimeField(required=False)
    recurrence_type = serializers.ChoiceField(choices=RecurrenceType.choices, required=False)
    recurrence_days = serializers.ListField(
        child=serializers.IntegerField(min_value=0, max_value=6),
        required=False,
    )


class DonationListQuerySerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=["active", "past", "inactive"],
        default="active",
    )


class RestaurantDonationSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    status = serializers.CharField()
    list_status = serializers.CharField()
    quantity_original = serializers.IntegerField()
    quantity_available = serializers.IntegerField()
    quantity_claimed = serializers.IntegerField()
    claims_progress_label = serializers.CharField()
    percent_claimed = serializers.IntegerField()
    is_done = serializers.BooleanField()
    pickup_window = serializers.CharField()
    recurrence_type = serializers.CharField()
    recurrence_days = serializers.ListField(child=serializers.IntegerField())
    recurrence_label = serializers.CharField(allow_null=True)
    sponsorship_type = serializers.CharField()
    sponsor_display_name = serializers.CharField(allow_null=True)
    is_sponsored = serializers.BooleanField()
    closed_at = serializers.DateTimeField(allow_null=True)
    closed_reason = serializers.CharField(allow_null=True)
    paused_ago = serializers.CharField(allow_null=True)
    expired_count = serializers.IntegerField()
    unclaimed_count = serializers.IntegerField()
    food_qr_data = serializers.CharField()


class DonationGroupSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    date = serializers.CharField(allow_null=True, required=False)
    listings_count = serializers.IntegerField(required=False)
    completed_count = serializers.IntegerField(required=False)
    portions = serializers.IntegerField(required=False)
    fed = serializers.IntegerField(required=False)
    items = RestaurantDonationSerializer(many=True)


class DonationListSummarySerializer(serializers.Serializer):
    active_count = serializers.IntegerField()
    past_count = serializers.IntegerField()
    inactive_count = serializers.IntegerField()
    selected_count = serializers.IntegerField()
    meals_this_week = serializers.IntegerField(allow_null=True)
    subtitle = serializers.CharField(allow_null=True)


class DonationListResponseSerializer(serializers.Serializer):
    summary = DonationListSummarySerializer()
    groups = DonationGroupSerializer(many=True)


class DashboardRestaurantSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    photo_url = serializers.CharField(allow_null=True)
    initials = serializers.CharField()


class DashboardImpactSerializer(serializers.Serializer):
    lives_impacted = serializers.IntegerField()
    donations_this_year = serializers.IntegerField()
    week_over_week_pct = serializers.IntegerField()


class DashboardTodaySerializer(serializers.Serializer):
    active_count = serializers.IntegerField()
    claimed_today = serializers.IntegerField()
    claim_rate_pct = serializers.IntegerField()


class DashboardWeekSerializer(serializers.Serializer):
    donations = serializers.IntegerField()
    meals = serializers.IntegerField()
    inactive_count = serializers.IntegerField()


class DashboardActiveDonationsSerializer(serializers.Serializer):
    groups = DonationGroupSerializer(many=True)


class DashboardSerializer(serializers.Serializer):
    restaurant = DashboardRestaurantSerializer()
    unread_alerts_count = serializers.IntegerField()
    impact = DashboardImpactSerializer()
    today = DashboardTodaySerializer()
    this_week = DashboardWeekSerializer()
    active_donations = DashboardActiveDonationsSerializer()
    lives_impacted = serializers.IntegerField()
    donations_this_year = serializers.IntegerField()
    claim_rate_pct = serializers.IntegerField()
    active_count = serializers.IntegerField()
    claimed_today = serializers.IntegerField()
    today_listings = RestaurantDonationSerializer(many=True)


class RestaurantProfileSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    address = serializers.CharField()
    is_approved = serializers.BooleanField(required=False)
    initials = serializers.CharField(required=False)


class RestaurantProfileUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200, required=False)
    address = serializers.CharField(required=False)
    contact_name = serializers.CharField(max_length=100, required=False)
    contact_email = serializers.EmailField(required=False, allow_blank=True)
    contact_phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    opening_hours = serializers.CharField(required=False, allow_blank=True)
    about = serializers.CharField(required=False, allow_blank=True)
    photo_url = serializers.URLField(required=False, allow_blank=True)
    latitude = serializers.FloatField(min_value=-90, max_value=90, required=False)
    longitude = serializers.FloatField(min_value=-180, max_value=180, required=False)

    def validate(self, data):
        lat = data.get("latitude")
        lng = data.get("longitude")
        if (lat is None) != (lng is None):
            raise serializers.ValidationError(
                {"latitude": "latitude and longitude must be provided together."}
            )
        return data


class ApprovalStatusSerializer(serializers.Serializer):
    is_approved = serializers.BooleanField()
    is_verified = serializers.BooleanField()
    submitted_at = serializers.DateTimeField()
