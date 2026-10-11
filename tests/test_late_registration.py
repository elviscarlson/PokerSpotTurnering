from datetime import date

import pytest
from sqlalchemy import func, select

from app.extensions import db
from app.models import Player, Prize, Tournament
from app.services.clock_service import pause_clock, start_clock
from app.services.buyin_undo import undo_last_buyin
from app.services.late_registration import LateRegistrationError, register_late_player
from app.services.player_elimination import eliminate_player, restore_last_elimination
from app.services.reentry_service import register_reentry
from app.services.setup_service import mark_tournament_ready
from app.services.tournament_service import create_tournament
from app.services.tournament_structure import ensure_tournament_structure


def build_game(bounty=True, status="RUNNING"):
    players = [Player(name=name, name_key=name.casefold())
               for name in ("Elvis", "Hugo", "Leo", "Elias", "Anton")]
    db.session.add_all(players)
    db.session.commit()
    tournament = create_tournament(
        name="Late registration", tournament_date=date.today(),
        target_duration_minutes=240, buy_in=300,
        bounty_enabled=bounty, bounty_amount=50 if bounty else 0,
        player_ids=[player.id for player in players[:4]],
    )
    ensure_tournament_structure(tournament)
    mark_tournament_ready(tournament)
    if status in ("RUNNING", "PAUSED"):
        start_clock(tournament)
    if status == "PAUSED":
        pause_clock(tournament)
    return tournament, players[-1]


@pytest.mark.parametrize("bounty", [True, False])
@pytest.mark.parametrize("status", ["READY", "RUNNING", "PAUSED"])
def test_existing_player_buyin_preserves_clock_and_paid_places(app, bounty, status):
    with app.app_context():
        tournament, reserve = build_game(bounty, status)
        runtime = tournament.runtime
        clock = ((runtime.current_level_position, runtime.timer_started_at,
                  runtime.remaining_seconds_when_paused) if runtime else None)
        levels = [level.id for level in tournament.structure.blind_levels]
        paid_places = len(tournament.prizes)
        entry = register_late_player(tournament=tournament, player_id=reserve.id)
        assert entry.status == "ACTIVE" and entry.buy_in_count == 1
        assert tournament.player_count == tournament.active_player_count == 5
        assert tournament.total_entries == 5
        assert tournament.total_buyins == 1500
        assert tournament.bounty_pool == (250 if bounty else 0)
        assert tournament.total_prizes == tournament.regular_prize_pool
        assert len(tournament.prizes) == paid_places
        assert tournament.structure.total_chips == 5 * tournament.structure.starting_stack
        assert [level.id for level in tournament.structure.blind_levels] == levels
        assert tournament.status == status
        assert ((runtime.current_level_position, runtime.timer_started_at,
                 runtime.remaining_seconds_when_paused) if runtime else None) == clock


def test_late_registration_shifts_placements_and_balances_final_result(app):
    with app.app_context():
        tournament, reserve = build_game()
        tournament.prizes[0].amount -= 100
        tournament.prizes.append(Prize(place=3, amount=100))
        db.session.commit()
        winner, runner_up, third, fourth = tournament.players
        eliminate_player(tournament=tournament, entry_id=fourth.id,
                         eliminated_by_entry_id=winner.id)
        eliminate_player(tournament=tournament, entry_id=third.id,
                         eliminated_by_entry_id=winner.id)
        assert third.prize_winnings == 100
        late = register_late_player(tournament=tournament, player_id=reserve.id)
        assert fourth.placement == 5 and third.placement == 4
        assert third.prize_winnings == fourth.prize_winnings == 0
        assert winner.bounty_winnings == 100
        restore_last_elimination(tournament=tournament, entry_id=third.id)
        eliminate_player(tournament=tournament, entry_id=third.id,
                         eliminated_by_entry_id=winner.id)
        eliminate_player(tournament=tournament, entry_id=late.id,
                         eliminated_by_entry_id=winner.id)
        register_reentry(tournament=tournament, entry_id=late.id)
        eliminate_player(tournament=tournament, entry_id=late.id,
                         eliminated_by_entry_id=winner.id)
        eliminate_player(tournament=tournament, entry_id=runner_up.id,
                         eliminated_by_entry_id=winner.id)
        assert tournament.status == "COMPLETED"
        assert sorted(entry.placement for entry in tournament.players) == [1, 2, 3, 4, 5]
        assert sum(entry.total_winnings for entry in tournament.players) == tournament.total_buyins


@pytest.mark.parametrize("payload", [
    {}, {"player_id": "bad"}, {"player_id": "9999"},
    {"player_id": "1"}, {"new_player_name": "  eLvIs "},
    {"player_id": "5", "new_player_name": "Sara"},
    {"new_player_name": "X" * 81},
])
def test_invalid_registration_does_not_change_data(client, app, payload):
    with app.app_context():
        tournament, _ = build_game()
        tournament_id = tournament.id
    response = client.post(f"/tournaments/{tournament_id}/players/add", data=payload)
    assert response.status_code == 302
    with app.app_context():
        tournament = db.session.get(Tournament, tournament_id)
        assert tournament.player_count == 4
        assert tournament.total_buyins == 1200
        assert db.session.scalar(select(func.count(Player.id))) == 5
        assert tournament.total_prizes == 1000


