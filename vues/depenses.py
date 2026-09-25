"""Dépenses courantes du bar et de la cabine."""
from datetime import date

import pandas as pd
import streamlit as st

from core import auth
from core.calculs import charger, soldes
from core.db import MouvementTresorerie, Session
from core.format import afficher_flash, date_fr, fcfa, flash, gen, vider

CATEGORIES = ["Glace", "Électricité", "Eau", "Loyer", "Transport", "Entretien / réparation",
              "Salaire", "Autre"]
ACTIVITES = {"bar": "Bar", "cabine": "Cabine"}


def page():
    st.title("Dépenses")
    st.caption("Toute sortie d'argent pour faire fonctionner l'activité : glace, électricité, transport…")
    afficher_flash()
    d = charger()
    sol = soldes(d)

    g = gen("depense")
    c1, c2 = st.columns(2)
    jour = c1.date_input("Date", value=date.today(), max_value=date.today(), format="DD/MM/YYYY", key=f"d{g}_date")
    act = c2.radio("Payée avec la caisse", list(ACTIVITES), format_func=ACTIVITES.get, horizontal=True,
                   key=f"d{g}_act")
    c3, c4 = st.columns(2)
    montant = c3.number_input("Montant (FCFA)", min_value=0, step=500, value=0, key=f"d{g}_montant")
    cat = c4.selectbox("Catégorie", CATEGORIES, key=f"d{g}_cat")
    precision = st.text_input("Détail" + (" (obligatoire)" if cat == "Autre" else " (facultatif)"),
                              placeholder="Ex. 2 sacs de glace", key=f"d{g}_prec")
    solde = sol[f"caisse_{act}"]
    if montant and montant > solde:
        st.warning(f"Cette dépense dépasse le solde de la caisse {ACTIVITES[act].lower()} "
                   f"({fcfa(solde)}). Vérifie le montant, ou qu'un apport a bien été enregistré.")

    if st.button("Enregistrer la dépense", type="primary", width="stretch", key=f"d{g}_ok"):
        if montant <= 0:
            st.error("Indique le montant.")
        elif cat == "Autre" and not precision.strip():
            st.error("Précise la nature de la dépense.")
        else:
            with Session() as s:
                s.add(MouvementTresorerie(date=jour, type="depense", montant=float(montant),
                                          compte_source=f"caisse_{act}", categorie=cat,
                                          libelle=precision.strip() or None,
                                          auteur_id=auth.utilisateur()["id"]))
                s.commit()
            vider("depense")
            flash(f"Dépense de {fcfa(montant)} enregistrée ({ACTIVITES[act]}).")
            st.rerun()

    debut = date.today().replace(day=1)
    du_mois = sorted([m for m in d.mouvements if m.type == "depense" and m.date >= debut],
                     key=lambda m: (m.date, m.id), reverse=True)
    st.subheader("Dépenses du mois")
    if not du_mois:
        st.caption("Aucune dépense ce mois-ci.")
        return
    t1, t2 = st.columns(2)
    t1.metric("Bar", fcfa(sum(m.montant for m in du_mois if m.compte_source == "caisse_bar")))
    t2.metric("Cabine", fcfa(sum(m.montant for m in du_mois if m.compte_source == "caisse_cabine")))
    moi = auth.utilisateur()
    for m in du_mois:
        a, b = st.columns([5, 1])
        a.write(f"{date_fr(m.date)} · {ACTIVITES.get(m.compte_source.replace('caisse_', ''), '?')} · "
                f"{m.categorie}{' : ' + m.libelle if m.libelle else ''} · **{fcfa(m.montant)}**")
        peut = auth.est_proprietaire() or (m.auteur_id == moi["id"] and m.date == date.today())
        if peut and b.button("Supprimer", key=f"del_dep_{m.id}"):
            with Session() as s:
                s.delete(s.get(MouvementTresorerie, m.id))
                s.commit()
            flash("Dépense supprimée.")
            st.rerun()
