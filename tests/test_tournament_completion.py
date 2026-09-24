from datetime import (
    date,
    datetime,
    timedelta,
    timezone,
)

from app.extensions import db
from app.models import (
    Player,
    Tournament,
    TournamentEvent,
    TournamentResult,
)
from app.services.clock_service import (
    start_clock,
)
from app.services.player_elimination import (
    eliminate_player,
    restore_last_elimination,
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


def build_two_player_tournament(
    *,
    bounty_enabled: bool = False,
) -> Tournament:
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
        name="Heads Up Final",
        tournament_date=date(
            2026,
            9,
            25,
        ),
        target_duration_minutes=180,
        buy_in=300,
        bounty_enabled=bounty_enabled,
        bounty_amount=(
            50
            if bounty_enabled
            else 0
        ),
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


def test_last_player_becomes_winner(
    app,
):
    with app.app_context():
        tournament = (
            build_two_player_tournament()
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

        loser = tournament.players[1]

        eliminate_player(
            tournament=tournament,
            entry_id=loser.id,
            now=(
                start
                + timedelta(
                    minutes=90
                )
            ),
        )

        winner = tournament.players[0]

        assert (
            tournament.status
            == "COMPLETED"
        )

        assert winner.placement == 1
        assert loser.placement == 2

        assert (
            winner.prize_winnings
            == tournament.regular_prize_pool
        )


def test_result_metadata_is_saved(
    app,
):
    with app.app_context():
        tournament = (
            build_two_player_tournament()
        )

        start = datetime(
            2026,
            9,
            24,
            18,
            0,
            tzinfo=timezone.utc,
        )

        finish = (
            start
            + timedelta(
                hours=2,
                minutes=13,
            )
        )

        start_clock(
            tournament,
            now=start,
        )

        eliminate_player(
            tournament=tournament,
            entry_id=(
                tournament.players[1].id
            ),
            now=finish,
        )

        result = tournament.result

        assert result is not None

        assert (
            result.duration_seconds
            == (
                2 * 60 * 60
                + 13 * 60
            )
        )

        assert (
            result.winner_entry_id
            == tournament.players[0].id
        )


def test_bounty_pool_is_fully_distributed(
    app,
):
    with app.app_context():
        tournament = (
            build_two_player_tournament(
                bounty_enabled=True
            )
        )

        start_clock(
            tournament
        )

        winner = tournament.players[0]
        loser = tournament.players[1]

        eliminate_player(
            tournament=tournament,
            entry_id=loser.id,
            eliminated_by_entry_id=(
                winner.id
            ),
        )

        assert (
            winner.bounty_winnings
            == 100
        )

        assert (
            tournament.total_bounty_winnings
            == tournament.bounty_pool
        )

        assert (
            tournament.total_prizes
            + tournament.total_bounty_winnings
            == tournament.total_buyins
        )


def test_completion_freezes_clock(
    app,
):
    with app.app_context():
        tournament = (
            build_two_player_tournament()
        )

        start_clock(
            tournament
        )

        eliminate_player(
            tournament=tournament,
            entry_id=(
                tournament.players[1].id
            ),
        )

        assert (
            tournament.runtime.timer_started_at
            is None
        )


def test_completion_creates_event(
    app,
):
    with app.app_context():
        tournament = (
            build_two_player_tournament()
        )

        start_clock(
            tournament
        )

        eliminate_player(
            tournament=tournament,
            entry_id=(
                tournament.players[1].id
            ),
        )

        completed_event = (
            db.session.scalar(
                db.select(
                    TournamentEvent
                )
                .where(
                    TournamentEvent.event_type
                    == "TOURNAMENT_COMPLETED"
                )
            )
        )

        assert completed_event is not None

        assert (
            "wins"
            in completed_event.message
        )


def test_completion_result_is_persisted(
    app,
):
    with app.app_context():
        tournament = (
            build_two_player_tournament()
        )

        start_clock(
            tournament
        )

        tournament_id = (
            tournament.id
        )

        eliminate_player(
            tournament=tournament,
            entry_id=(
                tournament.players[1].id
            ),
        )

        db.session.expire_all()

        result = db.session.scalar(
            db.select(
                TournamentResult
            )
            .where(
                TournamentResult.tournament_id
                == tournament_id
            )
        )

        assert result is not None

        assert (
            result.completed_at
            is not None
        )


def test_last_elimination_can_be_undone(
    app,
):
    with app.app_context():
        tournament = (
            build_two_player_tournament(
                bounty_enabled=True
            )
        )

        start_clock(
            tournament
        )

        winner = tournament.players[0]
        loser = tournament.players[1]

        eliminate_player(
            tournament=tournament,
            entry_id=loser.id,
            eliminated_by_entry_id=(
                winner.id
            ),
        )

        assert (
            tournament.status
            == "COMPLETED"
        )

        restore_last_elimination(
            tournament=tournament,
            entry_id=loser.id,
        )

        assert (
            tournament.status
            in (
                "RUNNING",
                "PAUSED",
            )
        )

        assert winner.placement is None
        assert loser.placement is None

        assert (
            loser.status
            == "ACTIVE"
        )

        assert (
            winner.bounty_winnings
            == 0
        )

        assert (
            tournament.result.completed_at
            is None
        )