"""Workspace invitation and membership-administration security tests."""

from __future__ import annotations

import json
from datetime import timedelta

from sqlmodel import Session, select

from api.api_keys import hash_api_key
from api.models.entities import (
    ApiKey,
    BrowserSession,
    User,
    Workspace,
    WorkspaceInvitation,
    WorkspaceMembership,
    WorkspaceMembershipEvent,
)
from api.models.enums import WorkspaceMembershipAction, WorkspaceRole
from api.lifecycle import purge_workspace
from api.utils.time import utcnow


def _headers(identity: str) -> dict[str, str]:
    return {"X-Test-User": identity}


def _workspace(client, identity: str) -> int:
    response = client.post(
        "/api/v1/projects",
        headers=_headers(identity),
        json={"name": f"{identity} membership test"},
    )
    assert response.status_code == 201, response.text
    return response.json()["workspace_id"]


def _invite(
    client,
    workspace_id: int,
    *,
    owner: str = "alice",
    email: str = "bob@example.com",
    role: str = "MEMBER",
) -> dict:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/invitations",
        headers=_headers(owner),
        json={"email": email, "role": role, "expires_in_days": 7},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _accept(client, token: str, identity: str = "bob"):
    return client.post(
        "/api/v1/workspaces/invitations/accept",
        headers=_headers(identity),
        json={"token": token},
    )


def test_invitation_is_hashed_email_bound_expiring_and_single_use(
    multi_user_client,
    engine,
):
    client, users = multi_user_client
    workspace_id = _workspace(client, "alice")
    invitation = _invite(client, workspace_id, role="VIEWER")

    assert len(invitation["token"]) >= 32
    assert invitation["token"] in invitation["accept_url"]
    assert "token_hash" not in invitation
    assert invitation["email"] == "bob@example.com"

    with Session(engine) as session:
        stored = session.get(WorkspaceInvitation, invitation["id"])
        assert stored is not None
        assert stored.token_hash == hash_api_key(invitation["token"])
        assert invitation["token"] not in stored.token_hash

    wrong_email = _accept(client, invitation["token"], identity="alice")
    assert wrong_email.status_code == 404

    accepted = _accept(client, invitation["token"])
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["id"] == workspace_id
    assert accepted.json()["role"] == "VIEWER"

    replay = _accept(client, invitation["token"])
    assert replay.status_code == 404

    with Session(engine) as session:
        membership = session.exec(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.user_id == users["bob"].id,
            )
        ).one()
        assert membership.role == WorkspaceRole.VIEWER
        stored = session.get(WorkspaceInvitation, invitation["id"])
        assert stored is not None
        assert stored.accepted_by_user_id == users["bob"].id
        actions = list(
            session.exec(
                select(WorkspaceMembershipEvent.action)
                .where(
                    WorkspaceMembershipEvent.workspace_id == workspace_id
                )
                .order_by(WorkspaceMembershipEvent.id)
            ).all()
        )
        assert actions == [
            WorkspaceMembershipAction.INVITATION_CREATED,
            WorkspaceMembershipAction.INVITATION_ACCEPTED,
        ]


def test_invitation_rejects_privileged_roles_duplicates_and_revocation(
    multi_user_client,
):
    client, _ = multi_user_client
    workspace_id = _workspace(client, "alice")

    owner_invite = client.post(
        f"/api/v1/workspaces/{workspace_id}/invitations",
        headers=_headers("alice"),
        json={"email": "bob@example.com", "role": "OWNER"},
    )
    assert owner_invite.status_code == 422

    invitation = _invite(client, workspace_id)
    duplicate = client.post(
        f"/api/v1/workspaces/{workspace_id}/invitations",
        headers=_headers("alice"),
        json={"email": " BOB@example.com ", "role": "MEMBER"},
    )
    assert duplicate.status_code == 409

    revoked = client.delete(
        f"/api/v1/workspaces/{workspace_id}/invitations/{invitation['id']}",
        headers=_headers("alice"),
    )
    assert revoked.status_code == 204
    assert _accept(client, invitation["token"]).status_code == 404


def test_invitation_acceptance_supports_normalized_unicode_email(
    multi_user_client,
    engine,
):
    client, users = multi_user_client
    users["bob"].email = "bücher@example.com"
    with Session(engine) as session:
        stored_bob = session.get(User, users["bob"].id)
        assert stored_bob is not None
        stored_bob.email = users["bob"].email
        session.add(stored_bob)
        session.commit()

    workspace_id = _workspace(client, "alice")
    invitation = _invite(
        client,
        workspace_id,
        email="BÜCHER@example.com",
    )
    accepted = _accept(client, invitation["token"])
    assert accepted.status_code == 200, accepted.text


