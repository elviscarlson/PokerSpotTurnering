from datetime import date

import pytest
from sqlalchemy import func, select, text

from app.extensions import db
from app.models import (
    BlindLevel, Bounty, Player, Prize, Tournament, TournamentEvent,
    TournamentPlayer, TournamentResult, TournamentRuntime, TournamentStructure,
)
from app.services.clock_service import pause_clock, start_clock
from app.services.player_elimination import eliminate_player
from app.services.setup_service import mark_tournament_ready
from app.services.statistics import calculate_dashboard_statistics
from app.services.tournament_service import create_tournament
from app.services.tournament_structure import ensure_tournament_structure


def create_game(status="DRAFT"):
    players = [Player(name=name, name_key=name.casefold())
               for name in ("Elvis", "Hugo", "Leo")]
    db.session.add_all(players)
    db.session.commit()
    arguments = dict(
        tournament_date=date.today(), target_duration_minutes=180,
        buy_in=300, bounty_enabled=True, bounty_amount=50,
        player_ids=[player.id for player in players],
    )
    tournament = create_tournament(name="Unwanted game", **arguments)
    other = create_tournament(name="Keep this game", **arguments)
    ensure_tournament_structure(tournament)
    if status != "DRAFT":
        mark_tournament_ready(tournament)
    if status in ("RUNNING", "PAUSED", "COMPLETED"):
        start_clock(tournament)
        eliminate_player(tournament=tournament, entry_id=tournament.players[-1].id,
                         eliminated_by_entry_id=tournament.players[0].id)
    if status == "PAUSED":
        pause_clock(tournament)
    if status == "COMPLETED":
        eliminate_player(tournament=tournament, entry_id=tournament.players[1].id,
                         eliminated_by_entry_id=tournament.players[0].id)
    return tournament.id, other.id


@pytest.mark.parametrize("status", ["DRAFT", "READY", "RUNNING", "PAUSED", "COMPLETED"])
@pytest.mark.filterwarnings("error::sqlalchemy.exc.SAWarning")
def test_delete_removes_related_data_and_preserves_players(client, app, status):
    with app.app_context():
        db.session.execute(text("PRAGMA foreign_keys=ON"))
        tournament_id, other_id = create_game(status)
        structure_id = db.session.get(Tournament, tournament_id).structure.id
        if status == "COMPLETED":
            assert calculate_dashboard_statistics().completed_tournaments == 1

    url = f"/tournaments/{tournament_id}/delete"
    confirmation = client.get(url)
    assert confirmation.status_code == 200
    assert "Unwanted game" in confirmation.get_data(as_text=True)
    assert "Detta går inte att ångra" in confirmation.get_data(as_text=True)
    with app.app_context():
        assert db.session.get(Tournament, tournament_id) is not None
    with client.session_transaction() as session:
        token = session["tournament_delete_token"]
    response = client.post(url, data={"delete_token": token}, follow_redirects=True)
    assert response.status_code == 200
    assert "Turneringen Unwanted game togs bort" in response.get_data(as_text=True)
    with app.app_context():
        assert db.session.get(Tournament, tournament_id) is None
        assert db.session.get(Tournament, other_id) is not None
        assert db.session.scalar(select(func.count(Player.id))) == 3
        assert db.session.scalar(select(func.count(TournamentPlayer.id)).where(
            TournamentPlayer.tournament_id == other_id)) == 3
        for model in (TournamentPlayer, Prize, TournamentStructure, TournamentRuntime,
                      TournamentResult, Bounty, TournamentEvent):
            assert db.session.scalar(select(func.count(model.id)).where(
                model.tournament_id == tournament_id)) == 0
        assert db.session.scalar(select(func.count(BlindLevel.id)).where(
            BlindLevel.structure_id == structure_id)) == 0
        assert calculate_dashboard_statistics().completed_tournaments == 0
    assert client.get(url).status_code == 404


@pytest.mark.parametrize("token", [None, "wrong-token", "åäö"])
def test_delete_requires_confirmation_token(client, app, token):
    with app.app_context():
        tournament_id, _ = create_game()
    url = f"/tournaments/{tournament_id}/delete"
    client.get(url)
    response = client.post(url, data={} if token is None else {"delete_token": token})
    assert response.status_code == 400
    with app.app_context():
        assert db.session.get(Tournament, tournament_id) is not None


def test_unknown_tournament_returns_404(client):
    assert client.get("/tournaments/9999/delete").status_code == 404
    assert client.post("/tournaments/9999/delete").status_code == 404


def test_history_has_delete_link(client, app):
    with app.app_context():
        tournament_id, _ = create_game()
    page = client.get("/tournaments/").get_data(as_text=True)
    assert f'/tournaments/{tournament_id}/delete' in page
    assert 'aria-label="Ta bort Unwanted game"' in page
