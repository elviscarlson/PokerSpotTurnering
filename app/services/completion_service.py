from __future__ import annotations

from datetime import datetime, timezone

from app.extensions import db
from app.models import (
    Tournament,
    TournamentEvent,
    TournamentResult,
    TournamentPlayer,
)
from app.services.clock_service import (
    get_remaining_seconds,
)


class CompletionError(ValueError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_datetime(
    value: datetime,
) -> datetime:
    if value.tzinfo is None:
        return value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    )


def get_winner(
    tournament: Tournament,
) -> TournamentPlayer:
    active_entries = [
        entry
        for entry in tournament.players
        if entry.status == "ACTIVE"
    ]

    if len(active_entries) != 1:
        raise CompletionError(
            "Turneringen kan endast avslutas när exakt en spelare återstår."
        )

    return active_entries[0]


def get_first_prize(
    tournament: Tournament,
) -> int:
    first_prize = next(
        (
            prize
            for prize in tournament.prizes
            if prize.place == 1
        ),
        None,
    )

    if first_prize is None:
        raise CompletionError(
            "Turneringen saknar förstapris."
        )

    return first_prize.amount


def ensure_result_record(
    tournament: Tournament,
    *,
    now: datetime,
) -> TournamentResult:
    if tournament.result is not None:
        return tournament.result

    started_at = now

    if tournament.runtime is not None:
        started_at = (
            tournament.runtime.created_at
            or now
        )

    result = TournamentResult(
        tournament=tournament,
        started_at=started_at,
    )

    db.session.add(
        result
    )

    db.session.flush()

    return result


def complete_tournament(
    tournament: Tournament,
    *,
    now: datetime | None = None,
) -> TournamentPlayer:
    if tournament.status not in (
        "RUNNING",
        "PAUSED",
    ):
        raise CompletionError(
            "Endast en pågående eller pausad turnering kan avslutas."
        )

    current_time = (
        now or utc_now()
    )

    winner = get_winner(
        tournament
    )

    first_prize = get_first_prize(
        tournament
    )

    result = ensure_result_record(
        tournament,
        now=current_time,
    )

    if tournament.runtime is not None:
        remaining_seconds = (
            get_remaining_seconds(
                tournament,
                now=current_time,
            )
        )

        tournament.runtime.remaining_seconds_when_paused = (
            remaining_seconds
        )

        tournament.runtime.timer_started_at = None

    winner.placement = 1
    winner.prize_winnings = first_prize

    retained_bounty = 0

    if tournament.bounty_enabled:
        retained_bounty = (
            tournament.bounty_amount
        )

        winner.bounty_winnings += (
            retained_bounty
        )

    started_at = normalize_datetime(
        result.started_at
    )

    completed_at = normalize_datetime(
        current_time
    )

    duration_seconds = max(
        0,
        int(
            (
                completed_at
                - started_at
            ).total_seconds()
        ),
    )

    result.winner_entry = winner
    result.completed_at = current_time
    result.duration_seconds = (
        duration_seconds
    )
    result.winner_retained_bounty = (
        retained_bounty
    )
    result.status_before_completion = (
        tournament.status
    )

    tournament.status = "COMPLETED"

    db.session.add(
        TournamentEvent(
            tournament=tournament,
            event_type="TOURNAMENT_COMPLETED",
            message=(
                f"Tournament completed — "
                f"{winner.player.name} wins"
            ),
        )
    )

    db.session.commit()

    return winner


def reopen_completed_tournament(
    tournament: Tournament,
    *,
    now: datetime | None = None,
) -> None:
    if tournament.status != "COMPLETED":
        return

    result = tournament.result

    if result is None:
        raise CompletionError(
            "Turneringen saknar resultatdata."
        )

    winner = result.winner_entry

    if winner is not None:
        winner.placement = None
        winner.prize_winnings = 0

        winner.bounty_winnings = max(
            0,
            winner.bounty_winnings
            - result.winner_retained_bounty,
        )

    restored_status = (
        result.status_before_completion
        if result.status_before_completion
        in (
            "RUNNING",
            "PAUSED",
        )
        else "PAUSED"
    )

    tournament.status = (
        restored_status
    )

    if tournament.runtime is not None:
        if restored_status == "RUNNING":
            tournament.runtime.timer_started_at = (
                now or utc_now()
            )
        else:
            tournament.runtime.timer_started_at = None

    result.winner_entry = None
    result.completed_at = None
    result.duration_seconds = None
    result.winner_retained_bounty = 0
    result.status_before_completion = None

    db.session.add(
        TournamentEvent(
            tournament=tournament,
            event_type="TOURNAMENT_REOPENED",
            message=(
                "Tournament completion was undone"
            ),
        )
    )

    db.session.flush()