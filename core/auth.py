"""Connexion des deux comptes (propriétaire / gestionnaire)."""
import hashlib
import hmac
import secrets

import streamlit as st
from sqlalchemy import func, select

from core.db import Session, Utilisateur

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
            st.rerun()
        else:
            st.error("Identifiant ou mot de passe incorrect.")


def exiger_connexion() -> dict:
    """Affiche la connexion si besoin et arrête la page tant que personne n'est connecté."""
    if utilisateur():
        return utilisateur()
    with Session() as s:
        nb = s.scalar(select(func.count()).select_from(Utilisateur))
    if nb == 0:
        _premier_lancement()
    else:
        _connexion()
    st.stop()


def deconnecter():
    st.session_state.pop("utilisateur", None)
