from datetime import date

from app.extensions import db
from app.models import Player
from app.services.clock_service import start_clock
from app.services.player_elimination import (
    eliminate_player,
    restore_last_elimination,
)
from app.services.reentry_service import (
    register_reentry,
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
        name="Re-entry Test",
        tournament_date=date.today(),
        target_duration_minutes=240,
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

    start_clock(
        tournament
    )

    return tournament


def test_reentry_increases_buyin_count(
    app,
):
    with app.app_context():
        tournament = (
            build_tournament(
                bounty_enabled=False
            )
        )

        hugo = tournament.players[1]

        eliminate_player(
            tournament=tournament,
            entry_id=hugo.id,
        )

        assert hugo.status == "ELIMINATED"
        assert hugo.buy_in_count == 1

        register_reentry(
            tournament=tournament,
            entry_id=hugo.id,
        )

        assert hugo.status == "ACTIVE"
        assert hugo.placement is None
        assert hugo.buy_in_count == 2


def test_reentry_increases_total_buyins(
    app,
):
    with app.app_context():
        tournament = (
            build_tournament(
                bounty_enabled=False
            )
        )

        hugo = tournament.players[1]

        assert tournament.total_entries == 4
        assert tournament.total_buyins == 1200

        eliminate_player(
            tournament=tournament,
            entry_id=hugo.id,
        )

        register_reentry(
            tournament=tournament,
            entry_id=hugo.id,
        )

        assert tournament.total_entries == 5
        assert tournament.total_buyins == 1500


def test_bounty_reentry_updates_both_pools(
    app,
):
    with app.app_context():
        tournament = (
            build_tournament()
        )

        elvis = tournament.players[0]
        hugo = tournament.players[1]

        assert tournament.total_buyins == 1200
        assert tournament.regular_prize_pool == 1000
        assert tournament.bounty_pool == 200

        eliminate_player(
            tournament=tournament,
            entry_id=hugo.id,
            eliminated_by_entry_id=elvis.id,
        )

        register_reentry(
            tournament=tournament,
            entry_id=hugo.id,
        )

        assert tournament.total_entries == 5
        assert tournament.total_buyins == 1500
        assert tournament.regular_prize_pool == 1250
        assert tournament.bounty_pool == 250


def test_previous_bounty_survives_reentry(
    app,
):
    with app.app_context():
        tournament = (
            build_tournament()
        )

        elvis = tournament.players[0]
        hugo = tournament.players[1]

        eliminate_player(
            tournament=tournament,
            entry_id=hugo.id,
            eliminated_by_entry_id=elvis.id,
        )

        assert elvis.bounty_winnings == 50
        assert len(hugo.elimination_bounties) == 1

        register_reentry(
            tournament=tournament,
            entry_id=hugo.id,
        )

        assert elvis.bounty_winnings == 50
        assert len(hugo.elimination_bounties) == 1


def test_same_player_can_be_eliminated_twice(
    app,
):
    with app.app_context():
        tournament = (
            build_tournament()
        )

        elvis = tournament.players[0]
        hugo = tournament.players[1]
        leo = tournament.players[2]

        eliminate_player(
            tournament=tournament,
            entry_id=hugo.id,
            eliminated_by_entry_id=elvis.id,
        )

        register_reentry(
            tournament=tournament,
            entry_id=hugo.id,
        )

        eliminate_player(
            tournament=tournament,
            entry_id=hugo.id,
            eliminated_by_entry_id=leo.id,
        )

        assert hugo.elimination_count == 2

        assert len(
            hugo.elimination_bounties
        ) == 2

        numbers = [
            bounty.elimination_number
            for bounty
            in hugo.elimination_bounties
        ]

        assert numbers == [
            1,
            2,
        ]

        assert elvis.bounty_winnings == 50
        assert leo.bounty_winnings == 50


def test_undo_second_elimination_keeps_first_bounty(
    app,
):
    with app.app_context():
        tournament = (
            build_tournament()
        )

        elvis = tournament.players[0]
        hugo = tournament.players[1]
        leo = tournament.players[2]

        eliminate_player(
            tournament=tournament,
            entry_id=hugo.id,
            eliminated_by_entry_id=elvis.id,
        )

        register_reentry(
            tournament=tournament,
            entry_id=hugo.id,
        )

        eliminate_player(
            tournament=tournament,
            entry_id=hugo.id,
            eliminated_by_entry_id=leo.id,
        )

        assert hugo.elimination_count == 2

        restore_last_elimination(
            tournament=tournament,
            entry_id=hugo.id,
        )

        assert hugo.status == "ACTIVE"
        assert hugo.elimination_count == 1

        assert len(
            hugo.elimination_bounties
        ) == 1

        assert (
            hugo.elimination_bounties[0]
            .elimination_number
            == 1
        )

        assert elvis.bounty_winnings == 50
        assert leo.bounty_winnings == 0


def test_reentry_recalculates_prizes(
    app,
):
    with app.app_context():
        tournament = (
            build_tournament()
        )

        elvis = tournament.players[0]
        hugo = tournament.players[1]

        old_pool = (
            tournament.regular_prize_pool
        )

        old_prizes = sum(
            prize.amount
            for prize in tournament.prizes
        )

        assert old_prizes == old_pool

        eliminate_player(
            tournament=tournament,
            entry_id=hugo.id,
            eliminated_by_entry_id=elvis.id,
        )

        register_reentry(
            tournament=tournament,
            entry_id=hugo.id,
        )

        assert (
            tournament.regular_prize_pool
            == old_pool + 250
        )

        assert (
            sum(
                prize.amount
                for prize
                in tournament.prizes
            )
            ==
            tournament.regular_prize_pool
        )


def test_reentry_adds_starting_stack_to_total_chips(
    app,
):
    with app.app_context():
        tournament = (
            build_tournament(
                bounty_enabled=False
            )
        )

        hugo = tournament.players[1]

        starting_stack = (
            tournament.structure
            .starting_stack
        )

        old_chips = (
            tournament.structure
            .total_chips
        )

        eliminate_player(
            tournament=tournament,
            entry_id=hugo.id,
        )

        register_reentry(
            tournament=tournament,
            entry_id=hugo.id,
        )

        assert (
            tournament.structure.total_chips
            ==
            old_chips
            + starting_stack
        )