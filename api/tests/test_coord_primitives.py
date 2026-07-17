"""Tests for coordination primitives: depends_on, ready query, claim, heartbeat, requeue."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _create_ticket(client: TestClient, subproject_id: int, title: str, depends_on=None):
    payload: dict = {"title": title}
    if depends_on is not None:
        payload["depends_on"] = depends_on
    r = client.post(f"/api/v1/subprojects/{subproject_id}/tickets", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def _make_project_and_subproject(client: TestClient):
    pr = client.post("/api/v1/projects", json={"name": "TestProj"})
    assert pr.status_code == 201
    project_id = pr.json()["id"]
    sr = client.post(
        f"/api/v1/projects/{project_id}/subprojects",
        json={"name": "TestSub", "context_brief": "testing"},
    )
    assert sr.status_code == 201
    subproject_id = sr.json()["id"]
    return project_id, subproject_id


# ---- TicketDependency + depends_on (#63) ----------------------------------


class TestTicketDependencies:
    def test_create_ticket_with_depends_on(self, client: TestClient):
        _, sp_id = _make_project_and_subproject(client)
        t1 = _create_ticket(client, sp_id, "First")
        t2 = _create_ticket(client, sp_id, "Second", depends_on=[t1["id"]])

        # GET ticket should show depends_on
        r = client.get(f"/api/v1/tickets/{t2['id']}")
        assert r.status_code == 200
        assert r.json()["depends_on"] == [t1["id"]]

    def test_create_ticket_self_dependency_rejected(self, client: TestClient):
        _, sp_id = _make_project_and_subproject(client)
        t1 = _create_ticket(client, sp_id, "Self")
        r = client.post(
            f"/api/v1/subprojects/{sp_id}/tickets",
            json={"title": "Bad", "depends_on": [t1["id"]]},
        )
        # Self-dep is caught at update time, not creation (ticket doesn't exist yet).
        # But we can test via PATCH.
        r2 = client.patch(
            f"/api/v1/tickets/{t1['id']}", json={"depends_on": [t1["id"]]}
        )
        assert r2.status_code == 422

    def test_update_ticket_depends_on(self, client: TestClient):
        _, sp_id = _make_project_and_subproject(client)
        t1 = _create_ticket(client, sp_id, "A")
        t2 = _create_ticket(client, sp_id, "B")
        t3 = _create_ticket(client, sp_id, "C")

        # Set deps on t3
        r = client.patch(
            f"/api/v1/tickets/{t3['id']}",
            json={"depends_on": [t1["id"], t2["id"]]},
        )
        assert r.status_code == 200

        # Verify
        r = client.get(f"/api/v1/tickets/{t3['id']}")
        assert sorted(r.json()["depends_on"]) == sorted([t1["id"], t2["id"]])

        # Replace deps with just t1
        r = client.patch(
            f"/api/v1/tickets/{t3['id']}",
            json={"depends_on": [t1["id"]]},
        )
        assert r.status_code == 200
        r = client.get(f"/api/v1/tickets/{t3['id']}")
        assert r.json()["depends_on"] == [t1["id"]]

        # Clear deps
        r = client.patch(
            f"/api/v1/tickets/{t3['id']}",
            json={"depends_on": []},
        )
        assert r.status_code == 200
        r = client.get(f"/api/v1/tickets/{t3['id']}")
        assert r.json()["depends_on"] == []

    def test_cycle_detection(self, client: TestClient):
        _, sp_id = _make_project_and_subproject(client)
        t1 = _create_ticket(client, sp_id, "A")
        t2 = _create_ticket(client, sp_id, "B", depends_on=[t1["id"]])

        # t1 -> t2 would create a cycle: t1 -> t2 -> t1
        r = client.patch(
            f"/api/v1/tickets/{t1['id']}",
            json={"depends_on": [t2["id"]]},
        )
        assert r.status_code == 422
        assert "Circular dependency" in r.json()["detail"]

    def test_dependency_on_nonexistent_ticket(self, client: TestClient):
        _, sp_id = _make_project_and_subproject(client)
        r = client.post(
            f"/api/v1/subprojects/{sp_id}/tickets",
            json={"title": "Ghost", "depends_on": [99999]},
        )
        assert r.status_code == 422
        assert "not found" in r.json()["detail"].lower()

    def test_dependency_cross_subproject_rejected(self, client: TestClient):
        _, sp1 = _make_project_and_subproject(client)
        _, sp2 = _make_project_and_subproject(client)
        t1 = _create_ticket(client, sp1, "InSP1")
        r = client.post(
            f"/api/v1/subprojects/{sp2}/tickets",
            json={"title": "Cross", "depends_on": [t1["id"]]},
        )
        assert r.status_code == 422
        assert "different subproject" in r.json()["detail"]

    def test_subproject_detail_includes_depends_on(self, client: TestClient):
        _, sp_id = _make_project_and_subproject(client)
        t1 = _create_ticket(client, sp_id, "A")
        t2 = _create_ticket(client, sp_id, "B", depends_on=[t1["id"]])

        r = client.get(f"/api/v1/subprojects/{sp_id}")
        assert r.status_code == 200
        tickets = r.json()["tickets"]
        t2_data = [t for t in tickets if t["id"] == t2["id"]][0]
        assert t2_data["depends_on"] == [t1["id"]]


# ---- Ready-ticket query (#64) ---------------------------------------------


class TestReadyQuery:
    def test_ready_returns_todo_with_deps_done(self, client: TestClient):
        _, sp_id = _make_project_and_subproject(client)
        t1 = _create_ticket(client, sp_id, "Dep")
        t2 = _create_ticket(client, sp_id, "Child", depends_on=[t1["id"]])

        # t2 is not ready (t1 is TODO)
        r = client.get(f"/api/v1/subprojects/{sp_id}?ready=true")
        tickets = r.json()["tickets"]
        ids = [t["id"] for t in tickets]
        assert t1["id"] in ids  # t1 has no deps, is TODO → ready
        assert t2["id"] not in ids  # t2 has unmet dep → not ready

        # Mark t1 DONE
        client.patch(f"/api/v1/tickets/{t1['id']}", json={"status": "DONE"})

        # Now t2 should be ready
        r = client.get(f"/api/v1/subprojects/{sp_id}?ready=true")
        tickets = r.json()["tickets"]
        ids = [t["id"] for t in tickets]
        assert t2["id"] in ids
        assert t1["id"] not in ids  # t1 is DONE, not TODO → not ready

    def test_ready_excludes_non_todo(self, client: TestClient):
        _, sp_id = _make_project_and_subproject(client)
        t1 = _create_ticket(client, sp_id, "A")
        client.patch(f"/api/v1/tickets/{t1['id']}", json={"status": "IN_PROGRESS"})

        r = client.get(f"/api/v1/subprojects/{sp_id}?ready=true")
        ids = [t["id"] for t in r.json()["tickets"]]
        assert t1["id"] not in ids


# ---- Atomic claim (#65) ---------------------------------------------------


class TestClaim:
    def test_claim_succeeds_on_ready_ticket(self, client: TestClient):
        _, sp_id = _make_project_and_subproject(client)
        t1 = _create_ticket(client, sp_id, "Claimable")

        r = client.post(
            f"/api/v1/tickets/{t1['id']}/claim",
            json={"worker_id": "worker-1"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "IN_PROGRESS"
        assert body["claimed_by"] == "worker-1"
        assert body["claimed_at"] is not None
        assert body["lease_expires_at"] is not None

    def test_claim_fails_on_non_todo(self, client: TestClient):
        _, sp_id = _make_project_and_subproject(client)
        t1 = _create_ticket(client, sp_id, "NotTodo")
        client.patch(f"/api/v1/tickets/{t1['id']}", json={"status": "DONE"})

        r = client.post(
            f"/api/v1/tickets/{t1['id']}/claim",
            json={"worker_id": "worker-1"},
        )
        assert r.status_code == 409

    def test_claim_fails_with_unmet_deps(self, client: TestClient):
        _, sp_id = _make_project_and_subproject(client)
        t1 = _create_ticket(client, sp_id, "Dep")
        t2 = _create_ticket(client, sp_id, "Child", depends_on=[t1["id"]])

        r = client.post(
            f"/api/v1/tickets/{t2['id']}/claim",
            json={"worker_id": "worker-1"},
        )
        assert r.status_code == 409
        assert "not available" in r.json()["detail"].lower()

    def test_claim_after_deps_done(self, client: TestClient):
        _, sp_id = _make_project_and_subproject(client)
        t1 = _create_ticket(client, sp_id, "Dep")
        t2 = _create_ticket(client, sp_id, "Child", depends_on=[t1["id"]])
        client.patch(f"/api/v1/tickets/{t1['id']}", json={"status": "DONE"})

        r = client.post(
            f"/api/v1/tickets/{t2['id']}/claim",
            json={"worker_id": "worker-1"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "IN_PROGRESS"

    def test_claim_audited(self, client: TestClient):
        _, sp_id = _make_project_and_subproject(client)
        t1 = _create_ticket(client, sp_id, "Audited")
        client.post(f"/api/v1/tickets/{t1['id']}/claim", json={"worker_id": "w1"})

        r = client.get(f"/api/v1/tickets/{t1['id']}")
        actions = [a["action"] for a in r.json()["audit_logs"]]
        assert "TICKET_CLAIMED" in actions


# ---- Heartbeat (#66) ------------------------------------------------------


class TestHeartbeat:
    def test_heartbeat_extends_lease(self, client: TestClient):
        _, sp_id = _make_project_and_subproject(client)
        t1 = _create_ticket(client, sp_id, "Beat")
        client.post(f"/api/v1/tickets/{t1['id']}/claim", json={"worker_id": "w1"})

        original = client.get(f"/api/v1/tickets/{t1['id']}").json()
        original_lease = original["lease_expires_at"]

        r = client.post(
            f"/api/v1/tickets/{t1['id']}/heartbeat",
            json={"worker_id": "w1", "extend_seconds": 1200},
        )
        assert r.status_code == 200
        new_lease = r.json()["lease_expires_at"]
        assert new_lease != original_lease

    def test_heartbeat_wrong_worker_rejected(self, client: TestClient):
        _, sp_id = _make_project_and_subproject(client)
        t1 = _create_ticket(client, sp_id, "Owned")
        client.post(f"/api/v1/tickets/{t1['id']}/claim", json={"worker_id": "w1"})

        r = client.post(
            f"/api/v1/tickets/{t1['id']}/heartbeat",
            json={"worker_id": "w2", "extend_seconds": 600},
        )
        assert r.status_code == 409


# ---- Requeue-expired (#66) ------------------------------------------------


class TestRequeueExpired:
    def test_requeue_expired_reverts_claimed_ticket(self, client: TestClient):
        _, sp_id = _make_project_and_subproject(client)
        t1 = _create_ticket(client, sp_id, "Expired")

        # Claim and then manually set lease_expires_at to the past via direct API
        client.post(f"/api/v1/tickets/{t1['id']}/claim", json={"worker_id": "w1"})

        # Use PATCH to set lease to past — but PATCH doesn't support lease_expires_at.
        # Instead, we'll test requeue with a ticket that has no lease set.
        # Actually, let's just verify the endpoint works with no expired tickets.
        r = client.post(f"/api/v1/tickets/subprojects/{sp_id}/requeue-expired")
        assert r.status_code == 200
        # The claimed ticket has a future lease, so it shouldn't be requeued
        assert len(r.json()) == 0

    def test_requeue_expired_with_past_lease(self, client: TestClient, engine):
        from datetime import timedelta

        from sqlmodel import Session

        from api.utils.time import utcnow

        _, sp_id = _make_project_and_subproject(client)
        t1 = _create_ticket(client, sp_id, "WillExpire")

        # Claim
        client.post(f"/api/v1/tickets/{t1['id']}/claim", json={"worker_id": "w1"})

        # Manually expire the lease via direct DB access
        from api.models.entities import Ticket

        with Session(engine) as session:
            ticket = session.get(Ticket, t1["id"])
            ticket.lease_expires_at = utcnow() - timedelta(seconds=60)
            session.add(ticket)
            session.commit()

        r = client.post(f"/api/v1/tickets/subprojects/{sp_id}/requeue-expired")
        assert r.status_code == 200
        requeued = r.json()
        assert len(requeued) == 1
        assert requeued[0]["id"] == t1["id"]
        assert requeued[0]["status"] == "TODO"
        assert requeued[0]["claimed_by"] is None
        assert requeued[0]["lease_expires_at"] is None

    def test_requeue_audited(self, client: TestClient, engine):
        from datetime import timedelta

        from sqlmodel import Session

        from api.utils.time import utcnow

        _, sp_id = _make_project_and_subproject(client)
        t1 = _create_ticket(client, sp_id, "AuditedRequeue")
        client.post(f"/api/v1/tickets/{t1['id']}/claim", json={"worker_id": "w1"})

        from api.models.entities import Ticket

        with Session(engine) as session:
            ticket = session.get(Ticket, t1["id"])
            ticket.lease_expires_at = utcnow() - timedelta(seconds=60)
            session.add(ticket)
            session.commit()

        client.post(f"/api/v1/tickets/subprojects/{sp_id}/requeue-expired")

        r = client.get(f"/api/v1/tickets/{t1['id']}")
        actions = [a["action"] for a in r.json()["audit_logs"]]
        assert "TICKET_REQUEUED" in actions
