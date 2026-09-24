"""Saisie d'un achat de boissons avec calculs automatiques."""
from datetime import date

import pandas as pd
import streamlit as st

from core import auth
from core.calculs import charger
from core.db import Achat, Produit, Session
from core.format import afficher_flash, date_fr, fcfa, flash, nombre, pluriel
from vues.produits import CONDITIONNEMENTS


def page():
    st.title("Nouvel achat")
    st.caption("Saisis ce qui a été acheté : l'application calcule le reste.")
    afficher_flash()
    d = charger()
    produits = [p for p in d.produits if p.actif]
    if not produits:
        st.info("Crée d'abord les boissons dans la page Produits.")
        return

    jour = st.date_input("Date de l'achat", value=date.today(), max_value=date.today(), format="DD/MM/YYYY")
    p = st.selectbox("Produit", produits, format_func=lambda x: x.nom)
    c1, c2 = st.columns(2)
    cond = c1.selectbox("Acheté en", list(CONDITIONNEMENTS), format_func=CONDITIONNEMENTS.get,
                        index=list(CONDITIONNEMENTS).index(p.conditionnement), key=f"cond_{p.id}")
    if cond == "unité":
        upc = 1
        c2.text_input("Unités par conditionnement", value="1", disabled=True, key=f"upc_dis_{p.id}")
    else:
        upc = c2.number_input(f"{pluriel(p.unite_vente).capitalize()} par {cond}", min_value=1, step=1,
                              value=int(p.unites_par_cond), key=f"upc_{p.id}_{cond}")
    nom_cond = p.unite_vente if cond == "unité" else cond
    c3, c4, c5 = st.columns(3)
    nb = c3.number_input(f"Nombre de {pluriel(nom_cond)}", min_value=0.0, step=1.0, value=0.0,
                         format="%g", key=f"nb_{p.id}")
    pa = c4.number_input(f"Prix d'achat par {nom_cond} (FCFA)", min_value=0, step=100, value=0,
                         key=f"pa_{p.id}_{cond}")
    pv = c5.number_input(f"Prix de vente d'une {p.unite_vente} (FCFA)", min_value=0, step=50,
                         value=int(p.prix_vente), key=f"pv_{p.id}")

    unites = nb * upc
    investi = nb * pa
    cout_u = pa / upc if upc else 0
    recette = unites * pv
    benef = recette - investi
    marge = benef / recette * 100 if recette else 0

    st.subheader("Calcul automatique")
    m1, m2, m3 = st.columns(3)
    m1.metric("Ajouté au stock", f"{nombre(unites)} {pluriel(p.unite_vente, unites)}")
    m2.metric("Montant investi", fcfa(investi))
    m3.metric(f"Coût d'une {p.unite_vente}", fcfa(cout_u))
    m4, m5, m6 = st.columns(3)
    m4.metric("Recette estimée", fcfa(recette))
    m5.metric("Bénéfice attendu", fcfa(benef))
    m6.metric("Marge", f"{nombre(round(marge, 1))} %")
    if pv and pv < cout_u:
        st.error(f"Le prix de vente ({fcfa(pv)}) est inférieur au coût d'une {p.unite_vente} "
                 f"({fcfa(cout_u)}). Chaque vente à ce prix serait à perte.")

    if st.button("Enregistrer l'achat", type="primary", width="stretch"):
        if nb <= 0:
            st.error("Indique le nombre acheté.")
        elif pa <= 0:
            st.error("Indique le prix d'achat.")
        else:
            with Session() as s:
                s.add(Achat(date=jour, produit_id=p.id, conditionnement=cond, nb_cond=float(nb),
                            unites_par_cond=int(upc), prix_achat_cond=float(pa),
                            prix_vente_unite=float(pv), auteur_id=auth.utilisateur()["id"]))
                prod = s.get(Produit, p.id)
                if pv:
                    prod.prix_vente = float(pv)
                s.commit()
            flash(f"Achat enregistré : {nombre(unites)} {pluriel(p.unite_vente, unites)} de {p.nom} "
                  f"ajoutées au stock.")
            st.rerun()

    derniers = sorted(d.achats, key=lambda a: (a.date, a.id), reverse=True)[:8]
    if derniers:
        st.subheader("Derniers achats")
        st.dataframe(pd.DataFrame([{
            "Date": date_fr(a.date),
            "Produit": d.produit(a.produit_id).nom if d.produit(a.produit_id) else "?",
            "Quantité": (f"{nombre(a.nb_cond)} {pluriel(a.conditionnement, a.nb_cond)}"
                         + ("" if a.conditionnement == "unité" else f" de {a.unites_par_cond}")),
            "Montant": fcfa(a.montant),
            "Saisi par": d.utilisateurs.get(a.auteur_id, "?"),
        } for a in derniers]), hide_index=True, width="stretch")
