import pytest

from app.extensions import db
from app.models import (
    BlindLevel,
    Player,
    Prize,
    Tournament,
    TournamentPlayer,
    TournamentStructure,
)
from app.services.setup_service import (
    SetupError,
    mark_tournament_ready,
    save_manual_setup,
    validate_blind_levels,
    validate_payouts,
)


def build_tournament() -> Tournament:
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

    tournament = Tournament(
        name="Friday Poker",
        target_duration_minutes=240,
        buy_in=300,
        bounty_enabled=True,
        bounty_amount=50,
    )

    for player in players:
        tournament.players.append(
            TournamentPlayer(
                player=player,
            )
        )

    tournament.prizes.extend(
        [
            Prize(
                place=1,
                amount=800,
            ),
            Prize(
                place=2,
                amount=450,
            ),
        ]
    )

    structure = TournamentStructure(
        starting_stack=15_000,
        chip_breakdown={
            "25": 8,
            "100": 8,
            "500": 6,
            "1000": 11,
        },
        level_duration_minutes=15,
        estimated_duration_min_minutes=204,
        estimated_duration_max_minutes=276,
    )

    structure.blind_levels.extend(
        [
            BlindLevel(
                position=1,
                small_blind=25,
                big_blind=50,
                duration_seconds=900,
            ),
            BlindLevel(
                position=2,
                small_blind=50,
                big_blind=100,
                duration_seconds=900,
            ),
            BlindLevel(
                position=3,
                small_blind=75,
                big_blind=150,
                duration_seconds=900,
            ),
        ]
    )

    tournament.structure = (
        structure
    )

    db.session.add(
        tournament
    )

    db.session.commit()

    return tournament


def test_valid_payouts(
    app,
):
    with app.app_context():
        tournament = (
            build_tournament()
        )

        payouts = validate_payouts(
            tournament=tournament,
            payouts=[
                750,
                500,
            ],
        )

        assert payouts == [
            750,
            500,
        ]


def test_payout_total_must_match_pool(
    app,
):
    with app.app_context():
        tournament = (
            build_tournament()
        )

        with pytest.raises(
            SetupError
        ):
            validate_payouts(
                tournament=tournament,
                payouts=[
                    900,
                    500,
                ],
            )


def test_payouts_must_descend(
    app,
):
    with app.app_context():
        tournament = (
            build_tournament()
        )

        with pytest.raises(
            SetupError
        ):
            validate_payouts(
                tournament=tournament,
                payouts=[
                    500,
                    750,
                ],
            )


def test_blinds_must_increase():
    with pytest.raises(
        SetupError
    ):
        validate_blind_levels(
            [
                (
                    25,
                    50,
                    15,
                ),
                (
                    20,
                    40,
                    15,
                ),
            ]
        )


def test_save_manual_setup(
    app,
):
    with app.app_context():
        tournament = (
            build_tournament()
        )

        save_manual_setup(
            tournament=tournament,
            starting_stack=20_000,
            payouts=[
                750,
                500,
            ],
            blind_levels=[
                (
                    25,
                    50,
                    12,
                ),
                (
                    50,
                    100,
                    12,
                ),
                (
                    100,
                    200,
                    15,
                ),
            ],
        )

        assert (
            tournament.structure.starting_stack
            == 20_000
        )

        assert [
            prize.amount
            for prize in (
                tournament.prizes
            )
        ] == [
            750,
            500,
        ]

        levels = (
            tournament.structure
            .blind_levels
        )

        assert len(levels) == 3

        assert (
            levels[2].small_blind
            == 100
        )

        assert (
            levels[2].big_blind
            == 200
        )

        assert (
            levels[2].duration_minutes
            == 15
        )

        assert (
            tournament.status
            == "DRAFT"
        )


def test_ready_status(
    app,
):
    with app.app_context():
        tournament = (
            build_tournament()
        )

        mark_tournament_ready(
            tournament
        )

        assert (
            tournament.status
            == "READY"
        )