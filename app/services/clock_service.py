from __future__ import annotations

from datetime import datetime, timezone
from math import floor

from app.extensions import db
from app.models import (
    BlindLevel,
    Tournament,
    TournamentEvent,
    TournamentResult,
    TournamentRuntime,
)


class ClockError(ValueError):
    pass


def utc_now() -> datetime:
    return datetime.now(
        timezone.utc
    )


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


def get_levels(
    tournament: Tournament,
) -> list[BlindLevel]:
    if tournament.structure is None:
        raise ClockError(
            "Turneringsstrukturen saknas."
        )

    levels = list(
        tournament.structure.blind_levels
    )

    if not levels:
        raise ClockError(
            "Turneringen saknar blindnivåer."
        )

    return levels


def get_level(
    tournament: Tournament,
    position: int,
) -> BlindLevel:
    levels = get_levels(
        tournament
    )

    for level in levels:
        if level.position == position:
            return level

    raise ClockError(
        "Aktuell blindnivå kunde inte hittas."
    )


def ensure_runtime(
    tournament: Tournament,
) -> TournamentRuntime:
    if tournament.runtime is not None:
        return tournament.runtime

    first_level = get_levels(
        tournament
    )[0]

    runtime = TournamentRuntime(
        tournament=tournament,
        current_level_position=(
            first_level.position
        ),
        timer_started_at=None,
        remaining_seconds_when_paused=(
            first_level.duration_seconds
        ),
    )

    db.session.add(
        runtime
    )

    db.session.commit()

    return runtime


def calculate_running_state(
    *,
    tournament: Tournament,
    runtime: TournamentRuntime,
    now: datetime,
) -> tuple[int, int]:
    levels = get_levels(
        tournament
    )

    levels_by_position = {
        level.position: level
        for level in levels
    }

    if runtime.timer_started_at is None:
        return (
            runtime.current_level_position,
            runtime.remaining_seconds_when_paused,
        )

    started_at = normalize_datetime(
        runtime.timer_started_at
    )

    now = normalize_datetime(
        now
    )

    elapsed_seconds = max(
        0,
        floor(
            (
                now
                - started_at
            ).total_seconds()
        ),
    )

    current_position = (
        runtime.current_level_position
    )

    remaining = (
        runtime.remaining_seconds_when_paused
        - elapsed_seconds
    )

    last_position = (
        levels[-1].position
    )

    while (
        remaining <= 0
        and current_position < last_position
    ):
        overrun = -remaining

        current_position += 1

        next_level = (
            levels_by_position[
                current_position
            ]
        )

        remaining = (
            next_level.duration_seconds
            - overrun
        )

    return (
        current_position,
        max(
            0,
            remaining,
        ),
    )


def sync_clock(
    tournament: Tournament,
    *,
    now: datetime | None = None,
) -> TournamentRuntime:
    runtime = ensure_runtime(
        tournament
    )

    if tournament.status != "RUNNING":
        return runtime

    current_time = (
        now or utc_now()
    )

    (
        calculated_position,
        calculated_remaining,
    ) = calculate_running_state(
        tournament=tournament,
        runtime=runtime,
        now=current_time,
    )

    if (
        calculated_position
        != runtime.current_level_position
    ):
        runtime.current_level_position = (
            calculated_position
        )

        runtime.remaining_seconds_when_paused = (
            calculated_remaining
        )

        runtime.timer_started_at = (
            current_time
        )

        db.session.commit()

    return runtime


def get_remaining_seconds(
    tournament: Tournament,
    *,
    now: datetime | None = None,
) -> int:
    runtime = ensure_runtime(
        tournament
    )

    if tournament.status != "RUNNING":
        return max(
            0,
            runtime.remaining_seconds_when_paused,
        )

    (
        _,
        remaining,
    ) = calculate_running_state(
        tournament=tournament,
        runtime=runtime,
        now=now or utc_now(),
    )

    return remaining


