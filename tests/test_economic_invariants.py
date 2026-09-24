from datetime import date

import pytest

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
from app.services.tournament_service import (
    create_tournament,
)
from app.services.tournament_structure import (
    ensure_tournament_structure,
)


@pytest.mark.parametrize(
    (
        "player_count",
        "buy_in",
        "bounty_amount",
    ),
    [
        (
            2,
            300,
            50,
        ),
        (
            5,
            300,
            50,
        ),
        (
            8,
            500,
            100,
        ),
        (
            12,
            250,
            25,
        ),
    ],
)
def test_prize_and_bounty_pool_equal_total_buyins(
    app,
    player_count,
    buy_in,
    bounty_amount,
):
    with app.app_context():
        players = [
            Player(
                name=(
                    f"Player {index}"
                ),
                name_key=(
                    f"player {index}"
                ),
            )
            for index in range(
                player_count
            )
        ]

        db.session.add_all(
            players
        )

        db.session.commit()

        tournament = create_tournament(
            name="Invariant Test",
            tournament_date=date.today(),
            target_duration_minutes=240,
            buy_in=buy_in,
            bounty_enabled=True,
            bounty_amount=(
                bounty_amount
            ),
            player_ids=[
                player.id
                for player in players
            ],
        )

        assert (
            tournament.total_prizes
            == tournament.regular_prize_pool
        )

        assert (
            tournament.total_prizes
            + tournament.bounty_pool
            == tournament.total_buyins
        )


def test_completed_bounty_tournament_accounts_for_every_crown(
    app,
):
    with app.app_context():
        players = [
            Player(
                name=name,
                name_key=name.casefold(),
            )
            for name in [
                "Elvis",
                "Hugo",
                "Leo",
                "Elias",
            ]
        ]

        db.session.add_all(
            players
        )

        db.session.commit()

        tournament = create_tournament(
            name="Accounting Test",
            tournament_date=date.today(),
            target_duration_minutes=180,
            buy_in=300,
            bounty_enabled=True,
            bounty_amount=50,
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

        winner = (
            tournament.players[0]
        )

        while (
            tournament.active_player_count
            > 1
        ):
            victim = next(
                entry
                for entry
                in tournament.players
                if (
                    entry.status
                    == "ACTIVE"
                    and entry.id
                    != winner.id
                )
            )

            eliminate_player(
                tournament=tournament,
                entry_id=victim.id,
                eliminated_by_entry_id=(
                    winner.id
                ),
            )

        assert (
            tournament.status
            == "COMPLETED"
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


def test_non_bounty_tournament_prizes_equal_all_buyins(
    app,
):
    with app.app_context():
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
        ]

        db.session.add_all(
            players
        )

        db.session.commit()

        tournament = create_tournament(
            name="No Bounty",
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

        assert (
            tournament.regular_prize_pool
            == tournament.total_buyins
        )

        assert (
            tournament.total_prizes
            == tournament.total_buyins
        )