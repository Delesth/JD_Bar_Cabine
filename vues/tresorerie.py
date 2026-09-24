"""Trésoreries du bar et de la cabine (propriétaire)."""
from datetime import date

import pandas as pd
import streamlit as st

from core import auth
from core.calculs import COMPTES, charger, soldes
from core.db import MouvementTresorerie, Session
from core.format import afficher_flash, date_fr, fcfa, flash

TYPES = {"apport": "Apport", "depense": "Dépense", "decaissement": "Décaissement",
         "reevaluation": "Réévaluation du capital", "transfert": "Transfert interne"}


def _enregistrer(**champs):
    with Session() as s:
        s.add(MouvementTresorerie(auteur_id=auth.utilisateur()["id"], **champs))
        s.commit()


def page():
    st.title("Trésorerie")
    st.caption("L'argent disponible sur chaque compte. Les caisses reçoivent les recettes "
               "(ventes, commissions) ; le capital Airtel / MTN sert à faire les opérations.")
    afficher_flash()
    d = charger()
    sol = soldes(d)

    c = st.columns(4)
    for col, (k, nom) in zip(c, COMPTES.items()):
        col.metric(nom, fcfa(sol[k]))
    t1, t2 = st.columns(2)
    t1.metric("Trésorerie disponible (caisses)", fcfa(sol["caisse_bar"] + sol["caisse_cabine"]))
    t2.metric("Capital cabine (Airtel + MTN)", fcfa(sol["capital_airtel"] + sol["capital_mtn"]))
    for k in COMPTES:
        if sol[k] < 0:
            st.warning(f"{COMPTES[k]} est négatif ({fcfa(sol[k])}) : un apport ou une recette n'a "
                       "probablement pas été saisi.")

    st.divider()
    onglets = st.tabs(["Apport", "Transfert interne", "Réévaluation du capital", "Décaissement"])

    with onglets[0]:
        st.caption("Argent que tu envoies : fonds de caisse du bar ou capital de départ Airtel / MTN.")
        with st.form("apport", clear_on_submit=True):
            a1, a2 = st.columns(2)
            jour = a1.date_input("Date", value=date.today(), format="DD/MM/YYYY")
            dest = a2.selectbox("Vers", list(COMPTES), format_func=COMPTES.get)
            montant = st.number_input("Montant (FCFA)", min_value=0, step=1000)
            note = st.text_input("Note (facultatif)")
            if st.form_submit_button("Enregistrer l'apport", type="primary"):
                if montant <= 0:
                    st.error("Indique le montant.")
                else:
                    _enregistrer(date=jour, type="apport", montant=float(montant), compte_dest=dest,
                                 libelle=note.strip() or None)
                    flash(f"Apport de {fcfa(montant)} enregistré sur {COMPTES[dest]}.")
                    st.rerun()

    with onglets[1]:
        st.caption("Argent qui passe d'un compte à l'autre, par exemple de la caisse du bar vers le "
                   "capital MTN. Ce n'est ni une recette ni une dépense.")
        with st.form("transfert", clear_on_submit=True):
            b1, b2, b3 = st.columns(3)
            jour = b1.date_input("Date", value=date.today(), format="DD/MM/YYYY", key="tr_date")
            src = b2.selectbox("De", list(COMPTES), format_func=COMPTES.get)
            dest = b3.selectbox("Vers", list(COMPTES), format_func=COMPTES.get, index=3)
            montant = st.number_input("Montant (FCFA)", min_value=0, step=1000, key="tr_m")
            note = st.text_input("Note (facultatif)", key="tr_n")
            if st.form_submit_button("Enregistrer le transfert", type="primary"):
                if montant <= 0:
                    st.error("Indique le montant.")
                elif src == dest:
                    st.error("Choisis deux comptes différents.")
                else:
                    _enregistrer(date=jour, type="transfert", montant=float(montant), compte_source=src,
                                 compte_dest=dest, libelle=note.strip() or None)
                    msg = f"Transfert de {fcfa(montant)} : {COMPTES[src]} → {COMPTES[dest]}."
                    if montant > sol[src]:
                        msg += f" Attention : le solde de {COMPTES[src]} devient négatif."
                    flash(msg, "warning" if montant > sol[src] else "success")
                    st.rerun()

    with onglets[2]:
        st.caption("Après un comptage réel du capital d'un réseau (solde électronique + espèces), "
                   "saisis le montant compté : l'écart est enregistré comme réévaluation.")
        r1, r2 = st.columns(2)
        cap = r1.selectbox("Capital", ["capital_airtel", "capital_mtn"], format_func=COMPTES.get)
        compte = r2.number_input("Montant compté (FCFA)", min_value=0, step=1000, value=int(max(sol[cap], 0)),
                                 key=f"reev_{cap}")
        ecart = compte - sol[cap]
        st.metric("Écart avec le capital enregistré", fcfa(ecart))
        note = st.text_input("Explication", key="reev_note", placeholder="Comptage du 30/09")
        if st.button("Enregistrer la réévaluation", type="primary", disabled=ecart == 0):
            _enregistrer(date=date.today(), type="reevaluation", montant=float(ecart), compte_dest=cap,
                         libelle=note.strip() or None)
            flash(f"{COMPTES[cap]} réévalué à {fcfa(compte)}.")
            st.rerun()

    with onglets[3]:
        st.caption("Argent sorti de l'activité pour toi ou pour le gestionnaire. À l'étape 3, la clôture "
                   "du mois créera ces décaissements automatiquement selon la clé de partage.")
        with st.form("decaissement", clear_on_submit=True):
            e1, e2, e3 = st.columns(3)
            jour = e1.date_input("Date", value=date.today(), format="DD/MM/YYYY", key="dec_date")
            src = e2.selectbox("Depuis", ["caisse_bar", "caisse_cabine"], format_func=COMPTES.get)
            benef = e3.selectbox("Bénéficiaire", ["Propriétaire", "Gestionnaire"])
            montant = st.number_input("Montant (FCFA)", min_value=0, step=1000, key="dec_m")
            note = st.text_input("Note (facultatif)", key="dec_n")
            if st.form_submit_button("Enregistrer le décaissement", type="primary"):
                if montant <= 0:
                    st.error("Indique le montant.")
                else:
                    _enregistrer(date=jour, type="decaissement", montant=float(montant), compte_source=src,
                                 categorie=benef, libelle=note.strip() or None)
                    flash(f"Décaissement de {fcfa(montant)} enregistré ({benef}).")
                    st.rerun()

    st.divider()
    st.subheader("Derniers mouvements")
    mvts = sorted(d.mouvements, key=lambda m: (m.date, m.id), reverse=True)[:30]
    if not mvts:
        st.caption("Aucun mouvement. Commence par les apports de départ : fonds de caisse du bar, "
                   "capital Airtel et capital MTN.")
        return
    st.dataframe(pd.DataFrame([{
        "Date": date_fr(m.date), "Type": TYPES.get(m.type, m.type),
        "De": COMPTES.get(m.compte_source, "—"), "Vers": COMPTES.get(m.compte_dest, "—"),
        "Montant": fcfa(m.montant),
        "Détail": " · ".join(x for x in [m.categorie, m.libelle] if x),
        "Par": d.utilisateurs.get(m.auteur_id, "?"),
    } for m in mvts]), hide_index=True, width="stretch")
