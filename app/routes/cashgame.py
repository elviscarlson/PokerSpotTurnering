from __future__ import annotations

from datetime import date
from functools import wraps
import secrets

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from sqlalchemy import select
from sqlalchemy.orm.exc import StaleDataError

from app.extensions import db
from app.models import AppMeta, CashGame, Player
from app.services import cashgame as service

cashgame_bp = Blueprint("cashgame", __name__, url_prefix="/cashgame")


@cashgame_bp.app_template_filter("cash_money")
def cash_money(ore, signed=False):
    return service.money(ore, signed)


@cashgame_bp.app_template_filter("cash_input")
def cash_input(ore):
    return service.money_input(ore)


@cashgame_bp.app_template_global()
def cashgame_csrf():
    if "cashgame_csrf" not in session:
        session["cashgame_csrf"] = secrets.token_urlsafe(32)
    return session["cashgame_csrf"]


@cashgame_bp.before_request
def check_csrf():
    if request.method == "POST":
        expected = session.get("cashgame_csrf", "")
        actual = request.form.get("csrf_token", "")
        if not expected or not secrets.compare_digest(expected.encode(), actual.encode()):
            abort(400, description="Formuläret har gått ut. Ladda om sidan och försök igen.")


def game_mutation(view):
    @wraps(view)
    def wrapped(game_id, **kwargs):
        game = db.get_or_404(CashGame, game_id)
        try:
            if request.form.get("version", type=int) != game.version:
                raise service.CashGameError("Spelkvällen har ändrats i en annan flik. Kontrollera de nya uppgifterna och försök igen.")
            message = view(game, **kwargs)
            db.session.commit()
        except (service.CashGameError, StaleDataError) as exc:
            db.session.rollback()
            flash(str(exc) if isinstance(exc, service.CashGameError) else "Spelkvällen ändrades samtidigt. Kontrollera uppgifterna och försök igen.", "error")
        else:
            flash(message, "success")
        return redirect(url_for("cashgame.detail", game_id=game.id))
    return wrapped


@cashgame_bp.get("")
@cashgame_bp.get("/")
def index():
    games = service.all_games()
    rows = service.summaries(games)
    player_id = request.args.get("player_id", type=int)
    selected_player = db.get_or_404(Player, player_id) if player_id is not None else None
    report = service.player_report(selected_player, games)
    players = list(db.session.scalars(select(Player).order_by(Player.name)))
    return render_template("cashgame/index.html", games=games, rows=rows, players=players, report=report,
                           selected_player=selected_player, completed_count=sum(g.status == "COMPLETED" for g in games),
                           total_buy_ins=sum(row["buy_ins"] for row in rows))


@cashgame_bp.route("/new", methods=["GET", "POST"])
def new():
    players = list(db.session.scalars(select(Player).where(Player.is_active.is_(True)).order_by(Player.name)))
    if request.method == "POST":
        try:
            try:
                played_on = date.fromisoformat(request.form.get("played_on", ""))
                player_ids = [int(value) for value in request.form.getlist("player_ids")]
            except (ValueError, TypeError):
                raise service.CashGameError("Välj ett giltigt datum och giltiga spelare.")
            selected = [player for player in players if player.id in player_ids]
            if len(selected) != len(player_ids):
                raise service.CashGameError("En eller flera spelare finns inte eller är arkiverade.")
            game = service.create_game(request.form.get("name", ""), played_on, selected, service.parse_money(request.form.get("buy_in", "")))
            db.session.commit()
        except service.CashGameError as exc:
            db.session.rollback()
            flash(str(exc), "error")
        else:
            return redirect(url_for("cashgame.detail", game_id=game.id))
    return render_template("cashgame/new.html", players=players, today=date.today())


