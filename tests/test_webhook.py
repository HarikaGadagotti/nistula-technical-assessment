import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from main import app


def _mock(text):
    m = MagicMock()
    m.content = [MagicMock(text=text)]
    m.usage = MagicMock(output_tokens=75)
    m.stop_reason = "end_turn"
    return m

AVAIL_REPLY = (
    "Hi Rahul! Villa B1 is available April 20–24. The rate is INR 18,000 per night "
    "for up to 4 guests — INR 72,000 total for 4 nights. Free cancellation up to 7 days "
    "before. Want me to hold the dates?"
)


@pytest.mark.asyncio
async def test_availability():
    payload = {
        "source": "whatsapp", "guest_name": "Rahul Sharma",
        "message": "Is the villa available from April 20 to 24? Rate for 2 adults?",
        "timestamp": "2026-05-05T10:30:00Z",
        "booking_ref": "NIS-2024-0891", "property_id": "villa-b1",
    }
    with patch("main.client.messages.create", return_value=_mock(AVAIL_REPLY)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.post("/webhook/message", json=payload)
    assert r.status_code == 200
    d = r.json()
    assert d["query_type"] == "pre_sales_availability"
    assert 0 <= d["confidence_score"] <= 1
    print(f"\n✅ availability | confidence={d['confidence_score']} | action={d['action']}")


@pytest.mark.asyncio
async def test_complaint_always_escalates():
    payload = {
        "source": "direct", "guest_name": "Priya Mehta",
        "message": "No hot water at 3am. This is unacceptable. I want a refund.",
        "timestamp": "2026-05-06T03:00:00Z",
        "booking_ref": "NIS-2024-0444", "property_id": "villa-b1",
    }
    reply = "Hi Priya, we sincerely apologise. The caretaker has been alerted right now."
    with patch("main.client.messages.create", return_value=_mock(reply)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.post("/webhook/message", json=payload)
    assert r.status_code == 200
    assert r.json()["action"] == "escalate"
    print(f"\n✅ complaint → escalate (forced)")


@pytest.mark.asyncio
async def test_checkin_query():
    payload = {
        "source": "booking_com", "guest_name": "Anil Kumar",
        "message": "What time is check-in and what is the WiFi password?",
        "timestamp": "2026-05-07T09:00:00Z",
        "booking_ref": "NIS-2024-0512", "property_id": "villa-b1",
    }
    reply = "Hi Anil! Check-in is at 2 PM. The WiFi password is Nistula@2024. See you soon!"
    with patch("main.client.messages.create", return_value=_mock(reply)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.post("/webhook/message", json=payload)
    assert r.status_code == 200
    assert r.json()["query_type"] == "post_sales_checkin"
    print(f"\n✅ checkin query passed")


@pytest.mark.asyncio
async def test_special_request():
    payload = {
        "source": "airbnb", "guest_name": "Sophie Martin",
        "message": "Can you arrange an airport transfer on April 20?",
        "timestamp": "2026-05-08T14:00:00Z", "property_id": "villa-b1",
    }
    reply = "Hi Sophie! We can arrange a transfer. Our team will confirm details within a few hours."
    with patch("main.client.messages.create", return_value=_mock(reply)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.post("/webhook/message", json=payload)
    assert r.status_code == 200
    assert r.json()["query_type"] == "special_request"
    print(f"\n✅ special request passed")


@pytest.mark.asyncio
async def test_invalid_source_rejected():
    payload = {
        "source": "telegram", "guest_name": "Test User",
        "message": "Hello?", "timestamp": "2026-05-09T12:00:00Z",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post("/webhook/message", json=payload)
    assert r.status_code == 422
    print(f"\n✅ invalid source correctly rejected")


@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/health")
    assert r.status_code == 200
    print(f"\n✅ health check ok")