from datetime import (
    date,
    datetime,
    timedelta,
    timezone,
)

from app.extensions import db
from app.models import Player
from app.services.clock_service import (
    adjust_time,
    get_remaining_seconds,
    move_level,
    pause_clock,
    reset_current_level,
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
        Player(
            name="Leo",
            name_key="leo",
        ),
        Player(
            name="Elias",
            name_key="elias",
        ),
        Player(
            name="Philip",
            name_key="philip",
        ),
    ]

    db.session.add_all(
        players
    )

    db.session.commit()

    tournament = create_tournament(
        name="Friday Poker",
        tournament_date=date(
            2026,
            9,
            25,
        ),
        target_duration_minutes=240,
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


def test_start_clock(
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

        start_clock(
            tournament,
            now=now,
        )

        assert (
            tournament.status
            == "RUNNING"
        )

        assert (
            tournament.runtime
            .current_level_position
            == 1
        )


def test_running_clock_counts_down(
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

        duration = (
            tournament.structure
            .blind_levels[0]
            .duration_seconds
        )

        remaining = (
            get_remaining_seconds(
                tournament,
                now=(
                    start
                    + timedelta(
                        seconds=37
                    )
                ),
            )
        )

        assert (
            remaining
            == duration - 37
        )


def test_pause_freezes_clock(
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

        pause_clock(
            tournament,
            now=(
                start
                + timedelta(
                    seconds=30
                )
            ),
        )

        paused_remaining = (
            tournament.runtime
            .remaining_seconds_when_paused
        )

        later_remaining = (
            get_remaining_seconds(
                tournament,
                now=(
                    start
                    + timedelta(
                        minutes=10
                    )
                ),
            )
        )

        assert (
            later_remaining
            == paused_remaining
        )

        assert (
            tournament.status
            == "PAUSED"
        )


def test_resume_continues_from_paused_time(
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

        pause_clock(
            tournament,
            now=(
                start
                + timedelta(
                    seconds=60
                )
            ),
        )

        paused_remaining = (
            tournament.runtime
            .remaining_seconds_when_paused
        )

        resume_time = (
            start
            + timedelta(
                minutes=5
            )
        )

        resume_clock(
            tournament,
            now=resume_time,
        )

        remaining = (
            get_remaining_seconds(
                tournament,
                now=(
                    resume_time
                    + timedelta(
                        seconds=20
                    )
                ),
            )
        )

        assert (
            remaining
            == paused_remaining - 20
        )


def test_clock_automatically_advances_level(
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

        first_duration = (
            tournament.structure
            .blind_levels[0]
            .duration_seconds
        )

        start_clock(
            tournament,
            now=start,
        )

        state = (
            serialize_clock_state(
                tournament,
                now=(
                    start
                    + timedelta(
                        seconds=(
                            first_duration
                            + 5
                        )
                    )
                ),
            )
        )

        assert (
            state[
                "current_level"
            ][
                "position"
            ]
            == 2
        )

        second_duration = (
            tournament.structure
            .blind_levels[1]
            .duration_seconds
        )

        assert (
            state[
                "remaining_seconds"
            ]
            == second_duration - 5
        )


def test_next_level_resets_timer(
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

        start_clock(
            tournament,
            now=now,
        )

        move_level(
            tournament,
            direction=1,
            now=(
                now
                + timedelta(
                    seconds=20
                )
            ),
        )

        assert (
            tournament.runtime
            .current_level_position
            == 2
        )

        assert (
            tournament.runtime
            .remaining_seconds_when_paused
            ==
            tournament.structure
            .blind_levels[1]
            .duration_seconds
        )


def test_adjust_time(
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

        start_clock(
            tournament,
            now=now,
        )

        original = (
            tournament.runtime
            .remaining_seconds_when_paused
        )

        adjust_time(
            tournament,
            delta_seconds=300,
            now=now,
        )

        assert (
            tournament.runtime
            .remaining_seconds_when_paused
            == original + 300
        )


def test_reset_level(
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

        start_clock(
            tournament,
            now=now,
        )

        adjust_time(
            tournament,
            delta_seconds=-300,
            now=now,
        )

        reset_current_level(
            tournament,
            now=now,
        )

        expected = (
            tournament.structure
            .blind_levels[0]
            .duration_seconds
        )

        assert (
            tournament.runtime
            .remaining_seconds_when_paused
            == expected
        )