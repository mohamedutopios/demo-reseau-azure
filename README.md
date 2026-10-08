# azure-demos-reseau

Applications de démonstration pour quatre démos Azure indépendantes, réalisées depuis le portail.
Le pas à pas complet est dans [GUIDE-DEMOS.md](GUIDE-DEMOS.md).

| Dossier | Démo | Application |
|---|---|---|
| `lb/` | Azure Load Balancer | Page qui interroge le serveur chaque seconde et affiche en direct la répartition entre les VM |
| `autoscale/` | VM Scale Set + autoscaling | Serveur Python avec un bouton « charger le CPU » et un tableau des instances qui apparaissent et disparaissent |
| `appgw/web/` + `appgw/api/` | Application Gateway | Boutique : site vitrine (nginx) et API catalogue (Python), derrière une seule adresse, routées par chemin d'URL |
| `peering/hub/` + `peering/spoke/` | VNet peering | Front dans le hub qui relaie vers un service interne du spoke, avec l'état de la liaison en temps réel |

Chaque VM clone ce dépôt au premier démarrage (champ **Custom data** du portail), puis exécute le `install.sh` de son dossier.
Aucune dépendance externe : nginx (paquet Ubuntu) et Python 3 (présent dans l'image Ubuntu).

## Publier ce dépôt sur GitHub (sans ligne de commande)

1. https://github.com → **New repository** → nom `azure-demos-reseau`, visibilité **Public** → **Create repository**.
2. Lien **uploading an existing file** → glisser-déposer le **contenu** du dossier `demos-reseau` : les dossiers `lb`, `autoscale`, `appgw`, `peering` et les fichiers `README.md`, `GUIDE-DEMOS.md`.
3. **Commit changes**.

✅ À la racine du dépôt, on voit directement `lb/`, `autoscale/`, `appgw/`, `peering/`.
