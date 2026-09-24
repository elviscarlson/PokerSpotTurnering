import pytest

from app.services.chip_structure import (
    generate_chip_breakdown,
    suggest_starting_stack,
)


@pytest.mark.parametrize(
    (
        "players",
        "duration",
        "expected",
    ),
    [
        (5, 150, 10_000),
        (5, 180, 10_000),
        (5, 240, 15_000),
        (5, 300, 20_000),
        (5, 360, 20_000),
        (5, 420, 25_000),
        (12, 240, 20_000),
        (12, 360, 25_000),
    ],
)
def test_starting_stack_suggestion(
    players,
    duration,
    expected,
):
    assert (
        suggest_starting_stack(
            number_of_players=players,
            target_duration_minutes=duration,
        )
        == expected
    )


@pytest.mark.parametrize(
    "starting_stack",
    [
        10_000,
        15_000,
        20_000,
        25_000,
        30_000,
    ],
)
def test_chip_breakdown_equals_stack(
    starting_stack,
):
    breakdown = (
        generate_chip_breakdown(
            starting_stack
        )
    )

    assert (
        sum(
            allocation.value
            for allocation in breakdown
        )
        == starting_stack
    )


def test_twenty_thousand_breakdown():
    breakdown = (
        generate_chip_breakdown(
            20_000
        )
    )

    values = {
        allocation.denomination: (
            allocation.count
        )
        for allocation in breakdown
    }

    assert values == {
        25: 8,
        100: 8,
        500: 8,
        1000: 15,
    }


def test_small_unused_denominations_are_omitted():
    breakdown = (
        generate_chip_breakdown(
            20_000
        )
    )

    denominations = {
        allocation.denomination
        for allocation in breakdown
    }

    assert 1 not in denominations
    assert 5 not in denominations
    assert 10 not in denominations


def test_invalid_stack_is_rejected():
    with pytest.raises(ValueError):
        generate_chip_breakdown(
            4_000
        )