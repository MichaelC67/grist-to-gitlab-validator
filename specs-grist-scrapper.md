# Spécification — Récupération paramétrable de données Grist

## Objectif

Développer une application Python en ligne de commande capable de lire les enregistrements d'un tableau précis d'un document Grist, via l'API REST Grist.

L'application doit être générique : sa configuration, notamment l'instance Grist, le document cible, le tableau cible, les identifiants d'accès et les colonnes à extraire, ne doit pas être codée en dur. Elle doit être fournie par des variables d'environnement, habituellement chargées depuis un fichier `.env`.

## Besoin métier

Un utilisateur souhaite automatiser l'extraction de données présentes dans un tableau Grist afin de pouvoir ensuite :

- consulter les données depuis un script ;
- les transformer ou les exploiter dans un autre programme ;
- préparer un export vers un autre système ;
- déclencher ultérieurement cette extraction localement, dans une tâche planifiée ou dans un pipeline CI/CD.

Un même document Grist pouvant contenir plusieurs tableaux, l'utilisateur doit pouvoir désigner explicitement le tableau source sans modifier le code Python.

## Périmètre fonctionnel

### Fonction principale

Le programme récupère l'ensemble des enregistrements d'un tableau Grist spécifié, en appelant l'endpoint REST suivant :

```text
GET /api/docs/{docId}/tables/{tableId}/records
```

Chaque enregistrement retourné par Grist contient un identifiant de ligne (`id`) et un objet `fields` contenant les valeurs des colonnes. Le programme convertit cette structure en une liste de dictionnaires Python plats :

```python
{
    "id": 12,
    "Nom": "Durand",
    "Email": "jean.durand@example.net"
}
```

L'identifiant de ligne Grist (`id`) est toujours conservé dans le résultat.

### Sélection du tableau

Le tableau à lire est fourni par la variable `GRIST_TABLE_ID`.

La valeur attendue est le `tableId` Grist, c'est-à-dire l'identifiant technique du tableau (souvent le nom normalisé). Il peut être identifié :

- dans la vue **Raw Data / Données brutes** du document Grist ;
- en appelant l'endpoint `GET /api/docs/{docId}/tables` ;
- grâce à une fonction Python optionnelle de listage des tableaux.

Exemple :

```env
GRIST_TABLE_ID=Clients
```

### Sélection optionnelle des colonnes

Le programme accepte une liste facultative de colonnes via la variable `GRIST_COLUMNS`.

- Les colonnes sont séparées par des virgules.
- Les espaces autour des noms sont ignorés.
- Seules les colonnes demandées sont présentes dans les résultats, en plus de l'identifiant `id`.
- Lorsqu'une colonne demandée n'existe pas dans un enregistrement, elle n'est pas ajoutée à cet enregistrement.
- Lorsque `GRIST_COLUMNS` est absente ou vide, toutes les colonnes retournées par Grist sont conservées.

Exemple :

```env
GRIST_COLUMNS=Nom,Prenom,Email,Ville
```

## Configuration

### Fichier `.env`

Le programme charge un fichier `.env` placé dans le même répertoire que le script Python. Le chargement est réalisé avec le package `python-dotenv`.

Variables attendues :

| Variable | Obligatoire | Description | Exemple |
|---|---:|---|---|
| `GRIST_HOST` | Non | URL de base de l'instance Grist. La valeur par défaut est `https://docs.getgrist.com`. | `https://docs.getgrist.com` |
| `GRIST_API_KEY` | Oui | Clé API personnelle Grist utilisée dans l'en-tête HTTP Bearer. | `xxxxxxxx` |
| `GRIST_DOC_ID` | Oui | Identifiant/UUID du document Grist à lire. | `abc123def456` |
| `GRIST_TABLE_ID` | Oui | Identifiant technique du tableau à récupérer. | `Clients` |
| `GRIST_COLUMNS` | Non | Liste des colonnes à conserver, séparées par des virgules. | `Nom,Email,Ville` |

Exemple complet :

```env
GRIST_HOST=https://docs.getgrist.com
GRIST_API_KEY=remplacer_par_une_cle_api
GRIST_DOC_ID=remplacer_par_l_uuid_du_document
GRIST_TABLE_ID=Clients
GRIST_COLUMNS=Nom,Prenom,Email,Ville
```

## Exigences techniques

### Langage et dépendances

- Python 3.10 ou version ultérieure recommandée.
- Package `requests` pour les appels HTTP.
- Package `python-dotenv` pour charger la configuration depuis `.env`.

Installation :

```bash
pip install requests python-dotenv
```

### Authentification

Chaque requête adressée à Grist doit contenir l'en-tête suivant :

