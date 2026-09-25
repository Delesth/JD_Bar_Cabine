"""Tableau de bord (propriétaire) : vue totale, bar et cabine."""
from datetime import date, timedelta

import altair as alt
import pandas as pd
import streamlit as st

from core.calculs import (OPERATEURS, TYPES_CABINE, charger, indicateurs, indicateurs_cabine,
                          par_produit, rejouer, soldes, total_mouvements)
from core.export import excel_tableau_de_bord, nom_fichier
from core.db import lire_parametre
from core.format import fcfa, nombre, quantite

VERT, AIRTEL, MTN = "#1E5A42", "#D7262E", "#E3B100"


def _periode():
    auj = date.today()
    choix = st.radio("Période", ["Aujourd'hui", "Ce mois", "Mois dernier", "Depuis le début", "Personnalisée"],
                     horizontal=True, index=1, label_visibility="collapsed")
    if choix == "Aujourd'hui":
        return auj, auj
    if choix == "Ce mois":
        return auj.replace(day=1), auj
    if choix == "Mois dernier":
        fin = auj.replace(day=1) - timedelta(days=1)
        return fin.replace(day=1), fin
    if choix == "Depuis le début":
        return None, None
    plage = st.date_input("Du … au …", value=(auj.replace(day=1), auj), format="DD/MM/YYYY")
    return (plage[0], plage[1]) if len(plage) == 2 else (plage[0], plage[0])


def _series(valeurs_par_jour: dict, debut, fin, serie: str) -> list:
    """Une ligne par jour de la période (ou par mois depuis le début)."""
    if debut is None:
        par_mois = {}
        for j, v in valeurs_par_jour.items():
            par_mois[(j.year, j.month)] = par_mois.get((j.year, j.month), 0) + v
        return [{"Période": f"{m:02d}/{a}", "Montant": v, "Série": serie, "o": a * 100 + m}
                for (a, m), v in sorted(par_mois.items())]
    lignes, j = [], debut
    while j <= fin:
        lignes.append({"Période": j.strftime("%d/%m"), "Montant": valeurs_par_jour.get(j, 0),
                       "Série": serie, "o": j.toordinal()})
        j += timedelta(days=1)
    return lignes


def _graphique(lignes: list, couleurs: dict, titre: str):
    if not lignes or not any(l["Montant"] for l in lignes):
        return
    st.subheader(titre)
    df = pd.DataFrame(lignes)
    df["Valeur"] = df["Montant"].map(fcfa)
    ordre = list(dict.fromkeys(df.sort_values("o")["Période"]))
    base = alt.Chart(df).mark_bar(cornerRadiusTopLeft=2, cornerRadiusTopRight=2).encode(
        x=alt.X("Période:N", sort=ordre, title=None, axis=alt.Axis(labelAngle=-45)),
        y=alt.Y("sum(Montant):Q", title="FCFA", axis=alt.Axis(format="d")),
        color=alt.Color("Série:N", title=None,
                        scale=alt.Scale(domain=list(couleurs), range=list(couleurs.values())),
                        legend=alt.Legend(orient="top") if len(couleurs) > 1 else None),
        tooltip=[alt.Tooltip("Période:N", title="Date"), alt.Tooltip("Série:N", title=" "),
                 alt.Tooltip("Valeur:N", title="Montant")],
    ).properties(height=260)
    st.altair_chart(base, width="stretch")