def test_new_player_route_and_duplicate_submission(client, app):
    with app.app_context():
        tournament, reserve = build_game()
        tournament_id, reserve_id = tournament.id, reserve.id
    page = client.get(f"/tournaments/{tournament_id}/admin").get_data(as_text=True)
    assert 'Lägg till spelare' in page
    assert f'<option value="{reserve_id}">Anton</option>' in page
    response = client.post(f"/tournaments/{tournament_id}/players/add",
                           data={"new_player_name": "  Sara   Svensson "}, follow_redirects=True)
    assert response.status_code == 200
    assert "Sara Svensson lades till" in response.get_data(as_text=True)
    with app.app_context():
        tournament = db.session.get(Tournament, tournament_id)
        sara = db.session.scalar(select(Player).where(Player.name_key == "sara svensson"))
        assert sara is not None
        assert tournament.players[-1].player_id == sara.id
    client.post(f"/tournaments/{tournament_id}/players/add",
                data={"new_player_name": "Sara Svensson"})
    with app.app_context():
        assert db.session.get(Tournament, tournament_id).player_count == 5


def test_existing_player_cannot_be_added_twice(client, app):
    with app.app_context():
        tournament, reserve = build_game()
        tournament_id, reserve_id = tournament.id, reserve.id
    url = f"/tournaments/{tournament_id}/players/add"
    for _ in range(2):
        response = client.post(url, data={"player_id": str(reserve_id)})
        assert response.status_code == 302
    with app.app_context():
        tournament = db.session.get(Tournament, tournament_id)
        assert tournament.player_count == 5
        assert tournament.total_buyins == 1500
        assert tournament.total_prizes == 1250


@pytest.mark.parametrize("status", ["DRAFT", "COMPLETED"])
def test_registration_rejects_closed_or_unprepared_game(app, status):
    with app.app_context():
        tournament, reserve = build_game()
        tournament.status = status
        db.session.commit()
        with pytest.raises(LateRegistrationError):
            register_late_player(tournament=tournament, player_id=reserve.id)
        assert tournament.player_count == 4


def test_archived_player_cannot_join(app):
    with app.app_context():
        tournament, reserve = build_game()
        reserve.is_active = False
        db.session.commit()
        with pytest.raises(LateRegistrationError):
            register_late_player(tournament=tournament, player_id=reserve.id)


@pytest.mark.parametrize("status", ["READY", "RUNNING", "PAUSED"])
def test_available_players_are_in_initial_page_and_live_state(client, app, status):
    with app.app_context():
        tournament, reserve = build_game(status=status)
        db.session.add(Player(name="Arkiverad", name_key="arkiverad", is_active=False))
        db.session.commit()
        tournament_id, reserve_id = tournament.id, reserve.id
        if status != "READY":
            eliminate_player(tournament=tournament, entry_id=tournament.players[-1].id,
                             eliminated_by_entry_id=tournament.players[0].id)
    page = client.get(f"/tournaments/{tournament_id}/admin").get_data(as_text=True)
    assert f'<option value="{reserve_id}">Anton</option>' in page
    state = client.get(f"/api/tournaments/{tournament_id}/state").get_json()
    assert state["registration_candidates"] == [{"player_id": reserve_id, "name": "Anton"}]


def test_live_candidates_follow_register_changes_after_page_opened(client, app):
    with app.app_context():
        tournament, reserve = build_game()
        reserve.is_active = False
        db.session.commit()
        tournament_id = tournament.id
    url = f"/api/tournaments/{tournament_id}/state"
    page = client.get(f"/tournaments/{tournament_id}/admin").get_data(as_text=True)
    assert 'aria-describedby="late-player-empty" disabled' in page
    assert client.get(url).get_json()["registration_candidates"] == []
    client.post("/players/", data={"name": "Ny i registret"})
    candidates = client.get(url).get_json()["registration_candidates"]
    assert len(candidates) == 1 and candidates[0]["name"] == "Ny i registret"
    with app.app_context():
        player = db.session.get(Player, candidates[0]["player_id"])
        player.name, player.name_key = "Nytt namn", "nytt namn"
        db.session.commit()
    assert client.get(url).get_json()["registration_candidates"][0]["name"] == "Nytt namn"
    with app.app_context():
        db.session.get(Player, candidates[0]["player_id"]).is_active = False
        db.session.commit()
    assert client.get(url).get_json()["registration_candidates"] == []


def test_candidate_returns_after_registration_is_undone(client, app):
    with app.app_context():
        tournament, reserve = build_game()
        tournament_id, reserve_id = tournament.id, reserve.id
    url = f"/api/tournaments/{tournament_id}/state"
    client.post(f"/tournaments/{tournament_id}/players/add", data={"player_id": reserve_id})
    state = client.get(url).get_json()
    assert state["registration_candidates"] == []
    with app.app_context():
        undo_last_buyin(db.session.get(Tournament, tournament_id), action_id=state["undo_buyin"]["id"])
    assert client.get(url).get_json()["registration_candidates"] == [{"player_id": reserve_id, "name": "Anton"}]
