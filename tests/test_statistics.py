from datetime import date

from app.extensions import db
from app.models import Player
from app.services.clock_service import (
    start_clock,
)
from app.services.player_elimination import (
    eliminate_player,
)
from app.services.setup_service import (
    mark_tournament_ready,
)
from app.services.statistics import (
    bounty_leaderboard,
    calculate_dashboard_statistics,
    calculate_player_statistics,
    winnings_leaderboard,
    wins_leaderboard,
)
from app.services.tournament_service import (
    create_tournament,
)
from app.services.tournament_structure import (
    ensure_tournament_structure,
)


def create_players():
    players = [
        Player(
            name=name,
            name_key=name.casefold(),
        )
        for name in [
            "Elvis",
            "Hugo",
            "Leo",
        ]
    ]

    db.session.add_all(
        players
    )

    db.session.commit()

    return players


def complete_three_player_tournament(
    players,
    *,
    bounty_enabled: bool = False,
):
    tournament = create_tournament(
        name="Statistics Test",
        tournament_date=date(
            2026,
            9,
            24,
        ),
        target_duration_minutes=180,
        buy_in=300,
        bounty_enabled=(
            bounty_enabled
        ),
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

    start_clock(
        tournament
    )

    elvis = tournament.players[0]
    hugo = tournament.players[1]
    leo = tournament.players[2]

    if bounty_enabled:
        eliminate_player(
            tournament=tournament,
            entry_id=leo.id,
            eliminated_by_entry_id=(
                elvis.id
            ),
        )

        eliminate_player(
            tournament=tournament,
            entry_id=hugo.id,
            eliminated_by_entry_id=(
                elvis.id
            ),
        )
    else:
        eliminate_player(
            tournament=tournament,
            entry_id=leo.id,
        )

        eliminate_player(
            tournament=tournament,
            entry_id=hugo.id,
        )

    return tournament


def test_player_statistics(
    app,
):
    with app.app_context():
        players = create_players()

        complete_three_player_tournament(
            players
        )

        stat = (
            calculate_player_statistics(
                players[0]
            )
        )

        assert stat.tournaments == 1
        assert stat.wins == 1
        assert stat.itm_finishes == 1

        assert (
            stat.total_buyins
            == 300
        )

        assert (
            stat.prize_winnings
            > 0
        )

        assert (
            stat.net_result
            ==
            stat.total_winnings
            - stat.total_buyins
        )


def test_itm_percentage(
    app,
):
    with app.app_context():
        players = create_players()

        complete_three_player_tournament(
            players
        )

        winner = (
            calculate_player_statistics(
                players[0]
            )
        )

        assert (
            winner.itm_percentage
            == 100.0
        )


def test_bounty_statistics_include_retained_winner_bounty(
    app,
):
    with app.app_context():
        players = create_players()

        tournament = (
            complete_three_player_tournament(
                players,
                bounty_enabled=True,
            )
        )

        stat = (
            calculate_player_statistics(
                players[0]
            )
        )

        assert (
            stat.bounty_winnings
            == tournament.bounty_pool
        )

        assert (
            stat.bounty_count
            == 3
        )


def test_incomplete_tournament_does_not_count(
    app,
):
    with app.app_context():
        players = create_players()

        tournament = create_tournament(
            name="Draft",
            tournament_date=date(
                2026,
                9,
                24,
            ),
            target_duration_minutes=180,
            buy_in=300,
            bounty_enabled=False,
            bounty_amount=0,
            player_ids=[
                player.id
                for player in players
            ],
        )

        assert (
            tournament.status
            == "DRAFT"
        )

        stat = (
            calculate_player_statistics(
                players[0]
            )
        )

        assert stat.tournaments == 0
        assert stat.total_buyins == 0
        assert stat.net_result == 0


def test_dashboard_statistics(
    app,
):
    with app.app_context():
        players = create_players()

        tournament = (
            complete_three_player_tournament(
                players
            )
        )

        dashboard = (
            calculate_dashboard_statistics()
        )

        assert (
            dashboard.completed_tournaments
            == 1
        )

        assert (
            dashboard.total_players
            == 3
        )

        assert (
            dashboard.latest_tournament.id
            == tournament.id
        )

        assert (
            dashboard.total_money_played
            == 900
        )


def test_winnings_leaderboard(
    app,
):
    with app.app_context():
        players = create_players()

        complete_three_player_tournament(
            players
        )

        leaderboard = (
            winnings_leaderboard()
        )

        assert leaderboard

        assert (
            leaderboard[0].player.name
            == "Elvis"
        )


def test_wins_leaderboard(
    app,
):
    with app.app_context():
        players = create_players()

        complete_three_player_tournament(
            players
        )

        leaderboard = (
            wins_leaderboard()
        )

        assert (
            leaderboard[0].wins
            == 1
        )


def test_bounty_leaderboard(
    app,
):
    with app.app_context():
        players = create_players()

        complete_three_player_tournament(
            players,
            bounty_enabled=True,
        )

        leaderboard = (
            bounty_leaderboard()
        )

        assert (
            leaderboard[0]
            .player.name
            == "Elvis"
        )

        assert (
            leaderboard[0]
            .bounty_count
            == 3
        )