def _vue_totale(d, r, ind_bar, ind_cab, dep_bar, sol, debut, fin):
    valeur_stock = sum(max(s["qte"], 0) * s["cmp"] for s in r.stock.values())
    benef_bar = ind_bar.benefice - dep_bar
    ca_total = ind_bar.ca + ind_cab.commission_totale
    benef_total = benef_bar + ind_cab.benefice
    tresor_bar, tresor_cab = sol["caisse_bar"], sol["caisse_cabine"]
    capital_cab = sol["capital_airtel"] + sol["capital_mtn"]

    c1, c2, c3 = st.columns(3)
    c1.metric("Chiffre d'affaires total", fcfa(ca_total))
    c2.metric("Bénéfice total", fcfa(benef_total))
    c3.metric("Trésorerie disponible", fcfa(tresor_bar + tresor_cab), help="À ce jour, toutes périodes")

    st.dataframe(pd.DataFrame([
        {"": "Chiffre d'affaires", "Bar": fcfa(ind_bar.ca), "Cabine": fcfa(ind_cab.commission_totale),
         "Total": fcfa(ca_total)},
        {"": "Dépenses", "Bar": fcfa(dep_bar), "Cabine": fcfa(ind_cab.depenses),
         "Total": fcfa(dep_bar + ind_cab.depenses)},
        {"": "Bénéfice", "Bar": fcfa(benef_bar), "Cabine": fcfa(ind_cab.benefice), "Total": fcfa(benef_total)},
        {"": "Trésorerie disponible (à ce jour)", "Bar": fcfa(tresor_bar), "Cabine": fcfa(tresor_cab),
         "Total": fcfa(tresor_bar + tresor_cab)},
        {"": "Capital (à ce jour)", "Bar": fcfa(valeur_stock) + " (stock)",
         "Cabine": fcfa(capital_cab) + " (Airtel + MTN)", "Total": fcfa(valeur_stock + capital_cab)},
    ]), hide_index=True, width="stretch")
    st.caption("Le chiffre d'affaires de la cabine correspond aux commissions, pas au volume des opérations. "
               "Bénéfice du bar = ventes − coût des boissons vendues − pertes de stock − dépenses du bar.")

    dec = total_mouvements(d, "decaissement", debut, fin)
    app = sum(total_mouvements(d, "apport", debut, fin, dest=k) for k in ("capital_airtel", "capital_mtn"))
    e1, e2 = st.columns(2)
    e1.metric("Décaissements sur la période", fcfa(dec))
    e2.metric("Apports au capital cabine sur la période", fcfa(app))

    ca_jour = dict(ind_bar.ca_par_jour)
    com_jour = {}
    for (j, _), v in ind_cab.commissions_par_jour.items():
        com_jour[j] = com_jour.get(j, 0) + v
    if debut != fin or debut is None:
        _graphique(_series(ca_jour, debut, fin, "Bar") + _series(com_jour, debut, fin, "Cabine"),
                   {"Bar": VERT, "Cabine": MTN}, "Chiffre d'affaires")


def _vue_bar(d, r, ind, dep_bar, tous, debut, fin):
    c1, c2, c3 = st.columns(3)
    c1.metric("Chiffre d'affaires", fcfa(ind.ca))
    c2.metric("Bénéfice net", fcfa(ind.benefice - dep_bar),
              help="Ventes − coût des boissons vendues − pertes de stock − dépenses du bar")
    c3.metric("Marge sur ventes", f"{nombre(round(ind.marge, 1))} %")
    c4, c5, c6 = st.columns(3)
    c4.metric("Coût des boissons vendues", fcfa(ind.cout_ventes))
    c5.metric("Dépenses du bar", fcfa(dep_bar))
    c6.metric("Pertes de stock (comptages)", fcfa(abs(ind.pertes_stock)))
    c7, c8 = st.columns(2)
    c7.metric("Achats de la période", fcfa(ind.achats))
    c8.metric("Valeur actuelle du stock", fcfa(sum(max(s["qte"], 0) * s["cmp"] for s in r.stock.values())))

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
    if debut != fin or debut is None:
        _graphique(_series(ind.ca_par_jour, debut, fin, "Bar"), {"Bar": VERT}, "Chiffre d'affaires du bar")


