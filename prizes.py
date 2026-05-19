"""
Motor de calculo de premios — MegaFeria 2026.

Entrada:
  - ventas:    DataFrame con columnas pedido, fecha, cliente, ruc, asesor,
               regional, itemid, descripcion, precio_autorizador, descuento,
               cantidad, venta_neta
  - productos: DataFrame con columnas itemid, descripcion, familia, asignacion
               (asignacion = list[int] de mecanicas)
  - mecanicas: lista de config.Mecanica
  - combos:    dict[int, dict[itemid, max_desc_pct]] del config.COMBOS

Salida:
  - resumen:   DataFrame largo (asesor, regional, mec_num, ganados, valor_acumulado,
               umbral, faltante, tipo_premio, valor_premio, total_efectivo, total_cupon)
  - lineas:    DataFrame largo (mec_num, asesor, regional, pedido, fecha, cliente,
               ruc, itemid, descripcion, cantidad, venta_neta, descuento, contribucion)
               para drill-down (cada fila de venta puede aparecer en multiples mecanicas).
"""
from __future__ import annotations

import math

import pandas as pd

from config import COMBOS, MECANICAS, Mecanica


def _explode_asignacion(productos: pd.DataFrame) -> pd.DataFrame:
    """productos -> filas (itemid, mecanica) por cada mecanica en asignacion."""
    df = productos[["itemid", "asignacion"]].copy()
    df["asignacion"] = df["asignacion"].apply(lambda x: x if isinstance(x, list) else [])
    df = df.explode("asignacion").dropna(subset=["asignacion"])
    df["asignacion"] = df["asignacion"].astype(int)
    return df.rename(columns={"asignacion": "mec_num"})


def _ventas_con_mecanicas(ventas: pd.DataFrame, productos: pd.DataFrame) -> pd.DataFrame:
    """Cada venta_line se duplica por cada mecanica del producto."""
    map_df = _explode_asignacion(productos)
    return ventas.merge(map_df, on="itemid", how="inner")


def _normalize_descuento(s: pd.Series) -> pd.Series:
    """Si los valores parecen porcentaje (>1), los pasa a fraccion 0..1.

    Asumimos que un valor > 1.0 es porcentaje (35.0 = 35%) y <=1 es fraccion (0.35).
    """
    s = pd.to_numeric(s, errors="coerce").fillna(0)
    looks_pct = (s > 1).mean() > 0.5  # si la mayoria > 1 -> porcentaje
    return s / 100.0 if looks_pct else s


