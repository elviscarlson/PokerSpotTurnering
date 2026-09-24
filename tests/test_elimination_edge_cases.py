from datetime import date

import pytest

from app.extensions import db
from app.models import Player
from app.services.clock_service import (
    start_clock,
)
from app.services.player_elimination import (
    EliminationError,
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


def build_tournament(
    *,
    bounty_enabled: bool = True,
):
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
        name="Elimination Edge",
        tournament_date=date.today(),
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

    return tournament


def test_player_cannot_be_eliminated_twice(
    app,
):
    with app.app_context():
        tournament = (
            build_tournament(
                bounty_enabled=False
            )
        )

        target = (
            tournament.players[0]
        )

        eliminate_player(
            tournament=tournament,
            entry_id=target.id,
        )

        with pytest.raises(
            EliminationError
        ):
            eliminate_player(
                tournament=tournament,
                entry_id=target.id,
            )


def test_player_cannot_eliminate_self(
    app,
):
    with app.app_context():
        tournament = (
            build_tournament()
        )

        target = (
            tournament.players[0]
        )

        with pytest.raises(
            EliminationError
        ):
            eliminate_player(
                tournament=tournament,
                entry_id=target.id,
                eliminated_by_entry_id=(
                    target.id
                ),
            )


def test_eliminated_player_cannot_receive_later_bounty(
    app,
):
    with app.app_context():
        tournament = (
            build_tournament()
        )

        first = (
            tournament.players[0]
        )

        second = (
            tournament.players[1]
        )

        active_killer = (
            tournament.players[2]
        )

        eliminate_player(
            tournament=tournament,
            entry_id=first.id,
            eliminated_by_entry_id=(
                active_killer.id
            ),
        )

        with pytest.raises(
            EliminationError
        ):
            eliminate_player(
                tournament=tournament,
                entry_id=second.id,
                eliminated_by_entry_id=(
                    first.id
                ),
            )


def test_only_latest_elimination_can_be_restored(
    app,
):
    with app.app_context():
        tournament = (
            build_tournament(
                bounty_enabled=False
            )
        )

        first = (
            tournament.players[0]
        )

        second = (
            tournament.players[1]
        )

        eliminate_player(
            tournament=tournament,
            entry_id=first.id,
        )

        eliminate_player(
            tournament=tournament,
            entry_id=second.id,
        )

        with pytest.raises(
            EliminationError
        ):
            restore_last_elimination(
                tournament=tournament,
                entry_id=first.id,
            )


def test_undo_restores_placement_sequence(
    app,
):
    with app.app_context():
        tournament = (
            build_tournament(
                bounty_enabled=False
            )
        )

        first = (
            tournament.players[0]
        )

        second = (
            tournament.players[1]
        )

        eliminate_player(
            tournament=tournament,
            entry_id=first.id,
        )

        eliminate_player(
            tournament=tournament,
            entry_id=second.id,
        )

        assert first.placement == 4
        assert second.placement == 3

        restore_last_elimination(
            tournament=tournament,
            entry_id=second.id,
        )

        assert (
            second.placement
            is None
        )

        assert (
            second.status
            == "ACTIVE"
        )

        eliminate_player(
            tournament=tournament,
            entry_id=second.id,
        )

        assert second.placement == 3