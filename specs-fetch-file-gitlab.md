# Spécification — Récupération paramétrable de fichiers GitLab

## Objectif

Développer une application Python en ligne de commande qui récupère un fichier défini dans plusieurs dépôts GitLab.

La liste des dépôts est issue d'un export JSON provenant d'un tableau Grist. L'application est générique : elle ne cible pas spécifiquement un changelog et peut télécharger tout fichier texte présent dans les dépôts, par exemple `README.md`, `CHANGELOG.md`, `HISTORY.md`, `docs/RELEASE_NOTES.md`, un fichier YAML ou un fichier de configuration.

La configuration doit permettre de choisir sans modifier le code :

- la propriété JSON contenant l'URL du dépôt ;
- le chemin du fichier à récupérer dans chaque dépôt ;
- la branche à utiliser par défaut ;
- la propriété JSON utilisée pour construire le nom du fichier local ;
- le motif de nommage des fichiers de sortie ;
- l'instance GitLab, le jeton d'accès, le fichier JSON source et le dossier de sortie.

## Besoin métier

Un utilisateur maintient un inventaire d'applications ou de composants dans un tableau Grist. Chaque enregistrement représente potentiellement un projet et contient une propriété donnant accès au dépôt GitLab correspondant.

Il souhaite récupérer de manière industrielle un même fichier depuis tous les dépôts référencés afin de :

- vérifier que le fichier est présent ;
- centraliser les contenus dans un répertoire local ;
- analyser des fichiers de documentation ou de configuration ;
- contrôler la conformité d'un ensemble de projets ;
- préparer une normalisation, une migration ou un rapport ;
- intégrer le traitement dans une exécution locale, planifiée ou CI/CD.

L'outil doit fonctionner à partir d'un export JSON local et ne contacte pas directement Grist. La récupération Grist constitue une étape distincte en amont.

## Périmètre fonctionnel

### Entrée JSON

Le programme lit un fichier local désigné par `FILE_FETCH_INPUT_JSON`.

Les formats supportés sont :

- un tableau JSON standard ;
- un objet JSON unique ;
- un objet JSON par ligne ;
- à titre de compatibilité, des dictionnaires Python simples affichés une ligne par enregistrement (guillemets simples et booléens Python).

Exemple d'enregistrement :

```json
{
  "id": 54,
  "Nom_historique": "Admission de la donnée - Batch",
  "URL_Github": "https://gitlab.exemple.fr/groupe/admission-donnees",
  "Nom_Harmonise": "admission-donnees"
}
```

## Configuration

### Variables d'environnement

Le programme charge un fichier `.env` situé dans le même répertoire que le script Python, grâce à `python-dotenv`.

| Variable | Obligatoire | Description | Exemple |
|---|---:|---|---|
| `FILE_FETCH_INPUT_JSON` | Non | Chemin du fichier JSON source. Défaut : `export_grist.json`. | `export_grist.json` |
| `FILE_FETCH_OUTPUT_DIR` | Non | Répertoire où les fichiers sont sauvegardés. Défaut : `fichiers_recuperes`. | `fichiers_recuperes` |
| `FILE_FETCH_URL_PROPERTY` | Non | Nom de la propriété JSON contenant l'URL du dépôt GitLab. Défaut : `URL_Github`. | `URL_Gitlab` |
| `FILE_FETCH_FILE_PATH` | Oui | Chemin du fichier à récupérer, relatif à la racine de chaque dépôt. | `docs/RELEASE_NOTES.md` |
| `FILE_FETCH_DEFAULT_BRANCH` | Non | Branche utilisée si l'URL ne précise aucune branche. Défaut : `main`. | `main` |
| `FILE_FETCH_NAME_PROPERTY` | Non | Nom de la propriété JSON utilisée pour la partie principale du nom du fichier de sortie. Défaut : `Nom_Harmonise`. | `Nom_historique` |
| `FILE_FETCH_OUTPUT_PATTERN` | Non | Motif de nommage du fichier en sortie. Défaut : `{name}-{file}.txt`. | `{name}{ext}` |
| `GITLAB_HOST` | Oui | URL de l'instance GitLab, sans `/api/v4`. | `https://gitlab.exemple.fr` |
| `GITLAB_TOKEN` | Oui | Jeton GitLab ayant un droit de lecture sur les projets. | `glpat-xxxxxxxx` |

