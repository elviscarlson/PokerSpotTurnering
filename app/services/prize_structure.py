from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PrizeSuggestion:
    place: int
    amount: int
    percentage: float


PAYOUT_WEIGHTS: dict[int, tuple[float, ...]] = {
    1: (
        1.00,
    ),
    2: (
        0.65,
        0.35,
    ),
    3: (
        0.55,
        0.30,
        0.15,
    ),
    4: (
        0.50,
        0.27,
        0.15,
        0.08,
    ),
    5: (
        0.45,
        0.25,
        0.15,
        0.10,
        0.05,
    ),
}


def suggest_paid_places(
    number_of_players: int,
) -> int:
    """
    Suggest a relatively top-heavy number of paid places.

    Philosophy:
    - Tiny fields should not pay too many places.
    - Larger private tournaments gradually add paid positions.
    - Never pay an unreasonable share of the field.
    """
    if number_of_players < 2:
        raise ValueError(
            "A tournament requires at least two players."
        )

    if number_of_players <= 3:
        return 1

    if number_of_players <= 6:
        return 2

    if number_of_players <= 10:
        return 3

    if number_of_players <= 15:
        return 4

    return 5


def payout_weights(
    paid_places: int,
) -> tuple[float, ...]:
    try:
        return PAYOUT_WEIGHTS[paid_places]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported number of paid places: {paid_places}"
        ) from exc


def choose_rounding_increment(
    prize_pool: int,
) -> int:
    """
    Prefer poker-night-friendly payout amounts.

    Exact conservation of money always has higher priority than
    perfect rounding.
    """
    if prize_pool < 500:
        return 10

    if prize_pool < 2_000:
        return 50

    return 100


def round_to_increment(
    amount: float,
    increment: int,
) -> int:
    return int(
        round(amount / increment)
        * increment
    )


def generate_payout_amounts(
    *,
    prize_pool: int,
    paid_places: int,
) -> list[int]:
    if prize_pool <= 0:
        raise ValueError(
            "Prize pool must be greater than zero."
        )

    weights = payout_weights(
        paid_places
    )

    increment = choose_rounding_increment(
        prize_pool
    )

    raw_amounts = [
        prize_pool * weight
        for weight in weights
    ]

    amounts = [
        round_to_increment(
            amount,
            increment,
        )
        for amount in raw_amounts
    ]

    difference = (
        prize_pool
        - sum(amounts)
    )

    # The specification explicitly prefers assigning small
    # rounding differences to first prize.
    amounts[0] += difference

    if any(amount <= 0 for amount in amounts):
        raise ValueError(
            "Prize pool is too small for the selected payout structure."
        )

    if amounts != sorted(
        amounts,
        reverse=True,
    ):
        raise ValueError(
            "Generated payout structure is not descending."
        )

    if sum(amounts) != prize_pool:
        raise AssertionError(
            "Payout generation violated the prize-pool invariant."
        )

    return amounts


def generate_payout_structure(
    *,
    prize_pool: int,
    number_of_players: int,
) -> list[PrizeSuggestion]:
    paid_places = suggest_paid_places(
        number_of_players
    )

    amounts = generate_payout_amounts(
        prize_pool=prize_pool,
        paid_places=paid_places,
    )

    suggestions = []

    for index, amount in enumerate(
        amounts,
        start=1,
    ):
        suggestions.append(
            PrizeSuggestion(
                place=index,
                amount=amount,
                percentage=(
                    amount
                    / prize_pool
                    * 100
                ),
            )
        )

    assert (
        sum(
            suggestion.amount
            for suggestion in suggestions
        )
        == prize_pool
    )

    return suggestions