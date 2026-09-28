#!/usr/bin/env python3
"""
Récupère un fichier donné depuis GitLab pour chaque enregistrement
d'un export JSON issu de Grist.

Configuration via .env :
- FILE_FETCH_INPUT_JSON : chemin du fichier JSON d'entrée
- FILE_FETCH_OUTPUT_DIR : dossier où sauvegarder les fichiers récupérés
- FILE_FETCH_URL_PROPERTY : nom de la propriété contenant l'URL du dépôt Git
- FILE_FETCH_FILE_PATH : chemin du fichier à récupérer dans le dépôt (OBLIGATOIRE)
- FILE_FETCH_DEFAULT_BRANCH : branche par défaut si non détectée (ex. main, master)
- FILE_FETCH_NAME_PROPERTY : propriété JSON utilisée comme « nom de projet »
dans le nom de fichier de sortie.
- FILE_FETCH_OUTPUT_PATTERN : motif de nommage du fichier de sortie.
Placeholders : {name}, {file}, {ext}
- GITLAB_HOST : URL de l'instance GitLab (OBLIGATOIRE)
- GITLAB_TOKEN : token d'accès à GitLab (Personal Access Token) (OBLIGATOIRE)
"""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Chargement .env
# ---------------------------------------------------------------------------

env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

FILE_FETCH_INPUT_JSON = os.getenv("FILE_FETCH_INPUT_JSON", "export_grist.json")
FILE_FETCH_OUTPUT_DIR = os.getenv("FILE_FETCH_OUTPUT_DIR", "fichiers_recuperes")

FILE_FETCH_URL_PROPERTY = os.getenv("FILE_FETCH_URL_PROPERTY", "URL_Github")
FILE_FETCH_FILE_PATH = os.getenv("FILE_FETCH_FILE_PATH")
FILE_FETCH_DEFAULT_BRANCH = os.getenv("FILE_FETCH_DEFAULT_BRANCH", "main")

FILE_FETCH_NAME_PROPERTY = os.getenv("FILE_FETCH_NAME_PROPERTY", "Nom_Harmonise")
FILE_FETCH_OUTPUT_PATTERN = os.getenv("FILE_FETCH_OUTPUT_PATTERN", "{name}-{file}.txt")

GITLAB_HOST = os.getenv("GITLAB_HOST")
GITLAB_TOKEN = os.getenv("GITLAB_TOKEN")

# ---------------------------------------------------------------------------
# Utilitaires GitLab
# ---------------------------------------------------------------------------

GITLAB_API_BASE = f"{GITLAB_HOST}/api/v4"


def parse_gitlab_url(repo_url: str) -> Optional[Dict[str, str]]:
    """
    Extrait project_path et branche depuis une URL GitLab.
    """
    parsed = urlparse(repo_url)
    if not parsed.netloc or not parsed.path:
        return None

    host_norm = parsed.netloc.lower()
    gitlab_host_norm = urlparse(GITLAB_HOST).netloc.lower()
    if host_norm != gitlab_host_norm:
        return None

    path_parts = [p for p in parsed.path.split("/") if p]

    branch = FILE_FETCH_DEFAULT_BRANCH
    project_end_index = len(path_parts)

    for i, part in enumerate(path_parts):
        if part == "-" and i + 1 < len(path_parts):
            sub = path_parts[i + 1]
            if sub in ("tree", "blob", "commits", "commit"):
                if i + 2 < len(path_parts):
                    branch = path_parts[i + 2]
                project_end_index = i
                break

    if project_end_index < 2:
        return None

    project_path = "/".join(path_parts[:project_end_index])

    return {"project_path": project_path, "branch": branch}


def get_gitlab_project_id(project_path: str) -> int:
    """
    Récupère l'ID numérique d'un projet GitLab à partir de son path.
    """
    url = f"{GITLAB_API_BASE}/projects"
    headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}
    params = {"search": project_path}

    resp = requests.get(url, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    projects = resp.json()

    for p in projects:
        if p.get("path_with_namespace") == project_path:
            return p["id"]

    url_project = f"{GITLAB_API_BASE}/projects/{requests.utils.quote(project_path, safe='')}"
    resp2 = requests.get(url_project, headers=headers, timeout=30)
    resp2.raise_for_status()
    return resp2.json()["id"]


def fetch_gitlab_file_raw(
    project_id: int,
    file_path: str,
    ref: str,
) -> Optional[str]:
    """
    Récupère le contenu brut d'un fichier depuis GitLab.
    """
    url = f"{GITLAB_API_BASE}/projects/{project_id}/repository/files/{requests.utils.quote(file_path, safe='')}/raw"
    headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}
    params = {"ref": ref}

    resp = requests.get(url, headers=headers, params=params, timeout=30)

    if resp.status_code == 404:
        return None

    resp.raise_for_status()
    return resp.text


