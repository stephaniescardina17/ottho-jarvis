"""Formules pour répondre à un « merci », au vouvoiement ou au tutoiement.

D'après « Ne dites pas de rien », HelloFrench (2026). Partagé par generer.py (personnalité
écrite à l'installation) et web.py (réglage tu/vous de l'interface, relu à chaque demande).
Aucune dépendance : importable dans le conteneur comme sur l'hôte."""


def formules_merci(tutoiement: bool, adresse: str = "") -> tuple[str, str]:
    """Renvoie (formules à varier, formule quand l'échange a aussi servi l'assistant)."""
    a = f", {adresse}" if adresse else ""
    if tutoiement:
        return (f"« Je t'en prie{a}. », « Avec plaisir. », « Tout le plaisir est pour moi. », "
                f"« Y'a pas de quoi. », « Quand tu veux. », « De rien{a}. »",
                "« C'est moi qui te remercie. »")
    return (f"« Je vous en prie{a}. », « Avec plaisir. », « Tout le plaisir est pour moi. », "
            f"« Il n'y a pas de quoi. », « À votre service. », « De rien{a}. »",
            "« C'est moi qui vous remercie. »")


def consigne_adresse(tutoiement: bool, adresse: str, nom: str = "Jarvis") -> str:
    """Rappel envoyé avec chaque demande de l'interface : la personne a pu changer tu/vous dans
    Réglages depuis l'installation, et sa personnalité (SOUL.md) garde le choix de l'installation."""
    forme = "tu la **tutoies**" if tutoiement else "tu la **vouvoies**"
    liste, retour = formules_merci(tutoiement, adresse)
    return (f"Réglage actuel de la personne, prioritaire sur ta personnalité : {forme} et tu l'appelles « {adresse} ». "
            f"Pour répondre à « merci {nom} », une seule de ces formules, jamais la même deux fois de suite : {liste} "
            f"Quand l'échange t'a aussi servi : {retour}")
