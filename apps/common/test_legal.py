from django.urls import reverse


def test_privacy_page(client):
    response = client.get(reverse("privacy-policy"))
    assert response.status_code == 200
    assert b"Privacy Policy" in response.content
    assert b"UDUFood" in response.content
    assert b"Receivers" in response.content
    assert b"Restaurant partners" in response.content


def test_terms_page(client):
    response = client.get(reverse("terms-of-service"))
    assert response.status_code == 200
    assert b"Terms of Use" in response.content
    assert b"UDUFood" in response.content
    assert b"Restaurant partners" in response.content
