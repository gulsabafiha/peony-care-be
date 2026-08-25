from django.urls import reverse


def test_privacy_page(client):
    response = client.get(reverse("privacy-policy"))
    assert response.status_code == 200
    assert b"Privacy Policy" in response.content
    assert b"Udufood" in response.content
    assert b"Receivers" in response.content
    assert b"Restaurant partners" in response.content


def test_terms_page(client):
    response = client.get(reverse("terms-of-service"))
    assert response.status_code == 200
    assert b"Terms of Use" in response.content
    assert b"Udufood" in response.content
    assert b"Restaurant partners" in response.content


def test_delete_account_page(client):
    response = client.get(reverse("delete-account"))
    assert response.status_code == 200
    assert b"Delete your Udufood account" in response.content
    assert b"support@udufood.com" in response.content
    assert b"What we delete" in response.content
    assert b"30 days" in response.content
    assert b"Delete some data, keep your account" in response.content
