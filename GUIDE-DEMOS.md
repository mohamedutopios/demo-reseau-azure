# Démos réseau Azure — Load Balancer, autoscaling, Application Gateway, peering

| | |
|---|---|
| Interface | Portail Azure (https://portal.azure.com) en **français**, libellé anglais entre parenthèses |
| Région | France Central |
| Outils | Un navigateur. Aucun terminal, aucune clé SSH |
| Applications | Dépôt `azure-demos-reseau` (dossier `demos-reseau`), cloné par chaque VM au démarrage |
| Démos | [A — Load Balancer](#démo-a--load-balancer) · [B — Autoscaling](#démo-b--vm-scale-set-et-autoscaling) · [C — Application Gateway](#démo-c--application-gateway) · [D — Peering](#démo-d--vnet-peering) |

Les quatre démos sont **indépendantes** : chacune a son groupe de ressources, son réseau, ses VM et son nettoyage. On peut les faire dans n'importe quel ordre.

Chaque étape suit le même format : un tableau **Champ | Valeur** à recopier dans le portail, une vérification ✅, puis un encadré 💡 **Pourquoi ?** qui explique les choix, à dire à l'oral pendant la manipulation.

> Les libellés du portail évoluent : si un libellé diffère légèrement, la logique reste la même. Astuce : tapez le nom du service dans la **barre de recherche** en haut du portail.

---

## Prérequis communs

### P1 — Publier les applications sur GitHub

Le dossier `demos-reseau` doit être publié dans un **dépôt public** nommé `azure-demos-reseau` (procédure sans ligne de commande dans le [README](README.md)).

Dans ce guide, l'URL du dépôt est `https://github.com/mohamedutopios/azure-demos-reseau.git`. **Si vous utilisez un autre compte GitHub, remplacez `mohamedutopios` dans chaque champ Custom data.**

✅ En navigation privée, https://github.com/mohamedutopios/azure-demos-reseau affiche les dossiers `lb`, `autoscale`, `appgw`, `peering` à la racine.

> 💡 **Pourquoi ?** Le portail ne sait pas envoyer des fichiers sur une VM. En revanche, une VM sait cloner un dépôt public au démarrage, sans identifiant. GitHub sert de point de passage entre le poste du formateur et les VM.

### P2 — Quotas

Barre de recherche → **Quotas** → **Calcul** (*Compute*) → filtre **Région** : `France Central`.

| Démo | Taille | vCPU nécessaires (famille **Standard BS**) |
|---|---|---|
| A — Load Balancer | 2 × `Standard_B1s` | 2 |
| B — Autoscaling | 2 à 4 × `Standard_B2s` | 8 |
| C — Application Gateway | 2 × `Standard_B1s` | 2 |
| D — Peering | 2 × `Standard_B1s` | 2 |

Vérifier aussi **Total des processeurs virtuels régionaux**. Si une taille n'est pas proposée, prendre son équivalent `_v2` (`Standard_B2s_v2`, etc.).

> 💡 **Pourquoi ?** Azure limite le nombre de vCPU par famille de tailles et par région. Un dépassement fait échouer la création dès la validation. La démo B est la plus gourmande : l'autoscaling crée des VM à la volée, et s'il touche le quota, il échoue sans prévenir.

### P3 — Coûts

| Démo | Ressource la plus coûteuse | Conseil |
|---|---|---|
| A | Load Balancer Standard + NAT Gateway | Supprimer le groupe juste après la démo |
| B | Jusqu'à 4 VM B2s pendant la charge | Supprimer le groupe juste après la démo |
| C | **Application Gateway v2** (facturé à l'heure, même sans trafic) | **La plus chère** : lancer la création en avance, supprimer juste après |
| D | NAT Gateway + trafic de peering (au Go) | Supprimer le groupe juste après la démo |

### P4 — Ce que fait le champ Custom data

Toutes les VM de ces démos reçoivent un court texte **cloud-init** dans l'onglet **Avancé** → **Données personnalisées** (*Custom data*). Il a toujours la même forme, seule la dernière ligne change :

```yaml
#cloud-config
package_update: true
packages:
  - git
runcmd:
  - git clone https://github.com/mohamedutopios/azure-demos-reseau.git /opt/demos
  - bash /opt/demos/<dossier>/install.sh
```

Pour savoir si l'installation est terminée sur une VM : **Opérations** → **Exécuter la commande** (*Run command*) → **RunShellScript** →

```bash
cloud-init status
tail -n 5 /var/log/cloud-init-output.log
```

Résultat attendu : `status: done`.

> 💡 **Pourquoi ?**
>
> - **cloud-init** est l'outil standard de configuration au premier démarrage des images Linux du cloud. Azure lui transmet le contenu de **Custom data**.
> - Il s'exécute **une seule fois**, au premier démarrage, sans aucune connexion à la VM. Pour un Scale Set (démo B), il s'exécute sur **chaque** nouvelle instance : c'est ce qui permet à l'autoscaling de produire des serveurs prêts à servir.
> - Le texte reste court : la logique d'installation est dans le dépôt (`install.sh`), versionnée avec l'application.

### P5 — Sous-réseaux privés et passerelle NAT

Sur les nouveaux réseaux virtuels, une VM **sans IP publique** n'a **aucun accès Internet sortant**, tant qu'on ne lui en donne pas un explicitement. Or les VM des démos doivent télécharger nginx et cloner le dépôt. Chaque démo crée donc une **passerelle NAT** sur le sous-réseau de ses VM privées.

> 💡 **Pourquoi ?** Historiquement, Azure donnait à toute VM une IP de sortie implicite, non maîtrisée et susceptible de changer. Ce comportement est retiré (principe « sécurisé par défaut »). La passerelle NAT donne une sortie **explicite** : sortante uniquement, avec une IP publique fixe et connue, et sans rien ouvrir en entrée.

---

# Démo A — Load Balancer

| | |
|---|---|
| Objectif | Répartir le trafic entre 2 VM placées dans 2 zones, voir la répartition en direct, puis simuler une panne |
| Durée | 45 min |
| Application | `lb/` — page qui interroge le serveur chaque seconde et trace la répartition des réponses |
| Ressources | 1 VNet, 1 NAT Gateway, 1 NSG, 2 VM sans IP publique, 1 Load Balancer public |
| Adressage | `vnet-lb` 10.10.0.0/16 · `snet-web` 10.10.1.0/24 |

> 🎯 **Ce que cette démo montre, et pourquoi**
>
> - Une VM seule est un **point unique de panne** : une maintenance de l'hôte, une panne matérielle ou un incident de datacenter, et le site tombe.
> - SLA Microsoft pour le calcul : 1 VM (disques Premium) 99,9 % ; 2 VM dans 2 zones de disponibilité **99,99 %**. Cela représente environ 8 h 45 contre 53 minutes d'indisponibilité tolérée par an.
> - Avoir deux VM ne suffit pas : il faut une **adresse unique** devant elles, qui répartit le trafic et écarte automatiquement une VM en panne. C'est le rôle de l'**Azure Load Balancer**.

```
Navigateur ──▶ IP publique du LB ──▶ lb-web ──┬──▶ vm-web-1 (zone 1) 10.10.1.4
                                   sonde HTTP └──▶ vm-web-2 (zone 2) 10.10.1.5
vm-web-1/2 ──▶ natgw-lb ──▶ Internet (installation uniquement)
```

## A.0 — Groupe de ressources

**Groupes de ressources** → **+ Créer**.

| Champ | Valeur |
|---|---|
| Groupe de ressources | `rg-demo-lb` |
| Région | `(Europe) France Central` |

**Vérifier et créer** → **Créer**.

> 💡 **Pourquoi ?** Un groupe par démo : toutes les ressources partagent le même cycle de vie, et une seule suppression efface tout à la fin.

## A.1 — Réseau virtuel

**Réseaux virtuels** → **+ Créer**.

**Onglet Informations de base**

| Champ | Valeur |
|---|---|
| Groupe de ressources | `rg-demo-lb` |
| Nom du réseau virtuel | `vnet-lb` |
| Région | `(Europe) France Central` |

**Onglet Sécurité** : ne rien activer.

**Onglet Adresses IP**

- Espace d'adressage : `10.10.0.0/16`.
- Cliquer sur le sous-réseau `default` pour le modifier :

| Champ | Valeur |
|---|---|
| Nom | `snet-web` |
| Adresse de début | `10.10.1.0` |
| Taille | `/24` |

**Enregistrer** → **Vérifier et créer** → **Créer**.

> 💡 **Pourquoi ?**
>
> - **`10.10.0.0/16`** : plage privée (RFC 1918). Chaque démo a sa propre plage (10.10, 10.20, 10.30…) pour qu'aucune ne chevauche une autre.
> - **Un seul sous-réseau** pour deux zones : un sous-réseau couvre **toutes** les zones de la région. La zone se choisit au niveau de chaque VM, pas du réseau.
> - **/24** : 256 adresses, dont 5 réservées par Azure (`.0`, `.1`, `.2`, `.3`, `.255`). La première VM reçoit `.4`, la seconde `.5`.

## A.2 — Passerelle NAT

**Passerelles NAT** → **+ Créer**.

| Onglet | Champ | Valeur |
|---|---|---|
| Informations de base | Groupe de ressources | `rg-demo-lb` |
| Informations de base | Nom de la passerelle NAT | `natgw-lb` |
| Informations de base | Région | `(Europe) France Central` |
| Informations de base | Zone de disponibilité | `Aucune zone` |
| IP sortante | Adresses IP publiques | **Créer une adresse IP publique** → `pip-natgw-lb` → **OK** |
| Mise en réseau (*Networking*) | Réseau virtuel | `vnet-lb` |
| Mise en réseau | Sous-réseaux | cocher `snet-web` |

**Vérifier et créer** → **Créer**.

> 💡 **Pourquoi ?** Les VM n'auront pas d'IP publique, mais elles doivent télécharger nginx et cloner le dépôt au démarrage (voir P5). La passerelle doit exister **avant** les VM : cloud-init s'exécute dès le premier démarrage.

## A.3 — Groupe de sécurité réseau

**Groupes de sécurité réseau** → **+ Créer** : Groupe de ressources `rg-demo-lb`, Nom `nsg-web`, Région France Central → **Vérifier et créer** → **Créer** → **Accéder à la ressource**.

**Paramètres** → **Règles de sécurité de trafic entrant** → **+ Ajouter** :

| Champ | Valeur |
|---|---|
| Source | `Étiquette de service` |
| Étiquette du service source | `Internet` |
| Plages de ports sources | `*` |
| Destination | `Any` |
| Service | `HTTP` |
| Action | `Autoriser` |
| Priorité | `100` |
| Nom | `Allow-HTTP-Internet` |

**Ajouter**. Puis **Paramètres** → **Sous-réseaux** → **+ Associer** → Réseau virtuel `vnet-lb`, Sous-réseau `snet-web` → **OK**.

✅ Cocher **Afficher les règles par défaut** : on voit `AllowAzureLoadBalancerInBound` (65001).

> 💡 **Pourquoi ?**
>
> - Le Load Balancer **Standard** est **fermé par défaut** : sans règle NSG explicite, aucun trafic Internet n'atteint les VM.
> - **Source `Internet`** : le Load Balancer n'est pas un proxy, il **conserve l'IP du client**. La VM voit donc l'adresse du visiteur, qui peut être n'importe laquelle.
> - **La sonde de santé**, elle, provient de l'adresse spéciale `168.63.129.16`, déjà autorisée par la règle par défaut `AllowAzureLoadBalancerInBound`.
> - **NSG sur le sous-réseau** : une seule règle protège les deux VM, et toute VM ajoutée plus tard.

## A.4 — Les deux VM

**Machines virtuelles** → **+ Créer** → **Machine virtuelle Azure**.

**Onglet Informations de base**

| Champ | vm-web-1 | vm-web-2 |
|---|---|---|
| Groupe de ressources | `rg-demo-lb` | `rg-demo-lb` |
| Nom de la machine virtuelle | `vm-web-1` | `vm-web-2` |
| Région | `(Europe) France Central` | idem |
| Options de disponibilité | `Zone de disponibilité` | idem |
| Options de zone | `Zone sélectionnée manuellement` (*Self-selected zone*) | idem |
| Zone de disponibilité | **`Zone 1`** | **`Zone 2`** |
| Type de sécurité | `Machines virtuelles de lancement fiable` | idem |
| Image | `Ubuntu Server 24.04 LTS - x64 Gen2` | idem |
| Taille | `Standard_B1s` | idem |
| Type d'authentification | `Mot de passe` | idem |
| Nom d'utilisateur / Mot de passe | `azureuser` / mot de passe fort | idem |
| Ports d'entrée publics | `Aucun` | idem |

**Onglet Mise en réseau**

| Champ | Valeur (les deux VM) |
|---|---|
| Réseau virtuel | `vnet-lb` |
| Sous-réseau | `snet-web (10.10.1.0/24)` |
| IP publique | `Aucun` |
| Groupe de sécurité réseau de la carte réseau | `Aucun` |
| Options d'équilibrage de charge | `Aucun` |

**Onglet Surveillance** : Diagnostics de démarrage `Activer avec un compte de stockage managé`.

**Onglet Avancé** → **Données personnalisées** (les deux VM) :

```yaml
#cloud-config
package_update: true
packages:
  - git
runcmd:
  - git clone https://github.com/mohamedutopios/azure-demos-reseau.git /opt/demos
  - bash /opt/demos/lb/install.sh
```

**Vérifier et créer** → **Créer**. Créer `vm-web-1`, puis recommencer pour `vm-web-2`.

✅ Après 3 à 4 minutes, sur chaque VM → **Exécuter la commande** → **RunShellScript** :

```bash
cloud-init status
curl -s http://localhost/info.json
```

Résultat attendu : `status: done`, puis `{"hostname": "vm-web-1", "zone": "1", "ip": "10.10.1.4"}` (et `vm-web-2`, zone `2`, `10.10.1.5` pour la seconde).

> 💡 **Pourquoi ?**
>
> - **Zone 1 et zone 2** : deux zones de disponibilité sont deux datacenters indépendants (alimentation, réseau, refroidissement) dans la même région. Le service survit à la perte d'une zone entière. Les numéros de zone sont **logiques** et propres à chaque abonnement.
> - **IP publique `Aucun`** : les VM ne sont joignables qu'à travers le Load Balancer. On réduit la surface d'attaque à une seule adresse.
> - **NSG de carte réseau `Aucun`** : `nsg-web` sur le sous-réseau suffit. Deux NSG empilés obligeraient à ouvrir chaque flux deux fois.
> - **Options d'équilibrage de charge `Aucun`** : le Load Balancer n'existe pas encore. On ajoutera les VM à son pool à l'étape suivante.
> - **Ce que fait `lb/install.sh`** : il installe nginx, écrit dans `/info.json` l'identité de la VM (nom, zone, IP, lus sur le service de métadonnées Azure `169.254.169.254`), et désactive le *keep-alive* de nginx. Ce dernier point est essentiel pour la démo : chaque requête du navigateur ouvre alors une **nouvelle connexion TCP**, que le Load Balancer peut envoyer vers l'autre VM.
> - **`Standard_B1s`** : servir une page statique ne demande presque aucune ressource.

## A.5 — Le Load Balancer

**Équilibreurs de charge** (*Load balancers*) → **+ Créer** → **Équilibreur de charge standard**.

**Onglet Informations de base**

| Champ | Valeur |
|---|---|
| Groupe de ressources | `rg-demo-lb` |
| Nom | `lb-web` |
| Région | `(Europe) France Central` |
| Référence SKU | `Standard` |
| Type | `Public` |
| Niveau (*Tier*) | `Régional` |

**Onglet Configuration IP front-end** → **+ Ajouter une configuration IP front-end** :

| Champ | Valeur |
|---|---|
| Nom | `fe-web` |
| Version IP | `IPv4` |
| Type d'IP | `Adresse IP` |
| Adresse IP publique | **Créer** → Nom `pip-lb-web`, Zone de disponibilité `Redondant interzone` (*Zone-redundant*) → **Enregistrer** |

**Enregistrer**.

**Onglet Pools back-end** → **+ Ajouter un pool de back-ends** :

| Champ | Valeur |
|---|---|
| Nom | `bp-web` |
| Réseau virtuel | `vnet-lb` |
| Configuration du pool de back-ends | `Carte d'interface réseau` (*NIC*) |

Sous **Configurations IP** → **+ Ajouter** → cocher `vm-web-1` et `vm-web-2` → **Ajouter** → **Enregistrer**.

**Onglet Règles de trafic entrant** → **+ Ajouter une règle d'équilibrage de charge** :

| Champ | Valeur |
|---|---|
| Nom | `rule-http` |
| Version IP | `IPv4` |
| Adresse IP front-end | `fe-web` |
| Pool de back-ends | `bp-web` |
| Protocole | `TCP` |
| Port | `80` |
| Port back-end | `80` |
| Sonde d'intégrité | **Créer** → Nom `hp-http`, Protocole `HTTP`, Port `80`, Chemin `/info.json`, Intervalle `5` → **Enregistrer** |
| Persistance de session | `Aucun` |
| Délai d'inactivité (minutes) | `4` |
| Activer la réinitialisation TCP | décoché |
| Activer l'IP flottante | décoché |
| Traduction d'adresses réseau source (SNAT) sortante | `(Recommandé) Utiliser des règles de trafic sortant…` |

**Enregistrer**.

**Onglet Règles de trafic sortant** : ne rien ajouter.

**Vérifier et créer** → **Créer** → **Accéder à la ressource**.

> 💡 **Pourquoi ?**
>
> - **SKU `Standard`** : le seul compatible avec les zones et couvert par un SLA (le SKU Basic a été retiré).
> - **Type `Public`** : il reçoit le trafic d'Internet. Un Load Balancer `Interne` répartirait du trafic privé, par exemple entre un front et une API.
> - **IP `Redondant interzone`** : l'adresse reste joignable même si une zone tombe. Une IP liée à une seule zone disparaîtrait avec elle, et la redondance des VM ne servirait à rien.
> - **Pool par carte réseau** : le pool référence les cartes réseau des VM. Une VM ajoutée au pool reçoit du trafic dès qu'elle passe la sonde.
> - **Sonde HTTP sur `/info.json`, toutes les 5 s** : le Load Balancer n'envoie du trafic qu'aux VM qui répondent `200`. Une sonde **HTTP** vérifie que l'application répond ; une sonde **TCP** ne vérifierait que l'ouverture du port.
> - **Persistance `Aucun`** : la répartition se fait par hachage sur 5 éléments (IP et port source, IP et port destination, protocole). Chaque nouvelle connexion, avec un nouveau port source, peut aller sur une autre VM.
> - **SNAT par règles sortantes, sans règle sortante** : on ne donne pas d'accès Internet aux VM par le Load Balancer. La sortie est déjà assurée par la passerelle NAT, qui est prioritaire sur le Load Balancer pour le trafic sortant.

## A.6 — Voir la répartition

1. `lb-web` → **Paramètres** → **Configuration IP front-end** : noter l'adresse IP de `fe-web`.
2. Ouvrir `http://<IP de fe-web>` dans le navigateur.

✅ La page **Démo Azure Load Balancer** affiche, chaque seconde, la VM qui a répondu. Les barres **Répartition des requêtes** se stabilisent autour de 50 % / 50 % entre `vm-web-1` et `vm-web-2`.

> 💡 **Pourquoi ?**
>
> - La page fait `GET /info.json` chaque seconde. Comme nginx ferme la connexion après chaque réponse, le navigateur en ouvre une nouvelle, avec un nouveau port source, donc un nouveau hachage, donc parfois l'autre VM.
> - Sur un site normal, le navigateur garde sa connexion ouverte (*keep-alive*) : toutes ses requêtes vont alors vers la même VM. La répartition se fait **par connexion**, pas par requête.

## A.7 — Simuler une panne

1. Laisser la page ouverte.
2. Dans un autre onglet : **Machines virtuelles** → `vm-web-1` → **Arrêter** → **Oui**.
3. Observer la page.

✅ Quelques carrés rouges (5 à 10 secondes), puis **uniquement** `vm-web-2`. Le site ne s'est jamais arrêté longtemps.

4. `lb-web` → **Supervision** → **Métriques** → Métrique **État de la sonde d'intégrité** (*Health Probe Status*), Agrégation `Moyenne` → **Appliquer la division** → **Adresse IP back-end** : la courbe de `10.10.1.4` tombe à 0.
5. `vm-web-1` → **Démarrer**. Après 1 à 2 minutes, `vm-web-1` réapparaît sur la page.

> 💡 **Pourquoi ?**
>
> - Les carrés rouges correspondent au temps nécessaire à la sonde pour constater que `vm-web-1` ne répond plus, et la retirer de la rotation.
> - **Aucune intervention humaine** : la sonde retire la VM, puis la réintègre dès qu'elle répond de nouveau.
> - Arrêter une VM simule la panne d'une VM. La panne d'une zone entière se traite de la même façon : l'autre zone prend tout le trafic.

## A.8 — Bonus : persistance de session

1. `lb-web` → **Paramètres** → **Règles d'équilibrage de charge** → `rule-http`.
2. **Persistance de session** : `Adresse IP du client` → **Enregistrer**.
3. Observer la page : après une minute, **toutes** les requêtes vont vers la même VM.
4. Remettre **Persistance de session** à `Aucun` → **Enregistrer**.

> 💡 **Pourquoi ?** Avec la persistance par IP du client, le hachage ne porte plus que sur les adresses source et destination : un même visiteur atterrit toujours sur la même VM. C'est utile pour une application qui garde la session en mémoire locale. Le revers : la charge est moins bien répartie, et la session est perdue si la VM tombe. La bonne pratique reste une application **sans état**.

## Points à faire passer

- Le Load Balancer travaille en **couche 4** (TCP/UDP) : il ne lit pas le HTTP. Pour router selon l'URL, terminer le TLS ou filtrer les attaques web, il faut l'Application Gateway (démo C).
- Sans sonde correcte, pas de haute disponibilité réelle.
- Zones de disponibilité (perte d'un datacenter) ou ensemble de disponibilité (perte d'une baie) : la zone protège davantage.

## Nettoyage

**Groupes de ressources** → `rg-demo-lb` → **Supprimer le groupe de ressources** → saisir `rg-demo-lb` → **Supprimer**.

---

# Démo B — VM Scale Set et autoscaling

| | |
|---|---|
| Objectif | Déployer un groupe de VM identiques derrière un Load Balancer, le faire grandir automatiquement sous la charge CPU, puis rétrécir |
| Durée | 60 min, dont environ 25 min d'observation |
| Application | `autoscale/` — serveur Python avec un bouton « Charger les instances » et un tableau des instances en direct |
| Ressources | 1 VNet, 1 NAT Gateway, 1 NSG, 1 VM Scale Set (2 à 4 instances), 1 Load Balancer public |
| Adressage | `vnet-vmss` 10.20.0.0/16 · `snet-vmss` 10.20.1.0/24 |

> 🎯 **Ce que cette démo montre, et pourquoi**
>
> - Dans la démo A, le nombre de VM est fixe et chacune est créée à la main. Un **VM Scale Set** crée et supprime lui-même des VM **identiques** à partir d'un **modèle** (image, taille, Custom data).
> - **Élasticité** : payer 2 VM au calme et 4 en pic, sans intervention humaine.
> - L'application est conçue pour rendre l'autoscaling **visible** : on déclenche la charge depuis le navigateur, et on voit les nouvelles instances apparaître dans un tableau.

## B.0 — Groupe de ressources

**Groupes de ressources** → **+ Créer** → `rg-demo-vmss`, `(Europe) France Central` → **Vérifier et créer** → **Créer**.

## B.1 — Réseau virtuel

**Réseaux virtuels** → **+ Créer**.

| Onglet | Champ | Valeur |
|---|---|---|
| Informations de base | Groupe de ressources | `rg-demo-vmss` |
| Informations de base | Nom du réseau virtuel | `vnet-vmss` |
| Informations de base | Région | `(Europe) France Central` |
| Adresses IP | Espace d'adressage | `10.20.0.0/16` |
| Adresses IP | Sous-réseau `default` → modifier | Nom `snet-vmss`, Adresse de début `10.20.1.0`, Taille `/24` → **Enregistrer** |

**Vérifier et créer** → **Créer**.

> 💡 **Pourquoi ?** On crée le réseau **avant** le Scale Set pour pouvoir lui associer une passerelle NAT et un NSG. L'assistant du Scale Set sait créer un réseau, mais il ne permet pas d'y attacher ces deux éléments.

## B.2 — Passerelle NAT

**Passerelles NAT** → **+ Créer**.

| Onglet | Champ | Valeur |
|---|---|---|
| Informations de base | Groupe de ressources / Nom / Région | `rg-demo-vmss` / `natgw-vmss` / France Central |
| Informations de base | Zone de disponibilité | `Aucune zone` |
| IP sortante | Adresses IP publiques | **Créer** → `pip-natgw-vmss` |
| Mise en réseau | Réseau virtuel / Sous-réseaux | `vnet-vmss` / cocher `snet-vmss` |

**Vérifier et créer** → **Créer**.

> 💡 **Pourquoi ?** Chaque instance, y compris celles créées par l'autoscaling, clone le dépôt au démarrage. Sans sortie Internet, les nouvelles instances démarreraient **sans application** et la sonde ne les mettrait jamais en service.

## B.3 — Groupe de sécurité réseau

**Groupes de sécurité réseau** → **+ Créer** : `rg-demo-vmss`, `nsg-vmss`, France Central → **Créer** → **Accéder à la ressource**.

**Règles de sécurité de trafic entrant** → **+ Ajouter** :

| Champ | Valeur |
|---|---|
| Source | `Étiquette de service` → `Internet` |
| Destination | `Any` |
| Service | `HTTP` |
| Action | `Autoriser` |
| Priorité | `100` |
| Nom | `Allow-HTTP-Internet` |

**Sous-réseaux** → **+ Associer** → `vnet-vmss` / `snet-vmss` → **OK**.

> 💡 **Pourquoi ?** Comme dans la démo A : le Load Balancer Standard est fermé par défaut et conserve l'IP du client. Le NSG est posé sur le **sous-réseau** : toute instance créée par l'autoscaling est protégée sans configuration supplémentaire.

## B.4 — Créer le Scale Set

**Groupes de machines virtuelles identiques** (*Virtual machine scale sets*) → **+ Créer**.

**Onglet Informations de base**

| Champ | Valeur |
|---|---|
| Groupe de ressources | `rg-demo-vmss` |
| Nom du groupe de machines virtuelles identiques | `vmss-web` |
| Région | `(Europe) France Central` |
| Zone de disponibilité | `Zones 1, 2, 3` |
| Mode d'orchestration | `Flexible` |
| Type de sécurité | `Machines virtuelles de lancement fiable` |
| Mode de mise à l'échelle (*Scaling mode*) | `Mettre à jour manuellement la capacité` |
| Nombre d'instances | `2` |
| Image | `Ubuntu Server 24.04 LTS - x64 Gen2` |
| Taille | `Standard_B2s` (2 vCPU, 4 Gio) |
| Type d'authentification | `Mot de passe` |
| Nom d'utilisateur / Mot de passe | `azureuser` / mot de passe fort |

**Onglet Disques** : par défaut.

**Onglet Mise en réseau**

- **Réseau virtuel** : `vnet-vmss`.
- **Interfaces réseau** : cliquer l'icône **Modifier** (crayon) de la carte réseau :

| Champ | Valeur |
|---|---|
| Sous-réseau | `snet-vmss (10.20.1.0/24)` |
| Groupe de sécurité réseau de la carte réseau | `Aucun` |
| Adresse IP publique | `Désactivé` |

  → **OK**.
- **Options d'équilibrage de charge** : `Azure Load Balancer`.
- **Sélectionner un équilibreur de charge** → **Créer un équilibreur de charge** :

| Champ | Valeur |
|---|---|
| Nom de l'équilibreur de charge | `lb-vmss` |
| Type | `Public` |
| Protocole | `TCP` |
| Règles | `Règle d'équilibreur de charge` |
| Port front-end / Port back-end | `80` / `80` |

  → **Créer**.

**Onglet Intégrité** (*Health*)

| Champ | Valeur |
|---|---|
| Activer la surveillance de l'intégrité des applications | coché |
| Protocole / Port / Chemin | `HTTP` / `80` / `/health` |
| Réparations automatiques | décoché |

**Onglet Avancé** → **Données personnalisées** :

```yaml
#cloud-config
package_update: true
packages:
  - git
runcmd:
  - git clone https://github.com/mohamedutopios/azure-demos-reseau.git /opt/demos
  - bash /opt/demos/autoscale/install.sh
```

**Vérifier et créer** → **Créer** → **Accéder à la ressource**.

> 💡 **Pourquoi ?**
>
> - **Zones 1, 2, 3** : les instances sont réparties automatiquement sur les trois zones.
> - **Orchestration `Flexible`** : mode recommandé. Chaque instance est une VM classique, visible dans **Machines virtuelles**, avec ses propres disques et sa propre carte réseau. Le mode `Uniform`, plus ancien, ne permet de gérer les instances qu'à travers le Scale Set.
> - **Capacité manuelle, 2 instances** : on démarre avec un nombre fixe. L'autoscaling est configuré à l'étape B.6, pour bien distinguer les deux temps.
> - **`Standard_B2s`** : 2 vCPU, pour qu'une charge sur tous les cœurs fasse vraiment monter la moyenne CPU. C'est une série « burstable » : elle tient une charge de quelques dizaines de minutes grâce à ses crédits CPU, ce qui suffit pour la démo.
> - **Pas d'IP publique par instance** : tout passe par le Load Balancer.
> - **Load Balancer créé dans l'assistant** : chaque instance créée plus tard est ajoutée **automatiquement** à son pool. C'est la différence clé avec la démo A.
> - **Surveillance de l'intégrité sur `/health`** : le Scale Set sait quelles instances répondent réellement. Les **réparations automatiques** remplaceraient une instance défaillante ; on les laisse désactivées pour ne pas perturber l'observation.
> - **Ce que fait `autoscale/install.sh`** : il installe `server.py` comme service systemd. Le serveur affiche la page, renvoie l'identité et le CPU de l'instance (`/api/info`), et sature tous les cœurs de l'instance qui reçoit `POST /api/stress`. Il n'utilise que Python, déjà présent dans l'image Ubuntu.

## B.5 — Vérifier le déploiement

1. `vmss-web` → **Instances** : 2 instances `En cours d'exécution`, dans des zones différentes.
2. Barre de recherche → **Équilibreurs de charge** → `lb-vmss` → **Configuration IP front-end** : noter l'adresse IP publique.
3. Ouvrir `http://<IP de lb-vmss>`.

✅ La page **Démo VM Scale Set — autoscaling** affiche **2 instances actives**, avec un CPU proche de 0 %.

> 💡 **Pourquoi ?** On valide le modèle **avant** d'activer l'autoscaling : si les 2 premières instances répondent, toutes les suivantes répondront aussi, puisqu'elles sont construites de la même façon.

## B.6 — Configurer l'autoscaling

1. `vmss-web` → **Disponibilité + mise à l'échelle** → **Mise à l'échelle** (*Scaling*) → **Mise à l'échelle automatique personnalisée** (*Custom autoscale*).
2. Condition **Default** → **Mode de mise à l'échelle** : `Mettre à l'échelle en fonction d'une métrique`.
3. **+ Ajouter une règle** — montée en charge :

| Champ | Valeur |
|---|---|
| Source de la métrique | `Ressource actuelle (vmss-web)` |
| Nom de la métrique | `Percentage CPU` |
| Agrégation du temps | `Moyenne` |
| Opérateur | `Supérieur à` |
| Seuil de métrique | `60` |
| Durée (minutes) | `5` |
| Statistique de fragment de temps | `Moyenne` |
| Opération | `Augmenter le nombre de` |
| Nombre d'instances | `1` |
| Refroidissement (minutes) | `5` |

**Ajouter**.

4. **+ Ajouter une règle** — réduction :

| Champ | Valeur |
|---|---|
| Nom de la métrique | `Percentage CPU` |
| Opérateur | `Inférieur à` |
| Seuil de métrique | `25` |
| Durée (minutes) | `5` |
| Opération | `Diminuer le nombre de` |
| Nombre d'instances | `1` |
| Refroidissement (minutes) | `5` |

**Ajouter**.

5. **Limites d'instances** : Minimum `2`, Maximum `4`, Par défaut `2`.
6. **Enregistrer**.

> 💡 **Pourquoi ?**
>
> - **Moyenne du CPU** sur **toutes** les instances du groupe : chaque instance ajoutée fait baisser la moyenne.
> - **Seuils 60 % et 25 %** : l'écart est volontaire. Des seuils trop proches feraient osciller le groupe, avec des ajouts et des retraits en boucle (*flapping*).
> - **Durée 5 minutes** : on réagit à une tendance, pas à un pic de quelques secondes.
> - **Refroidissement 5 minutes** : après une action, on laisse à la nouvelle instance le temps de démarrer et d'installer l'application, et à la métrique le temps de se stabiliser, avant de décider à nouveau.
> - **Toujours une règle de réduction** : sans elle, le groupe grandit et ne rétrécit jamais, et la facture suit.
> - **Minimum 2** : au moins une instance survit à la perte d'une zone. **Maximum 4** : plafond de la facture et du quota (4 × 2 vCPU = 8). **Par défaut 2** : nombre utilisé si la métrique est indisponible.

## B.7 — Générer la charge et observer la montée

1. Sur la page de démo : durée `10 minutes` → **🔥 Charger les instances**.

✅ Le **Journal** indique `charge reçu par : vmss-web_xxxx, vmss-web_yyyy` : les deux instances. Leur CPU passe à environ 100 %, en rouge.

2. Portail : `vmss-web` → **Supervision** → **Métriques** → `Percentage CPU`, Agrégation `Moyenne`, période **30 dernières minutes** : la courbe monte.
3. Après 6 à 8 minutes : **Mise à l'échelle** → onglet **Historique d'exécution** (*Run history*) : un événement d'augmentation apparaît.

✅ Sur la page, le journal affiche `nouvelle instance : vmss-web_zzzz`, et le tableau passe à **3 instances**. La nouvelle instance est à 0 % de CPU.

4. Raisonnement à faire au tableau :
   - 2 instances à 100 % + 1 au repos = moyenne de **67 %**, toujours au-dessus de 60 % : une 4e instance est créée après le refroidissement.
   - 2 instances à 100 % + 2 au repos = moyenne de **50 %** : entre 25 et 60 %, le groupe se stabilise à **4**, qui est aussi le maximum.

> 💡 **Pourquoi ?**
>
> - Le bouton envoie **8 requêtes** de charge. Le Load Balancer les répartit, donc toutes les instances présentes en reçoivent au moins une.
> - Les instances créées ensuite ne sont pas chargées : c'est ce qui fait baisser la moyenne, et c'est réaliste, car une nouvelle instance prend sa part du trafic **futur**.
> - **Délai observé** = 5 min d'observation + création de la VM + exécution de cloud-init. L'autoscaling absorbe une **tendance**, pas un pic instantané. Pour un pic prévisible (soldes, rentrée), on ajoute une condition **planifiée**.

## B.8 — Observer la réduction

1. Sur la page : **🧊 Arrêter la charge** (ou attendre la fin des 10 minutes).
2. Le CPU moyen tombe sous 25 %. Environ toutes les 6 minutes, l'**Historique d'exécution** montre une diminution, jusqu'au minimum de 2.

✅ Sur la page, les instances supprimées passent en grisé avec l'étiquette **disparue ?** : elles ne répondent plus.

> 💡 **Pourquoi ?**
>
> - En réduction, le Scale Set choisit lui-même les instances à supprimer, en gardant l'équilibre entre les zones.
> - Une instance supprimée perd tout son contenu local : l'application doit être **sans état** (sessions et fichiers dans une base de données ou un stockage, jamais sur le disque de l'instance).

## Points à faire passer

- Un Scale Set applique un **modèle** : les instances sont interchangeables et jetables.
- Minimum et maximum bornent à la fois la disponibilité et la facture.
- Plus l'instance démarre vite, plus l'autoscaling est réactif. Une **image personnalisée** (application préinstallée) démarre plus vite qu'un script qui installe tout au démarrage.

## Nettoyage

**Groupes de ressources** → `rg-demo-vmss` → **Supprimer le groupe de ressources** → saisir `rg-demo-vmss` → **Supprimer**.

---

# Démo C — Application Gateway

| | |
|---|---|
| Objectif | Publier un site web et une API derrière **une seule adresse**, routés selon le chemin de l'URL, et comprendre le rôle des sondes d'intégrité |
| Durée | 60 min, dont 10 à 15 min de création de l'Application Gateway (à lancer en avance) |
| Application | `appgw/web/` — boutique en ligne (nginx) · `appgw/api/` — API catalogue (Python) |
| Ressources | 1 VNet (2 sous-réseaux), 1 NAT Gateway, 1 NSG, 2 VM sans IP publique, 1 Application Gateway Standard V2 |
| Adressage | `vnet-appgw` 10.30.0.0/16 · `snet-appgw` 10.30.0.0/24 · `snet-backend` 10.30.1.0/24 |

> 🎯 **Ce que cette démo montre, et pourquoi**
>
> - Le Load Balancer (démo A) répartit des **connexions TCP** sans lire leur contenu. L'**Application Gateway** est un répartiteur **HTTP** (couche 7) : il lit l'URL, les en-têtes et le nom d'hôte, et décide où envoyer chaque requête.
> - Cas d'usage : `/` vers les serveurs du site, `/api/*` vers les serveurs de l'API, sous un seul nom de domaine. Le navigateur ne voit qu'une adresse, donc pas de configuration CORS, un seul certificat, et un seul point de filtrage (WAF).
> - La démo montre aussi un piège classique : une **sonde d'intégrité** mal réglée qui déclare l'API en panne alors qu'elle fonctionne.

```
                                  ┌── /*      ──▶ pool-web ──▶ vm-web  10.30.1.4 (nginx)
Navigateur ──▶ agw-boutique ──────┤
          (IP publique)           └── /api/*  ──▶ pool-api ──▶ vm-api  10.30.1.5 (Python)
             snet-appgw                                      snet-backend (+ natgw-appgw)
```

## C.0 — Groupe de ressources

**Groupes de ressources** → **+ Créer** → `rg-demo-appgw`, `(Europe) France Central` → **Vérifier et créer** → **Créer**.

## C.1 — Réseau virtuel avec deux sous-réseaux

**Réseaux virtuels** → **+ Créer**.

**Onglet Informations de base** : Groupe de ressources `rg-demo-appgw`, Nom `vnet-appgw`, Région France Central.

**Onglet Adresses IP** :

- Espace d'adressage : `10.30.0.0/16`.
- Modifier le sous-réseau `default` : Nom `snet-appgw`, Adresse de début `10.30.0.0`, Taille `/24` → **Enregistrer**.
- **+ Ajouter un sous-réseau** : Nom `snet-backend`, Adresse de début `10.30.1.0`, Taille `/24` → **Ajouter**.

**Vérifier et créer** → **Créer**.

> 💡 **Pourquoi ?**
>
> - **Pourquoi un sous-réseau dédié à l'Application Gateway ?** Comme Bastion, l'Application Gateway n'est pas une VM à vous : c'est un service managé dont Azure déploie les **instances dans votre VNet**, pour qu'elles joignent les serveurs par leur IP privée. Le sous-réseau ne doit contenir **que** des Application Gateway : aucune VM, aucune autre ressource. Azure peut ainsi ajouter et retirer des instances sans conflit. Contrairement à Bastion, le nom du sous-réseau est libre.
> - **Pourquoi /24 ?** Chaque instance consomme une adresse privée, et la v2 peut monter jusqu'à 125 instances avec l'autoscaling. Microsoft recommande un /24 pour ne jamais être bloqué : on ne peut pas agrandir un sous-réseau occupé.
> - **`snet-backend` séparé** : les serveurs et la passerelle ont des règles d'accès différentes, donc des sous-réseaux différents.

## C.2 — Passerelle NAT

**Passerelles NAT** → **+ Créer**.

| Onglet | Champ | Valeur |
|---|---|---|
| Informations de base | Groupe / Nom / Région / Zone | `rg-demo-appgw` / `natgw-appgw` / France Central / `Aucune zone` |
| IP sortante | Adresses IP publiques | **Créer** → `pip-natgw-appgw` |
| Mise en réseau | Réseau virtuel / Sous-réseaux | `vnet-appgw` / cocher **`snet-backend` uniquement** |

**Vérifier et créer** → **Créer**.

> 💡 **Pourquoi ?** Les deux VM doivent installer leur application au démarrage (voir P5). On ne l'associe **pas** à `snet-appgw` : une passerelle NAT n'est pas prise en charge sur le sous-réseau d'une Application Gateway, qui gère elle-même sa connectivité.

## C.3 — Groupe de sécurité réseau des serveurs

**Groupes de sécurité réseau** → **+ Créer** : `rg-demo-appgw`, `nsg-backend`, France Central → **Créer** → **Accéder à la ressource**.

**Règles de sécurité de trafic entrant** → **+ Ajouter** :

| Champ | Valeur |
|---|---|
| Source | `Adresses IP` |
| Adresses IP sources/plages CIDR | `10.30.0.0/24` |
| Plages de ports sources | `*` |
| Destination | `Any` |
| Service | `HTTP` |
| Action | `Autoriser` |
| Priorité | `100` |
| Nom | `Allow-HTTP-from-AppGW` |

**Sous-réseaux** → **+ Associer** → `vnet-appgw` / **`snet-backend`** → **OK**.

> 💡 **Pourquoi ?**
>
> - Contrairement au Load Balancer, l'Application Gateway est un **proxy** : il termine la connexion du visiteur et en ouvre une nouvelle vers le serveur, **depuis l'IP privée d'une de ses instances**, dans `snet-appgw`. Les serveurs ne voient jamais l'IP d'Internet : on autorise donc uniquement `10.30.0.0/24`. (L'IP du visiteur reste lisible dans l'en-tête `X-Forwarded-For`.)
> - Résultat : même si un serveur recevait par erreur une IP publique, il resterait injoignable autrement qu'à travers la passerelle.
> - **Pas de NSG sur `snet-appgw`** dans cette démo. Si on en pose un, il doit impérativement autoriser l'étiquette `GatewayManager` sur les ports 65200-65535, sinon Azure ne peut plus piloter la passerelle.

## C.4 — Les deux VM

**Machines virtuelles** → **+ Créer** → **Machine virtuelle Azure**. Créer **vm-web d'abord**, puis vm-api.

**Onglet Informations de base**

| Champ | vm-web | vm-api |
|---|---|---|
| Groupe de ressources | `rg-demo-appgw` | idem |
| Nom de la machine virtuelle | `vm-web` | `vm-api` |
| Région | `(Europe) France Central` | idem |
| Options de disponibilité | `Aucune redondance d'infrastructure requise` | idem |
| Type de sécurité | `Machines virtuelles de lancement fiable` | idem |
| Image | `Ubuntu Server 24.04 LTS - x64 Gen2` | idem |
| Taille | `Standard_B1s` | idem |
| Type d'authentification | `Mot de passe` (`azureuser`) | idem |
| Ports d'entrée publics | `Aucun` | idem |

**Onglet Mise en réseau**

| Champ | Valeur (les deux VM) |
|---|---|
| Réseau virtuel | `vnet-appgw` |
| Sous-réseau | **`snet-backend (10.30.1.0/24)`** |
| IP publique | `Aucun` |
| Groupe de sécurité réseau de la carte réseau | `Aucun` |
| Options d'équilibrage de charge | `Aucun` |

**Onglet Avancé** → **Données personnalisées** :

`vm-web` :

```yaml
#cloud-config
package_update: true
packages:
  - git
runcmd:
  - git clone https://github.com/mohamedutopios/azure-demos-reseau.git /opt/demos
  - bash /opt/demos/appgw/web/install.sh
```

`vm-api` :

```yaml
#cloud-config
package_update: true
packages:
  - git
runcmd:
  - git clone https://github.com/mohamedutopios/azure-demos-reseau.git /opt/demos
  - bash /opt/demos/appgw/api/install.sh
```

**Vérifier et créer** → **Créer**.

✅ Sur `vm-api` → **Exécuter la commande** → **RunShellScript** :

```bash
curl -s http://localhost/api/produits | head -c 120; echo
curl -s -o /dev/null -w "GET / -> %{http_code}\n" http://localhost/
```

Résultat attendu : le début du catalogue JSON, puis `GET / -> 404`. **Retenez ce 404** : il explique l'étape C.6.

> 💡 **Pourquoi ?**
>
> - **`appgw/web/install.sh`** installe nginx et publie la boutique. La page appelle `/api/produits` **sur la même adresse** qu'elle-même.
> - **`appgw/api/install.sh`** installe une API Python comme service systemd. Elle ne répond que sur `/api/health` et `/api/produits`, et renvoie `404` sur tout le reste, y compris `/`. C'est fréquent pour une API, et c'est voulu ici.
> - **vm-web d'abord** : elle reçoit `10.30.1.4`, vm-api `10.30.1.5`. Ce n'est pas indispensable (la passerelle désigne les VM par leur carte réseau), mais c'est plus lisible.

## C.5 — Créer l'Application Gateway

**Passerelles d'application** (*Application gateways*) → **+ Créer**.

**Onglet Informations de base**

| Champ | Valeur |
|---|---|
| Groupe de ressources | `rg-demo-appgw` |
| Nom de la passerelle d'application | `agw-boutique` |
| Région | `(Europe) France Central` |
| Niveau (*Tier*) | `Standard V2` |
| Activer la mise à l'échelle automatique | `Non` |
| Nombre d'instances | `1` |
| Zone de disponibilité | `Aucun` |
| HTTP2 | `Désactivé` |
| Type d'adresse IP | `IPv4 uniquement` |
| Réseau virtuel | `vnet-appgw` |
| Sous-réseau | **`snet-appgw (10.30.0.0/24)`** |

**Suivant : Front-ends**

| Champ | Valeur |
|---|---|
| Type d'adresse IP front-end | `Publique` |
| Adresse IP publique | **Ajouter nouveau** → `pip-agw-boutique` → **OK** |

**Suivant : Back-ends** → **Ajouter un pool de back-ends**, deux fois :

| Champ | Pool 1 | Pool 2 |
|---|---|---|
| Nom | `pool-web` | `pool-api` |
| Ajouter un pool de back-ends sans cibles | `Non` | `Non` |
| Type de cible | `Machine virtuelle` | `Machine virtuelle` |
| Cible | carte réseau de `vm-web` | carte réseau de `vm-api` |

**Suivant : Configuration** → **Ajouter une règle de routage** :

| Champ | Valeur |
|---|---|
| Nom de la règle | `rule-boutique` |
| Priorité | `100` |

Onglet **Écouteur** (*Listener*) :

| Champ | Valeur |
|---|---|
| Nom de l'écouteur | `listener-http` |
| IP front-end | `IPv4 publique` |
| Protocole | `HTTP` |
| Port | `80` |
| Type d'écouteur | `De base` (*Basic*) |
| URL de page d'erreur | `Non` |

Onglet **Cibles back-end** (*Backend targets*) :

| Champ | Valeur |
|---|---|
| Type de cible | `Pool de back-ends` |
| Cible back-end | `pool-web` |
| Paramètres de back-end | **Ajouter nouveau** → Nom `settings-web`, Protocole `HTTP`, Port `80`, Affinité basée sur les cookies `Désactiver`, Drainage de connexion `Désactiver`, Délai d'expiration de la demande `20`, Remplacer par le nouveau nom d'hôte `Non` → **Ajouter** |

Puis, dans le même onglet : **Ajouter plusieurs cibles pour créer une règle basée sur le chemin** :

| Champ | Valeur |
|---|---|
| Chemin d'accès | `/api/*` |
| Nom de la cible | `api` |
| Paramètres de back-end | **Ajouter nouveau** → Nom **`settings-api`**, Protocole `HTTP`, Port `80`, autres valeurs identiques → **Ajouter** |
| Cible back-end | `pool-api` |

**Ajouter** (la cible) → **Ajouter** (la règle).

**Suivant : Balises** → **Suivant : Vérifier et créer** → **Créer**. La création dure **10 à 15 minutes**.

> 💡 **Pourquoi ?**
>
> - **`Standard V2`** : la génération actuelle (la v1 est retirée). Elle prend en charge les zones, l'autoscaling et une IP publique statique. `WAF V2` ajouterait un pare-feu applicatif contre les attaques web (injection SQL, XSS…), plus cher.
> - **1 instance, sans autoscaling** : le minimum pour une démo. En production, au moins 2 instances (ou l'autoscaling avec un minimum de 2), réparties sur des zones.
> - Les quatre briques d'une Application Gateway, à dessiner au tableau :
>   - l'**écouteur** (*listener*) : sur quelle IP et quel port, et pour quel nom d'hôte, la passerelle écoute ;
>   - la **règle** : relie un écouteur à des cibles, ici selon le chemin ;
>   - le **pool de back-ends** : les serveurs ;
>   - les **paramètres de back-end** (*backend settings*) : comment la passerelle parle aux serveurs (protocole, port, délai, affinité) et quelle **sonde** les surveille.
> - **Règle basée sur le chemin** : `/api/*` va vers `pool-api` ; tout le reste (la cible par défaut) va vers `pool-web`.
> - **Pourquoi deux paramètres de back-end (`settings-web` et `settings-api`) ?** Ils portent chacun leur propre sonde. Le site et l'API ne se surveillent pas sur le même chemin : partager les paramètres obligerait à partager la sonde, et donc à en casser un des deux.
> - **Affinité par cookie désactivée** : chaque requête peut aller sur n'importe quel serveur du pool (application sans état).
> - **Pourquoi c'est long ?** Azure provisionne et configure des instances dédiées dans `snet-appgw`.

## C.6 — Premier test : le catalogue est cassé

1. `agw-boutique` → **Vue d'ensemble** : noter l'**Adresse IP publique front-end**.
2. Ouvrir `http://<IP de agw-boutique>`.

✅ La page **Boutique Contoso** s'affiche : la carte `/ → vm-web` est correcte. Mais la carte `/api/produits` est **rouge**, avec le message **Catalogue indisponible (HTTP 502)**.

3. `agw-boutique` → **Supervision** → **Intégrité du back-end** (*Backend health*).

✅ `pool-web` est **Sain** (*Healthy*). `pool-api` est **Non sain** (*Unhealthy*), avec un message du type *« Received invalid status code: 404 in the backend server's HTTP response »*.

> 💡 **Pourquoi ?**
>
> - Sans sonde personnalisée, la passerelle utilise une **sonde par défaut** : elle demande `GET /` à chaque serveur et attend un code entre 200 et 399.
> - Le site web répond `200` sur `/` : il est sain.
> - L'API répond `404` sur `/` (vu en C.4) : elle est jugée **en panne**, alors qu'elle fonctionne parfaitement sur `/api/produits`.
> - Quand un pool n'a **aucun** serveur sain, la passerelle répond elle-même **`502 Bad Gateway`**. Un 502 vient de la passerelle, pas de l'application.

## C.7 — Corriger avec une sonde personnalisée

1. `agw-boutique` → **Paramètres** → **Sondes d'intégrité** (*Health probes*) → **+ Ajouter**.

| Champ | Valeur |
|---|---|
| Nom | `probe-api` |
| Protocole | `HTTP` |
| Hôte | `127.0.0.1` |
| Choisir le nom d'hôte à partir des paramètres back-end | `Non` |
| Choisir le port à partir des paramètres back-end | `Oui` |
| Chemin d'accès | **`/api/health`** |
| Intervalle (secondes) | `10` |
| Délai d'expiration (secondes) | `10` |
| Seuil de défaillance | `3` |
| Utiliser les conditions de correspondance de la sonde | `Non` |
| Paramètres de back-end | **`settings-api`** |
| Je souhaite tester l'intégrité du back-end avant d'ajouter la sonde d'intégrité | coché |

2. **Tester** → le résultat indique `pool-api` **Sain** → **Ajouter**.
3. **Intégrité du back-end** : les deux pools sont **Sains**.
4. Recharger la boutique (**Ctrl + F5**).

✅ Les six produits s'affichent. La carte `/api/produits → vm-api (10.30.1.5)` est correcte.

> 💡 **Pourquoi ?**
>
> - La sonde interroge désormais `/api/health`, un chemin **fait pour ça** : il répond `200` tant que l'API fonctionne.
> - Bonne pratique : chaque application expose un point de santé dédié. Il peut aussi vérifier ses dépendances (base de données, etc.) pour que la passerelle écarte un serveur qui tourne mais ne peut pas travailler.
> - **Intervalle 10 s × seuil 3** : un serveur est retiré après environ 30 secondes de silence. C'est un compromis entre réactivité et fausses alertes.
> - **Associée à `settings-api` uniquement** : le site web garde la sonde par défaut sur `/`, qui lui convient.

## C.8 — Simuler la panne de l'API

1. **Machines virtuelles** → `vm-api` → **Arrêter**.
2. Après 30 à 60 secondes, recharger la boutique.

✅ La page s'affiche toujours (elle vient de `vm-web`), mais le catalogue est en erreur **502**. **Intégrité du back-end** : `pool-api` **Non sain**.

3. `vm-api` → **Démarrer**. Une minute après, le catalogue revient.

> 💡 **Pourquoi ?** Le routage par chemin isole les pannes : la panne de l'API ne fait pas tomber le site. En production, on mettrait au moins **deux** VM dans chaque pool, dans des zones différentes, et le visiteur ne verrait rien.

## Points à faire passer

| | Load Balancer (démo A) | Application Gateway |
|---|---|---|
| Couche | 4 (TCP/UDP) | 7 (HTTP/HTTPS) |
| Lit l'URL, les en-têtes | Non | Oui (routage par chemin et par nom d'hôte) |
| Connexion | Transmise telle quelle, IP client conservée | Terminée puis rouverte (proxy) ; IP client dans `X-Forwarded-For` |
| TLS (HTTPS) | Passe au travers | Peut le terminer (certificat sur la passerelle) |
| Sécurité applicative | Non | WAF (niveau WAF V2) |
| Sous-réseau dédié | Non | Oui |
| Coût | Faible | Plus élevé, facturé à l'heure |

- **Question aux stagiaires** : que renvoie `http://<IP>/api` (sans `/` final) ? *(Il ne correspond pas à `/api/*` : la requête part vers `pool-web`, dont nginx répond 404.)*

## Nettoyage

**Groupes de ressources** → `rg-demo-appgw` → **Supprimer le groupe de ressources** → saisir `rg-demo-appgw` → **Supprimer**. **À faire juste après la démo** : l'Application Gateway est facturée à l'heure, même sans trafic.

---

# Démo D — VNet peering

| | |
|---|---|
| Objectif | Relier deux réseaux virtuels isolés, constater en direct que le service de l'autre réseau devient joignable, puis comprendre les routes |
| Durée | 40 min |
| Application | `peering/hub/` — front nginx qui relaie `/api/` vers le spoke · `peering/spoke/` — service interne Python sur le port 8080 |
| Ressources | 2 VNet, 1 NAT Gateway, 2 VM (une seule avec IP publique), 1 peering |
| Adressage | `vnet-hub` 10.40.0.0/16 · `snet-hub` 10.40.1.0/24 — `vnet-spoke` 10.50.0.0/16 · `snet-spoke` 10.50.1.0/24 |

> 🎯 **Ce que cette démo montre, et pourquoi**
>
> - Deux réseaux virtuels sont **totalement isolés** par défaut, même dans le même abonnement et la même région. C'est une garantie de sécurité.
> - Le **peering** relie deux VNets par le réseau interne de Microsoft. Les VM se joignent par leurs **IP privées**, sans passer par Internet, sans passerelle VPN et sans traduction d'adresse.
> - Architecture **hub and spoke** : un réseau central (hub) porte les services partagés et l'exposition à Internet, et des réseaux applicatifs (spokes) restent privés.
> - La page de démo affiche en direct l'état de la liaison : on la voit passer du rouge au vert au moment où le peering est créé.

```
Navigateur ──HTTP──▶ vm-hub (IP publique, nginx) ── /api/ ──▶ 10.50.1.4:8080 vm-spoke
                     vnet-hub 10.40.0.0/16        ◀═ peering ═▶   vnet-spoke 10.50.0.0/16
                                                                   └─ natgw-spoke (installation)
```

## D.0 — Groupe de ressources

**Groupes de ressources** → **+ Créer** → `rg-demo-peering`, `(Europe) France Central` → **Vérifier et créer** → **Créer**.

## D.1 — Les deux réseaux virtuels

**Réseaux virtuels** → **+ Créer**, deux fois :

| Onglet | Champ | Hub | Spoke |
|---|---|---|---|
| Informations de base | Groupe de ressources | `rg-demo-peering` | `rg-demo-peering` |
| Informations de base | Nom du réseau virtuel | `vnet-hub` | `vnet-spoke` |
| Informations de base | Région | France Central | France Central |
| Adresses IP | Espace d'adressage | `10.40.0.0/16` | `10.50.0.0/16` |
| Adresses IP | Sous-réseau `default` → modifier | `snet-hub`, `10.40.1.0`, `/24` | `snet-spoke`, `10.50.1.0`, `/24` |

> 💡 **Pourquoi ?**
>
> - **Plages qui ne se chevauchent pas** : c'est la **condition obligatoire** du peering. Si les deux VNets utilisaient `10.0.0.0/16`, l'adresse `10.0.1.4` existerait des deux côtés, et le routage ne saurait pas laquelle viser. Azure refuse donc de les appairer.
> - D'où l'importance d'un **plan d'adressage** d'entreprise décidé dès le départ : on ne change pas facilement la plage d'un VNet rempli de ressources.

## D.2 — Passerelle NAT du spoke

**Passerelles NAT** → **+ Créer**.

| Onglet | Champ | Valeur |
|---|---|---|
| Informations de base | Groupe / Nom / Région / Zone | `rg-demo-peering` / `natgw-spoke` / France Central / `Aucune zone` |
| IP sortante | Adresses IP publiques | **Créer** → `pip-natgw-spoke` |
| Mise en réseau | Réseau virtuel / Sous-réseaux | `vnet-spoke` / cocher `snet-spoke` |

**Vérifier et créer** → **Créer**.

> 💡 **Pourquoi ?** `vm-spoke` n'aura pas d'IP publique, mais doit cloner le dépôt au démarrage (voir P5). `vm-hub` aura une IP publique, qui lui sert aussi pour sortir.

## D.3 — VM du spoke (service interne)

**Machines virtuelles** → **+ Créer** → **Machine virtuelle Azure**.

| Onglet | Champ | Valeur |
|---|---|---|
| Informations de base | Groupe de ressources | `rg-demo-peering` |
| Informations de base | Nom de la machine virtuelle | `vm-spoke` |
| Informations de base | Région | France Central |
| Informations de base | Options de disponibilité | `Aucune redondance d'infrastructure requise` |
| Informations de base | Image / Taille | `Ubuntu Server 24.04 LTS - x64 Gen2` / `Standard_B1s` |
| Informations de base | Authentification | `Mot de passe` (`azureuser`) |
| Informations de base | Ports d'entrée publics | `Aucun` |
| Mise en réseau | Réseau virtuel / Sous-réseau | `vnet-spoke` / `snet-spoke (10.50.1.0/24)` |
| Mise en réseau | IP publique | `Aucun` |
| Mise en réseau | Groupe de sécurité réseau de la carte réseau | `De base` |
| Mise en réseau | Ports d'entrée publics | `Aucun` |

**Onglet Avancé** → **Données personnalisées** :

```yaml
#cloud-config
package_update: true
packages:
  - git
runcmd:
  - git clone https://github.com/mohamedutopios/azure-demos-reseau.git /opt/demos
  - bash /opt/demos/peering/spoke/install.sh
```

**Vérifier et créer** → **Créer**.

Puis **fixer l'IP** : `vm-spoke` → **Mise en réseau** → **Paramètres réseau** → lien de la carte réseau → **Configurations IP** → `ipconfig1` → Allocation `Statique`, Adresse IP `10.50.1.4` → **Enregistrer**.

> 💡 **Pourquoi ?**
>
> - **Aucune IP publique** : ce service est interne. Le seul moyen de l'atteindre sera le peering.
> - **NSG `De base` sans port ouvert** : seules les règles par défaut s'appliquent. Rien n'entre depuis Internet, mais `AllowVnetInBound` autorise le trafic de l'étiquette `VirtualNetwork`. On verra en D.7 que cette étiquette s'élargit automatiquement avec le peering.
> - **IP statique `10.50.1.4`** : le relais nginx du hub vise cette adresse précise.
> - **Ce que fait `peering/spoke/install.sh`** : il installe un service Python sur le port 8080. Celui-ci répond sur `/api/interne`, en indiquant son nom, son IP et **l'adresse de l'appelant**.

## D.4 — VM du hub (front public)

**Machines virtuelles** → **+ Créer** → **Machine virtuelle Azure**. Mêmes valeurs que D.3, sauf :

| Onglet | Champ | Valeur |
|---|---|---|
| Informations de base | Nom de la machine virtuelle | `vm-hub` |
| Informations de base | Ports d'entrée publics | `Autoriser les ports sélectionnés` → **HTTP (80)** |
| Mise en réseau | Réseau virtuel / Sous-réseau | `vnet-hub` / `snet-hub (10.40.1.0/24)` |
| Mise en réseau | IP publique | **(nouveau) vm-hub-ip** |
| Mise en réseau | Groupe de sécurité réseau de la carte réseau | `De base`, ports **HTTP (80)** |

**Onglet Avancé** → **Données personnalisées** :

```yaml
#cloud-config
package_update: true
packages:
  - git
runcmd:
  - git clone https://github.com/mohamedutopios/azure-demos-reseau.git /opt/demos
  - bash /opt/demos/peering/hub/install.sh
```

**Vérifier et créer** → **Créer**. Noter l'**Adresse IP publique** de `vm-hub`.

> 💡 **Pourquoi ?**
>
> - Le hub est la **seule porte d'entrée** depuis Internet. Il porte le front et relaie les appels vers les services internes.
> - **Ce que fait `peering/hub/install.sh`** : il installe nginx, publie la page de démo, et configure un **relais** (*reverse proxy*) : toute requête `/api/…` est transmise à `http://10.50.1.4:8080`. Le délai de connexion est réglé à 3 secondes, pour que la page affiche l'échec rapidement.

## D.5 — Avant le peering : aucune route

1. Ouvrir `http://<IP de vm-hub>`.

✅ La page **Démo VNet peering** s'affiche (elle vient de `vm-hub`), mais le statut est **❌ Service interne injoignable (HTTP 504)** : la liaison est en pointillés rouges, **aucune route**.

2. `vm-hub` → **Mise en réseau** → **Paramètres réseau** → lien de la carte réseau → **Aide** → **Itinéraires effectifs** (*Effective routes*).

✅ Parmi les routes :

| Préfixe d'adresse | Type de tronçon suivant |
|---|---|
| `10.40.0.0/16` | Réseau virtuel |
| `0.0.0.0/0` | Internet |
| `10.0.0.0/8` | **Aucun** (*None*) |

> 💡 **Pourquoi ?**
>
> - nginx tente de joindre `10.50.1.4`. Cette adresse correspond à la route `10.0.0.0/8` → **Aucun** : Azure **jette** les paquets. nginx attend 3 secondes, puis renvoie **504 Gateway Timeout**.
> - Azure ajoute d'office des routes « Aucun » pour les plages privées (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`) : un paquet vers une adresse privée inconnue ne part **jamais** sur Internet. C'est cette isolation que le peering va lever, de façon contrôlée.

## D.6 — Créer le peering

1. **Réseaux virtuels** → `vnet-hub` → **Paramètres** → **Peerings** → **+ Ajouter**.

**Section « Récapitulatif du réseau virtuel distant »** (*Remote virtual network summary*)

| Champ | Valeur |
|---|---|
| Nom du lien de peering | `spoke-vers-hub` |
| Modèle de déploiement de réseau virtuel | `Resource Manager` |
| Je connais mon ID de ressource | décoché |
| Abonnement | votre abonnement |
| Réseau virtuel | `vnet-spoke` |

**Section « Paramètres de peering du réseau virtuel distant »**

| Option | Valeur |
|---|---|
| Autoriser « vnet-spoke » à accéder à « vnet-hub » | ☑ coché |
| Autoriser « vnet-spoke » à recevoir le trafic transféré depuis « vnet-hub » | ☐ décoché |
| Autoriser la passerelle ou le serveur de routes de « vnet-spoke » à transférer le trafic vers « vnet-hub » | ☐ décoché |
| Permettre à « vnet-spoke » d'utiliser la passerelle distante ou le serveur de routes de « vnet-hub » | ☐ décoché |

**Section « Récapitulatif du réseau virtuel local »** (*Local virtual network summary*)

| Champ | Valeur |
|---|---|
| Nom du lien de peering | `hub-vers-spoke` |

**Section « Paramètres de peering du réseau virtuel local »**

| Option | Valeur |
|---|---|
| Autoriser « vnet-hub » à accéder à « vnet-spoke » | ☑ coché |
| Les trois autres options | ☐ décochées |

2. **Ajouter**.

✅ Après quelques secondes, **Peerings** affiche `hub-vers-spoke`, **État du peering** `Connecté`, **État de synchronisation** `Entièrement synchronisé`. Le même lien (`spoke-vers-hub`) apparaît dans `vnet-spoke` → **Peerings**.

> 💡 **Pourquoi ?**
>
> - **Un peering a deux côtés** : un lien dans chaque VNet. Le portail crée les deux en une seule fois. Avec l'interface en ligne de commande, il faudrait créer chaque côté séparément, et le peering ne passe à `Connecté` qu'une fois les deux côtés créés.
> - **« Autoriser l'accès »** des deux côtés : c'est ce qui ouvre la communication. On peut le décocher pour suspendre le trafic sans supprimer le peering.
> - **« Trafic transféré »** : autorise du trafic qui ne vient pas du VNet lui-même, mais qui transite par une appliance (pare-feu, NVA). C'est utile dans un hub avec Azure Firewall, pas ici.
> - **Options de passerelle** : permettent à un spoke d'utiliser la passerelle VPN ou ExpressRoute du hub pour joindre le réseau de l'entreprise (*gateway transit*). C'est un usage central du modèle hub and spoke, sans objet ici.

## D.7 — Après le peering

1. Revenir sur la page de démo, sans la recharger.

✅ En moins de 3 secondes, le statut passe à **✅ Service interne joignable**, et la liaison devient verte, **peering actif**. Le message indique que le spoke voit l'appel venir de **`10.40.1.4`**.

2. **Itinéraires effectifs** de la carte réseau de `vm-hub` (rafraîchir) :

| Préfixe d'adresse | Type de tronçon suivant |
|---|---|
| `10.50.0.0/16` | **Peering de réseaux virtuels** (*VNet peering*) |

3. `vm-spoke` → **Mise en réseau** → **Paramètres réseau** → lien de la carte réseau → **Aide** → **Règles de sécurité effectives** → règle `AllowVnetInBound` → cliquer sur la source `VirtualNetwork`.

✅ La liste des préfixes contient `10.50.0.0/16` **et** `10.40.0.0/16`.

> 💡 **Pourquoi ?**
>
> - Azure a ajouté une **route** vers la plage de l'autre VNet, dans les deux VNets. Le trafic passe par le réseau interne de Microsoft, jamais par Internet.
> - **Appelant `10.40.1.4`** : aucune traduction d'adresse. Le spoke voit l'IP privée réelle du hub, ce qui permet de filtrer finement avec des règles NSG.
> - **L'étiquette `VirtualNetwork` s'élargit** aux réseaux appairés. Sans aucune modification du NSG de `vm-spoke`, la règle par défaut `AllowVnetInBound` laisse maintenant entrer le hub. Pour un vrai service, on ajoute une règle qui n'autorise que `10.40.1.0/24` sur le port 8080, puis une règle `Refuser` sur `VirtualNetwork`.

## D.8 — Couper et rétablir

1. `vnet-hub` → **Peerings** → `hub-vers-spoke` → décocher **Autoriser « vnet-hub » à accéder à « vnet-spoke »** → **Enregistrer**.

✅ La page repasse au rouge en quelques secondes.

2. Recocher l'option → **Enregistrer** : la page repasse au vert.

> 💡 **Pourquoi ?** Le peering s'active et se suspend **instantanément**, sans redémarrer les VM et sans couper les autres flux. C'est utile pour isoler en urgence un réseau compromis.

## Points à faire passer

- **Non transitif** : si `vnet-a` est appairé au hub, et le hub à `vnet-b`, alors `vnet-a` et `vnet-b` ne se voient **pas**. Pour faire communiquer deux spokes : un peering direct, ou un pare-feu / une appliance dans le hub (avec l'option « trafic transféré » et des tables de routage), ou Azure Virtual WAN.
- **Peering global** : il fonctionne aussi entre régions, et même entre abonnements ou entre tenants.
- **Coût** : le trafic qui traverse un peering est facturé au Go, dans chaque sens (plus cher entre régions). Le peering lui-même est gratuit.
- **Peering ou VPN** : le peering relie des VNets Azure entre eux ; un VPN ou ExpressRoute relie Azure au réseau de l'entreprise.

## Nettoyage

**Groupes de ressources** → `rg-demo-peering` → **Supprimer le groupe de ressources** → saisir `rg-demo-peering` → **Supprimer**. Les peerings sont supprimés avec les VNets.