def _vue_cabine(d, ind, sol, debut, fin):
    c1, c2, c3 = st.columns(3)
    c1.metric("Commissions (CA cabine)", fcfa(ind.commission_totale))
    c2.metric("Dépenses de la cabine", fcfa(ind.depenses))
    c3.metric("Bénéfice cabine", fcfa(ind.benefice))

    cols = st.columns(2)
    for col, (k, nom) in zip(cols, OPERATEURS.items()):
        with col.container(border=True):
            st.markdown(f"**{nom}**")
            st.metric("Capital actuel", fcfa(sol[f"capital_{k}"]))
            st.metric("Commissions", fcfa(ind.commissions[k]))
            st.metric("Volume d'opérations", fcfa(ind.volumes[k]))
            detail = [{"Opération": lib, "Volume": fcfa(ind.detail.get((k, t), (0, 0))[0]),
                       "Commission": fcfa(ind.detail.get((k, t), (0, 0))[1])} for t, lib in TYPES_CABINE.items()]
            st.dataframe(pd.DataFrame(detail), hide_index=True, width="stretch")
    st.caption("Le volume est l'argent des clients qui transite par la cabine : il n'est pas compté "
               "dans le chiffre d'affaires.")
    if debut != fin or debut is None:
        lignes = []
        for k, nom in OPERATEURS.items():
            par_jour = {j: v for (j, o), v in ind.commissions_par_jour.items() if o == k}
            lignes += _series(par_jour, debut, fin, nom)
        _graphique(lignes, {"Airtel": AIRTEL, "MTN": MTN}, "Commissions par réseau")


def page():
    st.title("Tableau de bord")
    d = charger()
    if not d.produits and not d.operations and not d.mouvements:
        st.info("Bienvenue ! Pour démarrer : crée les boissons (Produits), enregistre les apports de départ "
                "(Trésorerie : fonds de caisse du bar, capital Airtel, capital MTN), puis le compte du "
                "gestionnaire (Paramètres).")
        return
    debut, fin = _periode()
    r = rejouer(d)
    ind_bar = indicateurs(d, r, debut, fin)
    tous = indicateurs(d, r, None, None)
    ind_cab = indicateurs_cabine(d, debut, fin)
    dep_bar = total_mouvements(d, "depense", debut, fin, source="caisse_bar")
    sol = soldes(d)
    if tous.en_attente:
        st.error(f"{tous.en_attente} vente(s) à perte attendent ta décision dans la page « À valider ».")
    bouton_excel(d, debut, fin, proprietaire=True)

    t_total, t_bar, t_prod, t_cab = st.tabs(["Total", "Bar", "Par produit", "Cabine"])
    with t_total:
        _vue_totale(d, r, ind_bar, ind_cab, dep_bar, sol, debut, fin)
    with t_bar:
        _vue_bar(d, r, ind_bar, dep_bar, tous, debut, fin)
    with t_prod:
        tableau_par_produit(d, r, debut, fin, proprietaire=True)
    with t_cab:
        _vue_cabine(d, ind_cab, sol, debut, fin)


def tableau_par_produit(d, r, debut, fin, proprietaire: bool):
    lignes = par_produit(d, r, debut, fin)
    if not lignes:
        st.caption("Aucune vente ni aucun achat sur la période.")
        return
    rows = []
    for l in lignes:
        p = l["produit"]
        row = {"Produit": p.nom, "Vendu": quantite(l["qte_vendue"], p.unite_vente), "CA": fcfa(l["ca"]),
               "Bénéfice": fcfa(l["benefice"]), "Acheté": quantite(l["qte_achetee"], p.unite_vente),
               "Achats": fcfa(l["achats"]), "Stock actuel": quantite(l["stock"], p.unite_vente)}
        if proprietaire:
            row["Valeur du stock"] = fcfa(l["valeur_stock"])
        rows.append(row)
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def bouton_excel(d, debut, fin, proprietaire: bool):
    st.download_button("⬇️ Télécharger en Excel (période affichée)",
                       data=excel_tableau_de_bord(d, debut, fin, proprietaire),
                       file_name=nom_fichier(debut, fin),
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
