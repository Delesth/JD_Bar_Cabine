"""Bar & Cabine — point d'entrée de l'application.

Lancer :  streamlit run app.py
"""
import streamlit as st

st.set_page_config(page_title="Bar & Cabine", page_icon="🥤", layout="centered")

from core import auth  # noqa: E402
from vues import (achats, historique, parametres, produits, stock,  # noqa: E402
                  tableau_bord, validations, ventes)

utilisateur = auth.exiger_connexion()

if auth.est_proprietaire():
    n = validations.nb_en_attente()
    pages = {
        "Pilotage": [
            st.Page(tableau_bord.page, title="Tableau de bord", icon="📊", url_path="tableau-de-bord", default=True),
            st.Page(validations.page, title=f"À valider ({n})" if n else "À valider", icon="⚠️", url_path="a-valider"),
            st.Page(historique.page, title="Historique", icon="🗂️", url_path="historique"),
        ],
        "Saisie · Bar": [
            st.Page(ventes.page, title="Ventes du jour", icon="🧾", url_path="ventes"),
            st.Page(achats.page, title="Nouvel achat", icon="📦", url_path="achats"),
            st.Page(stock.page, title="Stock", icon="🍺", url_path="stock"),
            st.Page(produits.page, title="Produits", icon="🏷️", url_path="produits"),
        ],
        "Compte": [st.Page(parametres.page, title="Paramètres", icon="⚙️", url_path="parametres")],
    }
else:
    pages = {
        "Saisie · Bar": [
            st.Page(ventes.page, title="Ventes du jour", icon="🧾", url_path="ventes", default=True),
            st.Page(achats.page, title="Nouvel achat", icon="📦", url_path="achats"),
            st.Page(stock.page, title="Stock", icon="🍺", url_path="stock"),
            st.Page(produits.page, title="Produits", icon="🏷️", url_path="produits"),
        ],
    }

with st.sidebar:
    st.markdown(f"Connecté : **{utilisateur['nom']}**  \n"
                f"{'Propriétaire' if utilisateur['role'] == 'proprietaire' else 'Gestionnaire'}")
    if st.button("Se déconnecter", width="stretch"):
        auth.deconnecter()
        st.rerun()

st.navigation(pages).run()