```http
Authorization: Bearer <GRIST_API_KEY>
```

La clé API possède les permissions du compte Grist auquel elle appartient. Le compte doit donc disposer au minimum d'un droit de lecture sur le document cible.

### Construction de l'URL

L'URL de lecture est construite de la manière suivante :

```text
{GRIST_HOST}/api/docs/{GRIST_DOC_ID}/tables/{GRIST_TABLE_ID}/records
```

Les séparateurs superflus en fin d'URL de l'hôte doivent être évités ou neutralisés afin de ne pas produire de double slash.

### Gestion des erreurs

Le programme doit échouer explicitement dans les cas suivants :

- une des variables obligatoires est absente (`GRIST_API_KEY`, `GRIST_DOC_ID` ou `GRIST_TABLE_ID`) ;
- Grist retourne un statut HTTP d'erreur (authentification refusée, document ou tableau introuvable, autorisation insuffisante, erreur serveur) ;
- la requête dépasse le délai réseau configuré.

Les erreurs HTTP doivent être remontées à l'utilisateur grâce à `response.raise_for_status()` ou à une gestion d'exception équivalente. Un délai de 30 secondes est recommandé.

## Comportement attendu

1. Au démarrage, le programme charge le fichier `.env` situé à côté du script.
2. Il valide que les variables obligatoires sont définies.
3. Il lit `GRIST_COLUMNS` et la convertit, si elle est présente, en une liste de noms de colonnes nettoyés.
4. Il appelle l'API Grist avec le document et le tableau configurés.
5. Il transforme chaque réponse Grist de la forme `{"id": ..., "fields": {...}}` en dictionnaire plat.
6. Il conserve soit toutes les colonnes, soit seulement celles demandées dans `GRIST_COLUMNS`.
7. Il affiche les lignes obtenues ou les met à disposition du reste du programme sous la forme d'une liste de dictionnaires.

## Interface en ligne de commande

Le script est conçu pour être lancé depuis le répertoire qui contient le script et le fichier `.env` :

```bash
python grist-scrapper.py
```

Le chemin du fichier `.env` doit être construit à partir du répertoire du script afin que le lancement fonctionne aussi depuis un autre répertoire :

```python
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)
```

## Fonction de diagnostic optionnelle

Une fonction de diagnostic peut lister les tableaux accessibles dans le document :

```text
GET /api/docs/{docId}/tables
```

Cette fonction affiche au minimum :

- l'identifiant numérique de la table ;
- le `tableId` à utiliser dans `GRIST_TABLE_ID` ;
- le nom affiché dans l'interface Grist.

Elle est utile lors de la première configuration, mais ne doit pas forcément être appelée à chaque exécution.

## Sécurité

- Le fichier `.env` contient une information sensible (`GRIST_API_KEY`) et ne doit jamais être versionné.
- Le fichier `.env` doit être ajouté à `.gitignore`.
- Un fichier `.env.example`, sans clé réelle, peut être versionné pour documenter les variables requises.
- En CI/CD, la clé et les autres valeurs sensibles doivent être définies dans les variables protégées du système CI plutôt que copiées dans un fichier `.env` versionné.

Exemple de `.gitignore` :

```gitignore
.env
```

Exemple de `.env.example` :

```env
GRIST_HOST=https://docs.getgrist.com
GRIST_API_KEY=
GRIST_DOC_ID=
GRIST_TABLE_ID=
GRIST_COLUMNS=
```

## Hors périmètre actuel

La première version ne couvre pas :

- l'écriture, la modification ou la suppression de données dans Grist ;
- l'export automatique CSV, JSON ou Excel ;
- le filtrage côté API ;
- la pagination ou le traitement de très grands volumes ;
- la résolution automatique des colonnes par leur libellé affiché si celui-ci diffère de leur identifiant technique ;
- une interface graphique ;
- l'ordonnancement planifié ou l'intégration CI/CD.

Ces évolutions pourront être ajoutées sans modifier le principe de configuration par variables d'environnement.

## Critères d'acceptation

- Avec un `.env` valide, le script récupère les lignes du tableau désigné par `GRIST_TABLE_ID`.
- Sans `GRIST_COLUMNS`, chaque ligne retournée contient `id` et toutes les colonnes accessibles de la table.
- Avec `GRIST_COLUMNS=Nom,Email`, chaque ligne retournée contient `id`, `Nom` et `Email` lorsqu'elles existent.
- Un tableau différent peut être lu uniquement en changeant `GRIST_TABLE_ID` dans `.env`.
- Une clé API invalide ou sans droit d'accès produit une erreur HTTP explicite.
- Aucune clé API n'est inscrite dans le code source ni dans les fichiers versionnés.
