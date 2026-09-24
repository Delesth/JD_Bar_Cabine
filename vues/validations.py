"""Ventes à perte en attente de la décision du propriétaire."""
from datetime import datetime

import streamlit as st

from core import auth
from core.calculs import charger, rejouer
from core.db import Session, Vente
from core.format import afficher_flash, date_fr, fcfa, flash, quantite


def nb_en_attente() -> int:
    with Session() as s:
        return s.query(Vente).filter(Vente.statut == "en_attente").count()


def page():
    st.title("À valider")
    st.caption("Ventes à perte soumises par le gestionnaire. Validée : la vente compte normalement. "
               "Refusée : la perte devient un écart à régulariser à la clôture du mois.")
    afficher_flash()
    d = charger()
    r = rejouer(d)
    attente = sorted([v for v in d.ventes if v.statut == "en_attente"], key=lambda v: v.id)
    if not attente:
        st.success("Rien à valider pour le moment.")
    for v in attente:
        p = d.produit(v.produit_id)
        cout = r.cout_vente.get(v.id, v.quantite * v.cout_unitaire_saisie)
        with st.container(border=True):
            st.markdown(f"**{p.nom} · {quantite(v.quantite, p.unite_vente)} · {date_fr(v.date)}**")
            c1, c2, c3 = st.columns(3)
            c1.metric("Encaissé", fcfa(v.montant_encaisse))
            c2.metric("Coût d'achat", fcfa(cout))
            c3.metric("Perte", fcfa(cout - v.montant_encaisse))
            st.write(f"Motif : {v.motif} · Prix normal : {fcfa(v.montant_normal)} · "
                     f"Saisi par {d.utilisateurs.get(v.auteur_id, '?')}")
            comm = st.text_input("Commentaire (facultatif)", key=f"com_{v.id}")
            b1, b2 = st.columns(2)
            decision = None
            if b1.button("Valider", key=f"ok_{v.id}", type="primary", width="stretch"):
                decision = "validee"
            if b2.button("Refuser", key=f"non_{v.id}", width="stretch"):
                decision = "refusee"
            if decision:
                with Session() as s:
                    x = s.get(Vente, v.id)
                    x.statut, x.decide_par_id = decision, auth.utilisateur()["id"]
                    x.decide_le, x.commentaire_decision = datetime.now(), comm.strip() or None
                    s.commit()
                flash("Vente validée." if decision == "validee" else "Vente refusée : écart à régulariser.")
                st.rerun()

    traitees = sorted([v for v in d.ventes if v.type == "perte" and v.statut != "en_attente"],
                      key=lambda v: v.decide_le or datetime.min, reverse=True)[:15]
    if traitees:
        with st.expander("Décisions précédentes"):
            for v in traitees:
                p = d.produit(v.produit_id)
                st.write(f"{date_fr(v.date)} · {p.nom} · {quantite(v.quantite, p.unite_vente)} · "
                         f"{fcfa(v.montant_encaisse)} · {v.motif} · "
                         f"**{'Validée' if v.statut == 'validee' else 'Refusée'}**"
                         + (f" · {v.commentaire_decision}" if v.commentaire_decision else ""))
