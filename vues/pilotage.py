"""Tableau de bord du gestionnaire : pilotage des achats, des ventes et de la cabine."""
import streamlit as st

from core.calculs import OPERATEURS, charger, indicateurs, indicateurs_cabine, rejouer, total_mouvements
from core.db import lire_parametre
from core.format import fcfa, nombre
from vues.tableau_bord import (MTN, AIRTEL, VERT, _graphique, _periode, _series, bouton_excel,
                               tableau_par_produit)


def page():
    st.title("Tableau de bord")
    st.caption("Suivi des ventes, des achats et de la cabine sur la période choisie.")
    d = charger()
    if not d.produits and not d.operations:
        st.info("Aucune donnée pour l'instant : commence par saisir les achats et les ventes.")
        return
    debut, fin = _periode()
    r = rejouer(d)
    ib = indicateurs(d, r, debut, fin)
    ic = indicateurs_cabine(d, debut, fin)
    dep_bar = total_mouvements(d, "depense", debut, fin, source="caisse_bar")
    bouton_excel(d, debut, fin, proprietaire=False)

    t_bar, t_prod, t_cab = st.tabs(["Bar", "Par produit", "Cabine"])
    with t_bar:
        c1, c2, c3 = st.columns(3)
        c1.metric("Chiffre d'affaires", fcfa(ib.ca))
        c2.metric("Achats", fcfa(ib.achats))
        c3.metric("Bénéfice net du bar", fcfa(ib.benefice - dep_bar),
                  help="Ventes − coût des boissons vendues − pertes de stock − dépenses du bar")
        c4, c5, c6 = st.columns(3)
        c4.metric("Dépenses du bar", fcfa(dep_bar))
        seuil = float(lire_parametre("seuil_reductions_pct") or 5)
        c5.metric("Réductions accordées", fcfa(ib.reductions))
        c6.metric("Part des réductions", f"{nombre(round(ib.part_reductions, 1))} %",
                  help=f"Seuil d'alerte fixé par le propriétaire : {nombre(seuil)} %")
        if ib.part_reductions > seuil:
            st.warning(f"Les réductions dépassent le seuil de {nombre(seuil)} % du chiffre d'affaires.")
        if ib.en_attente:
            st.info(f"{ib.en_attente} vente(s) à perte en attente de validation par le propriétaire.")
        if debut != fin or debut is None:
            _graphique(_series(ib.ca_par_jour, debut, fin, "Bar"), {"Bar": VERT}, "Chiffre d'affaires du bar")
    with t_prod:
        tableau_par_produit(d, r, debut, fin, proprietaire=False)
    with t_cab:
        c1, c2, c3 = st.columns(3)
        c1.metric("Commissions", fcfa(ic.commission_totale))
        c2.metric("Dépenses de la cabine", fcfa(ic.depenses))
        c3.metric("Bénéfice de la cabine", fcfa(ic.benefice))
        cols = st.columns(2)
        for col, (k, nom) in zip(cols, OPERATEURS.items()):
            with col.container(border=True):
                st.markdown(f"**{nom}**")
                st.metric("Commissions", fcfa(ic.commissions[k]))
                st.metric("Volume d'opérations", fcfa(ic.volumes[k]))
        if debut != fin or debut is None:
            lignes = []
            for k, nom in OPERATEURS.items():
                par_jour = {j: v for (j, o), v in ic.commissions_par_jour.items() if o == k}
                lignes += _series(par_jour, debut, fin, nom)
            _graphique(lignes, {"Airtel": AIRTEL, "MTN": MTN}, "Commissions par réseau")