Exemple de `.env` :

```env
FILE_FETCH_INPUT_JSON=export_grist.json
FILE_FETCH_OUTPUT_DIR=fichiers_recuperes
FILE_FETCH_URL_PROPERTY=URL_Github
FILE_FETCH_FILE_PATH=CHANGELOG.md
FILE_FETCH_DEFAULT_BRANCH=main

FILE_FETCH_NAME_PROPERTY=Nom_Harmonise
FILE_FETCH_OUTPUT_PATTERN={name}-{file}.txt

GITLAB_HOST=https://gitlab.exemple.fr
GITLAB_TOKEN=remplacer_par_un_jeton_gitlab
```

### Propriété d'URL de dépôt

La variable `FILE_FETCH_URL_PROPERTY` désigne le nom de la propriété JSON dont la valeur est une URL de dépôt GitLab.

Exemple :

```env
FILE_FETCH_URL_PROPERTY=URL_Github
```

Pour l'enregistrement suivant, le programme lira donc la valeur `https://gitlab.exemple.fr/groupe/mon-projet` :

```json
{
  "URL_Github": "https://gitlab.exemple.fr/groupe/mon-projet"
}
```

Les valeurs absentes, vides, non valides, textuelles (par exemple `sur le gitlab interne`) ou correspondant à une autre instance que `GITLAB_HOST` sont ignorées avec un message de suivi explicite lorsqu'elles sont analysées.

### Chemin du fichier cible

`FILE_FETCH_FILE_PATH` définit le chemin relatif du fichier à télécharger dans chaque dépôt. Cette variable est obligatoire et le programme s'arrête explicitement si elle est absente ou vide.

La même valeur s'applique à tous les enregistrements d'une exécution.

Exemples :

```env
FILE_FETCH_FILE_PATH=CHANGELOG.md
```

```env
FILE_FETCH_FILE_PATH=README.md
```

```env
FILE_FETCH_FILE_PATH=docs/RELEASE_NOTES.md
```

Le fichier cible peut être changé uniquement en modifiant le fichier `.env`, sans modification du code Python.

### Branchement Git

Le programme utilise la branche précisée dans l'URL lorsque celle-ci est de l'une des formes suivantes :

```text
https://gitlab.exemple.fr/groupe/projet/-/tree/develop
https://gitlab.exemple.fr/groupe/projet/-/blob/release-1.2/docs/README.md
```

Dans les autres cas, notamment une URL de dépôt simple, il utilise `FILE_FETCH_DEFAULT_BRANCH`.

Exemple :

```env
FILE_FETCH_DEFAULT_BRANCH=main
```

## Nommage en sortie

### Choix de la propriété de nom

`FILE_FETCH_NAME_PROPERTY` désigne la propriété JSON qui fournit la partie principale du nom de fichier local.

Exemple :

```env
FILE_FETCH_NAME_PROPERTY=Nom_Harmonise
```

Avec l'enregistrement suivant :

```json
{
  "Nom_Harmonise": "admission-donnees"
}
```

la variable `{name}` vaut :

```text
admission-donnees
```

Si la propriété configurée est absente, vide ou non textuelle, le programme utilise `project_<idGitLab>` comme valeur de repli afin de garantir un nom de sortie exploitable.

### Motif de nommage

`FILE_FETCH_OUTPUT_PATTERN` détermine le nom de chaque fichier de sortie.

Les placeholders pris en charge sont :

| Placeholder | Valeur |
|---|---|
| `{name}` | Valeur de la propriété définie par `FILE_FETCH_NAME_PROPERTY`, nettoyée pour être utilisée dans un nom de fichier. |
| `{file}` | Valeur de `FILE_FETCH_FILE_PATH`, avec les séparateurs `/` remplacés par `_`, puis nettoyée. |
| `{ext}` | Extension du fichier cible, incluant le point, par exemple `.md`, `.txt` ou `.yaml`. |

Les caractères non compatibles avec un nom de fichier sont remplacés ou retirés dans les valeurs injectées : les lettres, chiffres, tirets, underscores et points sont conservés.

Exemples de motifs :