# ---------------------------------------------------------------------------
# Traitement des enregistrements
# ---------------------------------------------------------------------------

def load_records_from_json(path: str) -> List[Dict[str, Any]]:
    """
    Charge un fichier JSON où chaque ligne est un objet.
    """
    content = Path(path).read_text(encoding="utf-8")

    try:
        data = json.loads(content)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return [data]
    except json.JSONDecodeError:
        pass

    records = []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue

        normalized = re.sub(r"'([^']*)':", r'"\1":', line)
        normalized = re.sub(
            r": '([^']*)'",
            lambda m: ': "' + m.group(1).replace('"', '\\"') + '"',
            normalized,
        )
        normalized = re.sub(
            r": (True|False)",
            lambda m: ': ' + ('true' if m.group(1) == "True" else 'false'),
            normalized,
        )
        try:
            obj = json.loads(normalized)
            records.append(obj)
        except json.JSONDecodeError:
            continue

    return records


def sanitize_filename(name: str) -> str:
    """
    Nettoie un nom pour en faire un nom de fichier sûr.
    """
    sanitized = re.sub(r"[^0-9A-Za-z_.-]+", "_", name)
    return sanitized.strip("_.")


def get_project_name(rec: Dict[str, Any], project_id: int) -> str:
    """
    Retourne le nom de projet à utiliser dans le nom de fichier.

    Priorité :
    1. Propriété FILE_FETCH_NAME_PROPERTY si présente et non vide
    2. Fallback sur project_id
    """
    if FILE_FETCH_NAME_PROPERTY:
        value = rec.get(FILE_FETCH_NAME_PROPERTY)
        if value and isinstance(value, str) and value.strip():
            return value.strip()

    return f"project_{project_id}"


def build_output_filename(project_name: str, file_path: str) -> str:
    """
    Construit le nom de fichier de sortie à partir du motif FILE_FETCH_OUTPUT_PATTERN.

    Placeholders :
    {name} = project_name (sanitisé)
    {file} = file_path avec '/' -> '_' (sanitisé)
    {ext} = extension du fichier (ex. .md, .txt)
    """
    # Extension du fichier cible
    ext = Path(file_path).suffix  # ex. ".md", ".txt", ".yaml" ou ""

    # Version « safe » du chemin du fichier pour le nom
    file_safe = sanitize_filename(file_path.replace("/", "_"))

    name_safe = sanitize_filename(project_name)

    pattern = FILE_FETCH_OUTPUT_PATTERN

    filename = (
        pattern
        .replace("{name}", name_safe)
        .replace("{file}", file_safe)
        .replace("{ext}", ext)
    )

    return filename


def main():
    # Validation des variables obligatoires
    if not GITLAB_TOKEN:
        raise SystemExit("GITLAB_TOKEN doit être défini dans .env ou l'environnement.")

    if not GITLAB_HOST:
        raise SystemExit("GITLAB_HOST doit être défini dans .env ou l'environnement.")

    if not FILE_FETCH_FILE_PATH:
        raise SystemExit("FILE_FETCH_FILE_PATH doit être défini dans .env ou l'environnement.")

    out_dir = Path(FILE_FETCH_OUTPUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    records = load_records_from_json(FILE_FETCH_INPUT_JSON)

    for rec in records:
        repo_url = rec.get(FILE_FETCH_URL_PROPERTY)
        if not repo_url or repo_url == "sur le gitlab interne":
            continue

        parsed = parse_gitlab_url(repo_url)
        if not parsed:
            print(f"[SKIP] URL non supportée ou hors instance GitLab : {repo_url}")
            continue

        project_path = parsed["project_path"]
        branch = parsed["branch"]

        try:
            project_id = get_gitlab_project_id(project_path)
        except Exception as e:
            print(f"[ERROR] Impossible de résoudre le projet {project_path}: {e}")
            continue

        content = fetch_gitlab_file_raw(project_id, FILE_FETCH_FILE_PATH, branch)
        if content is None:
            print(
                f"[WARN] Pas de fichier '{FILE_FETCH_FILE_PATH}' sur {project_path} (branche {branch})"
            )
            continue

        project_name = get_project_name(rec, project_id)
        filename = build_output_filename(project_name, FILE_FETCH_FILE_PATH)
        output_file = out_dir / filename

        output_file.write_text(content, encoding="utf-8")
        print(
            f"[OK] {output_file} créé depuis {project_path} (branche {branch}, fichier {FILE_FETCH_FILE_PATH})"
        )


if __name__ == "__main__":
    main()