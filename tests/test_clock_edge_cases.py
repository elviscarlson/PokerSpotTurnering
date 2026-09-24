from datetime import (
    date,
    datetime,
    timedelta,
    timezone,
)

import pytest

from app.extensions import db
from app.models import Player
from app.services.clock_service import (
    ClockError,
    adjust_time,
    get_remaining_seconds,
    move_level,
    pause_clock,
    resume_clock,
    serialize_clock_state,
    start_clock,
)
from app.services.setup_service import (
    mark_tournament_ready,
)
from app.services.tournament_service import (
    create_tournament,
)
from app.services.tournament_structure import (
    ensure_tournament_structure,
)


def build_ready_tournament():
    players = [
        Player(
            name="Elvis",
            name_key="elvis",
        ),
        Player(
            name="Hugo",
            name_key="hugo",
        ),
    ]

    db.session.add_all(
        players
    )

    db.session.commit()

    tournament = create_tournament(
        name="Clock Edge Test",
        tournament_date=date.today(),
        target_duration_minutes=180,
        buy_in=300,
        bounty_enabled=False,
        bounty_amount=0,
        player_ids=[
            player.id
            for player in players
        ],
    )

    ensure_tournament_structure(
        tournament
    )

    mark_tournament_ready(
        tournament
    )

    return tournament


def test_clock_cannot_start_twice(
    app,
):
    with app.app_context():
        tournament = (
            build_ready_tournament()
        )

        start_clock(
            tournament
        )

        with pytest.raises(
            ClockError
        ):
            start_clock(
                tournament
            )


def test_ready_clock_cannot_be_paused(
    app,
):
    with app.app_context():
        tournament = (
            build_ready_tournament()
        )

        with pytest.raises(
            ClockError
        ):
            pause_clock(
                tournament
            )


def test_running_clock_cannot_resume(
    app,
):
    with app.app_context():
        tournament = (
            build_ready_tournament()
        )

        start_clock(
            tournament
        )

        with pytest.raises(
            ClockError
        ):
            resume_clock(
                tournament
            )


def test_time_cannot_be_adjusted_before_start(
    app,
):
    with app.app_context():
        tournament = (
            build_ready_tournament()
        )

        with pytest.raises(
            ClockError
        ):
            adjust_time(
                tournament,
                delta_seconds=60,
            )


def test_large_negative_adjustment_never_creates_negative_time(
    app,
):
    with app.app_context():
        tournament = (
            build_ready_tournament()
        )

        now = datetime(
            2026,
            9,
            24,
            18,
            0,
            tzinfo=timezone.utc,
        )

        levels = (
            tournament.structure
            .blind_levels
        )

        first_level = levels[0]
        second_level = levels[1]

        start_clock(
            tournament,
            now=now,
        )

        assert (
            tournament.runtime
            .current_level_position
            == first_level.position
        )

        adjust_time(
            tournament,
            delta_seconds=-100_000,
            now=now,
        )

        state = serialize_clock_state(
            tournament,
            now=now,
        )

        assert (
            state["remaining_seconds"]
            >= 0
        )

        assert (
            state[
                "current_level"
            ][
                "position"
            ]
            == second_level.position
        )

        assert (
            state["remaining_seconds"]
            == second_level.duration_seconds
        )


def test_clock_can_advance_multiple_levels_after_long_offline_period(
    app,
):
    with app.app_context():
        tournament = (
            build_ready_tournament()
        )

        levels = (
            tournament.structure
            .blind_levels
        )

        assert len(levels) >= 3

        start = datetime(
            2026,
            9,
            24,
            18,
            0,
            tzinfo=timezone.utc,
        )

        elapsed = (
            levels[0].duration_seconds
            + levels[1].duration_seconds
            + 10
        )

        start_clock(
            tournament,
            now=start,
        )

        state = serialize_clock_state(
            tournament,
            now=(
                start
                + timedelta(
                    seconds=elapsed
                )
            ),
        )

        assert (
            state[
                "current_level"
            ][
                "position"
            ]
            == levels[2].position
        )

        assert (
            state[
                "remaining_seconds"
            ]
            ==
            levels[2].duration_seconds
            - 10
        )


def test_final_level_never_advances_beyond_structure(
    app,
):
    with app.app_context():
        tournament = (
            build_ready_tournament()
        )

        start = datetime(
            2026,
            9,
            24,
            18,
            0,
            tzinfo=timezone.utc,
        )

        start_clock(
            tournament,
            now=start,
        )

        levels = (
            tournament.structure
            .blind_levels
        )

        for _ in range(
            len(levels) - 1
        ):
            move_level(
                tournament,
                direction=1,
                now=start,
            )

        assert (
            tournament.runtime
            .current_level_position
            == levels[-1].position
        )

        with pytest.raises(
            ClockError
        ):
            move_level(
                tournament,
                direction=1,
                now=start,
            )


def test_previous_level_is_blocked_at_first_level(
    app,
):
    with app.app_context():
        tournament = (
            build_ready_tournament()
        )

        start_clock(
            tournament
        )

        with pytest.raises(
            ClockError
        ):
            move_level(
                tournament,
                direction=-1,
            )