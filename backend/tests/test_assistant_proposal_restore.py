from datetime import UTC, datetime, timedelta

import pytest

from app.api.deps import get_or_create_user
from app.database.models import AssistantActionProposal, Commitment, ConversationMessage, ConversationThread, Event
from tests.conftest import AUTH_HEADERS


def propose(client):
    response = client.post("/api/v1/assistant/message", headers=AUTH_HEADERS, json={
        "message": "Meeting friend at university tomorrow at 11 for 5h",
        "now": "2026-10-03T08:00:00Z", "timezone": "UTC",
    })
    assert response.status_code == 200
    result = response.json()
    assert result["response_type"] == "PROPOSAL"
    return result


def restored_action(client, result):
    response = client.get(f"/api/v1/assistant/threads/{result['thread_id']}", headers=AUTH_HEADERS)
    assert response.status_code == 200
    message = next(row for row in response.json()["messages"] if row["id"] == result["assistant_message_id"])
    return message["metadata_json"]["proposed_action"]


def test_pending_proposal_survives_reload_without_applying_or_changing_world(client, db_session):
    result = propose(client)
    proposal = result["proposed_action"]
    message = db_session.get(ConversationMessage, result["assistant_message_id"])
    assert message.metadata_json["proposal_id"] == proposal["id"]
    assert "proposed_action" not in message.metadata_json
    user = get_or_create_user(db_session)
    revision, events = user.world_revision, db_session.query(Event).count()
    db_session.expire_all()

    assert restored_action(client, result) == {**proposal, "thread_id": result["thread_id"]}
    assert db_session.query(Commitment).count() == 0
    assert user.world_revision == revision
    assert db_session.query(Event).count() == events


@pytest.mark.parametrize("command,expected_status,entity_count", [
    ("confirm", "confirmed", 1), ("cancel", "cancelled", 0),
])
def test_restored_card_uses_current_canonical_status(client, db_session, command, expected_status, entity_count):
    result = propose(client)
    proposal_id = result["proposed_action"]["id"]
    response = client.post(f"/api/v1/assistant/proposals/{proposal_id}/{command}", headers=AUTH_HEADERS)
    assert response.status_code == 200
    action = restored_action(client, result)
    assert action["status"] == expected_status
    assert action["version"] > result["proposed_action"]["version"]
    assert db_session.query(Commitment).count() == entity_count


def test_expired_card_projects_expiry_without_mutating_proposal_or_approving(client, db_session):
    result = propose(client)
    proposal = db_session.get(AssistantActionProposal, result["proposed_action"]["id"])
    proposal.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db_session.commit()
    version = proposal.version
    assert restored_action(client, result)["status"] == "expired"
    db_session.refresh(proposal)
    assert proposal.status == "pending" and proposal.version == version
    confirmed = client.post(f"/api/v1/assistant/proposals/{proposal.id}/confirm", headers=AUTH_HEADERS).json()
    assert confirmed["error_code"] == "proposal_expired"
    assert db_session.query(Commitment).count() == 0


def test_restoring_does_not_refresh_a_stale_proposals_expected_world_revision(client, db_session):
    result = propose(client)
    original = result["proposed_action"]
    client.post("/api/v1/state/observations", headers=AUTH_HEADERS, json={"energy": 70, "mental_state": 70})
    assert restored_action(client, result)["expected_world_revision"] == original["expected_world_revision"]
    response = client.post(f"/api/v1/assistant/proposals/{original['id']}/confirm", headers=AUTH_HEADERS).json()
    assert response["error_code"] == "stale_proposal"
    assert db_session.query(Commitment).count() == 0


def test_thread_restoration_requires_authentication_and_does_not_disclose_foreign_proposals(client, db_session):
    result = propose(client)
    assert client.get(f"/api/v1/assistant/threads/{result['thread_id']}").status_code == 401
    other = get_or_create_user(db_session, email="other@example.local", auth_subject="other")
    foreign = AssistantActionProposal(
        user_id=other.id, tool_name="create_commitment", summary="Private proposal",
        arguments_json={"title": "Private meeting"}, expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    thread = ConversationThread(user_id=other.id, title="Private thread", last_message_at=datetime.now(UTC))
    db_session.add_all([foreign, thread])
    db_session.flush()
    assert client.get(f"/api/v1/assistant/threads/{thread.id}", headers=AUTH_HEADERS).status_code == 404

    own_message = db_session.get(ConversationMessage, result["assistant_message_id"])
    own_message.metadata_json = {**own_message.metadata_json, "proposal_id": foreign.id}
    db_session.commit()
    response = client.get(f"/api/v1/assistant/threads/{result['thread_id']}", headers=AUTH_HEADERS)
    metadata = next(row for row in response.json()["messages"] if row["id"] == own_message.id)["metadata_json"]
    assert "proposed_action" not in metadata


def test_legacy_message_without_proposal_reference_remains_readable(client, db_session):
    result = propose(client)
    message = db_session.get(ConversationMessage, result["assistant_message_id"])
    metadata = dict(message.metadata_json)
    metadata.pop("proposal_id")
    message.metadata_json = metadata
    db_session.commit()
    response = client.get(f"/api/v1/assistant/threads/{result['thread_id']}", headers=AUTH_HEADERS)
    restored = next(row for row in response.json()["messages"] if row["id"] == message.id)
    assert "proposed_action" not in restored["metadata_json"]
    assert restored["content"] == message.content


def test_pending_proposal_feed_is_owned_read_only_and_updates_after_confirmation(client, db_session):
    result = propose(client)
    proposal = result["proposed_action"]
    endpoint = "/api/v1/assistant/proposals/pending"
    assert client.get(endpoint).status_code == 401
    before = db_session.query(Commitment).count()
    response = client.get(endpoint, headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [proposal["id"]]
    assert response.json()[0]["thread_id"] == result["thread_id"]
    assert db_session.query(Commitment).count() == before

    client.post(f"/api/v1/assistant/proposals/{proposal['id']}/confirm", headers=AUTH_HEADERS)
    assert client.get(endpoint, headers=AUTH_HEADERS).json() == []


def test_decline_after_confirmation_reports_the_saved_change_truthfully(client, db_session):
    result = propose(client)
    proposal_id = result["proposed_action"]["id"]
    client.post(f"/api/v1/assistant/proposals/{proposal_id}/confirm", headers=AUTH_HEADERS)
    response = client.post(f"/api/v1/assistant/proposals/{proposal_id}/cancel", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert "already confirmed" in response.json()["message"]
    assert db_session.query(Commitment).count() == 1
    assert restored_action(client, result)["status"] == "confirmed"