def start_clock(
    tournament: Tournament,
    *,
    now: datetime | None = None,
) -> TournamentRuntime:
    if tournament.status != "READY":
        raise ClockError(
            "Turneringen måste vara READY innan den kan startas."
        )

    current_time = (
        now or utc_now()
    )

    runtime = ensure_runtime(
        tournament
    )

    first_level = get_levels(
        tournament
    )[0]

    runtime.current_level_position = (
        first_level.position
    )

    runtime.remaining_seconds_when_paused = (
        first_level.duration_seconds
    )

    runtime.timer_started_at = (
        current_time
    )

    if tournament.result is None:
        db.session.add(
            TournamentResult(
                tournament=tournament,
                started_at=current_time,
            )
        )
    else:
        tournament.result.started_at = (
            current_time
        )

        tournament.result.completed_at = None
        tournament.result.duration_seconds = None
        tournament.result.winner_entry = None
        tournament.result.winner_retained_bounty = 0
        tournament.result.status_before_completion = None

    tournament.status = "RUNNING"

    db.session.add(
        TournamentEvent(
            tournament=tournament,
            event_type="TOURNAMENT_STARTED",
            message="Tournament started",
        )
    )

    db.session.commit()

    return runtime


def pause_clock(
    tournament: Tournament,
    *,
    now: datetime | None = None,
) -> TournamentRuntime:
    if tournament.status != "RUNNING":
        raise ClockError(
            "Endast en pågående turnering kan pausas."
        )

    runtime = ensure_runtime(
        tournament
    )

    current_time = (
        now or utc_now()
    )

    (
        current_position,
        remaining,
    ) = calculate_running_state(
        tournament=tournament,
        runtime=runtime,
        now=current_time,
    )

    runtime.current_level_position = (
        current_position
    )

    runtime.remaining_seconds_when_paused = (
        remaining
    )

    runtime.timer_started_at = None

    tournament.status = "PAUSED"

    db.session.commit()

    return runtime


def resume_clock(
    tournament: Tournament,
    *,
    now: datetime | None = None,
) -> TournamentRuntime:
    if tournament.status != "PAUSED":
        raise ClockError(
            "Endast en pausad turnering kan återupptas."
        )

    runtime = ensure_runtime(
        tournament
    )

    runtime.timer_started_at = (
        now or utc_now()
    )

    tournament.status = "RUNNING"

    db.session.commit()

    return runtime


def move_level(
    tournament: Tournament,
    *,
    direction: int,
    now: datetime | None = None,
) -> TournamentRuntime:
    if direction not in (
        -1,
        1,
    ):
        raise ClockError(
            "Ogiltig level-riktning."
        )

    if tournament.status not in (
        "RUNNING",
        "PAUSED",
    ):
        raise ClockError(
            "Turneringen måste vara startad."
        )

    runtime = sync_clock(
        tournament,
        now=now,
    )

    levels = get_levels(
        tournament
    )

    positions = [
        level.position
        for level in levels
    ]

    try:
        current_index = positions.index(
            runtime.current_level_position
        )
    except ValueError as exc:
        raise ClockError(
            "Aktuell blindnivå är ogiltig."
        ) from exc

    new_index = (
        current_index
        + direction
    )

    if not (
        0
        <= new_index
        < len(levels)
    ):
        raise ClockError(
            "Det finns ingen blindnivå i den riktningen."
        )

    new_level = levels[
        new_index
    ]

    runtime.current_level_position = (
        new_level.position
    )

    runtime.remaining_seconds_when_paused = (
        new_level.duration_seconds
    )

    if tournament.status == "RUNNING":
        runtime.timer_started_at = (
            now or utc_now()
        )
    else:
        runtime.timer_started_at = None

    db.session.commit()

    return runtime


def adjust_time(
    tournament: Tournament,
    *,
    delta_seconds: int,
    now: datetime | None = None,
) -> TournamentRuntime:
    if tournament.status not in (
        "RUNNING",
        "PAUSED",
    ):
        raise ClockError(
            "Turneringen måste vara startad."
        )

    current_time = (
        now or utc_now()
    )

    runtime = ensure_runtime(
        tournament
    )

    if tournament.status == "RUNNING":
        (
            current_position,
            remaining,
        ) = calculate_running_state(
            tournament=tournament,
            runtime=runtime,
            now=current_time,
        )

        runtime.current_level_position = (
            current_position
        )
    else:
        remaining = (
            runtime.remaining_seconds_when_paused
        )

    runtime.remaining_seconds_when_paused = max(
        0,
        remaining
        + delta_seconds,
    )

    if tournament.status == "RUNNING":
        runtime.timer_started_at = (
            current_time
        )
    else:
        runtime.timer_started_at = None

    db.session.commit()

    return runtime


