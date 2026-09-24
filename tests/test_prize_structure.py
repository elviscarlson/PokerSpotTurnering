import pytest

from app.services.prize_structure import (
    choose_rounding_increment,
    generate_payout_amounts,
    generate_payout_structure,
    suggest_paid_places,
)


@pytest.mark.parametrize(
    (
        "players",
        "expected",
    ),
    [
        (2, 1),
        (3, 1),
        (4, 2),
        (6, 2),
        (7, 3),
        (10, 3),
        (11, 4),
        (15, 4),
        (16, 5),
        (25, 5),
    ],
)
def test_suggest_paid_places(
    players,
    expected,
):
    assert (
        suggest_paid_places(players)
        == expected
    )


def test_two_player_payout():
    payouts = generate_payout_structure(
        prize_pool=600,
        number_of_players=2,
    )

    assert len(payouts) == 1

    assert payouts[0].amount == 600


def test_five_player_payout():
    payouts = generate_payout_structure(
        prize_pool=1_250,
        number_of_players=5,
    )

    assert len(payouts) == 2

    assert [
        payout.amount
        for payout in payouts
    ] == [
        800,
        450,
    ]


def test_nine_player_payout():
    payouts = generate_payout_structure(
        prize_pool=2_250,
        number_of_players=9,
    )

    assert len(payouts) == 3

    assert sum(
        payout.amount
        for payout in payouts
    ) == 2_250


@pytest.mark.parametrize(
    (
        "prize_pool",
        "player_count",
    ),
    [
        (400, 2),
        (600, 3),
        (1_000, 4),
        (1_250, 5),
        (1_800, 6),
        (2_100, 7),
        (2_400, 8),
        (2_700, 9),
        (3_000, 10),
        (4_500, 12),
        (6_000, 15),
        (9_000, 20),
    ],
)
def test_prize_pool_is_always_conserved(
    prize_pool,
    player_count,
):
    payouts = generate_payout_structure(
        prize_pool=prize_pool,
        number_of_players=player_count,
    )

    assert (
        sum(
            payout.amount
            for payout in payouts
        )
        == prize_pool
    )


@pytest.mark.parametrize(
    (
        "prize_pool",
        "player_count",
    ),
    [
        (600, 2),
        (1_200, 4),
        (1_500, 5),
        (2_400, 8),
        (3_000, 10),
        (5_000, 15),
        (10_000, 20),
    ],
)
def test_payouts_are_descending(
    prize_pool,
    player_count,
):
    payouts = generate_payout_structure(
        prize_pool=prize_pool,
        number_of_players=player_count,
    )

    amounts = [
        payout.amount
        for payout in payouts
    ]

    assert amounts == sorted(
        amounts,
        reverse=True,
    )


def test_rounding_increment_small_pool():
    assert (
        choose_rounding_increment(400)
        == 10
    )


def test_rounding_increment_medium_pool():
    assert (
        choose_rounding_increment(1_250)
        == 50
    )


def test_rounding_increment_large_pool():
    assert (
        choose_rounding_increment(3_000)
        == 100
    )


def test_invalid_player_count():
    with pytest.raises(ValueError):
        suggest_paid_places(1)


def test_invalid_prize_pool():
    with pytest.raises(ValueError):
        generate_payout_amounts(
            prize_pool=0,
            paid_places=2,
        )