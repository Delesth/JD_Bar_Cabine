"""Saisie des ventes du jour, des ventes à tarif réduit et des ventes à perte."""
from datetime import date, datetime

import pandas as pd
import streamlit as st

from core import auth
from core.calculs import charger, rejouer
from core.db import Session, Vente
from core.format import afficher_flash, date_fr, equivalent, fcfa, flash, gen, nombre, pluriel, quantite, vider

MOTIFS = ["Client fidèle", "Vente en gros", "Promotion", "Geste commercial", "Autre"]


def _ventes_normales(d, jour, produits):
    st.subheader("1. Ventes au prix normal")
    st.caption("Pour chaque boisson, indique ce qui a été vendu aujourd'hui, à l'unité et/ou en "
               "conditionnement complet (un casier est converti automatiquement). "
               "Enregistrer de nouveau le même jour remplace les quantités.")
    existantes = {v.produit_id: v for v in d.ventes if v.date == jour and v.type == "normal"}
    cle_modif = f"modif_ventes_{jour.isoformat()}"
    if existantes and not st.session_state.get(cle_modif):
        st.success(f"Ventes du {date_fr(jour)} enregistrées. Pour éviter un double envoi, la saisie est "
                   "verrouillée ; clique sur « Modifier » pour la corriger.")
        recap = []
        for p in produits:
            v = existantes.get(p.id)
            if v:
                recap.append({"Produit": p.nom, "Vendu": quantite(v.quantite, p.unite_vente),
                              "Soit": equivalent(v.quantite, p), "Recette": fcfa(v.montant_encaisse),
                              "Saisi par": d.utilisateurs.get(v.auteur_id, "?")})
        st.dataframe(pd.DataFrame(recap), hide_index=True, width="stretch")
        st.metric("Recette au prix normal", fcfa(sum(v.montant_encaisse for v in existantes.values())))
        if st.button("Modifier les ventes de ce jour", key=f"btn_{cle_modif}"):
            st.session_state[cle_modif] = True
            st.rerun()
        return
    r = rejouer(d, jusqu_au=jour, sauf_ventes={v.id for v in existantes.values()})

    lignes = []
    for p in produits:
        v = existantes.get(p.id)
        dispo = r.stock.get(p.id, {}).get("qte", 0)
        a_cond = p.conditionnement != "unité" and p.unites_par_cond > 1
        lignes.append({
            "pid": p.id,
            "Produit": p.nom,
            "En stock": f"{quantite(dispo, p.unite_vente)}",
            "Vendu à l'unité": int(v.quantite) if v else 0,
            "Vendu en conditionnement": 0,
            "Conditionnement": f"{p.conditionnement} de {p.unites_par_cond}" if a_cond else "—",
            "Prix unitaire": fcfa(p.prix_vente),
        })
    df = pd.DataFrame(lignes)
    edite = st.data_editor(
        df, key=f"ventes_{jour.isoformat()}_{gen('ventes')}", hide_index=True, width="stretch",
        disabled=["Produit", "En stock", "Conditionnement", "Prix unitaire"],
        column_order=["Produit", "En stock", "Vendu à l'unité", "Vendu en conditionnement",
                      "Conditionnement", "Prix unitaire"],
        column_config={
            "Vendu à l'unité": st.column_config.NumberColumn(min_value=0, step=1, format="%d"),
            "Vendu en conditionnement": st.column_config.NumberColumn(
                min_value=0, step=1, format="%d", help="Ex. 1 casier complet vendu"),
        },
    )

    total_recette, a_enregistrer, depassements = 0.0, [], []
    for _, ligne in edite.iterrows():
        p = d.produit(int(ligne["pid"]))
        cond = 0 if p.conditionnement == "unité" else int(ligne["Vendu en conditionnement"] or 0)
        q = int(ligne["Vendu à l'unité"] or 0) + cond * (p.unites_par_cond or 1)
        dispo = r.stock.get(p.id, {}).get("qte", 0)
        if q > dispo:
            depassements.append(f"{p.nom} : {quantite(q, p.unite_vente)} saisies pour "
                                f"{quantite(dispo, p.unite_vente)} en stock")
        total_recette += q * p.prix_vente
        a_enregistrer.append((p, q, r.stock.get(p.id, {}).get("cmp", 0)))

    st.metric("Recette au prix normal", fcfa(total_recette))
    confirme = True
    if depassements:
        st.warning("Ces ventes dépassent le stock disponible. Vérifie qu'il ne s'agit pas d'une "
                   "erreur de saisie (40 au lieu de 4) ou d'un achat non enregistré :\n\n- "
                   + "\n- ".join(depassements))
        confirme = st.checkbox("Je confirme ces quantités", key=f"conf_{jour}_{gen('ventes')}")

    if existantes and st.button("Annuler la modification", key=f"annul_{cle_modif}"):
        st.session_state.pop(cle_modif, None)
        vider("ventes")
        st.rerun()
    if st.button(f"Enregistrer les ventes du {date_fr(jour)}", type="primary",
                 disabled=not confirme, width="stretch"):
        uid = auth.utilisateur()["id"]
        with Session() as s:
            for p, q, cmp in a_enregistrer:
                v = existantes.get(p.id)
                if q > 0:
                    v = s.get(Vente, v.id) if v else Vente(date=jour, produit_id=p.id, type="normal",
                                                           statut="validee", auteur_id=uid)
                    v.quantite, v.prix_normal_unite = float(q), float(p.prix_vente)
                    v.montant_encaisse, v.cout_unitaire_saisie = float(q * p.prix_vente), float(cmp)
                    s.add(v)
                elif v:
                    s.delete(s.get(Vente, v.id))
            s.commit()
        st.session_state.pop(cle_modif, None)
        vider("ventes")
        flash(f"Ventes du {date_fr(jour)} enregistrées.")
        st.rerun()


