"""Fumée de la ronde GitHub : le flux et le tri, sans n8n."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from automation.n8n.tri import ETAT_LISIBLE, trier_sujets
from dev.scripts.smoke_n8n import FLUX, main, verifier


def _ticket(**kwargs):
    base = {
        "number": 1,
        "title": "Coquille dans le README",
        "html_url": "https://example.test/1",
        "updated_at": "2026-11-11T12:00:00Z",
        "labels": [{"name": "doc"}],
        "body": "une ligne",
    }
    base.update(kwargs)
    return base


def test_le_flux_passe_la_fumee():
    texte = FLUX.read_text(encoding="utf-8")
    assert verifier(json_flux(texte), texte) == []
    assert main(["smoke_n8n.py"]) == 0


def json_flux(texte: str):
    import json

    return json.loads(texte)


def test_le_tri_garde_le_sujet_recent_et_eligible():
    maintenant = datetime(2026, 11, 11, 15, tzinfo=timezone.utc)
    sujets = trier_sujets([_ticket()], maintenant=maintenant)
    assert len(sujets) == 1
    assert sujets[0]["etat"] == ETAT_LISIBLE
    assert sujets[0]["numero"] == 1
    assert sujets[0]["donnees_ticket_corps"] == "une ligne"
    assert sujets[0]["libelles"] == "doc"


def test_le_tri_ecarte_fusion_anciennete_libelle_et_plafond():
    maintenant = datetime(2026, 11, 11, 15, tzinfo=timezone.utc)
    vieux = (maintenant - timedelta(days=8)).strftime("%Y-%m-%dT%H:%M:%SZ")
    tickets = [
        _ticket(number=1, pull_request={"url": "https://example.test/pull/1"}),
        _ticket(number=2, updated_at=vieux),
        _ticket(number=3, labels=[{"name": "security"}, {"name": "doc"}]),
        _ticket(number=4, labels=[{"name": "bug"}]),
        _ticket(number=5, labels=[{"name": "Typo"}]),
        _ticket(number=6, labels=[{"name": "auto"}], title="second"),
        _ticket(number=7, labels=[{"name": "doc"}], title="troisième"),
        _ticket(number=8, labels=[{"name": "doc"}], title="au-delà du plafond"),
    ]
    numeros = [s["numero"] for s in trier_sujets(tickets, maintenant=maintenant)]
    assert numeros == [5, 6, 7]


def test_une_date_illisible_ou_un_corps_vide_ne_cassent_pas():
    maintenant = datetime(2026, 11, 11, tzinfo=timezone.utc)
    sujets = trier_sujets(
        [_ticket(updated_at="pas une date"), _ticket(number=9, body=None, labels=[{"name": "auto"}])],
        maintenant=maintenant,
    )
    assert [s["numero"] for s in sujets] == [9]
    assert sujets[0]["donnees_ticket_corps"] == ""


def test_github_eteint_ne_produit_rien_dans_le_fichier():
    import json

    flux = json.loads(FLUX.read_text(encoding="utf-8"))
    branche = flux["connections"]["Accès GitHub activé ?"]["main"][1]
    assert branche == []