def test_owner_changes_roles_and_member_removal_revokes_access(
    multi_user_client,
    engine,
):
    client, users = multi_user_client
    alice_workspace_id = _workspace(client, "alice")
    bob_workspace_id = _workspace(client, "bob")
    invitation = _invite(client, alice_workspace_id, role="MEMBER")
    assert _accept(client, invitation["token"]).status_code == 200

    now = utcnow()
    with Session(engine) as session:
        session.add_all(
            [
                BrowserSession(
                    id="bob-active-session",
                    user_id=users["bob"].id,
                    created_at=now,
                    last_seen_at=now,
                    expires_at=now + timedelta(days=1),
                ),
                BrowserSession(
                    id="bob-already-revoked",
                    user_id=users["bob"].id,
                    created_at=now,
                    last_seen_at=now,
                    expires_at=now + timedelta(days=1),
                    revoked_at=now,
                ),
                ApiKey(
                    user_id=users["bob"].id,
                    workspace_id=alice_workspace_id,
                    name="removed-workspace-key",
                    key_prefix="mvd_removed",
                    key_hash=hash_api_key("removed-workspace-key"),
                    scopes=["read", "write"],
                ),
                ApiKey(
                    user_id=users["bob"].id,
                    workspace_id=bob_workspace_id,
                    name="other-workspace-key",
                    key_prefix="mvd_other",
                    key_hash=hash_api_key("other-workspace-key"),
                    scopes=["read", "write"],
                ),
            ]
        )
        session.commit()

    role_change = client.patch(
        f"/api/v1/workspaces/{alice_workspace_id}/members/{users['bob'].id}",
        headers=_headers("alice"),
        json={"role": "VIEWER"},
    )
    assert role_change.status_code == 200, role_change.text
    assert role_change.json()["role"] == "VIEWER"
    assert role_change.json()["revoked_api_keys"] == 1

    removed = client.delete(
        f"/api/v1/workspaces/{alice_workspace_id}/members/{users['bob'].id}",
        headers=_headers("alice"),
    )
    assert removed.status_code == 200, removed.text
    assert removed.json()["revoked_browser_sessions"] == 1
    assert removed.json()["revoked_api_keys"] == 0

    assert (
        client.get(
            f"/api/v1/workspaces/{alice_workspace_id}/members",
            headers=_headers("bob"),
        ).status_code
        == 404
    )
    with Session(engine) as session:
        assert session.get(BrowserSession, "bob-active-session").revoked_at is not None
        removed_key = session.exec(
            select(ApiKey).where(ApiKey.name == "removed-workspace-key")
        ).one()
        other_key = session.exec(
            select(ApiKey).where(ApiKey.name == "other-workspace-key")
        ).one()
        assert removed_key.revoked is True
        assert other_key.revoked is False


def test_ownership_transfer_is_atomic_and_preserves_exactly_one_owner(
    multi_user_client,
    engine,
):
    client, users = multi_user_client
    workspace_id = _workspace(client, "alice")
    invitation = _invite(client, workspace_id, role="ADMIN")
    assert _accept(client, invitation["token"]).status_code == 200

    workspace = client.get(
        "/api/v1/workspaces",
        headers=_headers("alice"),
    ).json()[0]
    bad_confirmation = client.post(
        f"/api/v1/workspaces/{workspace_id}/ownership-transfer",
        headers=_headers("alice"),
        json={"user_id": users["bob"].id, "confirmation": "wrong"},
    )
    assert bad_confirmation.status_code == 422

    transferred = client.post(
        f"/api/v1/workspaces/{workspace_id}/ownership-transfer",
        headers=_headers("alice"),
        json={
            "user_id": users["bob"].id,
            "confirmation": workspace["slug"],
        },
    )
    assert transferred.status_code == 200, transferred.text
    assert transferred.json()["role"] == "OWNER"

    assert (
        client.get(
            f"/api/v1/workspaces/{workspace_id}/members",
            headers=_headers("alice"),
        ).status_code
        == 404
    )
    members = client.get(
        f"/api/v1/workspaces/{workspace_id}/members",
        headers=_headers("bob"),
    )
    assert members.status_code == 200

    with Session(engine) as session:
        memberships = list(
            session.exec(
                select(WorkspaceMembership).where(
                    WorkspaceMembership.workspace_id == workspace_id
                )
            ).all()
        )
        roles = {member.user_id: WorkspaceRole(member.role) for member in memberships}
        assert roles[users["alice"].id] == WorkspaceRole.ADMIN
        assert roles[users["bob"].id] == WorkspaceRole.OWNER
        assert list(roles.values()).count(WorkspaceRole.OWNER) == 1


def test_owner_cannot_be_demoted_or_removed_without_transfer(
    multi_user_client,
):
    client, users = multi_user_client
    workspace_id = _workspace(client, "alice")
    demote = client.patch(
        f"/api/v1/workspaces/{workspace_id}/members/{users['alice'].id}",
        headers=_headers("alice"),
        json={"role": "ADMIN"},
    )
    assert demote.status_code == 409
    remove = client.delete(
        f"/api/v1/workspaces/{workspace_id}/members/{users['alice'].id}",
        headers=_headers("alice"),
    )
    assert remove.status_code == 409


