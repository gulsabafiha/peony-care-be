from rest_framework import serializers

from apps.common.choices import FoodCategory, RecurrenceType


class CreateDonationSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True)
    category = serializers.ChoiceField(choices=FoodCategory.choices)
    unit = serializers.CharField(max_length=20, required=False, default="packs")
    photo_url = serializers.URLField(required=False, allow_blank=True, default="")
    photo = serializers.FileField(required=False)
    quantity = serializers.IntegerField(min_value=1)
    pickup_start = serializers.DateTimeField()
    pickup_end = serializers.DateTimeField()
    recurrence_type = serializers.ChoiceField(
        choices=RecurrenceType.choices,
        required=False,
        default=RecurrenceType.NONE,
    )
    # UI schedule aliases: one-time | every_day | custom_days
    schedule = serializers.ChoiceField(
        choices=["one-time", "every_day", "custom_days", "ONE_TIME", "EVERY_DAY", "CUSTOM_DAYS"],
        required=False,
    )
    recurrence_days = serializers.ListField(
        child=serializers.IntegerField(min_value=0, max_value=6),
        required=False,
        default=list,
    )
    source_note = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, data):
        if data.get("notes") and not data.get("description"):
            data["description"] = data["notes"]

        schedule = data.pop("schedule", None)
        if schedule:
            normalized = schedule.lower().replace("-", "_")
            mapping = {
                "one_time": RecurrenceType.NONE,
                "every_day": RecurrenceType.DAILY,
                "custom_days": RecurrenceType.CUSTOM,
            }
            if normalized not in mapping:
                raise serializers.ValidationError(
                    {"schedule": "Must be one-time, every_day, or custom_days."}
                )
            data["recurrence_type"] = mapping[normalized]

        if data["pickup_end"] <= data["pickup_start"]:
            raise serializers.ValidationError(
                {"pickup_end": "Pickup end must be after pickup start."}
            )
        return data


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
    source_note = serializers.CharField(required=False, allow_blank=True)


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


class RestaurantProfileHubSerializer(serializers.Serializer):
    people_fed = serializers.IntegerField()
    people_fed_label = serializers.CharField()
    donations_count = serializers.IntegerField(required=False)
    donations_label = serializers.CharField(required=False)
    claim_rate_pct = serializers.IntegerField(allow_null=True)
    claim_rate_display = serializers.CharField()
    claim_rate_label = serializers.CharField()
    rating = serializers.FloatField(allow_null=True)
    rating_display = serializers.CharField()
    review_count = serializers.IntegerField()
    reviews_label = serializers.CharField()
    reviews_available = serializers.BooleanField()


class RestaurantProfileSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    address = serializers.CharField()
    area_label = serializers.CharField(allow_null=True, required=False)
    cuisine = serializers.CharField(required=False, allow_blank=True)
    opening_hours = serializers.CharField(required=False, allow_blank=True)
    opens_at = serializers.TimeField(allow_null=True, required=False)
    closes_at = serializers.TimeField(allow_null=True, required=False)
    open_days = serializers.ListField(child=serializers.IntegerField(), required=False)
    is_approved = serializers.BooleanField(required=False)
    is_verified = serializers.BooleanField(required=False)
    verified_label = serializers.CharField(allow_null=True, required=False)
    initials = serializers.CharField(required=False)
    uen = serializers.CharField(required=False)
    uen_verified = serializers.BooleanField(required=False)
    photo_url = serializers.CharField(allow_null=True, required=False)
    member_since = serializers.CharField(required=False)
    hub = RestaurantProfileHubSerializer(required=False)
    people_fed = serializers.IntegerField(required=False)
    donations_count = serializers.IntegerField(required=False)
    claim_rate_pct = serializers.IntegerField(allow_null=True, required=False)
    claim_rate_display = serializers.CharField(required=False)
    rating = serializers.FloatField(allow_null=True, required=False)
    rating_display = serializers.CharField(required=False)
    review_count = serializers.IntegerField(required=False)
    impact = serializers.DictField(required=False)
    available_meals = serializers.ListField(required=False)
    active_meal_count = serializers.IntegerField(required=False)
    contact_phone = serializers.CharField(required=False, allow_blank=True)


class RestaurantProfileUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200, required=False)
    address = serializers.CharField(required=False)
    contact_name = serializers.CharField(max_length=100, required=False)
    contact_email = serializers.EmailField(required=False, allow_blank=True)
    contact_phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    cuisine = serializers.CharField(max_length=200, required=False, allow_blank=True)
    opening_hours = serializers.CharField(required=False, allow_blank=True)
    opens_at = serializers.TimeField(required=False, allow_null=True)
    closes_at = serializers.TimeField(required=False, allow_null=True)
    open_days = serializers.ListField(
        child=serializers.IntegerField(min_value=0, max_value=6),
        required=False,
    )
    about = serializers.CharField(required=False, allow_blank=True)
    photo_url = serializers.URLField(required=False, allow_blank=True)
    photo = serializers.FileField(required=False)
    remove_photo = serializers.BooleanField(required=False, default=False)
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


class MenuPhotoSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    photo_url = serializers.CharField()
    sort_order = serializers.IntegerField()
    position = serializers.IntegerField()
    created_at = serializers.DateTimeField()


class MenuPhotoDonorPreviewSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    photos = MenuPhotoSerializer(many=True)


