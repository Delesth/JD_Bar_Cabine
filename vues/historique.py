"""Historique complet des saisies du bar (propriétaire)."""
import pandas as pd
import streamlit as st

from core.calculs import COMPTES, OPERATEURS, TYPES_CABINE, charger, rejouer
from core.db import Achat, AjustementStock, MouvementTresorerie, OperationCabine, Session, Vente
from core.format import afficher_flash, date_fr, fcfa, flash, nombre, pluriel

STATUTS = {"validee": "Validée", "en_attente": "En attente", "refusee": "Refusée"}
TYPES = {"normal": "Prix normal", "reduction": "Tarif réduit", "perte": "Vente à perte"}


def _suppression(libelle, modele, lignes, cle):
    if not lignes:
        return
    with st.expander(f"Supprimer {libelle}"):
        choix = st.selectbox("Ligne", lignes, format_func=lambda x: x[1], key=f"sel_{cle}")
        ok = st.checkbox("Je confirme la suppression (les calculs seront mis à jour)", key=f"cf_{cle}")
        if st.button("Supprimer", disabled=not ok, key=f"bt_{cle}"):
            with Session() as s:
                s.delete(s.get(modele, choix[0]))
                s.commit()
            flash("Ligne supprimée.")
            st.rerun()


def _csv(df, nom):
    st.download_button("Exporter en CSV", df.to_csv(index=False, sep=";").encode("utf-8-sig"),
                       file_name=nom, mime="text/csv", key=f"csv_{nom}")


def page():
    st.title("Historique")
    afficher_flash()
    d = charger()
    r = rejouer(d)
    nomp = lambda pid: d.produit(pid).nom if d.produit(pid) else "?"
    t1, t2, t3, t4, t5 = st.tabs(["Ventes", "Achats", "Comptages", "Cabine", "Trésorerie"])

    with t1:
        ventes = sorted(d.ventes, key=lambda v: (v.date, v.id), reverse=True)
        if not ventes:
            st.caption("Aucune vente.")
        else:
            df = pd.DataFrame([{
                "Date": date_fr(v.date), "Produit": nomp(v.produit_id), "Type": TYPES[v.type],
                "Quantité": v.quantite, "Encaissé": round(v.montant_encaisse),
                "Réduction": round(v.reduction), "Coût": round(r.cout_vente.get(v.id, 0)),
                "Bénéfice": round(v.montant_encaisse - r.cout_vente.get(v.id, 0)),
                "Motif": v.motif or "", "Statut": STATUTS[v.statut],
                "Saisi par": d.utilisateurs.get(v.auteur_id, "?"),
            } for v in ventes])
            st.dataframe(df, hide_index=True, width="stretch")
            _csv(df, "ventes.csv")
            _suppression("une vente", Vente, [(v.id, f"{date_fr(v.date)} · {nomp(v.produit_id)} · "
                                               f"{nombre(v.quantite)} · {fcfa(v.montant_encaisse)}")
                                              for v in ventes], "v")
    with t2:
        achats = sorted(d.achats, key=lambda a: (a.date, a.id), reverse=True)
        if not achats:
            st.caption("Aucun achat.")
        else:
            df = pd.DataFrame([{
                "Date": date_fr(a.date), "Produit": nomp(a.produit_id),
                "Conditionnement": a.conditionnement, "Nombre": a.nb_cond,
                "Unités par cond.": a.unites_par_cond, "Unités": a.unites,
                "Prix d'achat / cond.": round(a.prix_achat_cond), "Montant": round(a.montant),
                "Coût unitaire": round(a.cout_unitaire), "Prix de vente": round(a.prix_vente_unite),
                "Saisi par": d.utilisateurs.get(a.auteur_id, "?"),
            } for a in achats])
            st.dataframe(df, hide_index=True, width="stretch")
            _csv(df, "achats.csv")
            _suppression("un achat", Achat, [(a.id, f"{date_fr(a.date)} · {nomp(a.produit_id)} · "
                                              f"{nombre(a.nb_cond)} {pluriel(a.conditionnement, a.nb_cond)} · "
                                              f"{fcfa(a.montant)}") for a in achats], "a")
    with t3:
        ajs = sorted(d.ajustements, key=lambda j: (j.date, j.id), reverse=True)
        if not ajs:
            st.caption("Aucun comptage.")
        else:
            df = pd.DataFrame([{
                "Date": date_fr(j.date), "Produit": nomp(j.produit_id), "Calculé": j.quantite_theorique,
                "Compté": j.quantite_comptee, "Écart": j.ecart,
                "Valeur": round(r.valeur_ajust.get(j.id, 0)), "Explication": j.motif or "",
                "Saisi par": d.utilisateurs.get(j.auteur_id, "?"),
            } for j in ajs])
            st.dataframe(df, hide_index=True, width="stretch")
            _csv(df, "comptages.csv")
            _suppression("un comptage", AjustementStock,
                         [(j.id, f"{date_fr(j.date)} · {nomp(j.produit_id)} · écart {nombre(j.ecart)}")
                          for j in ajs], "j")

    with t4:
        ops = sorted(d.operations, key=lambda o: (o.date, o.id), reverse=True)
        if not ops:
            st.caption("Aucune opération de cabine.")
        else:
            df = pd.DataFrame([{
                "Date": date_fr(o.date), "Réseau": OPERATEURS.get(o.operateur, o.operateur),
                "Opération": TYPES_CABINE.get(o.type, o.type), "Montant": round(o.montant),
                "Commission": round(o.commission), "Saisi par": d.utilisateurs.get(o.auteur_id, "?"),
            } for o in ops])
            st.dataframe(df, hide_index=True, width="stretch")
            _csv(df, "cabine.csv")
            _suppression("une opération de cabine", OperationCabine,
                         [(o.id, f"{date_fr(o.date)} · {OPERATEURS.get(o.operateur)} · "
                                 f"{TYPES_CABINE.get(o.type)} · commission {fcfa(o.commission)}") for o in ops], "o")
    with t5:
        mv = sorted(d.mouvements, key=lambda m: (m.date, m.id), reverse=True)
        noms = {"apport": "Apport", "depense": "Dépense", "decaissement": "Décaissement",
                "reevaluation": "Réévaluation", "transfert": "Transfert interne"}
        if not mv:
            st.caption("Aucun mouvement de trésorerie.")
        else:
            df = pd.DataFrame([{
                "Date": date_fr(m.date), "Type": noms.get(m.type, m.type),
                "De": COMPTES.get(m.compte_source, ""), "Vers": COMPTES.get(m.compte_dest, ""),
                "Montant": round(m.montant), "Catégorie": m.categorie or "", "Détail": m.libelle or "",
                "Saisi par": d.utilisateurs.get(m.auteur_id, "?"),
            } for m in mv])
            st.dataframe(df, hide_index=True, width="stretch")
            _csv(df, "tresorerie.csv")
            _suppression("un mouvement", MouvementTresorerie,
                         [(m.id, f"{date_fr(m.date)} · {noms.get(m.type)} · {fcfa(m.montant)}") for m in mv], "m")