def reset_current_level(
    tournament: Tournament,
    *,
    now: datetime | None = None,
) -> TournamentRuntime:
    if tournament.status not in (
        "RUNNING",
        "PAUSED",
    ):
        raise ClockError(
            "Turneringen måste vara startad."
        )

    runtime = sync_clock(
        tournament,
        now=now,
    )

    level = get_level(
        tournament,
        runtime.current_level_position,
    )

    runtime.remaining_seconds_when_paused = (
        level.duration_seconds
    )

    if tournament.status == "RUNNING":
        runtime.timer_started_at = (
            now or utc_now()
        )
    else:
        runtime.timer_started_at = None

    db.session.commit()

    return runtime


def serialize_clock_state(
    tournament: Tournament,
    *,
    now: datetime | None = None,
) -> dict:
    current_time = (
        now or utc_now()
    )

    runtime = sync_clock(
        tournament,
        now=current_time,
    )

    current_level = get_level(
        tournament,
        runtime.current_level_position,
    )

    levels = get_levels(
        tournament
    )

    current_index = next(
        index
        for index, level in enumerate(levels)
        if (
            level.position
            == current_level.position
        )
    )

    next_level = None

    if (
        current_index + 1
        < len(levels)
    ):
        next_level = levels[
            current_index + 1
        ]

    remaining_seconds = (
        get_remaining_seconds(
            tournament,
            now=current_time,
        )
    )

    player_data = []

    for entry in tournament.players:
        bounty_count = 0

        if (
            tournament.bounty_enabled
            and tournament.bounty_amount > 0
        ):
            bounty_count = (
                entry.bounty_winnings
                // tournament.bounty_amount
            )

        player_data.append(
            {
                "entry_id": entry.id,
                "player_id": entry.player_id,
                "name": entry.player.name,
                "status": entry.status,
                "placement": entry.placement,
                "prize_winnings": (
                    entry.prize_winnings
                ),
                "bounty_winnings": (
                    entry.bounty_winnings
                ),
                "bounty_count": bounty_count,
                "total_winnings": (
                    entry.total_winnings
                ),
            }
        )

    upcoming_levels = [
        {
            "position": level.position,
            "small_blind": (
                level.small_blind
            ),
            "big_blind": (
                level.big_blind
            ),
            "duration_seconds": (
                level.duration_seconds
            ),
        }
        for level in levels[
            current_index:
            current_index + 5
        ]
    ]

    payouts = [
        {
            "place": prize.place,
            "amount": prize.amount,
        }
        for prize in tournament.prizes
    ]

    recent_events = sorted(
        tournament.events,
        key=lambda event: event.created_at,
        reverse=True,
    )[:10]

    events = [
        {
            "id": event.id,
            "type": event.event_type,
            "message": event.message,
            "created_at": (
                event.created_at.isoformat()
            ),
        }
        for event in recent_events
    ]

    winner = tournament.winner

    return {
        "tournament_id": tournament.id,
        "name": tournament.name,
        "status": tournament.status,
        "server_time": (
            current_time
            .astimezone(timezone.utc)
            .isoformat()
        ),
        "current_level": {
            "position": (
                current_level.position
            ),
            "small_blind": (
                current_level.small_blind
            ),
            "big_blind": (
                current_level.big_blind
            ),
            "duration_seconds": (
                current_level.duration_seconds
            ),
        },
        "next_level": (
            {
                "position": (
                    next_level.position
                ),
                "small_blind": (
                    next_level.small_blind
                ),
                "big_blind": (
                    next_level.big_blind
                ),
                "duration_seconds": (
                    next_level.duration_seconds
                ),
            }
            if next_level
            else None
        ),
        "remaining_seconds": (
            remaining_seconds
        ),
        "players_total": (
            tournament.player_count
        ),
        "players_remaining": (
            tournament.active_player_count
        ),
        "players": player_data,
        "payouts": payouts,
        "upcoming_levels": upcoming_levels,
        "events": events,
        "winner": (
            {
                "entry_id": winner.id,
                "player_id": winner.player_id,
                "name": winner.player.name,
                "prize_winnings": (
                    winner.prize_winnings
                ),
                "bounty_winnings": (
                    winner.bounty_winnings
                ),
                "total_winnings": (
                    winner.total_winnings
                ),
            }
            if winner is not None
            else None
        ),
        "bounty_enabled": (
            tournament.bounty_enabled
        ),
        "bounty_amount": (
            tournament.bounty_amount
        ),
        "prize_pool": (
            tournament.regular_prize_pool
        ),
        "bounty_pool": (
            tournament.bounty_pool
        ),
        "total_bounty_winnings": (
            tournament.total_bounty_winnings
        ),
    }