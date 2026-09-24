from __future__ import annotations

from dataclasses import dataclass


CHIP_DENOMINATIONS = (
    1,
    5,
    10,
    25,
    100,
    500,
    1000,
)


@dataclass(frozen=True)
class ChipAllocation:
    denomination: int
    count: int

    @property
    def value(self) -> int:
        return self.denomination * self.count


def suggest_starting_stack(
    *,
    number_of_players: int,
    target_duration_minutes: int,
) -> int:
    """
    Suggest a practical starting stack.

    Longer tournaments receive deeper stacks.
    Larger fields get a small additional depth adjustment.
    """
    if number_of_players < 2:
        raise ValueError(
            "At least two players are required."
        )

    if target_duration_minutes <= 0:
        raise ValueError(
            "Target duration must be greater than zero."
        )

    if target_duration_minutes <= 180:
        stack = 10_000
    elif target_duration_minutes <= 270:
        stack = 15_000
    elif target_duration_minutes <= 360:
        stack = 20_000
    else:
        stack = 25_000

    if (
        number_of_players >= 12
        and target_duration_minutes >= 240
    ):
        stack += 5_000

    return stack


def generate_chip_breakdown(
    starting_stack: int,
) -> list[ChipAllocation]:
    """
    Build an exact starting stack using the available denominations.

    The default structure assumes early blinds around 25/50,
    so 1, 5 and 10 chips are intentionally omitted.
    """
    if starting_stack < 5_000:
        raise ValueError(
            "Starting stack must be at least 5,000."
        )

    if starting_stack % 100 != 0:
        raise ValueError(
            "Starting stack must be divisible by 100."
        )

    allocations: list[ChipAllocation] = []

    # 8 × 25 = 200
    allocations.append(
        ChipAllocation(
            denomination=25,
            count=8,
        )
    )

    # 8 × 100 = 800
    allocations.append(
        ChipAllocation(
            denomination=100,
            count=8,
        )
    )

    remaining = (
        starting_stack
        - 1_000
    )

    if starting_stack >= 20_000:
        five_hundred_count = 8
    else:
        five_hundred_count = 6

    five_hundred_value = (
        five_hundred_count
        * 500
    )

    if five_hundred_value > remaining:
        five_hundred_count = (
            remaining // 500
        )

        five_hundred_value = (
            five_hundred_count
            * 500
        )

    if five_hundred_count:
        allocations.append(
            ChipAllocation(
                denomination=500,
                count=five_hundred_count,
            )
        )

    remaining -= five_hundred_value

    thousand_count = (
        remaining // 1000
    )

    if thousand_count:
        allocations.append(
            ChipAllocation(
                denomination=1000,
                count=thousand_count,
            )
        )

    remaining -= (
        thousand_count
        * 1000
    )

    if remaining:
        raise ValueError(
            "Could not generate an exact chip breakdown."
        )

    if (
        sum(
            allocation.value
            for allocation in allocations
        )
        != starting_stack
    ):
        raise AssertionError(
            "Chip breakdown does not equal starting stack."
        )

    return allocations


def chip_breakdown_as_dict(
    starting_stack: int,
) -> dict[str, int]:
    return {
        str(allocation.denomination): allocation.count
        for allocation in generate_chip_breakdown(
            starting_stack
        )
    }