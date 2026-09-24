from app.extensions import db
from app.models import (
    Player,
    Tournament,
    TournamentPlayer,
)
from app.services.tournament_structure import (
    ensure_tournament_structure,
)


def test_structure_is_created(
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

        tournament = Tournament(
            name="Friday Poker",
            target_duration_minutes=240,
            buy_in=300,
            bounty_enabled=False,
            bounty_amount=0,
        )

        for player in players:
            tournament.players.append(
                TournamentPlayer(
                    player=player,
                )
            )

        db.session.add(
            tournament
        )

        db.session.commit()

        structure = (
            ensure_tournament_structure(
                tournament
            )
        )

        assert structure is not None

        assert (
            structure.starting_stack
            == 15_000
        )

        assert (
            structure.total_chips
            == 75_000
        )

        assert (
            len(
                structure.blind_levels
            )
            > 0
        )


def test_structure_is_not_duplicated(
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
        ]

        db.session.add_all(
            players
        )

        tournament = Tournament(
            name="Heads Up",
            target_duration_minutes=180,
            buy_in=300,
        )

        for player in players:
            tournament.players.append(
                TournamentPlayer(
                    player=player,
                )
            )

        db.session.add(
            tournament
        )

        db.session.commit()

        first = (
            ensure_tournament_structure(
                tournament
            )
        )

        first_id = first.id

        second = (
            ensure_tournament_structure(
                tournament
            )
        )

        assert (
            second.id
            == first_id
        )