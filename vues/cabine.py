"""Saisie quotidienne de la cabine Airtel / MTN."""
from datetime import date

import pandas as pd
import streamlit as st

from core import auth
from core.calculs import OPERATEURS, TYPES_CABINE, charger, indicateurs_cabine, soldes
from core.db import OperationCabine, Session
from core.format import afficher_flash, date_fr, fcfa, flash, gen, vider


def page():
    st.title("Cabine du jour")
    st.caption("En fin de journée, pour chaque réseau : le montant total des opérations et la commission "
               "gagnée. Le montant est l'argent des clients (il ne fait que transiter) ; seule la "
               "commission est un revenu.")
    afficher_flash()
    d = charger()
    jour = st.date_input("Date", value=date.today(), max_value=date.today(), format="DD/MM/YYYY")
    op = st.radio("Réseau", list(OPERATEURS), format_func=OPERATEURS.get, horizontal=True)

    existantes = {o.type: o for o in d.operations if o.date == jour and o.operateur == op}
    cle_modif = f"modif_cab_{jour.isoformat()}_{op}"
    if existantes and not st.session_state.get(cle_modif):
        _recap_verrouille(d, jour, op, existantes, cle_modif)
    else:
        _saisie(jour, op, existantes, cle_modif)
    _resume(d, jour)


def _recap_verrouille(d, jour, op, existantes, cle_modif):
    st.success(f"{OPERATEURS[op]} du {date_fr(jour)} enregistré. La saisie est verrouillée pour éviter "
               "un double envoi ; clique sur « Modifier » pour la corriger.")
    st.dataframe(pd.DataFrame([{
        "Opération": TYPES_CABINE[t], "Montant total": fcfa(o.montant), "Commission": fcfa(o.commission),
        "Saisi par": d.utilisateurs.get(o.auteur_id, "?"),
    } for t, o in existantes.items()]), hide_index=True, width="stretch")
    if st.button(f"Modifier {OPERATEURS[op]} du {date_fr(jour)}", key=f"btn_{cle_modif}"):
        st.session_state[cle_modif] = True
        st.rerun()


def _saisie(jour, op, existantes, cle_modif):
    df = pd.DataFrame([{
        "type": k, "Opération": lib,
        "Montant total (FCFA)": int(existantes[k].montant) if k in existantes else 0,
        "Commission (FCFA)": int(existantes[k].commission) if k in existantes else 0,
    } for k, lib in TYPES_CABINE.items()])
    edite = st.data_editor(
        df, key=f"cab_{jour.isoformat()}_{op}_{gen('cabine')}", hide_index=True, width="stretch",
        disabled=["Opération"], column_order=["Opération", "Montant total (FCFA)", "Commission (FCFA)"],
        column_config={
            "Montant total (FCFA)": st.column_config.NumberColumn(min_value=0, step=500, format="%d"),
            "Commission (FCFA)": st.column_config.NumberColumn(min_value=0, step=50, format="%d"),
        },
    )
    lignes = [(l["type"], float(l["Montant total (FCFA)"] or 0), float(l["Commission (FCFA)"] or 0))
              for _, l in edite.iterrows()]
    volume = sum(m for _, m, _ in lignes)
    commission = sum(c for _, _, c in lignes)
    c1, c2 = st.columns(2)
    c1.metric(f"Volume {OPERATEURS[op]} du jour", fcfa(volume))
    c2.metric(f"Commission {OPERATEURS[op]} du jour", fcfa(commission))

    suspectes = [TYPES_CABINE[t] for t, m, c in lignes if c > 0 and c > m]
    confirme = True
    if suspectes:
        st.warning("La commission est supérieure au montant des opérations pour : "
                   + ", ".join(suspectes) + ". Vérifie qu'il n'y a pas d'inversion entre les deux colonnes.")
        confirme = st.checkbox("Je confirme ces montants", key=f"cab_conf_{jour}_{op}_{gen('cabine')}")
    if existantes and st.button("Annuler la modification", key=f"annul_{cle_modif}"):
        st.session_state.pop(cle_modif, None)
        vider("cabine")
        st.rerun()

    if st.button(f"Enregistrer {OPERATEURS[op]} du {date_fr(jour)}", type="primary",
                 disabled=not confirme, width="stretch"):
        uid = auth.utilisateur()["id"]
        with Session() as s:
            for t, m, c in lignes:
                o = existantes.get(t)
                if m > 0 or c > 0:
                    o = s.get(OperationCabine, o.id) if o else OperationCabine(
                        date=jour, operateur=op, type=t, auteur_id=uid)
                    o.montant, o.commission = m, c
                    s.add(o)
                elif o:
                    s.delete(s.get(OperationCabine, o.id))
            s.commit()
        st.session_state.pop(cle_modif, None)
        vider("cabine")
        flash(f"{OPERATEURS[op]} du {date_fr(jour)} enregistré.")
        st.rerun()


def _resume(d, jour):
    st.divider()
    st.subheader(f"Résumé du {date_fr(jour)}")
    ind = indicateurs_cabine(d, jour, jour)
    mois = indicateurs_cabine(d, jour.replace(day=1), jour)
    sol = soldes(d)
    cols = st.columns(2)
    for col, (k, nom) in zip(cols, OPERATEURS.items()):
        with col.container(border=True):
            st.markdown(f"**{nom}**")
            st.metric("Commission du jour", fcfa(ind.commissions[k]))
            st.metric("Commission du mois", fcfa(mois.commissions[k]))
            st.metric("Capital actuel", fcfa(sol[f"capital_{k}"]))
    st.metric("Total des commissions du jour", fcfa(ind.commission_totale))
