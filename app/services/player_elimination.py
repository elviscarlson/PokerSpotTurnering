from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.extensions import db
from app.models import (
    Bounty,
    Prize,
    Tournament,
    TournamentEvent,
    TournamentPlayer,
)
from app.services.completion_service import (
    complete_tournament,
    reopen_completed_tournament,
)


class EliminationError(ValueError):
    pass


def get_entry(
    tournament: Tournament,
    entry_id: int,
) -> TournamentPlayer:
    entry = db.session.scalar(
        select(TournamentPlayer).where(
            TournamentPlayer.id == entry_id,
            TournamentPlayer.tournament_id == tournament.id,
        )
    )

    if entry is None:
        raise EliminationError(
            "Spelaren finns inte i turneringen."
        )

    return entry


def get_prize_for_place(
    tournament: Tournament,
    placement: int,
) -> Prize | None:
    return next(
        (
            prize
            for prize in tournament.prizes
            if prize.place == placement
        ),
        None,
    )


def add_event(
    *,
    tournament: Tournament,
    event_type: str,
    message: str,
) -> TournamentEvent:
    event = TournamentEvent(
        tournament=tournament,
        event_type=event_type,
        message=message,
    )

    db.session.add(
        event
    )

    return event


def ordinal(
    number: int,
) -> str:
    if 10 <= number % 100 <= 20:
        suffix = "th"
    else:
        suffix = {
            1: "st",
            2: "nd",
            3: "rd",
        }.get(
            number % 10,
            "th",
        )

    return (
        f"{number}{suffix}"
    )


def get_bounty_for_elimination(
    *,
    entry: TournamentPlayer,
    elimination_number: int,
) -> Bounty | None:
    return next(
        (
            bounty
            for bounty in entry.elimination_bounties
            if (
                bounty.elimination_number
                == elimination_number
            )
        ),
        None,
    )


def eliminate_player(
    *,
    tournament: Tournament,
    entry_id: int,
    eliminated_by_entry_id: int | None = None,
    now: datetime | None = None,
) -> TournamentPlayer:
    if tournament.status not in (
        "RUNNING",
        "PAUSED",
    ):
        raise EliminationError(
            "Turneringen måste vara startad innan en spelare kan elimineras."
        )

    entry = get_entry(
        tournament,
        entry_id,
    )

    if entry.status != "ACTIVE":
        raise EliminationError(
            "Spelaren är redan eliminerad."
        )

    active_entries = [
        candidate
        for candidate in tournament.players
        if candidate.status == "ACTIVE"
    ]

    if len(active_entries) <= 1:
        raise EliminationError(
            "Den sista kvarvarande spelaren kan inte elimineras."
        )

    placement = len(
        active_entries
    )

    eliminator = None

    if tournament.bounty_enabled:
        if eliminated_by_entry_id is None:
            raise EliminationError(
                "Välj vem som vann bountyn."
            )

        eliminator = get_entry(
            tournament,
            eliminated_by_entry_id,
        )

        if eliminator.id == entry.id:
            raise EliminationError(
                "En spelare kan inte eliminera sig själv."
            )

        if eliminator.status != "ACTIVE":
            raise EliminationError(
                "Bountyn måste tilldelas en aktiv spelare."
            )

    entry.status = "ELIMINATED"

    entry.elimination_count += 1

    entry.placement = placement

    prize = get_prize_for_place(
        tournament,
        placement,
    )

    entry.prize_winnings = (
        prize.amount
        if prize is not None
        else 0
    )

    add_event(
        tournament=tournament,
        event_type="PLAYER_ELIMINATED",
        message=(
            f"{entry.player.name} eliminated — "
            f"{ordinal(placement)}"
        ),
    )

    if (
        tournament.bounty_enabled
        and eliminator is not None
    ):
        bounty = Bounty(
            tournament=tournament,
            winner_entry=eliminator,
            eliminated_entry=entry,
            elimination_number=(
                entry.elimination_count
            ),
            amount=(
                tournament.bounty_amount
            ),
        )

        eliminator.bounty_winnings += (
            tournament.bounty_amount
        )

        db.session.add(
            bounty
        )

        add_event(
            tournament=tournament,
            event_type="BOUNTY_AWARDED",
            message=(
                f"{eliminator.player.name} received "
                f"{entry.player.name}'s bounty "
                f"({tournament.bounty_amount} kr) "
                f"— elimination "
                f"#{entry.elimination_count}"
            ),
        )

    if (
        tournament.active_player_count
        == 1
    ):
        complete_tournament(
            tournament,
            now=now,
        )
    else:
        db.session.commit()

    return entry


def restore_last_elimination(
    *,
    tournament: Tournament,
    entry_id: int,
    now: datetime | None = None,
) -> TournamentPlayer:
    entry = get_entry(
        tournament,
        entry_id,
    )

    if entry.status != "ELIMINATED":
        raise EliminationError(
            "Spelaren är inte eliminerad."
        )

    eliminated_entries = [
        candidate
        for candidate in tournament.players
        if (
            candidate.status
            == "ELIMINATED"
            and candidate.placement
            is not None
        )
    ]

    if not eliminated_entries:
        raise EliminationError(
            "Det finns ingen eliminering att återställa."
        )

    most_recent = min(
        eliminated_entries,
        key=lambda candidate:
            candidate.placement,
    )

    if most_recent.id != entry.id:
        raise EliminationError(
            "Endast den senaste elimineringen kan ångras."
        )

    if entry.elimination_count <= 0:
        raise EliminationError(
            "Spelaren saknar en registrerad eliminering att återställa."
        )

    elimination_number = (
        entry.elimination_count
    )

    if tournament.status == "COMPLETED":
        reopen_completed_tournament(
            tournament,
            now=now,
        )

    bounty = (
        get_bounty_for_elimination(
            entry=entry,
            elimination_number=(
                elimination_number
            ),
        )
    )

    if bounty is not None:
        winner = (
            bounty.winner_entry
        )

        winner.bounty_winnings = max(
            0,
            winner.bounty_winnings
            - bounty.amount,
        )

        db.session.delete(
            bounty
        )

    name = entry.player.name

    entry.status = "ACTIVE"

    entry.placement = None

    entry.prize_winnings = 0

    entry.elimination_count -= 1

    add_event(
        tournament=tournament,
        event_type="ELIMINATION_RESTORED",
        message=(
            f"{name} restored to tournament "
            f"(elimination "
            f"#{elimination_number} undone)"
        ),
    )

    db.session.commit()

    return entry