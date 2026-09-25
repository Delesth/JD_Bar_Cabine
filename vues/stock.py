"""État du stock et comptage physique."""
from datetime import date

import pandas as pd
import streamlit as st

from core import auth
from core.calculs import charger, rejouer
from core.db import AjustementStock, Session
from core.format import afficher_flash, date_fr, equivalent, fcfa, flash, gen, quantite, vider


def page():
    proprio = auth.est_proprietaire()
    st.title("Stock")
    st.caption("Stock = achats − ventes − écarts de comptage. Mis à jour à chaque saisie.")
    afficher_flash()
    d = charger()
    produits = [p for p in d.produits if p.actif]
    if not produits:
        st.info("Aucun produit pour l'instant.")
        return
    r = rejouer(d)

    bas = [p for p in produits if p.seuil_stock and r.stock.get(p.id, {}).get("qte", 0) <= p.seuil_stock]
    if bas:
        st.warning("Stock bas : " + ", ".join(
            f"{p.nom} ({quantite(r.stock[p.id]['qte'], p.unite_vente)})" for p in bas))

    lignes, valeur_totale = [], 0.0
    for p in produits:
        s = r.stock.get(p.id, {"qte": 0, "cmp": 0})
        valeur = max(s["qte"], 0) * s["cmp"]
        valeur_totale += valeur
        ligne = {"Produit": p.nom, "En stock": quantite(s["qte"], p.unite_vente),
                 "Soit": equivalent(s["qte"], p)}
        if proprio:
            ligne |= {"Coût moyen": fcfa(s["cmp"]), "Prix de vente": fcfa(p.prix_vente),
                      "Valeur du stock": fcfa(valeur)}
        lignes.append(ligne)
    st.dataframe(pd.DataFrame(lignes), hide_index=True, width="stretch")
    if proprio:
        st.metric("Valeur totale du stock (au coût d'achat)", fcfa(valeur_totale))

    st.divider()
    st.subheader("Comptage physique")
    st.caption("Compte ce qu'il y a réellement en rayon et en réserve, puis saisis-le ici. "
               "L'écart (casse, boissons offertes, pertes) est enregistré comme perte, jamais comme vente. "
               "Laisse vide les produits non comptés.")
    df = pd.DataFrame([{"pid": p.id, "Produit": p.nom,
                        "Stock calculé": r.stock.get(p.id, {}).get("qte", 0),
                        "Quantité comptée": None} for p in produits])
    edite = st.data_editor(
        df, key=f"comptage_{gen('comptage')}", hide_index=True, width="stretch",
        disabled=["Produit", "Stock calculé"], column_order=["Produit", "Stock calculé", "Quantité comptée"],
        column_config={"Stock calculé": st.column_config.NumberColumn(format="%g"),
                       "Quantité comptée": st.column_config.NumberColumn(min_value=0, step=1, format="%d")},
    )
    motif = st.text_input("Explication des écarts (facultatif)", placeholder="2 bouteilles cassées à la livraison",
                          key=f"comptage_motif_{gen('comptage')}")
    ecarts = []
    for _, l in edite.iterrows():
        if pd.notna(l["Quantité comptée"]) and float(l["Quantité comptée"]) != float(l["Stock calculé"]):
            p = d.produit(int(l["pid"]))
            ecarts.append((p, float(l["Stock calculé"]), float(l["Quantité comptée"])))
    if ecarts:
        texte = []
        for p, theo, compte in ecarts:
            e = compte - theo
            val = e * r.stock.get(p.id, {}).get("cmp", 0)
            texte.append(f"{p.nom} : {'+' if e > 0 else ''}{quantite(e, p.unite_vente)}"
                         + (f" ({fcfa(val)})" if proprio else ""))
        st.info("Écarts constatés :\n\n- " + "\n- ".join(texte))
    if st.button("Enregistrer le comptage", type="primary", disabled=not ecarts, width="stretch"):
        with Session() as s:
            for p, theo, compte in ecarts:
                s.add(AjustementStock(date=date.today(), produit_id=p.id, quantite_theorique=theo,
                                      quantite_comptee=compte, motif=motif.strip() or None,
                                      auteur_id=auth.utilisateur()["id"]))
            s.commit()
        vider("comptage")
        flash(f"Comptage enregistré : {len(ecarts)} écart(s) pris en compte.")
        st.rerun()

    if d.ajustements:
        with st.expander("Derniers comptages"):
            st.dataframe(pd.DataFrame([{
                "Date": date_fr(j.date), "Produit": d.produit(j.produit_id).nom,
                "Calculé": j.quantite_theorique, "Compté": j.quantite_comptee, "Écart": j.ecart,
                "Explication": j.motif or "", "Par": d.utilisateurs.get(j.auteur_id, "?"),
            } for j in sorted(d.ajustements, key=lambda x: x.id, reverse=True)[:20]]),
                hide_index=True, width="stretch")
