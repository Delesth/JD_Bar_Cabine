"""Tableau de bord du bar (propriétaire)."""
from datetime import date, timedelta

import altair as alt
import pandas as pd
import streamlit as st

from core.calculs import charger, indicateurs, rejouer
from core.db import lire_parametre
from core.format import date_fr, fcfa, nombre


def page():
    st.title("Tableau de bord · Bar")
    d = charger()
    if not d.produits:
        st.info("Bienvenue ! Commence par créer tes boissons dans la page Produits, "
                "puis le compte du gestionnaire dans Paramètres.")
        return
    auj = date.today()
    choix = st.radio("Période", ["Aujourd'hui", "Ce mois", "Mois dernier", "Depuis le début", "Personnalisée"],
                     horizontal=True, index=1, label_visibility="collapsed")
    if choix == "Aujourd'hui":
        debut, fin = auj, auj
    elif choix == "Ce mois":
        debut, fin = auj.replace(day=1), auj
    elif choix == "Mois dernier":
        fin = auj.replace(day=1) - timedelta(days=1)
        debut = fin.replace(day=1)
    elif choix == "Depuis le début":
        debut, fin = None, None
    else:
        plage = st.date_input("Du … au …", value=(auj.replace(day=1), auj), format="DD/MM/YYYY")
        debut, fin = (plage[0], plage[1]) if len(plage) == 2 else (plage[0], plage[0])

    r = rejouer(d)
    ind = indicateurs(d, r, debut, fin)
    tous = indicateurs(d, r, None, None)

    if tous.en_attente:
        st.error(f"{tous.en_attente} vente(s) à perte attendent ta décision dans la page « À valider ».")

    c1, c2, c3 = st.columns(3)
    c1.metric("Chiffre d'affaires", fcfa(ind.ca))
    c2.metric("Bénéfice", fcfa(ind.benefice), help="Ventes − coût des boissons vendues − pertes de stock")
    c3.metric("Marge sur ventes", f"{nombre(round(ind.marge, 1))} %")
    c4, c5, c6 = st.columns(3)
    c4.metric("Coût des boissons vendues", fcfa(ind.cout_ventes))
    c5.metric("Achats de la période", fcfa(ind.achats))
    c6.metric("Pertes de stock (comptages)", fcfa(-ind.pertes_stock if ind.pertes_stock < 0 else ind.pertes_stock))

    valeur_stock = sum(max(s["qte"], 0) * s["cmp"] for s in r.stock.values())
    st.metric("Valeur actuelle du stock (au coût d'achat)", fcfa(valeur_stock))

    st.subheader("Réductions accordées")
    seuil = float(lire_parametre("seuil_reductions_pct") or 5)
    r1, r2 = st.columns(2)
    r1.metric("Total des réductions", fcfa(ind.reductions))
    r2.metric("Part du CA au prix normal", f"{nombre(round(ind.part_reductions, 1))} %",
              help=f"Seuil d'alerte : {nombre(seuil)} %")
    if ind.part_reductions > seuil:
        st.warning(f"Les réductions dépassent le seuil de {nombre(seuil)} % du chiffre d'affaires.")
    if ind.par_motif:
        st.dataframe(pd.DataFrame([{"Motif": m, "Montant": fcfa(v)} for m, v in
                                   sorted(ind.par_motif.items(), key=lambda x: -x[1])]),
                     hide_index=True, width="stretch")
    if ind.ventes_perte_validees or ind.a_regulariser:
        st.write(f"Ventes à perte validées : {fcfa(ind.ventes_perte_validees)} de perte · "
                 f"refusées, à régulariser : {fcfa(ind.a_regulariser)}")

    if ind.ca_par_jour and (debut is None or debut != fin):
        _graphique_ca(ind.ca_par_jour, debut, fin)


def _graphique_ca(ca_par_jour: dict, debut, fin):
    """Barres du CA : une par jour sur la période, ou une par mois depuis le début."""
    if debut is None:
        st.subheader("Chiffre d'affaires par mois")
        par_mois = {}
        for j, v in ca_par_jour.items():
            cle = (j.year, j.month)
            par_mois[cle] = par_mois.get(cle, 0) + v
        lignes = [{"Période": f"{m:02d}/{a}", "CA": v} for (a, m), v in sorted(par_mois.items())]
    else:
        st.subheader("Chiffre d'affaires par jour")
        lignes, j = [], debut
        while j <= fin:
            lignes.append({"Période": j.strftime("%d/%m"), "CA": ca_par_jour.get(j, 0)})
            j += timedelta(days=1)
    df = pd.DataFrame(lignes)
    df["Montant"] = df["CA"].map(fcfa)
    graphique = alt.Chart(df).mark_bar(color="#1E5A42", cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        x=alt.X("Période:N", sort=None, title=None, axis=alt.Axis(labelAngle=-45)),
        y=alt.Y("CA:Q", title="FCFA", axis=alt.Axis(format="d")),
        tooltip=[alt.Tooltip("Période:N", title="Date"), alt.Tooltip("Montant:N", title="CA")],
    ).properties(height=280)
    st.altair_chart(graphique, width="stretch")
