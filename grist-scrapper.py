#!/usr/bin/env python3
"""
Récupère les enregistrements d'un tableau Grist via l'API REST,
en ne gardant qu'une liste de colonnes optionnelle.

Docs: https://support.getgrist.com/api/

Variables d'environnement (dans .env) :
  GRIST_HOST=https://docs.getgrist.com
  GRIST_API_KEY=ton_api_key
  GRIST_DOC_ID=uuid-du-document
  GRIST_TABLE_ID=NomTable
  GRIST_COLUMNS=Col1,Col2,Col3  # optionnel
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import requests
from typing import Any, Dict, List, Optional

# Charge .env dans le répertoire du script
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

GRIST_HOST = os.getenv("GRIST_HOST", "https://docs.getgrist.com")
GRIST_API_KEY = os.getenv("GRIST_API_KEY")
DOC_ID = os.getenv("GRIST_DOC_ID")
TABLE_ID = os.getenv("GRIST_TABLE_ID")
COLUMNS_RAW = os.getenv("GRIST_COLUMNS", "")

# Parse la liste de colonnes : "Nom,Prenom,Email" -> ["Nom", "Prenom", "Email"]
COLUMNS: Optional[List[str]] = (
    [c.strip() for c in COLUMNS_RAW.split(",") if c.strip()] if COLUMNS_RAW else None
)


def list_grist_tables(host: str, doc_id: str, api_key: str):
    """
    Liste les tables d'un document Grist.
    Endpoint: GET /api/docs/{docId}/tables
    """
    url = f"{host}/api/docs/{doc_id}/tables"
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    for t in data.get("tables", []):
        print(f"ID: {t['id']:>3} | tableId: {t['tableId']:<20} | name: {t['name']}")


def fetch_grist_table_records(
    host: str,
    doc_id: str,
    table_id: str,
    api_key: str,
    columns: Optional[List[str]] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Récupère les enregistrements d'un tableau Grist.
    Endpoint: GET /api/docs/{docId}/tables/{tableId}/records

    columns: liste des noms de colonnes à garder (en plus de 'id').
             Si None, toutes les colonnes sont conservées.
    """
    url = f"{host}/api/docs/{doc_id}/tables/{table_id}/records"
    headers = {"Authorization": f"Bearer {api_key}"}
    params: Dict[str, Any] = {}

    if filters:
        params["filters"] = filters

    resp = requests.get(url, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    records = []
    for rec in data.get("records", []):
        row = {"id": rec["id"]}
        fields = rec.get("fields", {})

        if columns:
            # On ne garde que les colonnes demandées (si elles existent)
            filtered_fields = {
                col: fields[col] for col in columns if col in fields
            }
            row.update(filtered_fields)
        else:
            row.update(fields)

        records.append(row)

    return records


if __name__ == "__main__":
    if not all([GRIST_API_KEY, DOC_ID, TABLE_ID]):
        raise SystemExit(
            "Définis les variables d'environnement : "
            "GRIST_API_KEY, GRIST_DOC_ID, GRIST_TABLE_ID (et optionnellement GRIST_HOST)"
        )

    # Optionnel : afficher la liste des tables pour vérifier
    # list_grist_tables(GRIST_HOST, DOC_ID, GRIST_API_KEY)

    rows = fetch_grist_table_records(
        host=GRIST_HOST,
        doc_id=DOC_ID,
        table_id=TABLE_ID,
        api_key=GRIST_API_KEY,
        columns=COLUMNS,
    )

    # Exemple d'usage : afficher
    for row in rows:
        print(row)