| Valeur de `FILE_FETCH_OUTPUT_PATTERN` | Fichier cible | Nom obtenu pour `{name}=mon-projet` |
|---|---|---|
| `{name}-{file}.txt` | `CHANGELOG.md` | `mon-projet-CHANGELOG.md.txt` |
| `{name}.txt` | `README.md` | `mon-projet.txt` |
| `{name}{ext}` | `CHANGELOG.md` | `mon-projet.md` |
| `{name}-{file}` | `docs/README.md` | `mon-projet-docs_README.md` |

> Attention : le motif doit produire des noms uniques. Si plusieurs enregistrements aboutissent au même nom, le dernier fichier écrit remplacera le précédent.

## GitLab

### Formats d'URL acceptés

Le programme doit interpréter au minimum les formats suivants :

```text
https://gitlab.exemple.fr/groupe/projet
https://gitlab.exemple.fr/groupe/sous-groupe/projet
https://gitlab.exemple.fr/groupe/projet/-/tree/main
https://gitlab.exemple.fr/groupe/projet/-/blob/main/README.md
```

Il extrait :

- le chemin GitLab du projet, par exemple `groupe/projet` ou `groupe/sous-groupe/projet` ;
- la branche si elle est explicite dans l'URL ;
- sinon, la branche par défaut configurée.

### Authentification

Les appels à l'API GitLab utilisent l'en-tête :

```http
PRIVATE-TOKEN: <GITLAB_TOKEN>
```

Le jeton doit disposer au minimum d'un droit de lecture sur les projets ciblés. Il est recommandé d'appliquer le principe du moindre privilège et d'utiliser un jeton limité à la lecture de l'API lorsque l'instance le permet.

### Endpoints utilisés

L'application utilise l'API GitLab v4.

Le programme recherche d'abord le projet à partir de son chemin et vérifie une correspondance exacte sur `path_with_namespace`. En l'absence de correspondance dans les résultats de recherche, il interroge directement l'endpoint de projet avec le chemin URL-encodé.

Résolution directe d'un projet :

```text
GET /api/v4/projects/{projectPathEncode}
```

Récupération du contenu brut du fichier :

```text
GET /api/v4/projects/{projectId}/repository/files/{filePathEncode}/raw?ref={branch}
```

Les chemins du projet et du fichier sont encodés dans les URL afin de prendre en charge les namespaces et les sous-répertoires.

## Exigences techniques

### Langage et dépendances

- Python 3.10 ou version ultérieure recommandée.
- `requests` pour les requêtes HTTP.
- `python-dotenv` pour charger le fichier `.env`.

Installation :

```bash
pip install requests python-dotenv
```

### Gestion des erreurs

Le programme doit :

- arrêter immédiatement l'exécution si `GITLAB_HOST` est absent ou vide ;
- arrêter immédiatement l'exécution si `GITLAB_TOKEN` est absent ou vide ;
- arrêter immédiatement l'exécution si `FILE_FETCH_FILE_PATH` est absent ou vide ;
- signaler les erreurs HTTP lors de la résolution ou de la récupération d'un projet ;
- considérer une réponse HTTP 404 du fichier comme un cas normal : le fichier est absent pour ce projet ou cette branche, un avertissement est affiché et le traitement continue ;
- poursuivre le traitement des enregistrements suivants lorsqu'un projet est inaccessible, introuvable ou en erreur ;
- appliquer un délai de 30 secondes aux requêtes HTTP ;
- afficher un état de suivi par enregistrement traité.

## Comportement attendu

1. Le script charge `.env` depuis le même répertoire que le script.
2. Il valide la présence de `GITLAB_HOST`, `GITLAB_TOKEN` et `FILE_FETCH_FILE_PATH`.
3. Il lit le fichier de données défini par `FILE_FETCH_INPUT_JSON`.
4. Il crée le dossier `FILE_FETCH_OUTPUT_DIR` s'il n'existe pas.
5. Pour chaque enregistrement, il lit l'URL de la propriété définie par `FILE_FETCH_URL_PROPERTY`.
6. Il ignore l'enregistrement si l'URL n'est pas exploitable.
7. Il détermine le chemin du projet et la branche.
8. Il résout le projet GitLab.
9. Il télécharge le fichier défini par `FILE_FETCH_FILE_PATH`.
10. Si le fichier existe, il construit un nom à partir de `FILE_FETCH_NAME_PROPERTY` et `FILE_FETCH_OUTPUT_PATTERN`, puis l'écrit dans le dossier de sortie.
11. Si le fichier n'existe pas, il signale l'absence et poursuit.

