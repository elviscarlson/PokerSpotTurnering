from __future__ import annotations

from flask import (
    Blueprint,
    jsonify,
    render_template,
)

from app.services.statistics import (
    bounty_leaderboard,
    calculate_dashboard_statistics,
    winnings_leaderboard,
    wins_leaderboard,
)


main_bp = Blueprint(
    "main",
    __name__,
)


@main_bp.get("/")
def dashboard():
    statistics = (
        calculate_dashboard_statistics()
    )

    return render_template(
        "dashboard.html",
        statistics=statistics,
        winnings_leaders=(
            winnings_leaderboard()
        ),
        win_leaders=(
            wins_leaderboard()
        ),
        bounty_leaders=(
            bounty_leaderboard()
        ),
    )


@main_bp.get("/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "application": (
                "Pokerturneringsapp"
            ),
        }
    )