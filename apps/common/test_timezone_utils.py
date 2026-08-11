from datetime import datetime, timezone

from django.test import SimpleTestCase

from apps.common.timezone_utils import (
    BDT,
    SGT,
    format_pickup_window,
    timezone_for_postal_code,
    to_local_iso,
)


class TimezoneUtilsTests(SimpleTestCase):
    def test_postal_code_maps_to_country_timezone(self):
        self.assertEqual(timezone_for_postal_code("1205"), BDT)
        self.assertEqual(timezone_for_postal_code("427656"), SGT)
        self.assertEqual(timezone_for_postal_code(""), SGT)

    def test_bangladesh_donation_pickup_keeps_same_instant_in_local_tz(self):
        start = datetime(2026, 8, 11, 19, 8, 11, 945000, tzinfo=timezone.utc)
        end = datetime(2026, 8, 12, 19, 8, 11, 945000, tzinfo=timezone.utc)

        self.assertEqual(to_local_iso(start, BDT), "2026-08-12T01:08:11.945000+06:00")
        self.assertEqual(to_local_iso(end, BDT), "2026-08-13T01:08:11.945000+06:00")
        # Must not render as Singapore (+08).
        self.assertNotIn("+08:00", to_local_iso(start, BDT))

    def test_singapore_donation_pickup_uses_sgt(self):
        start = datetime(2026, 8, 11, 19, 8, 11, 945000, tzinfo=timezone.utc)
        self.assertEqual(to_local_iso(start, SGT), "2026-08-12T03:08:11.945000+08:00")

    def test_pickup_window_includes_dates_when_spanning_days(self):
        start = datetime(2026, 8, 11, 19, 8, 11, 945000, tzinfo=timezone.utc)
        end = datetime(2026, 8, 12, 19, 8, 11, 945000, tzinfo=timezone.utc)
        window = format_pickup_window(start, end, tz=BDT)
        self.assertIn("1:08 AM", window)
        self.assertIn("Thu, 13 Aug", window)
        # Start day may show as "Today" when the test runs on that local date.
        self.assertTrue("Today" in window or "Wed, 12 Aug" in window)
