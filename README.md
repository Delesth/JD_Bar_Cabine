# Bar & Cabine — étapes 1 et 2 (version 2.1)

© Appli développée par Grâce Delesth NGANGA

Application Streamlit de suivi du bar et de la cabine Airtel / MTN.

## Ce que contient l'étape 1

- **Connexion** : un compte propriétaire (créé au premier lancement) et un compte gestionnaire (créé dans Paramètres).
- **Produits** : boissons locales ou importées, vendues à la bouteille ou à la canette, achetées en casier, pack, carton ou à l'unité.
- **Nouvel achat** : le gestionnaire saisit le nombre de conditionnements, les unités par conditionnement, le prix d'achat et le prix de vente ; l'application calcule le stock ajouté, le montant investi, le coût unitaire, la recette estimée, le bénéfice attendu et la marge.
- **Ventes du jour** : saisie en fin de journée, à l'unité ou en conditionnement complet (converti automatiquement), alerte si la vente dépasse le stock.
- **Ventes à tarif réduit** : prix encaissé + motif obligatoire.
- **Ventes à perte** : saisie normale bloquée, soumission au propriétaire, page « À valider » pour valider ou refuser.
- **Stock** : stock en unités et en conditionnements, alerte stock bas, comptage physique avec enregistrement des écarts.
- **Tableau de bord** (propriétaire) : CA, bénéfice, marge, achats, valeur du stock, réductions (total, % du CA, par motif, seuil d'alerte), CA par jour.
- **Historique** (propriétaire) : ventes, achats, comptages, suppression, export CSV.

## Ce que contient l'étape 2

- **Cabine du jour** : pour Airtel et MTN, montant total et commission des crédits / recharges, dépôts et retraits. Le montant est un volume (argent des clients) ; seule la commission est du chiffre d'affaires.
- **Dépenses** : glace, électricité, loyer, transport… rattachées à la caisse du bar ou de la cabine.
- **Trésorerie** (propriétaire) : soldes de la caisse bar, de la caisse cabine, du capital Airtel et du capital MTN ; apports, transferts internes, réévaluation du capital après comptage, décaissements.
- **Tableau de bord** en trois onglets : Total (CA, bénéfice, trésorerie, capital par activité), Bar, Cabine (commissions, volumes et capital par réseau).
- **Historique** : onglets Cabine et Trésorerie, avec export CSV.

Mise à jour d'une base existante : les nouvelles tables sont créées automatiquement au démarrage, sans toucher aux données déjà saisies.

## Ajouts (version 2.1)

- **Tableau de bord du gestionnaire** : ventes, achats, réductions, bénéfice du bar, détail par produit et commissions de la cabine (sans les coûts d'achat moyens ni la trésorerie).
- **Onglet « Par produit »** dans le tableau de bord du propriétaire.
- **Export Excel** de la période affichée, depuis les deux tableaux de bord : synthèse, par produit, ventes, achats, cabine, dépenses (et trésorerie pour le propriétaire).
- **Saisies vidées après enregistrement** ; les ventes du jour et la cabine du jour sont verrouillées une fois envoyées (bouton « Modifier » pour corriger).
- **Accès perdu** : le propriétaire génère un mot de passe provisoire pour le gestionnaire (Paramètres), qui doit le changer à sa connexion. Le propriétaire réinitialise son propre accès avec le code d'installation (« Identifiant ou mot de passe oublié ? » sur la page de connexion).
- Mention « Appli développée par Grâce Delesth NGANGA ».

Le gestionnaire voit : Tableau de bord, Ventes du jour, Nouvel achat, Stock boissons, Produits, Cabine du jour et Dépenses.

## Lancer l'application sur ton ordinateur

1. Installe Python 3.11 ou plus récent : https://www.python.org/downloads/ (sous Windows, coche « Add Python to PATH »).
2. Ouvre un terminal dans ce dossier, puis installe les dépendances :
   ```
   pip install -r requirements.txt
   ```
3. Lance l'application :
   ```
   streamlit run app.py
   ```
4. Le navigateur s'ouvre sur http://localhost:8501. Crée ton compte propriétaire, puis le compte du gestionnaire dans **Paramètres**.

Les données de test sont enregistrées dans le fichier `barcabine.db` du dossier. Pour repartir de zéro, supprime ce fichier.

## Mise en ligne (GitHub + Streamlit Community Cloud + Supabase)

Sur Streamlit Community Cloud, les fichiers locaux sont effacés à chaque redémarrage :
la base de données doit donc être en ligne (Supabase, offre gratuite).

1. **Supabase** : créer un compte sur https://supabase.com, puis un projet (région Europe, par
   exemple Paris). Noter le mot de passe de la base.
2. **Adresse de connexion** : dans le projet, bouton « Connect » > « Session pooler » > copier l'URI
   et remplacer `[YOUR-PASSWORD]` par le mot de passe. Si le mot de passe contient des caractères
   spéciaux (@, #, /, :…), en choisir un sans ces caractères.
3. **GitHub** : créer un dépôt **privé** (ex. `barcabine`) et y envoyer le contenu de ce dossier
   (« Add file » > « Upload files »). Le fichier `.gitignore` empêche l'envoi des secrets et de la base locale.
4. **Streamlit Community Cloud** : sur https://share.streamlit.io, se connecter avec GitHub,
   « Create app » > dépôt `barcabine`, branche `main`, fichier `app.py`.
   Dans « Advanced settings » : Python 3.12, et dans « Secrets » coller :
   ```
   DATABASE_URL = "postgresql://postgres.xxxx:MOT_DE_PASSE@....pooler.supabase.com:5432/postgres"
   CODE_INSTALLATION = "ton-code-secret"
   ```
5. **Premier lancement** : ouvrir l'adresse de l'application, créer le compte propriétaire avec le
   code d'installation, puis le compte du gestionnaire dans Paramètres.
6. **Gestionnaire** : lui envoyer l'adresse (…streamlit.app) et ses identifiants. Sur son téléphone,
   il peut l'ajouter à l'écran d'accueil depuis le navigateur.

Mises à jour : toute modification d'un fichier sur GitHub redéploie l'application automatiquement.
Les données, stockées dans Supabase, ne sont pas touchées.

À savoir : une application Streamlit gratuite se met en veille après une période sans visite
(un bouton permet de la réveiller en quelques secondes), et un projet Supabase gratuit est mis
en pause après une semaine sans activité. Une utilisation quotidienne évite ces deux cas.

## Organisation du code

```
app.py              navigation et menus selon le rôle
core/db.py          tables de la base et connexion (SQLite en local, Supabase en ligne)
core/auth.py        connexion et mots de passe (chiffrés)
core/calculs.py     stock, coût moyen pondéré, bénéfices, indicateurs
core/format.py      affichage des montants en FCFA, dates, quantités
vues/*.py           une page par fichier
```

Tous les chiffres sont recalculés à partir de l'historique : corriger ou supprimer une saisie met automatiquement à jour le stock et les bénéfices.