def test_admin_cannot_use_owner_only_membership_controls(
    multi_user_client,
):
    client, users = multi_user_client
    workspace_id = _workspace(client, "alice")
    invitation = _invite(client, workspace_id, role="ADMIN")
    assert _accept(client, invitation["token"]).status_code == 200
    headers = _headers("bob")

    attempts = [
        client.get(
            f"/api/v1/workspaces/{workspace_id}/members",
            headers=headers,
        ),
        client.get(
            f"/api/v1/workspaces/{workspace_id}/invitations",
            headers=headers,
        ),
        client.post(
            f"/api/v1/workspaces/{workspace_id}/invitations",
            headers=headers,
            json={"email": "other@example.com", "role": "MEMBER"},
        ),
        client.patch(
            f"/api/v1/workspaces/{workspace_id}/members/{users['bob'].id}",
            headers=headers,
            json={"role": "MEMBER"},
        ),
        client.delete(
            f"/api/v1/workspaces/{workspace_id}/members/{users['alice'].id}",
            headers=headers,
        ),
        client.post(
            f"/api/v1/workspaces/{workspace_id}/ownership-transfer",
            headers=headers,
            json={
                "user_id": users["bob"].id,
                "confirmation": "not-authorized",
            },
        ),
        client.get(
            f"/api/v1/workspaces/{workspace_id}/membership-events",
            headers=headers,
        ),
    ]
    assert all(response.status_code == 404 for response in attempts)


def test_api_keys_cannot_administer_membership(
    enforce_auth_client,
    agent_headers,
    engine,
    test_user,
):
    with Session(engine) as session:
        membership = session.exec(
            select(WorkspaceMembership).where(
                WorkspaceMembership.user_id == test_user.id,
                WorkspaceMembership.role == WorkspaceRole.OWNER,
            )
        ).one()
        workspace_id = membership.workspace_id

    response = enforce_auth_client.post(
        f"/api/v1/workspaces/{workspace_id}/invitations",
        headers=agent_headers,
        json={"email": "someone@example.com", "role": "MEMBER"},
    )
    assert response.status_code == 403


def test_export_redacts_invite_token_and_deletion_permanently_revokes_invite(
    multi_user_client,
    engine,
):
    client, _ = multi_user_client
    workspace_id = _workspace(client, "alice")
    invitation = _invite(client, workspace_id)

    exported = client.get(
        f"/api/v1/workspaces/{workspace_id}/export",
        headers=_headers("alice"),
    )
    assert exported.status_code == 200, exported.text
    payload = json.loads(exported.content)
    invitation_rows = payload["tables"]["workspace_invitations"]
    assert invitation_rows[0]["email"] == "bob@example.com"
    assert "token_hash" not in invitation_rows[0]
    assert invitation["token"] not in exported.text

    scheduled = client.post(
        f"/api/v1/workspaces/{workspace_id}/deletion",
        headers=_headers("alice"),
        json={
            "confirmation": payload["workspace"]["slug"],
            "export_sha256": exported.headers[
                "X-Mouvadah-Export-SHA256"
            ],
        },
    )
    assert scheduled.status_code == 200, scheduled.text
    assert scheduled.json()["revoked_invitations"] == 1

    restored = client.post(
        f"/api/v1/workspaces/{workspace_id}/restore",
        headers=_headers("alice"),
    )
    assert restored.status_code == 200
    assert _accept(client, invitation["token"]).status_code == 404

    # Schedule again with a fresh export, then prove purge handles the new
    # child table under the same child-first deletion contract.
    second_export = client.get(
        f"/api/v1/workspaces/{workspace_id}/export",
        headers=_headers("alice"),
    )
    second_payload = json.loads(second_export.content)
    scheduled_again = client.post(
        f"/api/v1/workspaces/{workspace_id}/deletion",
        headers=_headers("alice"),
        json={
            "confirmation": second_payload["workspace"]["slug"],
            "export_sha256": second_export.headers[
                "X-Mouvadah-Export-SHA256"
            ],
        },
    )
    assert scheduled_again.status_code == 200
    with Session(engine) as session:
        workspace = session.get(Workspace, workspace_id)
        assert workspace is not None
        now = utcnow()
        workspace.deletion_requested_at = now - timedelta(seconds=2)
        workspace.purge_after = now - timedelta(seconds=1)
        session.add(workspace)
        session.commit()
        result = purge_workspace(
            session,
            workspace_id,
            backup_evidence="verified-backup-20260725",
        )
        assert result.deleted_records["workspace_invitations"] == 1
        assert session.get(WorkspaceInvitation, invitation["id"]) is None
