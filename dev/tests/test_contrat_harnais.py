from src.brain.contrat_harnais import (
    LIMITE_DETAIL_VOIX,
    LIMITE_RESUME_VOIX,
    PREFIXE_CONTRAT,
    analyser,
    envelopper,
)


def test_envelopper_ajoute_le_prefixe_et_la_question():
    question = "Quelle est la meteo aujourd hui ?"
    enveloppe = envelopper(question)
    assert PREFIXE_CONTRAT in enveloppe
    assert enveloppe.endswith(question)


def test_json_pur_est_parse_et_conforme():
    charge = (
        '{"verdict": "ok", "resume_voix": "Tout va bien.", '
        '"detail_voix": "Detail complet.", "resultat_complet": "analyse"}'
    )
    rep = analyser(charge)
    assert rep.conforme is True
    assert rep.verdict == "ok"
    assert rep.resume_voix == "Tout va bien."
    assert rep.resultat_complet == "analyse"


def test_json_entoure_de_cloture_markdown_est_extrait():
    charge = (
        '```json\n{"verdict": "ok", "resume_voix": "Ca marche.", '
        '"detail_voix": "D", "resultat_complet": "C"}\n```'
    )
    rep = analyser(charge)
    assert rep.resume_voix == "Ca marche."
    # La cloture markdown est une enveloppe, pas une violation du contrat :
    # un agent CLI en met presque toujours une.
    assert rep.conforme is True


def test_json_avec_bavardage_autour_est_extrait():
    charge = (
        'Voici le resultat : {"verdict": "ok", "resume_voix": "Analyse finie.", '
        '"detail_voix": "D", "resultat_complet": "C"} Voila.'
    )
    rep = analyser(charge)
    assert rep.resume_voix == "Analyse finie."
    # Le bavardage autour de l'objet ne casse pas le contrat non plus.
    assert rep.conforme is True


def test_json_avec_cles_manquantes_est_non_conforme():
    charge = '{"verdict": "ok", "resume_voix": "Texte court."}'
    rep = analyser(charge)
    assert rep.conforme is False
    assert rep.resultat_complet == charge
    assert rep.resume_voix == "Texte court."


def test_json_avec_mauvais_types_est_non_conforme():
    charge = (
        '{"verdict": 42, "resume_voix": ["a"], '
        '"detail_voix": null, "resultat_complet": true}'
    )
    rep = analyser(charge)
    assert rep.conforme is False
    # Une valeur non-chaine est jetee, jamais convertie : `str(42)` puis
    # `str(["a"])` finiraient prononces tels quels.
    assert rep.verdict == ""
    assert rep.resume_voix == ""


def test_texte_libre_degrade_gracieusement():
    texte = "Bonjour. Voici une analyse simple. Elle est terminee."
    rep = analyser(texte)
    assert rep.conforme is False
    assert rep.resultat_complet == texte
    assert rep.resume_voix.startswith("Bonjour.")
    assert len(rep.resume_voix) <= LIMITE_RESUME_VOIX


def test_texte_libre_trop_long_est_tronque_sans_mot_coupe():
    texte = "Phrase une. " * 50
    rep = analyser(texte)
    assert rep.conforme is False
    assert len(rep.resume_voix) <= LIMITE_RESUME_VOIX
    assert not rep.resume_voix.endswith(" ")


def test_chaine_vide_ou_none_ne_leve_pas():
    for entree in ("", "   ", None):
        rep = analyser(entree)
        assert rep.conforme is False
        assert rep.resume_voix == ""
        assert rep.resultat_complet == (entree or "")


def test_resume_voix_trop_long_est_tronque():
    charge = (
        '{"verdict": "v", "resume_voix": "' + "mot " * 100 +
        '", "detail_voix": "d", "resultat_complet": "c"}'
    )
    rep = analyser(charge)
    assert len(rep.resume_voix) <= LIMITE_RESUME_VOIX
    assert rep.conforme is False


def test_detail_voix_trop_long_est_tronque():
    charge = (
        '{"verdict": "v", "resume_voix": "court", "detail_voix": "' +
        "mot " * 200 + '", "resultat_complet": "c"}'
    )
    rep = analyser(charge)
    assert len(rep.detail_voix) <= LIMITE_DETAIL_VOIX
    assert rep.conforme is False


def test_chemin_windows_est_neutralise_dans_resume():
    charge = r'{"verdict": "v", "resume_voix": "Le fichier C:\\Users\\test\\doc.txt est pret.", "detail_voix": "d", "resultat_complet": "c"}'
    rep = analyser(charge)
    assert "C:" not in rep.resume_voix
    assert "fichier" in rep.resume_voix


def test_cloture_code_est_retiree_dans_resume():
    charge = (
        '{"verdict": "v", "resume_voix": "Voici ```python\\nprint(1)\\n``` '
        'le resultat.", "detail_voix": "d", "resultat_complet": "c"}'
    )
    rep = analyser(charge)
    assert "```" not in rep.resume_voix
    assert "print" in rep.resume_voix
    assert "resultat" in rep.resume_voix


def test_balisage_inline_garde_tous_les_mots():
    """Retirer les accents graves, jamais le texte qu'ils entourent.

    Mesure du 21/09 : « Le Dockerfile installe , le définit comme et par
    défaut. » — trois fragments entre backticks avaient disparu, la phrase
    restait grammaticale et donc fausse à l'oreille.
    """
    from src.brain.contrat_harnais import _nettoyer_voix

    brut = (
        "Le Dockerfile installe `python:3.11`, le définit comme `python3` "
        "et `3.11` par défaut."
    )
    propre = _nettoyer_voix(brut)
    for mot in ("Dockerfile", "installe", "python:3.11", "définit", "python3", "3.11", "défaut"):
        assert mot in propre, f"mot perdu : {mot!r} dans {propre!r}"
    assert "`" not in propre


def test_liste_a_puces_est_neutralisee_dans_resume():
    charge = (
        '{"verdict": "v", "resume_voix": "- premier point\\n'
        '- deuxieme point", "detail_voix": "d", "resultat_complet": "c"}'
    )
    rep = analyser(charge)
    assert not rep.resume_voix.startswith("-")
    assert "premier point" in rep.resume_voix
    assert "deuxieme point" in rep.resume_voix
