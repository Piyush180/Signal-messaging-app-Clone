import pytest

from tests.conftest import register


async def test_group_admin_can_add_and_remove_but_member_cannot(client):
    alice = await register(client, "+15551114444", "Alice")  # creator/admin
    bob = await register(client, "+15553336666", "Bob")
    charlie = await register(client, "+15557778888", "Charlie")

    r = await client.post(
        "/api/v1/conversations/group",
        headers=alice["headers"],
        json={"name": "Team", "member_user_ids": [bob["user"]["id"]]},
    )
    assert r.status_code == 200
    conv = r.json()
    conv_id = conv["id"]
    assert len(conv["members"]) == 2

    # Admin (Alice) adds Charlie.
    r = await client.post(
        f"/api/v1/groups/{conv_id}/members",
        headers=alice["headers"],
        json={"user_ids": [charlie["user"]["id"]]},
    )
    assert r.status_code == 200
    assert len(r.json()["members"]) == 3

    # Non-admin (Bob) cannot remove anyone.
    r = await client.delete(
        f"/api/v1/groups/{conv_id}/members/{charlie['user']['id']}",
        headers=bob["headers"],
    )
    assert r.status_code == 403

    # Admin can remove.
    r = await client.delete(
        f"/api/v1/groups/{conv_id}/members/{charlie['user']['id']}",
        headers=alice["headers"],
    )
    assert r.status_code == 200
    assert len(r.json()["members"]) == 2
