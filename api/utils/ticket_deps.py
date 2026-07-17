"""Helpers for ticket dependency edges: validation, cycle detection, and lookups."""

from __future__ import annotations

from sqlmodel import Session, select

from api.models.entities import Ticket, TicketDependency


def get_depends_on(session: Session, ticket_id: int) -> list[int]:
    """Return the list of ticket IDs that *ticket_id* depends on."""
    rows = session.exec(
        select(TicketDependency.depends_on_ticket_id)
        .where(TicketDependency.ticket_id == ticket_id)
        .order_by(TicketDependency.depends_on_ticket_id)
    ).all()
    return list(rows)


def get_depends_on_map(session: Session, ticket_ids: list[int]) -> dict[int, list[int]]:
    """Batch-fetch depends_on edges for multiple tickets.

    Returns ``{ticket_id: [dep_id, ...]}`` sorted by dep id.
    """
    if not ticket_ids:
        return {}
    rows = session.exec(
        select(TicketDependency)
        .where(TicketDependency.ticket_id.in_(ticket_ids))
        .order_by(TicketDependency.ticket_id, TicketDependency.depends_on_ticket_id)
    ).all()
    result: dict[int, list[int]] = {tid: [] for tid in ticket_ids}
    for row in rows:
        result.setdefault(row.ticket_id, []).append(row.depends_on_ticket_id)
    return result


def _detect_cycle(
    session: Session, ticket_id: int, new_deps: list[int]
) -> list[int] | None:
    """DFS to find a cycle if we add edges *ticket_id -> new_deps*.

    Returns the offending cycle as a list of ticket IDs, or ``None`` if no
    cycle would be introduced.
    """
    # Build adjacency list of existing edges, then temporarily add new ones.
    all_edges: dict[int, list[int]] = {}

    def _load_edges(node_ids: list[int]) -> None:
        missing = [n for n in node_ids if n not in all_edges]
        if not missing:
            return
        rows = session.exec(
            select(TicketDependency)
            .where(TicketDependency.ticket_id.in_(missing))
        ).all()
        for n in missing:
            all_edges[n] = []
        for row in rows:
            all_edges[row.ticket_id].append(row.depends_on_ticket_id)

    _load_edges([ticket_id] + new_deps)
    all_edges[ticket_id] = list(set(all_edges.get(ticket_id, []) + new_deps))

    # DFS from each new dep back to ticket_id.
    visited: set[int] = set()
    path: list[int] = []

    def _dfs(node: int) -> list[int] | None:
        if node == ticket_id and path:
            return path + [node]
        if node in visited:
            return None
        visited.add(node)
        path.append(node)
        _load_edges([node])
        for neighbor in all_edges.get(node, []):
            result = _dfs(neighbor)
            if result is not None:
                return result
        path.pop()
        return None

    for dep in new_deps:
        result = _dfs(dep)
        if result is not None:
            return result
    return None


def validate_and_set_deps(
    session: Session,
    ticket_id: int,
    subproject_id: int,
    depends_on: list[int],
) -> None:
    """Validate and persist dependency edges for *ticket_id*.

    Raises ``HTTPException(422)`` on validation failure.
    """
    from fastapi import HTTPException

    # Deduplicate and sort.
    deps = sorted(set(depends_on))

    # No self-reference.
    if ticket_id in deps:
        raise HTTPException(
            status_code=422,
            detail=f"Ticket {ticket_id} cannot depend on itself.",
        )

    # All dep IDs must exist and belong to the same subproject.
    if deps:
        existing = session.exec(
            select(Ticket).where(Ticket.id.in_(deps))
        ).all()
        existing_ids = {t.id for t in existing}
        missing = set(deps) - existing_ids
        if missing:
            raise HTTPException(
                status_code=422,
                detail=f"Dependency ticket(s) not found: {sorted(missing)}",
            )
        wrong_subproject = [t for t in existing if t.subproject_id != subproject_id]
        if wrong_subproject:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Dependency ticket(s) belong to a different subproject: "
                    f"{sorted(t.id for t in wrong_subproject)}"
                ),
            )

    # Cycle detection.
    cycle = _detect_cycle(session, ticket_id, deps)
    if cycle is not None:
        raise HTTPException(
            status_code=422,
            detail=f"Circular dependency detected: {' -> '.join(str(n) for n in cycle)}",
        )

    # Replace existing edges.
    old_edges = session.exec(
        select(TicketDependency).where(TicketDependency.ticket_id == ticket_id)
    ).all()
    for edge in old_edges:
        session.delete(edge)

    for dep_id in deps:
        session.add(TicketDependency(ticket_id=ticket_id, depends_on_ticket_id=dep_id))


def is_ticket_ready(session: Session, ticket: Ticket) -> bool:
    """A ticket is *ready* iff status==TODO and all depends_on tickets are DONE."""
    from api.models.enums import TicketStatus

    if ticket.status != TicketStatus.TODO:
        return False
    deps = get_depends_on(session, ticket.id)  # type: ignore[arg-type]
    if not deps:
        return True
    dep_tickets = session.exec(
        select(Ticket).where(Ticket.id.in_(deps))
    ).all()
    return all(t.status == TicketStatus.DONE for t in dep_tickets)
