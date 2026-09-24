"""Comptes et réglages (propriétaire)."""
import streamlit as st
from sqlalchemy import select

from core import auth
from core.db import Session, Utilisateur, ecrire_parametre, est_locale, lire_parametre
from core.format import afficher_flash, flash


def page():
    st.title("Paramètres")
    afficher_flash()

    st.subheader("Compte du gestionnaire")
    with Session() as s:
        gest = s.scalar(select(Utilisateur).where(Utilisateur.role == "gestionnaire"))
    if gest:
        st.write(f"Compte actuel : **{gest.nom}** (identifiant : `{gest.identifiant}`) · "
                 f"{'actif' if gest.actif else 'désactivé'}")
    with st.form("gestionnaire", clear_on_submit=True):
        nom = st.text_input("Nom", value=gest.nom if gest else "")
        ident = st.text_input("Identifiant", value=gest.identifiant if gest else "")
        mdp = st.text_input("Nouveau mot de passe (8 caractères minimum)" +
                            (" — laisser vide pour ne pas le changer" if gest else ""), type="password")
        actif = st.checkbox("Compte actif", value=gest.actif if gest else True)
        ok = st.form_submit_button("Enregistrer le compte" if gest else "Créer le compte", type="primary")
    if ok:
        if not (nom.strip() and ident.strip()):
            st.error("Renseigne le nom et l'identifiant.")
        elif (not gest or mdp) and len(mdp) < 8:
            st.error("Le mot de passe doit contenir au moins 8 caractères.")
        else:
            with Session() as s:
                autre = s.scalar(select(Utilisateur).where(Utilisateur.identifiant == ident.strip().lower(),
                                                           Utilisateur.id != (gest.id if gest else -1)))
                if autre:
                    st.error("Cet identifiant est déjà utilisé.")
                else:
                    g = s.get(Utilisateur, gest.id) if gest else Utilisateur(role="gestionnaire")
                    g.nom, g.identifiant, g.actif = nom.strip(), ident.strip().lower(), actif
                    if mdp:
                        g.mot_de_passe = auth.hacher(mdp)
                    s.add(g)
                    s.commit()
                    flash("Compte du gestionnaire enregistré. Transmets-lui son identifiant et son mot de passe.")
                    st.rerun()

    st.subheader("Réglages")
    seuil = st.number_input("Seuil d'alerte des réductions (% du chiffre d'affaires mensuel)",
                            min_value=0.0, max_value=100.0, step=0.5,
                            value=float(lire_parametre("seuil_reductions_pct") or 5))
    if st.button("Enregistrer le seuil"):
        ecrire_parametre("seuil_reductions_pct", str(seuil))
        flash("Seuil enregistré.")
        st.rerun()

    st.subheader("Mon mot de passe")
    with st.form("mon_mdp", clear_on_submit=True):
        ancien = st.text_input("Mot de passe actuel", type="password")
        nouveau = st.text_input("Nouveau mot de passe", type="password")
        ok2 = st.form_submit_button("Changer mon mot de passe")
    if ok2:
        with Session() as s:
            moi = s.get(Utilisateur, auth.utilisateur()["id"])
            if not auth.verifier(ancien, moi.mot_de_passe):
                st.error("Mot de passe actuel incorrect.")
            elif len(nouveau) < 8:
                st.error("Le nouveau mot de passe doit contenir au moins 8 caractères.")
            else:
                moi.mot_de_passe = auth.hacher(nouveau)
                s.commit()
                st.success("Mot de passe changé.")

    st.caption("Base de données : " + ("locale (fichier barcabine.db, pour les tests)" if est_locale()
                                       else "en ligne (Supabase / PostgreSQL)"))