@cashgame_bp.get("/<int:game_id>")
def detail(game_id):
    game = db.get_or_404(CashGame, game_id)
    plan = service.settlement_plan(game) if game.status == "COMPLETED" else []
    joined_ids = {entry.player_id for entry in game.entries}
    available = list(db.session.scalars(select(Player).where(Player.is_active.is_(True), ~Player.id.in_(joined_ids)).order_by(Player.name)))
    adjustments = {}
    adjustment_error = ""
    if game.status == "OPEN" and all(entry.cash_out_ore is not None for entry in game.entries):
        try:
            adjustments = service.difference_adjustments(game)
        except service.CashGameError as exc:
            adjustment_error = str(exc)
    return render_template("cashgame/detail.html", game=game, plan=plan, available_players=available,
                           adjustments=adjustments, adjustment_error=adjustment_error,
                           difference=game.total_cash_outs - game.total_buy_ins,
                           pending_cash_outs=sum(entry.cash_out_ore is None for entry in game.entries))


@cashgame_bp.post("/<int:game_id>/buy-ins")
@game_mutation
def buy_in(game):
    player = db.session.get(Player, request.form.get("player_id", type=int))
    if player is None:
        raise service.CashGameError("Välj en registrerad spelare.")
    service.add_buy_in(game, player, service.parse_money(request.form.get("amount", "")))
    return f"Inköpet för {player.name} är registrerat."


@cashgame_bp.post("/<int:game_id>/buy-ins/<int:buy_in_id>/undo")
@game_mutation
def undo_buy_in(game, buy_in_id):
    service.undo_buy_in(game, buy_in_id)
    return "Inköpet är ångrat. Kontrollera spelarens utcheckning."


@cashgame_bp.post("/<int:game_id>/cash-outs")
@game_mutation
def cash_outs(game):
    # Entry IDs in the form also detect a participant added since this form was rendered.
    amounts = {}
    for key, value in request.form.items():
        if key.startswith("cash_out_"):
            try:
                entry_id = int(key.removeprefix("cash_out_"))
            except ValueError:
                raise service.CashGameError("Ogiltig spelare i utcheckningen.")
            amounts[entry_id] = service.parse_money(value, allow_zero=True) if value.strip() else None
    service.save_cash_outs(game, amounts)
    return "Utcheckningarna är sparade."


@cashgame_bp.post("/<int:game_id>/complete")
@game_mutation
def complete(game):
    service.complete_game(game)
    return "Spelkvällen är avslutad. Resultat och Swish-förslag är klara."


@cashgame_bp.post("/<int:game_id>/reopen")
@game_mutation
def reopen(game):
    service.reopen_game(game)
    return "Spelkvällen är öppen för ändringar igen."


@cashgame_bp.post("/<int:game_id>/transfers")
@game_mutation
def transfer(game):
    service.record_transfer(game, request.form.get("payer_id", type=int), request.form.get("receiver_id", type=int), service.parse_money(request.form.get("amount", "")))
    return "Swish-betalningen är markerad som gjord. Ingen betalning skickas från appen."


@cashgame_bp.post("/<int:game_id>/transfers/<int:transfer_id>/undo")
@game_mutation
def undo_transfer(game, transfer_id):
    service.undo_transfer(game, transfer_id)
    return "Betalningsmarkeringen är ångrad. Swish-förslaget har räknats om."


@cashgame_bp.post("/profiles/<slug>")
def bind_profile(slug):
    if slug not in service.PROFILE_SLUGS:
        abort(404)
    value = request.form.get("player_id", "")
    if value and (not value.isascii() or not value.isdecimal() or db.session.get(Player, int(value)) is None):
        abort(400, description="Välj en registrerad spelare.")
    binding = db.session.scalar(select(AppMeta).where(AppMeta.key == f"cashgame.profile.{slug}"))
    if binding is None:
        binding = AppMeta(key=f"cashgame.profile.{slug}")
        db.session.add(binding)
    binding.value = value
    db.session.commit()
    flash("Personsidan är kopplad till den valda spelaren.", "success")
    return redirect(url_for(f"main.{slug}", _anchor="cashgame-results"))
