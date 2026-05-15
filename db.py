"""
Cliente Supabase + helpers de lectura/escritura.
La paginacion silenciosa de PostgREST limita a 1000 filas por SELECT, asi que
usamos `_fetch_all` con `.range()` explicito.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

import pandas as pd
import streamlit as st
from supabase import Client, create_client

PAGE_SIZE = 1000


@lru_cache(maxsize=1)
def get_client() -> Client:
    """Devuelve un cliente Supabase singleton.

    Lee credenciales de st.secrets["supabase"] o de env vars (SUPABASE_URL /
    SUPABASE_KEY) para que la app corra tambien fuera de Streamlit Cloud.
    """
    try:
        cfg = st.secrets["supabase"]
        url, key = cfg["url"], cfg["key"]
    except (KeyError, FileNotFoundError, st.errors.StreamlitSecretNotFoundError):  # type: ignore[attr-defined]
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError(
            "Faltan credenciales de Supabase. Configura .streamlit/secrets.toml "
            "o las env vars SUPABASE_URL / SUPABASE_KEY."
        )
    return create_client(url, key)


def fetch_all(table: str, select: str = "*", filters: dict[str, Any] | None = None) -> pd.DataFrame:
    """SELECT * paginado. Evita el cap silencioso de 1000 filas de PostgREST."""
    client = get_client()
    rows: list[dict] = []
    start = 0
    while True:
        q = client.table(table).select(select)
        for k, v in (filters or {}).items():
            q = q.eq(k, v)
        resp = q.range(start, start + PAGE_SIZE - 1).execute()
        batch = resp.data or []
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        start += PAGE_SIZE
    return pd.DataFrame(rows)


# PK por tabla — PostgREST exige un filtro en DELETE, así que usamos neq(pk, sentinel)
# para borrar todo. mecanicas usa `numero`, productos `itemid`, combos/ventas `id`.
_PK_FOR_DELETE = {
    "productos": ("itemid", "__never__"),
    "mecanicas": ("numero", -1),
    "combos":    ("id", -1),
    "ventas":    ("id", -1),
}


def replace_table(table: str, rows: list[dict], chunk_size: int = 500) -> int:
    """Borra todo el contenido de la tabla y reinserta `rows`. Devuelve filas escritas."""
    client = get_client()
    pk_col, sentinel = _PK_FOR_DELETE.get(table, ("id", -1))
    client.table(table).delete().neq(pk_col, sentinel).execute()
    if not rows:
        return 0
    n = 0
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i:i + chunk_size]
        client.table(table).insert(chunk).execute()
        n += len(chunk)
    return n


def upsert_rows(table: str, rows: list[dict], on_conflict: str) -> int:
    """Upsert por la(s) columna(s) `on_conflict` (CSV)."""
    if not rows:
        return 0
    client = get_client()
    client.table(table).upsert(rows, on_conflict=on_conflict).execute()
    return len(rows)


def has_connection() -> bool:
    try:
        get_client().table("mecanicas").select("numero").limit(1).execute()
        return True
    except Exception:
        return False
