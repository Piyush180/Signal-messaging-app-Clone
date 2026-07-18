import pytest

from tests.conftest import register


async def _direct_conv(client, a, b_user_id):
    r = await client.post(
        "/api/v1/conversations/direct",
        headers=a["headers"],
        json={"contact_user_id": b_user_id},
    )
    assert r.status_code == 200
    return r.json()["id"]


async def test_pagination_returns_newest_and_walks_back(client):
    alice = await register(client, "+15551112222", "Alice")
    bob = await register(client, "+15553334444", "Bob")
    conv_id = await _direct_conv(client, alice, bob["user"]["id"])

    for i in range(25):
        await client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            headers=alice["headers"],
            json={"content": f"msg {i}"},
        )

    # First page = the NEWEST 10, in chronological order.
    r = await client.get(
        f"/api/v1/conversations/{conv_id}/messages?limit=10", headers=bob["headers"]
    )
    page = r.json()
    assert page["has_more"] is True
    assert [m["content"] for m in page["messages"]][-1] == "msg 24"

    # Older page via the cursor.
    r2 = await client.get(
        f"/api/v1/conversations/{conv_id}/messages?limit=10&before_id={page['next_cursor']}",
        headers=bob["headers"],
    )
    assert r2.json()["messages"][-1]["content"] == "msg 14"


async def test_unread_and_read_receipt_are_per_user(client):
    alice = await register(client, "+15551113333", "Alice")
    bob = await register(client, "+15553335555", "Bob")
    conv_id = await _direct_conv(client, alice, bob["user"]["id"])

    await client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        headers=alice["headers"],
        json={"content": "hello bob"},
    )

    # Bob has 1 unread; Alice (the sender) has 0.
    convs_bob = (await client.get("/api/v1/conversations", headers=bob["headers"])).json()
    convs_alice = (await client.get("/api/v1/conversations", headers=alice["headers"])).json()
    assert convs_bob[0]["unread_count"] == 1
    assert convs_alice[0]["unread_count"] == 0


async def test_reply_quotes_original_message(client):
    alice = await register(client, "+15551117777", "Alice")
    bob = await register(client, "+15553337777", "Bob")
    conv_id = await _direct_conv(client, alice, bob["user"]["id"])

    r = await client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        headers=alice["headers"],
        json={"content": "original"},
    )
    original_id = r.json()["id"]

    r = await client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        headers=bob["headers"],
        json={"content": "a reply", "reply_to_id": original_id},
    )
    assert r.status_code == 200
    quote = r.json()["reply_to"]
    assert quote["id"] == original_id
    assert quote["content"] == "original"
    assert quote["sender_name"] == "Alice"

    # The quote must also come back through history (eager-loaded, not lazy).
    r = await client.get(
        f"/api/v1/conversations/{conv_id}/messages", headers=alice["headers"]
    )
    replies = [m for m in r.json()["messages"] if m["reply_to"]]
    assert len(replies) == 1
    assert replies[0]["reply_to"]["id"] == original_id


async def test_reply_rejects_message_from_another_conversation(client):
    alice = await register(client, "+15551118888", "Alice")
    bob = await register(client, "+15553338888", "Bob")
    eve = await register(client, "+15555558888", "Eve")
    conv_ab = await _direct_conv(client, alice, bob["user"]["id"])
    conv_ae = await _direct_conv(client, alice, eve["user"]["id"])

    r = await client.post(
        f"/api/v1/conversations/{conv_ae}/messages",
        headers=alice["headers"],
        json={"content": "secret"},
    )
    foreign_id = r.json()["id"]

    # Bob tries to quote a message from a conversation he is not part of.
    r = await client.post(
        f"/api/v1/conversations/{conv_ab}/messages",
        headers=bob["headers"],
        json={"content": "sneaky quote", "reply_to_id": foreign_id},
    )
    assert r.status_code == 400