## Messages de suivi

Le programme doit afficher des messages explicites, par exemple :

```text
[OK] fichiers_recuperes/admission-donnees-CHANGELOG.md.txt créé depuis groupe/admission-donnees (branche main, fichier CHANGELOG.md)
[WARN] Pas de fichier 'CHANGELOG.md' sur groupe/autre-projet (branche main)
[SKIP] URL non supportée ou hors instance GitLab : sur le gitlab interne
[ERROR] Impossible de résoudre le projet groupe/projet-inaccessible: 404 Client Error
```

## Exécution

Depuis un terminal, avec le script et `.env` dans le même répertoire :

```bash
python fetch-file-gitlab.py
```

Le programme doit fonctionner même si la commande est lancée depuis un autre répertoire, en localisant `.env` à partir de `Path(__file__).parent`.

## Sécurité

- `GITLAB_TOKEN` est sensible et ne doit jamais apparaître dans le code ni dans un fichier versionné.
- Le fichier `.env` doit être ignoré par Git.
- Un fichier `.env.example`, sans secret, peut être versionné afin de documenter les variables nécessaires.
- En CI/CD, les valeurs sensibles doivent être injectées par les variables sécurisées de la plateforme CI.
- Le dossier de sortie est généralement ignoré par Git, car il contient des données extraites et potentiellement sensibles.

Exemple de `.gitignore` :

```gitignore
.env
.env.local
.env.*.local
fichiers_recuperes/
export_grist.json
__pycache__/
*.log
```

Exemple de `.env.example` :

```env
FILE_FETCH_INPUT_JSON=export_grist.json
FILE_FETCH_OUTPUT_DIR=fichiers_recuperes
FILE_FETCH_URL_PROPERTY=URL_Github
FILE_FETCH_FILE_PATH=README.md
FILE_FETCH_DEFAULT_BRANCH=main
FILE_FETCH_NAME_PROPERTY=Nom_Harmonise
FILE_FETCH_OUTPUT_PATTERN={name}-{file}.txt

GITLAB_HOST=https://gitlab.exemple.fr
GITLAB_TOKEN=
```

## Hors périmètre

La première version ne couvre pas :

- l'écriture, la création, la mise à jour ou la suppression de fichiers GitLab ;
- le clonage des dépôts ;
- le téléchargement de plusieurs fichiers différents dans une unique exécution ;
- la sélection d'un chemin de fichier spécifique à chaque enregistrement ;
- l'accès direct à Grist, sans export JSON intermédiaire ;
- GitHub, Bitbucket ou d'autres forges Git ;
- l'analyse ou l'interprétation du contenu téléchargé ;
- la génération d'un rapport consolidé CSV, JSON ou Markdown ;
- les mécanismes de cache, retry, parallélisation ou rate limiting avancé ;
- une interface graphique.

## Critères d'acceptation

- Le programme traite un fichier JSON contenant plusieurs enregistrements.
- La propriété contenant l'URL du dépôt est configurable avec `FILE_FETCH_URL_PROPERTY`.
- Le chemin du fichier à télécharger est obligatoirement fourni avec `FILE_FETCH_FILE_PATH`.
- L'instance GitLab est obligatoirement fournie avec `GITLAB_HOST`.
- La propriété servant de base au nom local est configurable avec `FILE_FETCH_NAME_PROPERTY`.
- Le nom de sortie est configurable avec `FILE_FETCH_OUTPUT_PATTERN` et les placeholders `{name}`, `{file}` et `{ext}`.
- Pour une URL GitLab valide et un fichier présent sur la branche ciblée, le contenu est téléchargé dans `FILE_FETCH_OUTPUT_DIR`.
- Pour un fichier absent, le programme affiche un avertissement et poursuit les autres enregistrements.
- Pour une URL absente, invalide ou hors de l'instance GitLab configurée, le programme affiche un message de saut et poursuit.
- Pour un projet inaccessible ou inexistant, le programme signale l'erreur sans empêcher le traitement des autres projets.
- La modification de `FILE_FETCH_FILE_PATH`, `FILE_FETCH_NAME_PROPERTY` ou `FILE_FETCH_OUTPUT_PATTERN` ne nécessite aucune modification du code.
- Aucun jeton GitLab réel n'est versionné.
