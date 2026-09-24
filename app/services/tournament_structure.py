from __future__ import annotations

from app.extensions import db
from app.models import (
    BlindLevel,
    Tournament,
    TournamentStructure,
)
from app.services.blind_structure import (
    generate_blind_structure,
)
from app.services.chip_structure import (
    chip_breakdown_as_dict,
    suggest_starting_stack,
)


def generate_structure_values(
    tournament: Tournament,
) -> tuple[
    int,
    dict[str, int],
    object,
]:
    starting_stack = (
        suggest_starting_stack(
            number_of_players=(
                tournament.player_count
            ),
            target_duration_minutes=(
                tournament.target_duration_minutes
            ),
        )
    )

    chip_breakdown = (
        chip_breakdown_as_dict(
            starting_stack
        )
    )

    blind_suggestion = (
        generate_blind_structure(
            number_of_players=(
                tournament.player_count
            ),
            starting_stack=starting_stack,
            target_duration_minutes=(
                tournament.target_duration_minutes
            ),
        )
    )

    return (
        starting_stack,
        chip_breakdown,
        blind_suggestion,
    )


def ensure_tournament_structure(
    tournament: Tournament,
) -> TournamentStructure:
    if tournament.structure is not None:
        return tournament.structure

    (
        starting_stack,
        chip_breakdown,
        blind_suggestion,
    ) = generate_structure_values(
        tournament
    )

    structure = TournamentStructure(
        tournament=tournament,
        starting_stack=starting_stack,
        chip_breakdown=chip_breakdown,
        level_duration_minutes=(
            blind_suggestion
            .level_duration_minutes
        ),
        estimated_duration_min_minutes=(
            blind_suggestion
            .estimated_duration_min_minutes
        ),
        estimated_duration_max_minutes=(
            blind_suggestion
            .estimated_duration_max_minutes
        ),
    )

    for level in (
        blind_suggestion.levels
    ):
        structure.blind_levels.append(
            BlindLevel(
                position=level.position,
                small_blind=(
                    level.small_blind
                ),
                big_blind=(
                    level.big_blind
                ),
                duration_seconds=(
                    level.duration_minutes
                    * 60
                ),
            )
        )

    db.session.add(
        structure
    )

    db.session.commit()

    return structure


def regenerate_tournament_structure(
    tournament: Tournament,
) -> TournamentStructure:
    (
        starting_stack,
        chip_breakdown,
        blind_suggestion,
    ) = generate_structure_values(
        tournament
    )

    structure = (
        ensure_tournament_structure(
            tournament
        )
    )

    structure.starting_stack = (
        starting_stack
    )

    structure.chip_breakdown = (
        chip_breakdown
    )

    structure.level_duration_minutes = (
        blind_suggestion
        .level_duration_minutes
    )

    structure.estimated_duration_min_minutes = (
        blind_suggestion
        .estimated_duration_min_minutes
    )

    structure.estimated_duration_max_minutes = (
        blind_suggestion
        .estimated_duration_max_minutes
    )

    for level in list(
        structure.blind_levels
    ):
        db.session.delete(
            level
        )

    db.session.flush()

    for level in (
        blind_suggestion.levels
    ):
        structure.blind_levels.append(
            BlindLevel(
                position=level.position,
                small_blind=(
                    level.small_blind
                ),
                big_blind=(
                    level.big_blind
                ),
                duration_seconds=(
                    level.duration_minutes
                    * 60
                ),
            )
        )

    tournament.status = "DRAFT"

    db.session.commit()

    return structure