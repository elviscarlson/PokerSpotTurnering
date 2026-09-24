from datetime import date

from app.extensions import db
from app.models import (
    Player,
    Tournament,
)
from app.services.clock_service import (
    pause_clock,
    resume_clock,
    start_clock,
)
from app.services.player_elimination import (
    eliminate_player,
)
from app.services.setup_service import (
    mark_tournament_ready,
)
from app.services.statistics import (
    calculate_player_statistics,
)
from app.services.tournament_service import (
    create_tournament,
)
from app.services.tournament_structure import (
    ensure_tournament_structure,
)


def test_complete_tournament_flow(
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
                "Philip",
            ]
        ]

        db.session.add_all(
            players
        )

        db.session.commit()


        tournament = create_tournament(
            name="Full Flow",
            tournament_date=date.today(),
            target_duration_minutes=240,
            buy_in=300,
            bounty_enabled=True,
            bounty_amount=50,
            player_ids=[
                player.id
                for player in players
            ],
        )


        assert (
            tournament.status
            == "DRAFT"
        )

        assert (
            tournament.player_count
            == 5
        )

        assert (
            tournament.total_buyins
            == 1500
        )

        assert (
            tournament.bounty_pool
            == 250
        )

        assert (
            tournament.regular_prize_pool
            == 1250
        )

        assert (
            tournament.total_prizes
            == 1250
        )


        ensure_tournament_structure(
            tournament
        )

        assert (
            tournament.structure
            is not None
        )

        assert (
            len(
                tournament.structure
                .blind_levels
            )
            > 0
        )


        mark_tournament_ready(
            tournament
        )

        assert (
            tournament.status
            == "READY"
        )


        start_clock(
            tournament
        )

        assert (
            tournament.status
            == "RUNNING"
        )


        pause_clock(
            tournament
        )

        assert (
            tournament.status
            == "PAUSED"
        )


        resume_clock(
            tournament
        )

        assert (
            tournament.status
            == "RUNNING"
        )


        entries = {
            entry.player.name:
                entry
            for entry
            in tournament.players
        }

        elvis = entries[
            "Elvis"
        ]

        hugo = entries[
            "Hugo"
        ]

        leo = entries[
            "Leo"
        ]

        elias = entries[
            "Elias"
        ]

        philip = entries[
            "Philip"
        ]


        eliminate_player(
            tournament=tournament,
            entry_id=philip.id,
            eliminated_by_entry_id=(
                hugo.id
            ),
        )

        assert philip.placement == 5

        assert (
            tournament.active_player_count
            == 4
        )


        eliminate_player(
            tournament=tournament,
            entry_id=elias.id,
            eliminated_by_entry_id=(
                elvis.id
            ),
        )

        assert elias.placement == 4


        eliminate_player(
            tournament=tournament,
            entry_id=leo.id,
            eliminated_by_entry_id=(
                elvis.id
            ),
        )

        assert leo.placement == 3


        eliminate_player(
            tournament=tournament,
            entry_id=hugo.id,
            eliminated_by_entry_id=(
                elvis.id
            ),
        )


        assert hugo.placement == 2

        assert (
            tournament.status
            == "COMPLETED"
        )

        assert (
            elvis.placement
            == 1
        )

        assert (
            tournament.winner.id
            == elvis.id
        )

        assert (
            tournament.active_player_count
            == 1
        )


        placements = sorted(
            entry.placement
            for entry
            in tournament.players
        )

        assert placements == [
            1,
            2,
            3,
            4,
            5,
        ]


        assert (
            tournament.total_prizes
            == tournament.regular_prize_pool
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


        assert (
            tournament.result
            is not None
        )

        assert (
            tournament.result.completed_at
            is not None
        )

        assert (
            tournament.result.winner_entry_id
            == elvis.id
        )


        elvis_stats = (
            calculate_player_statistics(
                players[0]
            )
        )

        assert (
            elvis_stats.tournaments
            == 1
        )

        assert (
            elvis_stats.wins
            == 1
        )

        assert (
            elvis_stats.itm_finishes
            == 1
        )

        assert (
            elvis_stats.total_buyins
            == 300
        )

        assert (
            elvis_stats.net_result
            ==
            elvis_stats.total_winnings
            - 300
        )


        db.session.expire_all()

        persisted = (
            db.session.get(
                Tournament,
                tournament.id,
            )
        )

        assert persisted is not None

        assert (
            persisted.status
            == "COMPLETED"
        )

        assert (
            persisted.winner
            is not None
        )

        assert (
            persisted.winner.player.name
            == "Elvis"
        )