"""
Lectura/validacion de Excels de la feria.

  - Ventas: PEDIDO | FECHA | CLIENTE | RUC | ASESOR | REGIONAL | CODIGO/ITEMID |
            DESCRIPCION | PRECIO AUTORIZADOR | DESCUENTO | CANTIDAD | VENTA_NETA
  - Productos: ITEMID/CODIGO | DESCRIPCION | FAMILIA | ASIGNACION
"""
from __future__ import annotations

import io
import re

import pandas as pd

# Mapas de aliases -> nombre canonico (snake_case)
VENTAS_ALIASES = {
    "pedido": "pedido",
    "fecha": "fecha",
    "cliente": "cliente",
    "ruc": "ruc",
    "asesor": "asesor",
    "regional": "regional",
    "codigo": "itemid",
    "itemid": "itemid",
    "item id": "itemid",
    "descripcion": "descripcion",
    "descripción": "descripcion",
    "precio autorizador": "precio_autorizador",
    "precio_autorizador": "precio_autorizador",
    "descuento": "descuento",
    "cantidad": "cantidad",
    "venta_neta": "venta_neta",
    "venta neta": "venta_neta",
    "venta": "venta_neta",
}

PRODUCTOS_ALIASES = {
    "codigo": "itemid",
    "código": "itemid",
    "itemid": "itemid",
    "item id": "itemid",
    "descripcion": "descripcion",
    "descripción": "descripcion",
    "familia": "familia",
    "asignacion": "asignacion",
    "asignación": "asignacion",
}


def _normalize_cols(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    df = df.copy()
    norm = {c: mapping.get(str(c).strip().lower(), str(c).strip().lower()) for c in df.columns}
    return df.rename(columns=norm)


def _pad_zero(x) -> str:
    """Normaliza RUC/itemid que Excel comio ceros a la izquierda.
    Si parece numerico, lo deja como string. No agrega ceros automaticos para itemid
    (los itemids reales tienen prefijo de letra)."""
    if pd.isna(x):
        return ""
    if isinstance(x, float) and x.is_integer():
        return str(int(x))
    return str(x).strip()


def parse_asignacion(val) -> list[int]:
    """Convierte '1, 5, 9' o '1; 5; 9' o 27 -> [1,5,9] o [27]."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return []
    if isinstance(val, list):
        return [int(x) for x in val if str(x).strip().isdigit()]
    s = str(val).strip()
    if not s:
        return []
    parts = re.split(r"[,;\s/|]+", s)
    out = []
    for p in parts:
        p = p.strip()
        if p.isdigit():
            out.append(int(p))
    return out


def read_ventas_excel(file) -> pd.DataFrame:
    """Lee Excel de ventas y devuelve DataFrame normalizado.
    Levanta ValueError con la lista de columnas faltantes si la estructura no es valida.
    """
    df = pd.read_excel(file, dtype={"RUC": str, "CODIGO": str, "ITEMID": str, "PEDIDO": str})
    df = _normalize_cols(df, VENTAS_ALIASES)
    required = {"pedido", "asesor", "regional", "itemid", "cantidad", "venta_neta"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Columnas faltantes en Ventas: {sorted(missing)}")

    df["pedido"] = df["pedido"].apply(_pad_zero)
    df["itemid"] = df["itemid"].apply(_pad_zero)
    df["ruc"] = df.get("ruc", "").apply(_pad_zero) if "ruc" in df.columns else ""
    df["asesor"] = df["asesor"].astype(str).str.strip()
    df["regional"] = df["regional"].astype(str).str.strip().str.upper()
    df["cliente"] = df.get("cliente", "").astype(str).str.strip() if "cliente" in df.columns else ""
    df["descripcion"] = df.get("descripcion", "").astype(str) if "descripcion" in df.columns else ""
    df["fecha"] = pd.to_datetime(df.get("fecha"), errors="coerce") if "fecha" in df.columns else pd.NaT
    df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce").fillna(0)
    df["venta_neta"] = pd.to_numeric(df["venta_neta"], errors="coerce").fillna(0)
    df["descuento"] = pd.to_numeric(df.get("descuento", 0), errors="coerce").fillna(0)
    df["precio_autorizador"] = pd.to_numeric(df.get("precio_autorizador", 0), errors="coerce").fillna(0)
    return df[[
        "pedido", "fecha", "cliente", "ruc", "asesor", "regional",
        "itemid", "descripcion", "precio_autorizador", "descuento",
        "cantidad", "venta_neta",
    ]]


def read_productos_excel(file) -> pd.DataFrame:
    """Lee Excel de clasificacion de productos."""
    df = pd.read_excel(file, dtype={"CODIGO": str, "ITEMID": str})
    df = _normalize_cols(df, PRODUCTOS_ALIASES)
    if "itemid" not in df.columns:
        raise ValueError("Columna ITEMID/CODIGO faltante en productos")
    df["itemid"] = df["itemid"].apply(_pad_zero)
    df["descripcion"] = df.get("descripcion", "").astype(str)
    df["familia"] = df.get("familia", "").astype(str)
    df["asignacion"] = df.get("asignacion", "").apply(parse_asignacion)
    return df[["itemid", "descripcion", "familia", "asignacion"]]


def ventas_to_rows(df: pd.DataFrame) -> list[dict]:
    """Convierte DataFrame de ventas a filas para insertar en Supabase."""
    out = df.copy()
    out["fecha"] = out["fecha"].dt.strftime("%Y-%m-%d").where(out["fecha"].notna(), None)
    return out.to_dict("records")


def productos_to_rows(df: pd.DataFrame) -> list[dict]:
    return df.to_dict("records")
