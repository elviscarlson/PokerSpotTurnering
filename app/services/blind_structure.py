from __future__ import annotations

from dataclasses import dataclass
from math import ceil


@dataclass(frozen=True)
class BlindLevelSuggestion:
    position: int
    small_blind: int
    big_blind: int
    duration_minutes: int


@dataclass(frozen=True)
class BlindStructureSuggestion:
    level_duration_minutes: int
    levels: tuple[BlindLevelSuggestion, ...]
    estimated_duration_min_minutes: int
    estimated_duration_max_minutes: int


NATURAL_BLIND_LEVELS: tuple[
    tuple[int, int],
    ...,
] = (
    (25, 50),
    (50, 100),
    (75, 150),
    (100, 200),
    (150, 300),
    (200, 400),
    (300, 600),
    (400, 800),
    (500, 1000),
    (600, 1200),
    (800, 1600),
    (1000, 2000),
    (1500, 3000),
    (2000, 4000),
    (2500, 5000),
    (3000, 6000),
    (4000, 8000),
    (5000, 10000),
    (6000, 12000),
    (8000, 16000),
    (10000, 20000),
    (15000, 30000),
    (20000, 40000),
    (25000, 50000),
)


ALLOWED_LEVEL_DURATIONS = (
    12,
    15,
    18,
    20,
)


def calculate_total_chips(
    *,
    number_of_players: int,
    starting_stack: int,
) -> int:
    if number_of_players < 2:
        raise ValueError(
            "At least two players are required."
        )

    if starting_stack <= 0:
        raise ValueError(
            "Starting stack must be greater than zero."
        )

    return (
        number_of_players
        * starting_stack
    )


def target_final_big_blind(
    total_chips: int,
) -> int:
    """
    Estimate a blind level sufficiently aggressive for the
    tournament to approach its conclusion.

    Near heads-up, an average stack of roughly 10 big blinds
    corresponds approximately to total_chips / 20.
    """
    if total_chips <= 0:
        raise ValueError(
            "Total chips must be greater than zero."
        )

    return max(
        1000,
        ceil(
            total_chips
            / 20
        ),
    )


def required_blind_levels(
    *,
    total_chips: int,
) -> tuple[
    tuple[int, int],
    ...,
]:
    required_big_blind = (
        target_final_big_blind(
            total_chips
        )
    )

    selected: list[
        tuple[int, int]
    ] = []

    for small_blind, big_blind in NATURAL_BLIND_LEVELS:
        selected.append(
            (
                small_blind,
                big_blind,
            )
        )

        if big_blind >= required_big_blind:
            break

    if (
        selected[-1][1]
        < required_big_blind
    ):
        raise ValueError(
            "Blind level catalogue is not deep enough."
        )

    return tuple(
        selected
    )


def choose_level_duration(
    *,
    target_duration_minutes: int,
    number_of_levels: int,
) -> int:
    if target_duration_minutes <= 0:
        raise ValueError(
            "Target duration must be greater than zero."
        )

    if number_of_levels <= 0:
        raise ValueError(
            "Number of levels must be greater than zero."
        )

    raw_duration = (
        target_duration_minutes
        / number_of_levels
    )

    return min(
        ALLOWED_LEVEL_DURATIONS,
        key=lambda value: abs(
            value
            - raw_duration
        ),
    )


def estimate_duration_range(
    *,
    number_of_levels: int,
    level_duration_minutes: int,
) -> tuple[int, int]:
    nominal_duration = (
        number_of_levels
        * level_duration_minutes
    )

    lower = round(
        nominal_duration
        * 0.85
    )

    upper = round(
        nominal_duration
        * 1.15
    )

    return (
        lower,
        upper,
    )


def generate_blind_structure(
    *,
    number_of_players: int,
    starting_stack: int,
    target_duration_minutes: int,
) -> BlindStructureSuggestion:
    total_chips = (
        calculate_total_chips(
            number_of_players=number_of_players,
            starting_stack=starting_stack,
        )
    )

    blind_pairs = (
        required_blind_levels(
            total_chips=total_chips,
        )
    )

    level_duration = (
        choose_level_duration(
            target_duration_minutes=(
                target_duration_minutes
            ),
            number_of_levels=len(
                blind_pairs
            ),
        )
    )

    levels = tuple(
        BlindLevelSuggestion(
            position=index,
            small_blind=small_blind,
            big_blind=big_blind,
            duration_minutes=(
                level_duration
            ),
        )
        for index, (
            small_blind,
            big_blind,
        ) in enumerate(
            blind_pairs,
            start=1,
        )
    )

    (
        estimated_min,
        estimated_max,
    ) = estimate_duration_range(
        number_of_levels=len(
            levels
        ),
        level_duration_minutes=(
            level_duration
        ),
    )

    return BlindStructureSuggestion(
        level_duration_minutes=(
            level_duration
        ),
        levels=levels,
        estimated_duration_min_minutes=(
            estimated_min
        ),
        estimated_duration_max_minutes=(
            estimated_max
        ),
    )