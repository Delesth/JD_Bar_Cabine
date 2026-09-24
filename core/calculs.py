"""Calculs automatiques : stock, coût moyen pondéré, recettes, bénéfices.

Toutes les valeurs sont recalculées à partir de l'historique (achats, ventes,
ajustements). Rien n'est stocké en double : corriger ou supprimer une saisie
met automatiquement à jour tous les chiffres.
"""
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select

from core.db import (AjustementStock, Achat, MouvementTresorerie, OperationCabine, Produit,
                     Session, Utilisateur, Vente)


@dataclass
class Donnees:
    produits: list = field(default_factory=list)
    achats: list = field(default_factory=list)
    ventes: list = field(default_factory=list)
    ajustements: list = field(default_factory=list)
    operations: list = field(default_factory=list)
    mouvements: list = field(default_factory=list)
    utilisateurs: dict = field(default_factory=dict)

    def produit(self, pid):
        return next((p for p in self.produits if p.id == pid), None)


def charger() -> Donnees:
    with Session() as s:
        return Donnees(
            produits=list(s.scalars(select(Produit).order_by(Produit.categorie, Produit.nom))),
            achats=list(s.scalars(select(Achat))),
            ventes=list(s.scalars(select(Vente))),
            ajustements=list(s.scalars(select(AjustementStock))),
            operations=list(s.scalars(select(OperationCabine))),
            mouvements=list(s.scalars(select(MouvementTresorerie))),
            utilisateurs={u.id: u.nom for u in s.scalars(select(Utilisateur))},
        )


@dataclass
class Rejeu:
    stock: dict        # produit_id -> {"qte": unités, "cmp": coût moyen unitaire}
    cout_vente: dict   # vente_id -> coût d'achat des unités vendues
    valeur_ajust: dict  # ajustement_id -> valeur de l'écart (négatif = perte)


def rejouer(d: Donnees, jusqu_au: date | None = None, sauf_ventes: set | None = None) -> Rejeu:
    """Rejoue l'historique dans l'ordre chronologique.

    Le jour même, les achats passent avant les ventes et les ajustements.
    Coût moyen pondéré : à chaque achat, le coût unitaire devient la moyenne
    du stock restant et des nouvelles unités, pondérée par les quantités.
    """
    sauf_ventes = sauf_ventes or set()
    evenements = [(a.date, 0, a.id, "A", a) for a in d.achats]
    evenements += [(v.date, 1, v.id, "V", v) for v in d.ventes if v.id not in sauf_ventes]
    evenements += [(j.date, 2, j.id, "J", j) for j in d.ajustements]
    evenements.sort(key=lambda e: (e[0], e[1], e[2]))
    stock = {p.id: {"qte": 0.0, "cmp": 0.0} for p in d.produits}
    cout_vente, valeur_ajust = {}, {}
    for jour, _, _, genre, o in evenements:
        if jusqu_au and jour > jusqu_au:
            break
        s = stock.setdefault(o.produit_id, {"qte": 0.0, "cmp": 0.0})
        if genre == "A":
            base = max(s["qte"], 0)
            q, c = o.unites, o.cout_unitaire
            s["cmp"] = (base * s["cmp"] + q * c) / (base + q) if base + q > 0 else c
            s["qte"] += q
        elif genre == "V":
            cout_vente[o.id] = o.quantite * s["cmp"]
            s["qte"] -= o.quantite
        else:
            valeur_ajust[o.id] = o.ecart * s["cmp"]
            s["qte"] += o.ecart
    return Rejeu(stock, cout_vente, valeur_ajust)


@dataclass
class Indicateurs:
    ca: float = 0
    cout_ventes: float = 0
    achats: float = 0
    reductions: float = 0
    ca_normal: float = 0
    pertes_stock: float = 0
    ventes_perte_validees: float = 0
    a_regulariser: float = 0
    en_attente: int = 0
    par_motif: dict = field(default_factory=dict)
    ca_par_jour: dict = field(default_factory=dict)

    @property
    def benefice_ventes(self):
        return self.ca - self.cout_ventes

    @property
    def benefice(self):
        """Bénéfice du bar sur la période, pertes de stock déduites."""
        return self.benefice_ventes + self.pertes_stock

    @property
    def marge(self):
        return self.benefice_ventes / self.ca * 100 if self.ca else 0

    @property
    def part_reductions(self):
        return self.reductions / self.ca_normal * 100 if self.ca_normal else 0


