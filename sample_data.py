"""
Genera Excels de ejemplo (productos + ventas) para probar la app de MegaFeria.
Cubre las 34 mecanicas con productos sembrados y ventas semi-aleatorias.

Uso: `python sample_data.py` -> crea data/ejemplo_productos.xlsx y data/ejemplo_ventas.xlsx
"""
from __future__ import annotations

import os
import random
from datetime import datetime

import pandas as pd

from config import COMBOS, MECANICAS_BY_NUM

OUT_DIR = "data"
os.makedirs(OUT_DIR, exist_ok=True)

import random as _r
_NOMBRES = [
    "ALARCON", "BENAVIDES", "CASTRO", "DIAZ", "ESPINOZA", "FUENTES", "GARCIA",
    "HERRERA", "IBARRA", "JIMENEZ", "KARP", "LOPEZ", "MENDOZA", "NUNEZ",
    "ORTIZ", "PEREZ", "QUIROZ", "RAMIREZ", "SANCHEZ", "TORRES", "URBINA",
    "VEGA", "WONG", "XIMENEZ", "YEPEZ", "ZAMORA", "ALVAREZ", "BRAVO",
    "CORONEL", "DELGADO", "ESCOBAR", "FLORES", "GUERRA", "HIDALGO", "INGA",
    "JARAMILLO", "LARA", "MEDINA", "NAVARRO", "OLIVO", "PARRA", "QUINTERO",
    "RIVERA", "SOLIS", "TAPIA", "ULLAURI", "VACA", "ZAPATA",
]
_INICIALES = list("ABCDEFGHIJKLMNOPRSTUV")
_r.seed(7)

def _gen_asesores_por_regional(min_n=18, max_n=22):
    used = set()
    out = {}
    for reg_idx, reg in enumerate([f"REGIONAL {i}" for i in range(1, 7)], start=1):
        n = _r.randint(min_n, max_n)
        roster = []
        while len(roster) < n:
            ini = _r.choice(_INICIALES)
            ape = _r.choice(_NOMBRES)
            full = f"{ini}. {ape}"
            if full in used:
                continue
            used.add(full)
            roster.append(full)
        out[reg] = sorted(roster)
    return out

ASESORES_POR_REGIONAL = _gen_asesores_por_regional()

# Para cada mecanica que NO sea single_sku/combo/coverage, generamos 3 productos.
# itemid prefix: M{nn}P{x}
PRODUCTOS_GENERADOS: list[tuple[str, str, str, list[int]]] = []
PRICE_HINT = {
    1: 100, 2: 25, 3: 30, 4: 40, 5: 30, 6: 80, 7: 60, 8: 12, 9: 10, 10: 15,
    11: 12, 12: 30, 13: 25, 14: 60, 15: 90, 16: 40, 17: 8, 18: 35, 19: 250,
    20: 120, 25: 20, 26: 70, 27: 30, 28: 75, 29: 30, 30: 40, 31: 90, 32: 70,
    33: 80,
}

for mec_num in range(1, 34):
    m = MECANICAS_BY_NUM[mec_num]
    if m.tipo in {"single_sku", "combo", "coverage"}:
        continue
    fam = m.descripcion.split("—")[0].strip()
    # tres productos por mecanica
    for j in range(1, 4):
        itemid = f"M{mec_num:02d}P{j}"
        PRODUCTOS_GENERADOS.append((itemid, f"{fam} prod {j}", fam, [mec_num]))

# Mecanica 1 (REFOR todas) — ASIGNACION debe incluir el 1 ademas del de cada sub-familia REFOR.
# Sobre los productos REFOR de mecanicas 2..13, agrega tambien la 1 a su asignacion.
sub_refor = {2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13}
NEW: list[tuple[str, str, str, list[int]]] = []
for itemid, desc, fam, asig in PRODUCTOS_GENERADOS:
    if set(asig) & sub_refor:
        asig = sorted(set(asig) | {1})
    NEW.append((itemid, desc, fam, asig))
PRODUCTOS_GENERADOS = NEW

# Single SKU (mec 21, 22, 23)
PRODUCTOS_GENERADOS += [
    ("L46448", "EMTOP FUMIGADORA",    "EMTOP", [21]),
    ("L47611", "EMTOP KIT TAL+AMOL",  "EMTOP", [22]),
    ("L09223", "EMTOP BOMBA 1/2HP",   "EMTOP", [23, 24]),  # 09223 esta en combo 6
]

# Combos (mec 24): todos los itemids unicos
combo_items: set[str] = set()
for codes in COMBOS.values():
    combo_items.update(codes.keys())
for itemid in sorted(combo_items):
    if itemid not in {p[0] for p in PRODUCTOS_GENERADOS}:
        PRODUCTOS_GENERADOS.append((itemid, f"EMTOP {itemid}", "EMTOP", [24]))


