"""Connexion des deux comptes (propriétaire / gestionnaire)."""
import hashlib
import hmac
import secrets

import streamlit as st
from sqlalchemy import func, select

from core.db import Session, Utilisateur, ecrire_parametre, lire_parametre
from core.format import signature

ITERATIONS = 200_000


def hacher(mot_de_passe: str) -> str:
    sel = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", mot_de_passe.encode(), sel.encode(), ITERATIONS).hex()
    return f"pbkdf2${ITERATIONS}${sel}${h}"


def verifier(mot_de_passe: str, stocke: str) -> bool:
    try:
        _, it, sel, h = stocke.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", mot_de_passe.encode(), sel.encode(), int(it)).hex()
        return hmac.compare_digest(calc, h)
    except ValueError:
        return False


def utilisateur() -> dict | None:
    return st.session_state.get("utilisateur")


def est_proprietaire() -> bool:
    u = utilisateur()
    return bool(u and u["role"] == "proprietaire")


def _code_installation() -> str | None:
    try:
        return st.secrets.get("CODE_INSTALLATION")
    except Exception:
        return None


def _premier_lancement():
    st.title("Bar & Cabine")
    st.subheader("Premier lancement : crée ton compte propriétaire")
    st.caption("Ce compte a accès à tout. Tu créeras ensuite le compte du gestionnaire dans Paramètres.")
    with st.form("creation_proprietaire"):
        nom = st.text_input("Ton nom")
        ident = st.text_input("Identifiant de connexion")
        mdp = st.text_input("Mot de passe (8 caractères minimum)", type="password")
        mdp2 = st.text_input("Confirme le mot de passe", type="password")
        code_attendu = _code_installation()
        code = st.text_input("Code d'installation", type="password",
                             help="Le code CODE_INSTALLATION défini dans les secrets.") if code_attendu else ""
        ok = st.form_submit_button("Créer mon compte", type="primary")
    if ok:
        if code_attendu and not hmac.compare_digest(code.strip(), str(code_attendu)):
            st.error("Code d'installation incorrect.")
        elif not (nom.strip() and ident.strip()):
            st.error("Renseigne ton nom et un identifiant.")
        elif len(mdp) < 8:
            st.error("Le mot de passe doit contenir au moins 8 caractères.")
        elif mdp != mdp2:
            st.error("Les deux mots de passe ne sont pas identiques.")
        else:
            with Session() as s:
                u = Utilisateur(identifiant=ident.strip().lower(), nom=nom.strip(),
                                role="proprietaire", mot_de_passe=hacher(mdp))
                s.add(u)
                s.commit()
                st.session_state.utilisateur = {"id": u.id, "nom": u.nom, "role": u.role}
            st.rerun()


def _connexion():
    st.title("Bar & Cabine")
    st.caption("Connecte-toi pour saisir ou consulter l'activité.")
    with st.form("connexion"):
        ident = st.text_input("Identifiant")
        mdp = st.text_input("Mot de passe", type="password")
        ok = st.form_submit_button("Se connecter", type="primary")
    if ok:
        with Session() as s:
            u = s.scalar(select(Utilisateur).where(Utilisateur.identifiant == ident.strip().lower()))
        if u and u.actif and verifier(mdp, u.mot_de_passe):
            st.session_state.utilisateur = {"id": u.id, "nom": u.nom, "role": u.role}
            st.session_state.doit_changer = mot_de_passe_provisoire(u.id)
            st.rerun()
        else:
            st.error("Identifiant ou mot de passe incorrect.")

    with st.expander("Identifiant ou mot de passe oublié ?"):
        st.markdown("**Gestionnaire** : contacte le propriétaire. Il peut te rappeler ton identifiant et "
                    "te donner un mot de passe provisoire, que tu remplaceras à ta prochaine connexion.")
        st.markdown("**Propriétaire** : réinitialise ton accès avec le code d'installation "
                    "(celui des « Secrets » de l'application).")
        with st.form("recuperation", clear_on_submit=True):
            code = st.text_input("Code d'installation", type="password")
            n1 = st.text_input("Nouveau mot de passe (8 caractères minimum)", type="password")
            n2 = st.text_input("Confirme le nouveau mot de passe", type="password")
            ok2 = st.form_submit_button("Réinitialiser mon accès propriétaire")
        if ok2:
            attendu = _code_installation()
            if not attendu:
                st.error("Aucun code d'installation n'est configuré dans les secrets de l'application.")
            elif not hmac.compare_digest(code.strip(), str(attendu)):
                st.error("Code d'installation incorrect.")
            elif len(n1) < 8 or n1 != n2:
                st.error("Les mots de passe doivent être identiques et contenir au moins 8 caractères.")
            else:
                with Session() as s:
                    proprio = s.scalar(select(Utilisateur).where(Utilisateur.role == "proprietaire"))
                    proprio.mot_de_passe, proprio.actif = hacher(n1), True
                    s.commit()
                    ident = proprio.identifiant
                marquer_provisoire(proprio.id, False)
                st.success(f"Accès réinitialisé. Ton identifiant est « {ident} ». Connecte-toi ci-dessus.")


def marquer_provisoire(uid: int, provisoire: bool = True) -> None:
    ecrire_parametre(f"mdp_provisoire_{uid}", "1" if provisoire else "0")


def mot_de_passe_provisoire(uid: int) -> bool:
    return lire_parametre(f"mdp_provisoire_{uid}") == "1"


def generer_mot_de_passe() -> str:
    """Mot de passe provisoire lisible (sans caractères ambigus comme 0/O ou 1/l)."""
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
    return "-".join("".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(3))


def _changement_obligatoire():
    u = utilisateur()
    st.title("Choisis ton mot de passe")
    st.info(f"Bonjour {u['nom']} ! Tu t'es connecté avec un mot de passe provisoire. "
            "Choisis maintenant ton mot de passe personnel.")
    with st.form("changement_obligatoire"):
        n1 = st.text_input("Nouveau mot de passe (8 caractères minimum)", type="password")
        n2 = st.text_input("Confirme le mot de passe", type="password")
        ok = st.form_submit_button("Enregistrer mon mot de passe", type="primary")
    if ok:
        if len(n1) < 8:
            st.error("Le mot de passe doit contenir au moins 8 caractères.")
        elif n1 != n2:
            st.error("Les deux mots de passe ne sont pas identiques.")
        else:
            with Session() as s:
                moi = s.get(Utilisateur, u["id"])
                moi.mot_de_passe = hacher(n1)
                s.commit()
            marquer_provisoire(u["id"], False)
            st.session_state.doit_changer = False
            st.rerun()
    signature()


def exiger_connexion() -> dict:
    """Affiche la connexion si besoin et arrête la page tant que personne n'est connecté."""
    if utilisateur():
        if st.session_state.get("doit_changer"):
            _changement_obligatoire()
            st.stop()
        return utilisateur()
    with Session() as s:
        nb = s.scalar(select(func.count()).select_from(Utilisateur))
    if nb == 0:
        _premier_lancement()
    else:
        _connexion()
    signature()
    st.stop()


def deconnecter():
    st.session_state.pop("utilisateur", None)
    st.session_state.pop("doit_changer", None)