def _vente_speciale(d, jour, produits):
    st.subheader("2. Ventes à tarif réduit")
    st.caption("Une ligne par réduction accordée, avec le prix réellement encaissé et le motif.")
    r = rejouer(d, jusqu_au=jour)
    g = gen("reduction")
    c1, c2 = st.columns(2)
    p = c1.selectbox("Produit", produits, format_func=lambda x: x.nom, key=f"r{g}_prod")
    unites_possibles = [p.unite_vente]
    if p.conditionnement != "unité" and p.unites_par_cond > 1:
        unites_possibles.append(p.conditionnement)
    u = c2.selectbox("Vendu en", unites_possibles,
                     format_func=lambda x: x if x == p.unite_vente else f"{x} de {p.unites_par_cond}",
                     key=f"r{g}_unite_{p.id}")
    c3, c4 = st.columns(2)
    nb = c3.number_input(f"Nombre de {pluriel(u)}", min_value=0, step=1, value=0, key=f"r{g}_nb_{p.id}_{u}")
    q = nb * (p.unites_par_cond if u != p.unite_vente else 1)
    normal = q * p.prix_vente
    encaisse = c4.number_input("Montant total encaissé (FCFA)", min_value=0, step=100,
                               value=int(normal), key=f"r{g}_enc_{p.id}_{u}_{nb}")
    c5, c6 = st.columns(2)
    motif = c5.selectbox("Motif", MOTIFS, key=f"r{g}_motif")
    precision = c6.text_input("Précision" + (" (obligatoire)" if motif == "Autre" else " (facultatif)"),
                              key=f"r{g}_prec")

    cmp = r.stock.get(p.id, {}).get("cmp", 0)
    cout = q * cmp
    dispo = r.stock.get(p.id, {}).get("qte", 0)
    reduction = normal - encaisse
    if q:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Prix normal", fcfa(normal))
        m2.metric("Réduction", fcfa(reduction),
                  f"{nombre(round(reduction / normal * 100, 1))} %" if normal else None,
                  delta_color="inverse")
        m3.metric("Coût d'achat", fcfa(cout))
        m4.metric("Bénéfice réel", fcfa(encaisse - cout))
    if q > dispo:
        st.warning(f"Stock disponible : {quantite(dispo, p.unite_vente)} seulement.")

    motif_complet = motif + (f" : {precision.strip()}" if precision.strip() else "")
    perte = q > 0 and encaisse < cout
    motif_ok = motif != "Autre" or precision.strip()

    if perte:
        st.error(f"Vente à perte : {fcfa(encaisse)} encaissés pour un coût d'achat de {fcfa(cout)}, "
                 f"soit une perte de {fcfa(cout - encaisse)}. Cette vente ne peut pas être enregistrée "
                 "normalement : elle sera soumise au propriétaire pour validation.")
        libelle = "Soumettre la vente à perte pour validation"
    else:
        libelle = "Enregistrer la vente à tarif réduit"

    if st.button(libelle, type="primary", width="stretch", key=f"r{g}_ok"):
        if q <= 0:
            st.error("Indique la quantité vendue.")
        elif reduction <= 0 and not perte:
            st.error("Le montant encaissé n'est pas inférieur au prix normal : "
                     "saisis cette vente dans le tableau des ventes au prix normal.")
        elif not motif_ok:
            st.error("Précise le motif.")
        else:
            with Session() as s:
                s.add(Vente(date=jour, produit_id=p.id, type="perte" if perte else "reduction",
                            quantite=float(q), prix_normal_unite=float(p.prix_vente),
                            montant_encaisse=float(encaisse), motif=motif_complet,
                            statut="en_attente" if perte else "validee",
                            cout_unitaire_saisie=float(cmp), auteur_id=auth.utilisateur()["id"]))
                s.commit()
            vider("reduction")
            flash("Vente à perte soumise : elle apparaîtra dans la page « À valider » du propriétaire."
                  if perte else "Vente à tarif réduit enregistrée.", "warning" if perte else "success")
            st.rerun()

    du_jour = [v for v in d.ventes if v.date == jour and v.type != "normal"]
    if du_jour:
        st.markdown("**Réductions et ventes à perte de ce jour**")
        statuts = {"validee": "Enregistrée", "en_attente": "En attente de validation", "refusee": "Refusée"}
        for v in sorted(du_jour, key=lambda x: x.id):
            p2 = d.produit(v.produit_id)
            ca, cb = st.columns([5, 1])
            ca.write(f"{p2.nom} · {quantite(v.quantite, p2.unite_vente)} · {fcfa(v.montant_encaisse)} "
                     f"au lieu de {fcfa(v.montant_normal)} · {v.motif} · **{statuts[v.statut]}**")
            u = auth.utilisateur()
            peut = auth.est_proprietaire() or (v.auteur_id == u["id"] and v.statut != "refusee"
                                               and v.date == date.today())
            if peut and cb.button("Supprimer", key=f"del_red_{v.id}"):
                with Session() as s:
                    s.delete(s.get(Vente, v.id))
                    s.commit()
                flash("Ligne supprimée.")
                st.rerun()


def page():
    st.title("Ventes du jour")
    afficher_flash()
    d = charger()
    produits = [p for p in d.produits if p.actif]
    if not produits:
        st.info("Crée d'abord les boissons dans la page Produits.")
        return
    jour = st.date_input("Date", value=date.today(), max_value=date.today(), format="DD/MM/YYYY")
    _ventes_normales(d, jour, produits)
    st.divider()
    _vente_speciale(d, jour, produits)
