from __future__ import annotations

import time
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import (
    DonorProfile,
    ReceiverDataExport,
    ReceiverLocationHistory,
    ReceiverProfile,
    RestaurantProfile,
    User,
)
from apps.claims.models import FoodClaim
from apps.common.choices import (
    ClaimStatus,
    CreditPreference,
    FoodCategory,
    FoodStatus,
    ListStatus,
    LocationPlaceType,
    MealOrderStatus,
    MoneyDonationStatus,
    SponsorshipType,
    UserRole,
)
from apps.donations.models import FoodItem, FoodReport, FoodReportReasonOption, MenuItem
from apps.donors.models import MealOrder, MealOrderItem, MoneyDonation
from apps.notifications.models import Notification, NotificationSettings

SEED_PHONES = {
    "admin": "+6590000001",
    "receiver_sarah": "+6591000001",
    "receiver_marcus": "+6591000002",
    "restaurant_tian_tian": "+6592000001",
    "restaurant_joo_chiat": "+6592000002",
    "donor_james": "+6593000001",
    "donor_emily": "+6593000002",
}

DEFAULT_ADMIN_PASSWORD = "PeonyAdmin123!"

REPORT_REASONS = [
    ("unsafe-or-spoiled", "Food was unsafe or spoiled", 1),
    ("misleading-listing", "Listing is misleading", 2),
    ("restaurant-closed", "Restaurant was closed or absent", 3),
    ("rude-behaviour", "Rude or inappropriate behaviour", 4),
    ("asked-to-pay", "Asked me to pay for the food", 5),
    ("other", "Something else", 6),
]

RESTAURANTS = [
    {
        "key": "tian_tian",
        "phone": SEED_PHONES["restaurant_tian_tian"],
        "name": "Tian Tian Hainanese",
        "uen": "2009000001A",
        "address": "443 Joo Chiat Rd, Singapore 427656",
        "postal_code": "427656",
        "latitude": 1.3140123,
        "longitude": 103.9010456,
        "contact_name": "Ah Meng",
        "contact_email": "contact@tiantian.sg",
    },
    {
        "key": "joo_chiat",
        "phone": SEED_PHONES["restaurant_joo_chiat"],
        "name": "Joo Chiat Kitchen",
        "uen": "2009000002B",
        "address": "12 East Coast Rd, Singapore 428718",
        "postal_code": "428718",
        "latitude": 1.3050789,
        "longitude": 103.9040321,
        "contact_name": "Siti Rahman",
        "contact_email": "hello@joochiat.sg",
    },
]


def _qr_data(food: FoodItem) -> str:
    return f"{food.id}|{food.restaurant_id}|{int(time.time())}"