class MenuPhotoListSerializer(serializers.Serializer):
    max_photos = serializers.IntegerField()
    uploaded_count = serializers.IntegerField()
    slots_left = serializers.IntegerField()
    is_empty = serializers.BooleanField()
    photos = MenuPhotoSerializer(many=True)
    donor_preview = MenuPhotoDonorPreviewSerializer()
    reorder_hint = serializers.CharField()
    counter_label = serializers.CharField()
    add_slot_label = serializers.CharField(allow_null=True)


class MenuPhotoUploadSerializer(serializers.Serializer):
    photo = serializers.FileField(required=False)
    photos = serializers.ListField(child=serializers.FileField(), required=False)

    def validate(self, data):
        files = []
        if data.get("photo") is not None:
            files.append(data["photo"])
        files.extend(data.get("photos") or [])
        if not files:
            raise serializers.ValidationError(
                {"photo": "Provide photo or photos (image file upload)."}
            )
        data["files"] = files
        return data


class MenuPhotoReorderSerializer(serializers.Serializer):
    photo_ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=False,
    )


class LocationSearchQuerySerializer(serializers.Serializer):
    q = serializers.CharField(min_length=2, max_length=200)


class LocationResultSerializer(serializers.Serializer):
    address_line = serializers.CharField()
    address = serializers.CharField()
    postal_code = serializers.CharField(allow_blank=True)
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    country = serializers.CharField(required=False, allow_blank=True)
    subtitle = serializers.CharField(required=False)
    display = serializers.CharField(required=False)
    snapped = serializers.BooleanField(required=False)
    distance_m = serializers.IntegerField(allow_null=True, required=False)


class LocationSearchResponseSerializer(serializers.Serializer):
    query = serializers.CharField()
    count = serializers.IntegerField()
    results = LocationResultSerializer(many=True)


class LocationReverseQuerySerializer(serializers.Serializer):
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lng = serializers.FloatField(min_value=-180, max_value=180)


class LocationConfirmSerializer(serializers.Serializer):
    address = serializers.CharField()
    address_line = serializers.CharField(required=False, allow_blank=True)
    postal_code = serializers.CharField(required=False, allow_blank=True)
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)


class AnalyticsRangeQuerySerializer(serializers.Serializer):
    range = serializers.ChoiceField(
        choices=["7D", "30D", "3M", "1Y", "ALL"],
        required=False,
        default="30D",
    )


class AnalyticsImpactSerializer(serializers.Serializer):
    people_fed = serializers.IntegerField()
    people_fed_label = serializers.CharField()
    donations_posted = serializers.IntegerField()
    donations_label = serializers.CharField()
    claim_rate_pct = serializers.IntegerField(allow_null=True)
    claim_rate_label = serializers.CharField()
    claim_rate_display = serializers.CharField()
    sponsored_sgd = serializers.CharField()
    sponsored_display = serializers.CharField()
    sponsored_label = serializers.CharField()


class AnalyticsWeekSerializer(serializers.Serializer):
    week = serializers.CharField()
    week_start = serializers.CharField()
    week_end = serializers.CharField()
    meals = serializers.IntegerField(required=False)
    claim_rate_pct = serializers.IntegerField(required=False)


class AnalyticsMealsPerWeekSerializer(serializers.Serializer):
    title = serializers.CharField()
    total = serializers.IntegerField(required=False)
    weeks = AnalyticsWeekSerializer(many=True)
    has_data = serializers.BooleanField()
    caption = serializers.CharField(allow_null=True)


class AnalyticsEmptyStateSerializer(serializers.Serializer):
    title = serializers.CharField()
    subtitle = serializers.CharField()
    cta_label = serializers.CharField()


class AnalyticsTotalImpactSerializer(serializers.Serializer):
    lives_fed = serializers.IntegerField()
    donations = serializers.IntegerField()
    claim_rate_pct = serializers.IntegerField()
    subtitle = serializers.CharField()
    week_over_week_pct = serializers.IntegerField()
    week_over_week_label = serializers.CharField()


class AnalyticsDonationSourceSerializer(serializers.Serializer):
    total = serializers.IntegerField()


class AnalyticsDishSerializer(serializers.Serializer):
    name = serializers.CharField()
    photo_url = serializers.CharField(allow_null=True)
    meals = serializers.IntegerField()
    claim_rate_pct = serializers.IntegerField()
    detail = serializers.CharField()


class AnalyticsSponsorSerializer(serializers.Serializer):
    display_name = serializers.CharField()
    initials = serializers.CharField(allow_blank=True)
    is_anonymous = serializers.BooleanField()
    photo_url = serializers.CharField(allow_null=True, required=False)
    sponsored_count = serializers.IntegerField()
    amount_sgd = serializers.CharField()
    amount_display = serializers.CharField()
    detail = serializers.CharField()


class AnalyticsSerializer(serializers.Serializer):
    is_empty = serializers.BooleanField()
    selected_range = serializers.CharField()
    range_options = serializers.ListField(child=serializers.CharField())
    empty_state = AnalyticsEmptyStateSerializer(allow_null=True)
    total_impact = AnalyticsTotalImpactSerializer()
    impact = AnalyticsImpactSerializer()
    meals_donated = AnalyticsMealsPerWeekSerializer()
    claim_rate_trend = serializers.DictField()
    donation_source = AnalyticsDonationSourceSerializer()
    claim_activity_heatmap = serializers.DictField()
    quick_stats = serializers.DictField()
    most_claimed_dishes = AnalyticsDishSerializer(many=True)
    sponsors = AnalyticsSponsorSerializer(many=True)
    meals_per_week = AnalyticsMealsPerWeekSerializer()
