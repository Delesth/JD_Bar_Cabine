"""Base de données : modèles et connexion.

Fonctionne avec SQLite (tests locaux) et PostgreSQL / Supabase (mise en ligne).
L'adresse de la base est lue dans st.secrets["DATABASE_URL"] ou la variable
d'environnement DATABASE_URL ; à défaut, un fichier local barcabine.db est utilisé.
"""
import os
from datetime import date, datetime

import streamlit as st
from sqlalchemy import (Boolean, Date, DateTime, Float, ForeignKey, Integer,
                        String, Text, create_engine)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class Utilisateur(Base):
    __tablename__ = "utilisateurs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    identifiant: Mapped[str] = mapped_column(String(50), unique=True)
    nom: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20))  # "proprietaire" | "gestionnaire"
    mot_de_passe: Mapped[str] = mapped_column(String(300))
    actif: Mapped[bool] = mapped_column(Boolean, default=True)
    cree_le: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Produit(Base):
    __tablename__ = "produits"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nom: Mapped[str] = mapped_column(String(100), unique=True)
    categorie: Mapped[str] = mapped_column(String(20))  # "locale" | "importee"
    unite_vente: Mapped[str] = mapped_column(String(20))  # "bouteille" | "canette"
    conditionnement: Mapped[str] = mapped_column(String(20))  # casier | pack | carton | unité
    unites_par_cond: Mapped[int] = mapped_column(Integer, default=1)
    prix_vente: Mapped[float] = mapped_column(Float, default=0)  # prix d'une unité
    seuil_stock: Mapped[int] = mapped_column(Integer, default=0)
    actif: Mapped[bool] = mapped_column(Boolean, default=True)
    cree_le: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Achat(Base):
    __tablename__ = "achats"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date)
    produit_id: Mapped[int] = mapped_column(ForeignKey("produits.id"))
    conditionnement: Mapped[str] = mapped_column(String(20))
    nb_cond: Mapped[float] = mapped_column(Float)
    unites_par_cond: Mapped[int] = mapped_column(Integer)
    prix_achat_cond: Mapped[float] = mapped_column(Float)
    prix_vente_unite: Mapped[float] = mapped_column(Float)
    auteur_id: Mapped[int] = mapped_column(ForeignKey("utilisateurs.id"))
    cree_le: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    @property
    def unites(self) -> float:
        return self.nb_cond * self.unites_par_cond

    @property
    def montant(self) -> float:
        return self.nb_cond * self.prix_achat_cond

    @property
    def cout_unitaire(self) -> float:
        return self.prix_achat_cond / self.unites_par_cond if self.unites_par_cond else 0


class Vente(Base):
    """Une ligne de vente. type : normal | reduction | perte.
    statut : validee | en_attente (vente à perte à valider) | refusee."""
    __tablename__ = "ventes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date)
    produit_id: Mapped[int] = mapped_column(ForeignKey("produits.id"))
    type: Mapped[str] = mapped_column(String(20), default="normal")
    quantite: Mapped[float] = mapped_column(Float)  # en unités de vente
    prix_normal_unite: Mapped[float] = mapped_column(Float)
    montant_encaisse: Mapped[float] = mapped_column(Float)
    motif: Mapped[str | None] = mapped_column(Text, nullable=True)
    statut: Mapped[str] = mapped_column(String(20), default="validee")
    cout_unitaire_saisie: Mapped[float] = mapped_column(Float, default=0)
    auteur_id: Mapped[int] = mapped_column(ForeignKey("utilisateurs.id"))
    cree_le: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    decide_par_id: Mapped[int | None] = mapped_column(ForeignKey("utilisateurs.id"), nullable=True)
    decide_le: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    commentaire_decision: Mapped[str | None] = mapped_column(Text, nullable=True)

    @property
    def montant_normal(self) -> float:
        return self.quantite * self.prix_normal_unite

    @property
    def reduction(self) -> float:
        return max(self.montant_normal - self.montant_encaisse, 0)


class AjustementStock(Base):
    """Écart constaté lors d'un comptage physique (casse, offert, perte)."""
    __tablename__ = "ajustements_stock"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date)
    produit_id: Mapped[int] = mapped_column(ForeignKey("produits.id"))
    quantite_theorique: Mapped[float] = mapped_column(Float)
    quantite_comptee: Mapped[float] = mapped_column(Float)
    motif: Mapped[str | None] = mapped_column(Text, nullable=True)
    auteur_id: Mapped[int] = mapped_column(ForeignKey("utilisateurs.id"))
    cree_le: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    @property
    def ecart(self) -> float:
        return self.quantite_comptee - self.quantite_theorique


class Parametre(Base):
    __tablename__ = "parametres"
    cle: Mapped[str] = mapped_column(String(50), primary_key=True)
    valeur: Mapped[str] = mapped_column(String(200))


def _adresse_base() -> str:
    url = None
    try:
        url = st.secrets.get("DATABASE_URL")
    except Exception:
        url = None
    url = url or os.environ.get("DATABASE_URL") or "sqlite:///barcabine.db"
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url


@st.cache_resource
def _moteur():
    moteur = create_engine(_adresse_base(), pool_pre_ping=True)
    Base.metadata.create_all(moteur)
    return moteur


def Session():
    """Ouvre une session : `with Session() as s: ...`"""
    return sessionmaker(bind=_moteur(), expire_on_commit=False)()


def est_locale() -> bool:
    return _adresse_base().startswith("sqlite")


PARAMETRES_DEFAUT = {"seuil_reductions_pct": "5"}


def lire_parametre(cle: str) -> str:
    with Session() as s:
        p = s.get(Parametre, cle)
        return p.valeur if p else PARAMETRES_DEFAUT.get(cle, "")


def ecrire_parametre(cle: str, valeur: str) -> None:
    with Session() as s:
        p = s.get(Parametre, cle)
        if p:
            p.valeur = valeur
        else:
            s.add(Parametre(cle=cle, valeur=valeur))
        s.commit()