def generate_productos() -> pd.DataFrame:
    rows = [
        {"ITEMID": i, "DESCRIPCION": d, "FAMILIA": f, "ASIGNACION": ",".join(map(str, a))}
        for i, d, f, a in PRODUCTOS_GENERADOS
    ]
    return pd.DataFrame(rows)


def generate_ventas(seed: int = 42) -> pd.DataFrame:
    random.seed(seed)
    rows: list[dict] = []
    counter = 100001
    base_date = datetime(2026, 5, 15)
    clientes = [f"CLIENTE {i:03d}" for i in range(1, 41)]
    rucs = {c: f"179{i:07d}001" for i, c in enumerate(clientes)}
    skus_por_mec: dict[int, list[tuple]] = {}
    for p in PRODUCTOS_GENERADOS:
        for mec in p[3]:
            skus_por_mec.setdefault(mec, []).append(p)

    # 1) Ventas que aportan a una mecanica al azar (cubre todas las monetary/unit)
    for regional, asesores in ASESORES_POR_REGIONAL.items():
        for asesor in asesores:
            for mec in range(1, 34):
                m = MECANICAS_BY_NUM[mec]
                if m.tipo in {"single_sku", "combo", "coverage"}:
                    continue
                # Probabilidad de tener ventas en esta mecanica
                if random.random() > 0.85:
                    continue
                n_pedidos = random.randint(1, 3)
                for _ in range(n_pedidos):
                    pedido = f"P{counter:06d}"; counter += 1
                    cliente = random.choice(clientes)
                    candidatos = skus_por_mec.get(mec, [])
                    if not candidatos:
                        continue
                    n_lin = random.randint(1, min(3, len(candidatos)))
                    for p in random.sample(candidatos, n_lin):
                        cant = random.randint(1, 6) if m.tipo == "unit" else random.randint(1, 3)
                        precio = round(PRICE_HINT.get(mec, 50) * random.uniform(0.7, 1.5), 2)
                        desc = round(random.uniform(0, 0.20), 2)
                        venta = round(precio * cant * (1 - desc), 2)
                        rows.append(_row(pedido, base_date, cliente, rucs[cliente],
                                         asesor, regional, p, cant, precio, desc, venta))

    # 2) SKU especifico (mec 21, 22, 23)
    for regional, asesores in ASESORES_POR_REGIONAL.items():
        for asesor in asesores:
            for itemid in ["L46448", "L47611", "L09223"]:
                if random.random() < 0.7:
                    pedido = f"P{counter:06d}"; counter += 1
                    cliente = random.choice(clientes)
                    cant = random.randint(1, 5)
                    p = next(pp for pp in PRODUCTOS_GENERADOS if pp[0] == itemid)
                    precio = round(random.uniform(50, 300), 2)
                    desc = round(random.uniform(0, 0.30), 2)
                    venta = round(precio * cant * (1 - desc), 2)
                    rows.append(_row(pedido, base_date, cliente, rucs[cliente],
                                     asesor, regional, p, cant, precio, desc, venta))

    # 3) Combos completos
    for regional, asesores in ASESORES_POR_REGIONAL.items():
        for asesor in asesores:
            for _ in range(random.randint(0, 2)):
                combo_num = random.choice(list(COMBOS.keys()))
                codes = COMBOS[combo_num]
                pedido = f"P{counter:06d}"; counter += 1
                cliente = random.choice(clientes)
                for itemid, max_desc in codes.items():
                    p = next(pp for pp in PRODUCTOS_GENERADOS if pp[0] == itemid)
                    cant = 1
                    precio = round(random.uniform(80, 400), 2)
                    desc = round(max_desc / 100.0 * random.uniform(0.7, 1.0), 3)
                    venta = round(precio * cant * (1 - desc), 2)
                    rows.append(_row(pedido, base_date, cliente, rucs[cliente],
                                     asesor, regional, p, cant, precio, desc, venta))

    return pd.DataFrame(rows)


def _row(pedido, base_date, cliente, ruc, asesor, regional, prod, cant, precio, desc, venta):
    itemid, descripcion, familia, _ = prod
    return {
        "PEDIDO": pedido,
        "FECHA": base_date,
        "CLIENTE": cliente,
        "RUC": ruc,
        "ASESOR": asesor,
        "REGIONAL": regional,
        "ITEMID": itemid,
        "DESCRIPCION": descripcion,
        "PRECIO AUTORIZADOR": precio,
        "DESCUENTO": desc,
        "CANTIDAD": cant,
        "VENTA_NETA": venta,
    }


def main():
    prod = generate_productos()
    vent = generate_ventas()
    prod_path = os.path.join(OUT_DIR, "ejemplo_productos.xlsx")
    vent_path = os.path.join(OUT_DIR, "ejemplo_ventas.xlsx")
    prod.to_excel(prod_path, index=False)
    vent.to_excel(vent_path, index=False)
    print(f"OK -> {prod_path}  ({len(prod)} productos)")
    print(f"OK -> {vent_path}  ({len(vent)} lineas de venta)")


if __name__ == "__main__":
    main()
