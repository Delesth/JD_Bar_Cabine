"""Référentiel des boissons."""
import pandas as pd
import streamlit as st

from core.calculs import charger
from core.db import Produit, Session
from core.format import afficher_flash, fcfa, flash

CATEGORIES = {"locale": "Locale", "importee": "Importée"}
UNITES = {"bouteille": "Bouteille", "canette": "Canette"}
CONDITIONNEMENTS = {"casier": "Casier", "pack": "Pack", "carton": "Carton", "unité": "À l'unité"}


def _formulaire(p: Produit | None, cle: str):
    with st.form(cle, clear_on_submit=p is None):
        nom = st.text_input("Nom", value=p.nom if p else "", placeholder="Primus")
        c1, c2 = st.columns(2)
        cat = c1.selectbox("Catégorie", list(CATEGORIES), format_func=CATEGORIES.get,
                           index=list(CATEGORIES).index(p.categorie) if p else 0)
        unite = c2.selectbox("Unité de vente (unité du stock)", list(UNITES), format_func=UNITES.get,
                             index=list(UNITES).index(p.unite_vente) if p else 0)
        c3, c4 = st.columns(2)
        cond = c3.selectbox("Conditionnement habituel à l'achat", list(CONDITIONNEMENTS),
                            format_func=CONDITIONNEMENTS.get,
                            index=list(CONDITIONNEMENTS).index(p.conditionnement) if p else 0)
        upc = c4.number_input("Unités par conditionnement", min_value=1, step=1,
                              value=int(p.unites_par_cond) if p else 12,
                              help="Ignoré si le produit est acheté à l'unité.")
        c5, c6 = st.columns(2)
        pv = c5.number_input("Prix de vente d'une unité (FCFA)", min_value=0, step=50,
                             value=int(p.prix_vente) if p else 0)
        seuil = c6.number_input("Alerte stock bas (en unités)", min_value=0, step=1,
                                value=int(p.seuil_stock) if p else 0)
        actif = st.checkbox("Produit actif", value=p.actif if p else True,
                            help="Un produit inactif n'apparaît plus dans les saisies.") if p else True
        ok = st.form_submit_button("Enregistrer les modifications" if p else "Ajouter le produit",
                                   type="primary")
    if not ok:
        return
    if not nom.strip():
        st.error("Donne un nom au produit.")
        return
    with Session() as s:
        cible = s.get(Produit, p.id) if p else Produit()
        doublon = s.query(Produit).filter(Produit.nom.ilike(nom.strip()), Produit.id != (p.id if p else -1)).first()
        if doublon:
            st.error(f"Un produit s'appelle déjà « {doublon.nom} ».")
            return
        cible.nom, cible.categorie, cible.unite_vente = nom.strip(), cat, unite
        cible.conditionnement = cond
        cible.unites_par_cond = 1 if cond == "unité" else int(upc)
        cible.prix_vente, cible.seuil_stock, cible.actif = float(pv), int(seuil), bool(actif)
        if not p:
            s.add(cible)
        s.commit()
    flash("Produit enregistré.")
    st.rerun()


def page():
    st.title("Produits")
    st.caption("La liste des boissons du bar. Le coût d'achat n'est pas saisi ici : "
               "il est calculé à partir des achats.")
    afficher_flash()
    d = charger()
    if d.produits:
        df = pd.DataFrame([{
            "Produit": p.nom,
            "Catégorie": CATEGORIES.get(p.categorie, p.categorie),
            "Vendu en": UNITES.get(p.unite_vente, p.unite_vente).lower(),
            "Acheté en": ("à l'unité" if p.conditionnement == "unité"
                          else f"{p.conditionnement} de {p.unites_par_cond}"),
            "Prix de vente": fcfa(p.prix_vente),
            "Actif": "Oui" if p.actif else "Non",
        } for p in d.produits])
        st.dataframe(df, hide_index=True, width="stretch")
    else:
        st.info("Aucun produit pour l'instant. Ajoute ta première boisson ci-dessous.")

    t1, t2 = st.tabs(["Ajouter un produit", "Modifier un produit"])
    with t1:
        _formulaire(None, "nouveau_produit")
    with t2:
        if not d.produits:
            st.caption("Aucun produit à modifier.")
        else:
            choix = st.selectbox("Produit à modifier", d.produits, format_func=lambda p: p.nom)
            _formulaire(choix, f"modif_{choix.id}")
