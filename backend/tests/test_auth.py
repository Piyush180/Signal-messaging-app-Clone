import pytest

from tests.conftest import register


async def test_request_and_verify_otp_registers_user(client):
    r = await client.post("/api/v1/auth/request-otp", json={"phone_number": "+15551110000"})
    assert r.status_code == 200
    assert r.json()["otp_demo"] == "123456"

    session = await register(client, "+15551110000", "Test User")
    me = await client.get("/api/v1/auth/me", headers=session["headers"])
    assert me.status_code == 200
    assert me.json()["phone_number"] == "+15551110000"


async def test_verify_without_requesting_is_rejected(client):
    # The universal "123456 always works" bypass is gone: you must have an
    # outstanding, unexpired OTP row for that number.
    r = await client.post(
        "/api/v1/auth/verify-otp",
        json={"phone_number": "+15559990000", "code": "123456"},
    )
    assert r.status_code == 400


async def test_protected_route_requires_token(client):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 401