def indicateurs(d: Donnees, r: Rejeu, debut: date | None, fin: date | None) -> Indicateurs:
    def dans(x):
        return (debut is None or x >= debut) and (fin is None or x <= fin)

    ind = Indicateurs()
    for v in d.ventes:
        if not dans(v.date):
            continue
        if v.statut == "en_attente":
            ind.en_attente += 1
            continue
        cout = r.cout_vente.get(v.id, 0)
        if v.statut == "refusee":
            ind.a_regulariser += max(cout - v.montant_encaisse, 0)
            continue
        ind.ca += v.montant_encaisse
        ind.ca_normal += v.montant_normal
        ind.cout_ventes += cout
        ind.ca_par_jour[v.date] = ind.ca_par_jour.get(v.date, 0) + v.montant_encaisse
        if v.type in ("reduction", "perte") and v.reduction:
            ind.reductions += v.reduction
            m = (v.motif or "Sans motif").split(" : ")[0]
            ind.par_motif[m] = ind.par_motif.get(m, 0) + v.reduction
        if v.type == "perte":
            ind.ventes_perte_validees += max(cout - v.montant_encaisse, 0)
    for a in d.achats:
        if dans(a.date):
            ind.achats += a.montant
    for j in d.ajustements:
        if dans(j.date):
            ind.pertes_stock += r.valeur_ajust.get(j.id, 0)
    return ind


# ---------------------------------------------------------------- Cabine & trésorerie

COMPTES = {
    "caisse_bar": "Caisse bar",
    "caisse_cabine": "Caisse cabine",
    "capital_airtel": "Capital Airtel",
    "capital_mtn": "Capital MTN",
}
OPERATEURS = {"airtel": "Airtel", "mtn": "MTN"}
TYPES_CABINE = {"credit": "Crédit / recharge", "depot": "Dépôt", "retrait": "Retrait"}


def soldes(d: Donnees) -> dict:
    """Argent disponible sur chaque compte, à ce jour.

    Caisse bar     = ventes encaissées − achats ± mouvements
    Caisse cabine  = commissions ± mouvements
    Capital réseau = apports ± réévaluations ± transferts
    Toutes les ventes encaissées comptent, même en attente de validation :
    l'argent est bien dans la caisse.
    """
    s = {k: 0.0 for k in COMPTES}
    s["caisse_bar"] += sum(v.montant_encaisse for v in d.ventes)
    s["caisse_bar"] -= sum(a.montant for a in d.achats)
    s["caisse_cabine"] += sum(o.commission for o in d.operations)
    for m in d.mouvements:
        if m.compte_source in s:
            s[m.compte_source] -= m.montant
        if m.compte_dest in s:
            s[m.compte_dest] += m.montant
    return s


def _dans(x, debut, fin):
    return (debut is None or x >= debut) and (fin is None or x <= fin)


@dataclass
class IndicateursCabine:
    commissions: dict = field(default_factory=lambda: {k: 0.0 for k in OPERATEURS})
    volumes: dict = field(default_factory=lambda: {k: 0.0 for k in OPERATEURS})
    detail: dict = field(default_factory=dict)  # (operateur, type) -> (volume, commission)
    commissions_par_jour: dict = field(default_factory=dict)  # (jour, operateur) -> commission
    depenses: float = 0

    @property
    def commission_totale(self):
        return sum(self.commissions.values())

    @property
    def benefice(self):
        return self.commission_totale - self.depenses


def indicateurs_cabine(d: Donnees, debut, fin) -> IndicateursCabine:
    ind = IndicateursCabine()
    for o in d.operations:
        if not _dans(o.date, debut, fin):
            continue
        ind.commissions[o.operateur] = ind.commissions.get(o.operateur, 0) + o.commission
        ind.volumes[o.operateur] = ind.volumes.get(o.operateur, 0) + o.montant
        v, c = ind.detail.get((o.operateur, o.type), (0, 0))
        ind.detail[(o.operateur, o.type)] = (v + o.montant, c + o.commission)
        cle = (o.date, o.operateur)
        ind.commissions_par_jour[cle] = ind.commissions_par_jour.get(cle, 0) + o.commission
    ind.depenses = total_mouvements(d, "depense", debut, fin, source="caisse_cabine")
    return ind


def total_mouvements(d: Donnees, type_: str, debut, fin, source=None, dest=None) -> float:
    return sum(m.montant for m in d.mouvements
               if m.type == type_ and _dans(m.date, debut, fin)
               and (source is None or m.compte_source == source)
               and (dest is None or m.compte_dest == dest))
