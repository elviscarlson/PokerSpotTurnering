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


@main_bp.get("/leo")
def leo():
    return render_template("leo.html")


FRIEND_PROFILES = {
    "elvis": {
        "name": "Elvis",
        "image": "elvis.jpeg",
        "eyebrow": "POKERSPOTS EGEN KUNG",
        "headline": "POKERFEJS",
        "tagline": "PÅ MAX.",
        "subtitle": "Ingen vet vad han har. Inte ens han själv.",
        "button": "HÖJ INSATSEN!",
        "response": "Kungen har intagit bordet.",
        "badge": "KUNG VID BORDET",
        "alt": "Elvis med sitt mest seriösa pokerfejs",
        "lines": [
            "Pokerfejs: 100. Läsbarhet: 0.",
            "Elvis höjer. Bordet börjar omvärdera sina livsval.",
            "Kung på handen? Nej, kungen sitter vid bordet.",
            "Han bluffar inte. Han testar bara er intuition.",
        ],
    },
    "hugo": {
        "name": "Hugo",
        "image": "hugo.png",
        "eyebrow": "POKERSPOTS DJUPASTE SPELARE",
        "headline": "DJUPT I",
        "tagline": "POTTEN.",
        "subtitle": "Alla andra tänker på floppen. Hugo tänker på djupet.",
        "button": "DYK IN I POTTEN!",
        "response": "Lugnt på ytan. All-in under den.",
        "badge": "BUBBLANS MÄSTARE",
        "alt": "Hugo i sin undervattenspose med armarna utsträckta",
        "lines": [
            "Hugo synar. Potten får kallsup.",
            "Alla vill undvika bubblan. Hugo har flyttat in.",
            "Djup stack? Hugo tog det bokstavligt.",
            "Han simmar lugnt. Era marker gör det inte.",
        ],
    },
    "olle": {
        "name": "Olle",
        "image": "olle1.png",
        "alternate_image": "olle2.png",
        "alternate_alt": "Olle med spegelblanka solglasögon och maximal energi",
        "eyebrow": "POKERSPOTS VILDA KORT",
        "headline": "TVÅ LÄGEN.",
        "tagline": "NOLL FOLD.",
        "subtitle": "Korv på hjärnan. Solglasögon på. Samma orimliga självförtroende.",
        "button": "BYT POKERFEJS!",
        "response": "Dagens meny: en riktigt saftig pott.",
        "badge": "BORDETS VILDA KORT",
        "alt": "Olle i randig tröja med ett svävande korvfilter ovanför huvudet",
        "lines": [
            "Solglasögon på. Nu kan ingen se honom räkna fel.",
            "Tillbaka till korvläget. Potten ska grillas.",
            "Pokerfejs? Olle tog med hela festivalfejset.",
            "Han har inte nötterna. Han har korvarna.",
        ],
    },
    "elias": {
        "name": "Elias",
        "image": "elias.png",
        "eyebrow": "POKERSPOTS BLUFFDETEKTOR",
        "headline": "VÄNTA NU.",
        "tagline": "JAG SYNAR.",
        "subtitle": "Den där höjningen kommer du få förklara.",
        "button": "SYNA BLUFFEN!",
        "response": "Elias har redan en följdfråga.",
        "badge": "MISSTÄNKSAM SEDAN FLOPPEN",
        "alt": "Elias i mörk jacka, mitt i en mycket engagerad diskussion",
        "lines": [
            "Vänta. Du höjde med VAD sa du?",
            "Elias synar både handen och din förklaring.",
            "Den där bluffen behöver en bättre presentation.",
            "Han skulle bara ställa en fråga. Nu är det korsförhör.",
        ],
    },
}


@main_bp.get("/elvis")
def elvis():
    return render_template("friend.html", slug="elvis", profile=FRIEND_PROFILES["elvis"])


@main_bp.get("/hugo")
def hugo():
    return render_template("friend.html", slug="hugo", profile=FRIEND_PROFILES["hugo"])


@main_bp.get("/olle")
def olle():
    return render_template("friend.html", slug="olle", profile=FRIEND_PROFILES["olle"])


@main_bp.get("/elias")
def elias():
    return render_template("friend.html", slug="elias", profile=FRIEND_PROFILES["elias"])


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
