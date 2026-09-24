import pytest

from app.services.blind_structure import (
    calculate_total_chips,
    choose_level_duration,
    generate_blind_structure,
    required_blind_levels,
    target_final_big_blind,
)


def test_total_chips():
    assert (
        calculate_total_chips(
            number_of_players=8,
            starting_stack=20_000,
        )
        == 160_000
    )


def test_target_final_big_blind():
    assert (
        target_final_big_blind(
            100_000
        )
        == 5_000
    )


def test_required_structure_starts_25_50():
    levels = required_blind_levels(
        total_chips=100_000
    )

    assert levels[0] == (
        25,
        50,
    )


def test_required_structure_reaches_target():
    total_chips = 160_000

    levels = required_blind_levels(
        total_chips=total_chips
    )

    assert (
        levels[-1][1]
        >= target_final_big_blind(
            total_chips
        )
    )


@pytest.mark.parametrize(
    (
        "target",
        "levels",
        "expected",
    ),
    [
        (240, 16, 15),
        (300, 16, 18),
        (360, 18, 20),
    ],
)
def test_level_duration_selection(
    target,
    levels,
    expected,
):
    assert (
        choose_level_duration(
            target_duration_minutes=target,
            number_of_levels=levels,
        )
        == expected
    )


def test_generated_structure_has_no_blind_regressions():
    structure = (
        generate_blind_structure(
            number_of_players=8,
            starting_stack=20_000,
            target_duration_minutes=240,
        )
    )

    previous_small = 0
    previous_big = 0

    for level in structure.levels:
        assert (
            level.small_blind
            > previous_small
        )

        assert (
            level.big_blind
            > previous_big
        )

        previous_small = (
            level.small_blind
        )

        previous_big = (
            level.big_blind
        )


def test_generated_structure_uses_same_level_time():
    structure = (
        generate_blind_structure(
            number_of_players=5,
            starting_stack=15_000,
            target_duration_minutes=240,
        )
    )

    assert all(
        level.duration_minutes
        == structure.level_duration_minutes
        for level in structure.levels
    )


def test_estimated_duration_is_range():
    structure = (
        generate_blind_structure(
            number_of_players=5,
            starting_stack=15_000,
            target_duration_minutes=240,
        )
    )

    assert (
        structure.estimated_duration_min_minutes
        <
        structure.estimated_duration_max_minutes
    )


def test_invalid_player_count():
    with pytest.raises(ValueError):
        calculate_total_chips(
            number_of_players=1,
            starting_stack=20_000,
        )