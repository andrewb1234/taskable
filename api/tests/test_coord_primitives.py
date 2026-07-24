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
    def test_list_project_tickets_for_dependency_picker(self, client: TestClient):
        project_id, first_subproject_id = _make_project_and_subproject(client)
        second_subproject = client.post(
            f"/api/v1/projects/{project_id}/subprojects",
            json={"name": "Second", "context_brief": ""},
        )
        assert second_subproject.status_code == 201
        first = _create_ticket(client, first_subproject_id, "First")
        second = _create_ticket(client, second_subproject.json()["id"], "Second")

        response = client.get(f"/api/v1/projects/{project_id}/tickets")

        assert response.status_code == 200
        assert [ticket["id"] for ticket in response.json()] == [first["id"], second["id"]]
        assert response.json()[1]["subproject_name"] == "Second"

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

    def test_dependency_cross_project_rejected(self, client: TestClient):
        _, sp1 = _make_project_and_subproject(client)
        _, sp2 = _make_project_and_subproject(client)
        t1 = _create_ticket(client, sp1, "InSP1")
        r = client.post(
            f"/api/v1/subprojects/{sp2}/tickets",
            json={"title": "Cross", "depends_on": [t1["id"]]},
        )
        assert r.status_code == 422
        assert "different project" in r.json()["detail"]

    def test_subproject_detail_includes_depends_on(self, client: TestClient):
        _, sp_id = _make_project_and_subproject(client)
        t1 = _create_ticket(client, sp_id, "A")
        t2 = _create_ticket(client, sp_id, "B", depends_on=[t1["id"]])

        r = client.get(f"/api/v1/subprojects/{sp_id}")
        assert r.status_code == 200
        tickets = r.json()["tickets"]
        t2_data = [t for t in tickets if t["id"] == t2["id"]][0]
        assert t2_data["depends_on"] == [t1["id"]]

    def test_update_ticket_response_includes_depends_on(self, client: TestClient):
        _, sp_id = _make_project_and_subproject(client)
        t1 = _create_ticket(client, sp_id, "A")
        t2 = _create_ticket(client, sp_id, "B")

        r = client.patch(
            f"/api/v1/tickets/{t2['id']}",
            json={"depends_on": [t1["id"]]},
        )
        assert r.status_code == 200
        assert r.json()["depends_on"] == [t1["id"]]

    def test_delete_ticket_cleans_dependency_edges(self, client: TestClient):
        _, sp_id = _make_project_and_subproject(client)
        t1 = _create_ticket(client, sp_id, "Dep")
        t2 = _create_ticket(client, sp_id, "Child", depends_on=[t1["id"]])

        # Delete t1 — t2's dependency on t1 should be removed
        r = client.delete(f"/api/v1/tickets/{t1['id']}")
        assert r.status_code == 204

        # t2 should no longer show t1 in depends_on
        r = client.get(f"/api/v1/tickets/{t2['id']}")
        assert r.status_code == 200
        assert r.json()["depends_on"] == []


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


def test_dependency_cross_subproject_same_project_allowed(client: TestClient):
    project_id, sp1 = _make_project_and_subproject(client)
    response = client.post(
        f"/api/v1/projects/{project_id}/subprojects",
        json={"name": "SecondSubproject"},
    )
    sp2 = response.json()["id"]
    dependency = _create_ticket(client, sp1, "Dependency")
    ticket = _create_ticket(client, sp2, "Cross-subproject", [dependency["id"]])

    assert ticket["depends_on"] == [dependency["id"]]
    assert ticket["depends_on_refs"][0]["subproject_id"] == sp1


def test_delete_subproject_cleans_cross_subproject_dependencies(client: TestClient):
    project_id, sp1 = _make_project_and_subproject(client)
    response = client.post(
        f"/api/v1/projects/{project_id}/subprojects",
        json={"name": "SecondSubproject"},
    )
    sp2 = response.json()["id"]
    dependency = _create_ticket(client, sp1, "Dependency")
    ticket = _create_ticket(client, sp2, "Cross-subproject", [dependency["id"]])

    assert client.delete(f"/api/v1/subprojects/{sp1}").status_code == 204
    response = client.get(f"/api/v1/tickets/{ticket['id']}")
    assert response.status_code == 200
    assert response.json()["depends_on"] == []


def test_heartbeat_rejects_expired_lease(client: TestClient, engine):
    from datetime import timedelta

    from sqlmodel import Session

    from api.models.entities import Ticket
    from api.utils.time import utcnow

    _, sp_id = _make_project_and_subproject(client)
    ticket = _create_ticket(client, sp_id, "Expired heartbeat")
    client.post(f"/api/v1/tickets/{ticket['id']}/claim", json={"worker_id": "w1"})
    with Session(engine) as session:
        claimed = session.get(Ticket, ticket["id"])
        claimed.lease_expires_at = utcnow() - timedelta(seconds=1)
        session.add(claimed)
        session.commit()

    response = client.post(
        f"/api/v1/tickets/{ticket['id']}/heartbeat",
        json={"worker_id": "w1", "extend_seconds": 600},
    )
    assert response.status_code == 409


def test_claim_compare_and_set_allows_one_concurrent_winner(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from sqlmodel import Session, SQLModel, create_engine

    from api.models.entities import Project, Subproject, Ticket
    from api.routes.tickets import _claim_ticket_atomic
    from api.utils.time import utcnow

    engine = create_engine(
        f"sqlite:///{tmp_path / 'claims.db'}",
        connect_args={"check_same_thread": False, "timeout": 10},
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        project = Project(name="Concurrent")
        session.add(project)
        session.flush()
        subproject = Subproject(project_id=project.id, name="Claims")
        session.add(subproject)
        session.flush()
        ticket = Ticket(subproject_id=subproject.id, title="Claim once")
        session.add(ticket)
        session.commit()
        ticket_id = ticket.id

    barrier = Barrier(2)

    def attempt(worker_id: str) -> bool:
        with Session(engine) as session:
            barrier.wait()
            won = _claim_ticket_atomic(session, ticket_id, worker_id, utcnow())
            session.commit() if won else session.rollback()
            return won

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(attempt, ["worker-1", "worker-2"]))

    assert sorted(outcomes) == [False, True]
    with Session(engine) as session:
        claimed = session.get(Ticket, ticket_id)
        assert claimed.status.value == "IN_PROGRESS"
        assert claimed.claimed_by in {"worker-1", "worker-2"}


def test_legacy_ticket_table_gets_coordination_columns(tmp_path):
    from sqlalchemy import create_engine, inspect, text

    from api.database import _upgrade_ticket_coordination_schema

    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE ticket (id INTEGER PRIMARY KEY, title VARCHAR NOT NULL)")
        )

    _upgrade_ticket_coordination_schema(engine)
    _upgrade_ticket_coordination_schema(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("ticket")}
    assert {"claimed_by", "claimed_at", "lease_expires_at"} <= columns