class Command(BaseCommand):
    help = "Populate the database with dummy data for local testing across all modules."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Remove previously seeded users and their related data before seeding.",
        )
        parser.add_argument(
            "--clear-only",
            action="store_true",
            help="Remove seeded users and related data, then exit (no re-seed).",
        )
        parser.add_argument(
            "--password",
            default=DEFAULT_ADMIN_PASSWORD,
            help=f"Admin password (default: {DEFAULT_ADMIN_PASSWORD})",
        )

    def handle(self, *args, **options):
        if options["clear"] or options["clear_only"]:
            self._clear_seed_data()
            if options["clear_only"]:
                return

        with transaction.atomic():
            summary = self._seed_all(options["password"])

        self._print_summary(summary)

    def _clear_seed_data(self):
        phones = list(SEED_PHONES.values())
        deleted, breakdown = User.objects.filter(phone_e164__in=phones).delete()
        self.stdout.write(self.style.WARNING(f"Cleared {deleted} seeded object(s)."))
        if breakdown:
            self.stdout.write("Deleted:")
            for model_label, count in sorted(breakdown.items()):
                self.stdout.write(f"  {model_label}: {count}")
        self.stdout.write("Removed phones:")
        for phone in phones:
            self.stdout.write(f"  {phone}")

    def _seed_all(self, admin_password: str) -> dict:
        now = timezone.now()
        pickup_start = now
        pickup_end = now + timezone.timedelta(hours=3)
        past_pickup_end = now - timezone.timedelta(hours=1)

        self._seed_report_reasons()

        admin = self._get_or_create_admin(admin_password)
        sarah = self._get_or_create_receiver(
            SEED_PHONES["receiver_sarah"],
            "Sarah Mun",
            1.3135,
            103.9005,
        )
        marcus = self._get_or_create_receiver(
            SEED_PHONES["receiver_marcus"],
            "Marcus Tan",
            1.3048,
            103.9038,
        )
        restaurants = [self._get_or_create_restaurant(data) for data in RESTAURANTS]
        james = self._get_or_create_donor(
            SEED_PHONES["donor_james"],
            "James Tan",
            "james@example.com",
            CreditPreference.SHOW_NAME,
        )
        emily = self._get_or_create_donor(
            SEED_PHONES["donor_emily"],
            "Emily Koh",
            "emily@example.com",
            CreditPreference.ANONYMOUS,
        )

        menu_items = {}
        for restaurant in restaurants:
            menu_items[restaurant.id] = self._seed_menu_items(restaurant)

        foods = {}
        foods["tian_active"] = self._get_or_create_food(
            restaurants[0],
            "Chicken Rice (5 packs)",
            FoodCategory.RICE,
            quantity=5,
            pickup_start=pickup_start,
            pickup_end=pickup_end,
            list_status=ListStatus.ACTIVE,
        )
        foods["tian_partial"] = self._get_or_create_food(
            restaurants[0],
            "Laksa (3 packs)",
            FoodCategory.NOODLES,
            quantity=3,
            quantity_available=1,
            quantity_claimed=2,
            pickup_start=pickup_start,
            pickup_end=pickup_end,
            list_status=ListStatus.ACTIVE,
            status=FoodStatus.PARTIALLY_CLAIMED,
        )
        foods["joo_active"] = self._get_or_create_food(
            restaurants[1],
            "Nasi Lemak (4 packs)",
            FoodCategory.RICE,
            quantity=4,
            pickup_start=pickup_start,
            pickup_end=pickup_end,
            list_status=ListStatus.ACTIVE,
        )
        foods["joo_past"] = self._get_or_create_food(
            restaurants[1],
            "Curry Puff (2 packs)",
            FoodCategory.SNACKS,
            quantity=2,
            pickup_start=now - timezone.timedelta(hours=5),
            pickup_end=past_pickup_end,
            list_status=ListStatus.PAST,
            status=FoodStatus.EXPIRED,
        )

        sponsored_food = self._seed_sponsored_food(
            restaurants[0],
            james,
            menu_items[restaurants[0].id][0],
            pickup_start,
            pickup_end,
        )

        claim = self._get_or_create_claim(sarah, foods["tian_partial"], restaurants[0])

        self._seed_food_report(sarah, foods["tian_active"], restaurants[0])
        self._seed_location_history(sarah)
        self._seed_notifications(sarah, restaurants[0])
        self._seed_notification_settings(sarah.user)
        self._seed_notification_settings(marcus.user)
        self._seed_money_donations(james, emily)
        self._seed_data_export(sarah)

        restaurants[0].total_food_shared = 10
        restaurants[0].save(update_fields=["total_food_shared"])
        restaurants[1].total_food_shared = 6
        restaurants[1].save(update_fields=["total_food_shared"])

        return {
            "admin": admin,
            "receivers": [sarah, marcus],
            "restaurants": restaurants,
            "donors": [james, emily],
            "foods": foods,
            "sponsored_food": sponsored_food,
            "claim": claim,
            "admin_password": admin_password,
        }

    def _seed_report_reasons(self):
        for code, label, sort_order in REPORT_REASONS:
            FoodReportReasonOption.objects.get_or_create(
                code=code,
                defaults={"label": label, "sort_order": sort_order, "is_active": True},
            )

    def _get_or_create_admin(self, password: str) -> User:
        user, created = User.objects.get_or_create(
            phone_e164=SEED_PHONES["admin"],
            defaults={
                "role": UserRole.RECEIVER,
                "is_active": True,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created or not user.is_superuser:
            user.is_staff = True
            user.is_superuser = True
            user.is_active = True
            user.set_password(password)
            user.save()
        return user

    def _get_or_create_receiver(
        self,
        phone: str,
        display_name: str,
        latitude: float,
        longitude: float,
    ) -> ReceiverProfile:
        user, _ = User.objects.get_or_create(
            phone_e164=phone,
            defaults={"role": UserRole.RECEIVER, "is_active": True},
        )
        profile, _ = ReceiverProfile.objects.get_or_create(
            user=user,
            defaults={
                "display_name": display_name,
                "latitude": latitude,
                "longitude": longitude,
                "browse_radius_km": 5.0,
            },
        )
        if profile.display_name != display_name:
            profile.display_name = display_name
            profile.latitude = latitude
            profile.longitude = longitude
            profile.save(update_fields=["display_name", "latitude", "longitude"])
        return profile

    def _get_or_create_restaurant(self, data: dict) -> RestaurantProfile:
        user, _ = User.objects.get_or_create(
            phone_e164=data["phone"],
            defaults={"role": UserRole.RESTAURANT, "is_active": True},
        )
        profile, created = RestaurantProfile.objects.get_or_create(
            user=user,
            defaults={
                "name": data["name"],
                "uen": data["uen"],
                "address": data["address"],
                "postal_code": data["postal_code"],
                "latitude": data["latitude"],
                "longitude": data["longitude"],
                "contact_name": data["contact_name"],
                "contact_email": data["contact_email"],
                "contact_phone": data["phone"],
                "is_approved": True,
                "is_verified": True,
                "approved_at": timezone.now(),
            },
        )
        if not created:
            for field in (
                "name",
                "address",
                "postal_code",
                "latitude",
                "longitude",
                "contact_name",
                "contact_email",
                "contact_phone",
            ):
                setattr(profile, field, data.get(field, getattr(profile, field)))
            profile.is_approved = True
            profile.is_verified = True
            profile.save()
        return profile

    def _get_or_create_donor(
        self,
        phone: str,
        display_name: str,
        contact_email: str,
        credit_preference: str,
    ) -> DonorProfile:
        user, _ = User.objects.get_or_create(
            phone_e164=phone,
            defaults={"role": UserRole.DONOR, "is_active": True},
        )
        profile, _ = DonorProfile.objects.get_or_create(
            user=user,
            defaults={
                "display_name": display_name,
                "contact_email": contact_email,
                "credit_preference": credit_preference,
            },
        )
        return profile

    def _seed_menu_items(self, restaurant: RestaurantProfile) -> list[MenuItem]:
        items = [
            ("Chicken Rice", "1 pack", Decimal("5.50"), FoodCategory.RICE),
            ("Laksa", "1 bowl", Decimal("6.00"), FoodCategory.NOODLES),
            ("Ice Kachang", "1 cup", Decimal("3.50"), FoodCategory.DRINKS),
        ]
        created_items = []
        for index, (name, description, price, _category) in enumerate(items, start=1):
            item, _ = MenuItem.objects.get_or_create(
                restaurant=restaurant,
                name=name,
                defaults={
                    "description": description,
                    "price_sgd": price,
                    "is_available": True,
                    "sort_order": index,
                },
            )
            created_items.append(item)
        return created_items

    def _get_or_create_food(
        self,
        restaurant: RestaurantProfile,
        name: str,
        category: str,
        quantity: int,
        pickup_start,
        pickup_end,
        list_status: str = ListStatus.ACTIVE,
        status: str = FoodStatus.AVAILABLE,
        quantity_available: int | None = None,
        quantity_claimed: int = 0,
    ) -> FoodItem:
        available = quantity if quantity_available is None else quantity_available
        food, created = FoodItem.objects.get_or_create(
            restaurant=restaurant,
            name=name,
            defaults={
                "description": "Seeded test donation",
                "category": category,
                "unit": "pack",
                "quantity_original": quantity,
                "quantity_available": available,
                "quantity_claimed": quantity_claimed,
                "status": status,
                "list_status": list_status,
                "pickup_start": pickup_start,
                "pickup_end": pickup_end,
                "sponsorship_type": SponsorshipType.DIRECT,
            },
        )
        if not created:
            food.quantity_original = quantity
            food.quantity_available = available
            food.quantity_claimed = quantity_claimed
            food.status = status
            food.list_status = list_status
            food.pickup_start = pickup_start
            food.pickup_end = pickup_end
            food.save()

        if not food.food_qr_data:
            food.food_qr_data = _qr_data(food)
            food.save(update_fields=["food_qr_data"])
        return food

    def _seed_sponsored_food(
        self,
        restaurant: RestaurantProfile,
        donor: DonorProfile,
        menu_item: MenuItem,
        pickup_start,
        pickup_end,
    ) -> FoodItem:
        order, _ = MealOrder.objects.get_or_create(
            donor=donor,
            restaurant=restaurant,
            status=MealOrderStatus.POSTED,
            defaults={
                "total_amount_sgd": menu_item.price_sgd * 2,
                "credit_preference": donor.credit_preference,
            },
        )
        MealOrderItem.objects.get_or_create(
            meal_order=order,
            menu_item=menu_item,
            defaults={
                "quantity": 2,
                "unit_price_sgd": menu_item.price_sgd,
            },
        )

        food, created = FoodItem.objects.get_or_create(
            restaurant=restaurant,
            meal_order_id=order.id,
            defaults={
                "name": f"Sponsored: {menu_item.name} x2",
                "description": menu_item.description,
                "category": FoodCategory.OTHER,
                "unit": "pack",
                "quantity_original": 2,
                "quantity_available": 2,
                "quantity_claimed": 0,
                "status": FoodStatus.AVAILABLE,
                "list_status": ListStatus.ACTIVE,
                "pickup_start": pickup_start,
                "pickup_end": pickup_end,
                "sponsorship_type": SponsorshipType.SPONSORED_NAMED,
                "individual_donor": donor,
                "sponsor_display_name": donor.display_name,
            },
        )
        if created or not food.food_qr_data:
            food.food_qr_data = _qr_data(food)
            food.save(update_fields=["food_qr_data"])
        donor.total_meals_sponsored = 2
        donor.save(update_fields=["total_meals_sponsored"])
        return food

    def _get_or_create_claim(
        self,
        receiver: ReceiverProfile,
        food: FoodItem,
        restaurant: RestaurantProfile,
    ) -> FoodClaim:
        claim, created = FoodClaim.objects.get_or_create(
            food=food,
            receiver=receiver.user,
            defaults={
                "restaurant": restaurant,
                "claim_date": timezone.localdate(),
                "claimed_at": timezone.now() - timezone.timedelta(hours=1),
                "receiver_lat": receiver.latitude,
                "receiver_lng": receiver.longitude,
                "status": ClaimStatus.CLAIMED,
                "quantity_claimed": 1,
            },
        )
        if created:
            receiver.total_claims = FoodClaim.objects.filter(receiver=receiver.user).count()
            receiver.last_claim_date = timezone.localdate()
            receiver.save(update_fields=["total_claims", "last_claim_date"])
        return claim

    def _seed_food_report(
        self,
        receiver: ReceiverProfile,
        food: FoodItem,
        restaurant: RestaurantProfile,
    ):
        reason = FoodReportReasonOption.objects.get(code="misleading-listing")
        FoodReport.objects.get_or_create(
            reporter=receiver.user,
            food_item=food,
            defaults={
                "restaurant": restaurant,
                "reason_option": reason,
                "comment": "Seeded report for QA review.",
            },
        )

    def _seed_location_history(self, receiver: ReceiverProfile):
        ReceiverLocationHistory.objects.get_or_create(
            receiver=receiver.user,
            place_name="Joo Chiat Complex",
            visited_at=timezone.now() - timezone.timedelta(days=1),
            defaults={
                "area_label": "Joo Chiat, Singapore",
                "place_type": LocationPlaceType.FOOD_CENTRE,
                "latitude": 1.3142,
                "longitude": 103.9011,
            },
        )

    def _seed_notifications(self, receiver: ReceiverProfile, restaurant: RestaurantProfile):
        Notification.objects.get_or_create(
            user=receiver.user,
            type="NEW_FOOD_NEARBY",
            title="New food near you",
            defaults={
                "body": f"{restaurant.name} just posted chicken rice nearby.",
                "payload": {"restaurant_id": str(restaurant.id)},
            },
        )

    def _seed_notification_settings(self, user: User):
        NotificationSettings.objects.get_or_create(
            user=user,
            defaults={
                "push_enabled": True,
                "email_enabled": False,
                "alert_new_claim": True,
                "alert_sponsored": True,
            },
        )

    def _seed_money_donations(self, james: DonorProfile, emily: DonorProfile):
        pending, _ = MoneyDonation.objects.get_or_create(
            donor=emily,
            reference_code="SEED-PAYNOW-001",
            defaults={
                "amount_sgd": Decimal("25.00"),
                "is_anonymous": True,
                "status": MoneyDonationStatus.PENDING_TRANSFER,
            },
        )
        confirmed, created = MoneyDonation.objects.get_or_create(
            donor=james,
            reference_code="SEED-PAYNOW-002",
            defaults={
                "amount_sgd": Decimal("50.00"),
                "is_anonymous": False,
                "status": MoneyDonationStatus.CONFIRMED,
                "confirmed_at": timezone.now() - timezone.timedelta(days=2),
                "confirmed_by": "seed_data",
            },
        )
        if created:
            james.total_amount_donated_sgd = confirmed.amount_sgd
            james.save(update_fields=["total_amount_donated_sgd"])
        return pending, confirmed

    def _seed_data_export(self, receiver: ReceiverProfile):
        ReceiverDataExport.objects.get_or_create(
            user=receiver.user,
            phone_e164=receiver.user.phone_e164,
            status=ReceiverDataExport.Status.COMPLETED,
            defaults={
                "file_path": f"exports/receivers/{receiver.user.id}/seed-export.pdf",
                "completed_at": timezone.now() - timezone.timedelta(days=3),
            },
        )

    def _print_summary(self, summary: dict):
        self.stdout.write(self.style.SUCCESS("\nSeed data ready.\n"))
        self.stdout.write("Test accounts (OTP login in dev — check container logs for code):\n")
        rows = [
            ("Admin (Django /admin/)", SEED_PHONES["admin"], f"password: {summary['admin_password']}"),
            ("Receiver", SEED_PHONES["receiver_sarah"], "Sarah Mun — browse & claim"),
            ("Receiver", SEED_PHONES["receiver_marcus"], "Marcus Tan — second tester"),
            ("Restaurant", SEED_PHONES["restaurant_tian_tian"], RESTAURANTS[0]["name"]),
            ("Restaurant", SEED_PHONES["restaurant_joo_chiat"], RESTAURANTS[1]["name"]),
            ("Donor", SEED_PHONES["donor_james"], "James Tan — meal sponsor"),
            ("Donor", SEED_PHONES["donor_emily"], "Emily Koh — pending PayNow"),
        ]
        for role, phone, note in rows:
            self.stdout.write(f"  {role:<24} {phone}  ({note})")

        self.stdout.write("\nSeeded modules:")
        self.stdout.write("  users, receiver profiles, restaurant profiles, donor profiles")
        self.stdout.write("  menu items, food donations (active/past/sponsored)")
        self.stdout.write("  food claims, food reports, report reasons")
        self.stdout.write("  meal orders, money donations, notifications, location history")
        self.stdout.write("  receiver data export")
        self.stdout.write(
            "\nRe-run safely:  python manage.py seed_data"
            "\nReset first:    python manage.py seed_data --clear"
            "\nDelete only:    python manage.py seed_data --clear-only\n"
        )
