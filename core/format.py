"""Mise en forme des montants, quantités et dates."""
from datetime import date

import streamlit as st

ESP = "\u202f"  # espace fine insécable (séparateur de milliers)


def fcfa(x) -> str:
    return f"{round(x or 0):,}".replace(",", ESP) + " FCFA"


def nombre(x) -> str:
    x = float(x or 0)
    txt = f"{x:,.0f}" if x.is_integer() else f"{x:,.1f}"
    return txt.replace(",", ESP).replace(".", ",")


def pluriel(mot: str, q: float = 2) -> str:
    if mot == "unité":
        return "unités" if abs(q) >= 2 else "unité"
    return mot + ("s" if abs(q) >= 2 else "")


def quantite(q: float, unite: str) -> str:
    return f"{nombre(q)} {pluriel(unite, q)}"


def equivalent(q: float, produit) -> str:
    """48 bouteilles -> '4 casiers' ; 50 -> '4 casiers + 2 bouteilles'."""
    upc = produit.unites_par_cond or 1
    if upc <= 1 or produit.conditionnement == "unité":
        return ""
    signe = "−" if q < 0 else ""
    q = abs(q)
    nb = int(q // upc)
    reste = q - nb * upc
    morceaux = []
    if nb:
        morceaux.append(f"{nb} {pluriel(produit.conditionnement, nb)}")
    if reste:
        morceaux.append(quantite(reste, produit.unite_vente))
    return signe + " + ".join(morceaux) if morceaux else "0"


def date_fr(d: date) -> str:
    return d.strftime("%d/%m/%Y") if d else ""


def flash(message: str, genre: str = "success") -> None:
    """Message affiché après le rechargement de la page."""
    st.session_state["_flash"] = (message, genre)


def afficher_flash() -> None:
    m = st.session_state.pop("_flash", None)
    if m:
        getattr(st, m[1])(m[0])
