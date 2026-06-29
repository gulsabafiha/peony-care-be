from django.db import models


class UserRole(models.TextChoices):
    RECEIVER = "RECEIVER", "Receiver"
    RESTAURANT = "RESTAURANT", "Restaurant"
    DONOR = "DONOR", "Donor"


class OtpPurpose(models.TextChoices):
    REGISTER = "REGISTER", "Register"
    LOGIN = "LOGIN", "Login"


class FoodCategory(models.TextChoices):
    RICE = "RICE", "Rice"
    NOODLES = "NOODLES", "Noodles"
    BREAD = "BREAD", "Bread"
    SNACKS = "SNACKS", "Snacks"
    DRINKS = "DRINKS", "Drinks"
    OTHER = "OTHER", "Other"


class FoodStatus(models.TextChoices):
    AVAILABLE = "AVAILABLE", "Available"
    PARTIALLY_CLAIMED = "PARTIALLY_CLAIMED", "Partially Claimed"
    FULLY_CLAIMED = "FULLY_CLAIMED", "Fully Claimed"
    EXPIRED = "EXPIRED", "Expired"


class ListStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    PAST = "PAST", "Past"
    INACTIVE = "INACTIVE", "Inactive"


class SponsorshipType(models.TextChoices):
    DIRECT = "DIRECT", "Direct"
    SPONSORED_NAMED = "SPONSORED_NAMED", "Sponsored Named"
    SPONSORED_ANONYMOUS = "SPONSORED_ANONYMOUS", "Sponsored Anonymous"


class ClaimStatus(models.TextChoices):
    CLAIMED = "CLAIMED", "Claimed"


class CreditPreference(models.TextChoices):
    SHOW_NAME = "SHOW_NAME", "Show Name"
    INITIALS = "INITIALS", "Initials"
    ANONYMOUS = "ANONYMOUS", "Anonymous"


class MealOrderStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    PAID = "PAID", "Paid"
    POSTED = "POSTED", "Posted"
    CANCELLED = "CANCELLED", "Cancelled"


class MoneyDonationStatus(models.TextChoices):
    PENDING_TRANSFER = "PENDING_TRANSFER", "Pending Transfer"
    CONFIRMED = "CONFIRMED", "Confirmed"
    REJECTED = "REJECTED", "Rejected"


class ClosedReason(models.TextChoices):
    MANUAL = "MANUAL", "Manual"
    EXPIRED = "EXPIRED", "Expired"
    FULLY_CLAIMED = "FULLY_CLAIMED", "Fully Claimed"


class LocationPlaceType(models.TextChoices):
    FOOD_CENTRE = "FOOD_CENTRE", "Food centre"
    RESTAURANT = "RESTAURANT", "Restaurant"
    SHOPPING = "SHOPPING", "Shopping"
    TRANSIT = "TRANSIT", "Transit"
    PARK = "PARK", "Park"
    OTHER = "OTHER", "Other"
 