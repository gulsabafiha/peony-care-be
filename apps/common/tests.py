from django.test import Client, SimpleTestCase


class HealthCheckTests(SimpleTestCase):
    def test_health_endpoint_returns_success(self):
        response = Client().get("/health/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "success")
        self.assertTrue(payload["data"]["healthy"])