def calcular_premios(
    ventas: pd.DataFrame,
    productos: pd.DataFrame,
    mecanicas: list[Mecanica] | None = None,
    combos: dict[int, dict[str, float]] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Devuelve (resumen, lineas)."""
    if mecanicas is None:
        mecanicas = MECANICAS
    if combos is None:
        combos = COMBOS

    if ventas.empty:
        return _empty_resumen(), _empty_lineas()

    # Normaliza tipos
    v = ventas.copy()
    v["cantidad"] = pd.to_numeric(v["cantidad"], errors="coerce").fillna(0)
    v["venta_neta"] = pd.to_numeric(v["venta_neta"], errors="coerce").fillna(0)
    v["descuento"] = _normalize_descuento(v["descuento"]) if "descuento" in v.columns else 0.0

    # Mapping mec -> ventas que aplican
    ventas_mec = _ventas_con_mecanicas(v, productos)  # mec_num agregado

    resumen_rows: list[dict] = []
    lineas_rows: list[dict] = []

    # asesor -> regional (1:1 esperado, tomamos el mas frecuente).
    # Robusto: si un asesor no tiene ninguna regional válida, cae a "".
    def _top_regional(s: pd.Series) -> str:
        vc = s.value_counts()
        return str(vc.index[0]) if len(vc) else ""

    asesor_regional = (
        v.groupby("asesor")["regional"].agg(_top_regional).to_dict()
    )
    asesores = sorted(v["asesor"].dropna().unique().tolist())

    for m in mecanicas:
        if m.tipo == "monetary":
            sub = ventas_mec[ventas_mec["mec_num"] == m.numero]
            agg = sub.groupby("asesor")["venta_neta"].sum()
            for asesor in asesores:
                total = float(agg.get(asesor, 0.0))
                ganados = int(math.floor(total / m.umbral)) if m.umbral else 0
                faltante = max(m.umbral * (ganados + 1) - total, 0.0)
                resumen_rows.append(_resumen_row(m, asesor, asesor_regional, ganados, total, faltante))
            for _, r in sub.iterrows():
                lineas_rows.append(_linea_row(m, r, contrib=r["venta_neta"]))

        elif m.tipo == "unit":
            sub = ventas_mec[ventas_mec["mec_num"] == m.numero]
            agg = sub.groupby("asesor")["cantidad"].sum()
            for asesor in asesores:
                total = float(agg.get(asesor, 0.0))
                ganados = int(math.floor(total / m.umbral)) if m.umbral else 0
                faltante = max(m.umbral * (ganados + 1) - total, 0.0)
                resumen_rows.append(_resumen_row(m, asesor, asesor_regional, ganados, total, faltante))
            for _, r in sub.iterrows():
                lineas_rows.append(_linea_row(m, r, contrib=r["cantidad"]))

        elif m.tipo == "single_sku":
            sub = v[v["itemid"].isin(m.skus)]
            agg = sub.groupby("asesor")["cantidad"].sum()
            for asesor in asesores:
                total = float(agg.get(asesor, 0.0))
                ganados = int(math.floor(total / m.umbral)) if m.umbral else 0
                faltante = max(m.umbral * (ganados + 1) - total, 0.0)
                resumen_rows.append(_resumen_row(m, asesor, asesor_regional, ganados, total, faltante))
            for _, r in sub.iterrows():
                lineas_rows.append(_linea_row(m, r, contrib=r["cantidad"]))

        elif m.tipo == "combo":
            ganados_por_asesor, combo_lineas = _count_combos_completed(v, combos)
            for asesor in asesores:
                total = float(ganados_por_asesor.get(asesor, 0))
                ganados = int(total)
                faltante = 1.0  # falta 1 combo mas para el siguiente premio
                resumen_rows.append(_resumen_row(m, asesor, asesor_regional, ganados, total, faltante))
            for r in combo_lineas:
                r["mec_num"] = m.numero
                lineas_rows.append(r)

        elif m.tipo == "coverage":
            # Ranking + TOP 1 POR REGIONAL (no global).
            # Cuentan TODAS las ventas de productos que estén cargados en la
            # plantilla de productos (cualquier asignación). Excluye ventas
            # de itemids que no existen en el catálogo.
            min_per_client = float(m.config.get("min_per_client", m.umbral))
            top_only = int(m.config.get("top_only", 1))

            items_catalogo = set(productos["itemid"].astype(str))
            sub_cov = v[v["itemid"].astype(str).isin(items_catalogo)]
            por_cliente = sub_cov.groupby(["regional", "asesor", "cliente"])["venta_neta"].sum().reset_index()
            calificados = por_cliente[por_cliente["venta_neta"] >= min_per_client]
            counts = (calificados.groupby(["regional", "asesor"])["cliente"]
                      .nunique().to_dict())

            # Top por regional + rank por asesor (dentro de su regional)
            top_por_reg: dict[str, set[str]] = {}
            rank_por_asesor: dict[str, int] = {}
            for regional in sorted(set(asesor_regional.values())):
                items = sorted(
                    [(a, counts.get((regional, a), 0)) for a in asesores
                     if asesor_regional.get(a) == regional],
                    key=lambda x: x[1], reverse=True,
                )
                top_set: set[str] = set()
                for a, c in items[:top_only]:
                    if c > 0:
                        top_set.add(a)
                top_por_reg[regional] = top_set
                for i, (a, c) in enumerate(items):
                    rank_por_asesor[a] = (i + 1) if c > 0 else 0

            for asesor in asesores:
                regional = asesor_regional.get(asesor, "")
                total = float(counts.get((regional, asesor), 0))
                ganados = 1 if asesor in top_por_reg.get(regional, set()) else 0
                row = _resumen_row(m, asesor, asesor_regional, ganados, total, float("nan"))
                row["es_coverage"] = True
                row["rank"] = rank_por_asesor.get(asesor, 0)
                resumen_rows.append(row)

            for _, r in calificados.iterrows():
                lineas_rows.append({
                    "mec_num": m.numero,
                    "asesor": r["asesor"],
                    "regional": r["regional"],
                    "cliente": r["cliente"],
                    "venta_neta": r["venta_neta"],
                    "contribucion": r["venta_neta"],
                    "pedido": "(varios)",
                    "fecha": None,
                    "ruc": "",
                    "itemid": "(varios)",
                    "descripcion": "Acumulado cliente",
                    "cantidad": 0,
                    "descuento": 0,
                })

    resumen = pd.DataFrame(resumen_rows)
    lineas = pd.DataFrame(lineas_rows)
    return resumen, lineas


def _resumen_row(
    m: Mecanica,
    asesor: str,
    asesor_regional: dict[str, str],
    ganados: int,
    valor_acumulado: float,
    faltante: float,
) -> dict:
    return {
        "mec_num": m.numero,
        "mec_descripcion": m.descripcion,
        "tipo": m.tipo,
        "umbral": m.umbral,
        "tipo_premio": m.tipo_premio,
        "valor_premio": m.valor_premio,
        "premio_descripcion": m.premio_descripcion,
        "asesor": asesor,
        "regional": asesor_regional.get(asesor, ""),
        "ganados": int(ganados),
        "valor_acumulado": float(valor_acumulado),
        "faltante": float(faltante) if not (isinstance(faltante, float) and math.isnan(faltante)) else None,
        "total_efectivo": ganados * m.valor_premio if m.tipo_premio == "EFECTIVO" else 0,
        "total_cupon": ganados * m.valor_premio if m.tipo_premio == "CUPON" else 0,
        "es_coverage": m.tipo == "coverage",
        "rank": 0,
    }


def _linea_row(m: Mecanica, r, contrib: float) -> dict:
    return {
        "mec_num": m.numero,
        "asesor": r.get("asesor"),
        "regional": r.get("regional"),
        "pedido": r.get("pedido"),
        "fecha": r.get("fecha"),
        "cliente": r.get("cliente"),
        "ruc": r.get("ruc"),
        "itemid": r.get("itemid"),
        "descripcion": r.get("descripcion"),
        "cantidad": r.get("cantidad"),
        "venta_neta": r.get("venta_neta"),
        "descuento": r.get("descuento"),
        "contribucion": float(contrib),
    }


def _count_combos_completed(
    v: pd.DataFrame,
    combos: dict[int, dict[str, float]],
) -> tuple[dict[str, int], list[dict]]:
    """Cuenta cuántos combos completos hay en cada pedido.

    Un combo se "completa" cuando TODOS los itemids requeridos están en el
    pedido con descuento <= max permitido. El número de combos formados es el
    mínimo de las cantidades vendidas (con descuento válido) de los items
    requeridos: si un pedido tiene 2 unidades de cada SKU del combo, cuenta 2.

    Devuelve:
      - dict asesor -> total combos completados
      - lista de lineas (para drill-down)
    """
    ganados: dict[str, int] = {}
    lineas: list[dict] = []
    if v.empty:
        return ganados, lineas

    for combo_num, codes in combos.items():
        items_combo = set(codes.keys())
        cand = v[v["itemid"].isin(items_combo)].copy()
        if cand.empty:
            continue
        cand["_max_desc_frac"] = cand["itemid"].map(lambda c: codes[c] / 100.0)
        cand["_ok_desc"] = cand["descuento"] <= cand["_max_desc_frac"]

        for pedido, sub in cand.groupby("pedido"):
            valid = sub[sub["_ok_desc"]]
            if not items_combo.issubset(set(valid["itemid"])):
                continue
            qty_por_item = valid.groupby("itemid")["cantidad"].sum()
            n_combos = int(qty_por_item.reindex(list(items_combo)).min())
            if n_combos <= 0:
                continue
            asesor = sub["asesor"].iloc[0]
            ganados[asesor] = ganados.get(asesor, 0) + n_combos
            for _, r in sub.iterrows():
                lineas.append({
                    "asesor": r["asesor"],
                    "regional": r["regional"],
                    "pedido": r["pedido"],
                    "fecha": r.get("fecha"),
                    "cliente": r["cliente"],
                    "ruc": r["ruc"],
                    "itemid": r["itemid"],
                    "descripcion": r.get("descripcion"),
                    "cantidad": r["cantidad"],
                    "venta_neta": r["venta_neta"],
                    "descuento": r["descuento"],
                    "contribucion": float(n_combos) / max(len(items_combo), 1),
                    "combo_num": combo_num,
                    "combos_en_pedido": n_combos,
                })
    return ganados, lineas


def _empty_resumen() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "mec_num", "mec_descripcion", "tipo", "umbral", "tipo_premio",
        "valor_premio", "premio_descripcion", "asesor", "regional", "ganados",
        "valor_acumulado", "faltante", "total_efectivo", "total_cupon",
        "es_coverage", "rank",
    ])


def _empty_lineas() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "mec_num", "asesor", "regional", "pedido", "fecha", "cliente", "ruc",
        "itemid", "descripcion", "cantidad", "venta_neta", "descuento",
        "contribucion",
    ])


def totales_por_tipo(resumen: pd.DataFrame) -> pd.DataFrame:
    """Tabla pivote: filas = asesor, columnas = EFECTIVO/CUPON, valores = $ total."""
    if resumen.empty:
        return pd.DataFrame()
    g = resumen.groupby(["regional", "asesor"]).agg(
        total_efectivo=("total_efectivo", "sum"),
        total_cupon=("total_cupon", "sum"),
    ).reset_index()
    g["total_general"] = g["total_efectivo"] + g["total_cupon"]
    return g.sort_values(["regional", "total_general"], ascending=[True, False])
