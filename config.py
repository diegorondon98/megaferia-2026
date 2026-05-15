"""
Catalogo de mecanicas (34) y combos EMTOP (10) — MegaFeria 2026.

Tipos de mecanica:
  - 'monetary'   : suma VENTA_NETA de productos con la mecanica en su ASIGNACION.
                   premio = floor(suma / umbral). umbral en USD.
  - 'unit'       : suma CANTIDAD de productos con la mecanica en su ASIGNACION.
                   premio = floor(suma / umbral). umbral en unidades.
  - 'single_sku' : suma CANTIDAD de los SKUs listados en `skus`.
                   premio = floor(suma / umbral).
  - 'combo'      : cuenta cuantas veces se completo el combo `combo_id`.
                   Un combo se completa cuando en UN MISMO PEDIDO aparecen
                   TODOS los itemids del combo, cada uno con DESCUENTO <= max
                   permitido para ese itemid. premio = combos_completados.
  - 'coverage'   : especial (mec 34). Cuenta clientes con suma VENTA_NETA >= 150
                   en productos ELITE (todos los del catalogo). Ranking + TOP 3.

REGLA DE COMBOS (mecanica 24): documentada en el PDF "Combos Emtop".
Asumimos que un combo cuenta UNA vez por pedido cuando los seis (o N) codigos
estan en ese pedido con descuento <= el maximo permitido por codigo. Si
el cliente quiere otra regla (p.ej. permitir multiples combos por pedido si
hay multiples unidades), ajustar `_count_combos_completed` en prizes.py.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Mecanica:
    numero: int
    descripcion: str
    tipo: str  # 'monetary' | 'unit' | 'single_sku' | 'combo' | 'coverage'
    umbral: float
    tipo_premio: str  # 'EFECTIVO' | 'CUPON' | 'OTRO'
    valor_premio: float  # valor $ del premio unitario (sirve para totalizar)
    premio_descripcion: str
    skus: list[str] = field(default_factory=list)
    combo_id: int | None = None
    config: dict[str, Any] = field(default_factory=dict)


# ============================================================
# COMBOS EMTOP (mecanica 24) — del PDF "Combos Emtop"
# Estructura: combo_numero -> { itemid: max_descuento_pct (0..100) }
# ============================================================
COMBOS: dict[int, dict[str, float]] = {
    1: {"L08909": 48, "L13667": 35, "L08910": 35, "L46459": 35, "L09798": 35, "L09826": 35},
    2: {"L08905": 48, "L46578": 35, "L46579": 35, "L46570": 35, "L09017": 35, "L08930": 35},
    3: {"L08907": 40, "L09799": 35, "L46560": 35, "L46561": 35, "L13672": 35, "L09826": 35},
    4: {"L09284": 48, "L09519": 38, "L46578": 38, "L46579": 38, "L09017": 38, "L09215": 38},
    5: {"L11104": 48, "L18680": 38, "L09243": 38, "L09245": 38, "L47583": 38, "L47599": 38},
    6: {"L09223": 45, "L46455": 40, "L09276": 40, "L09282": 40, "L09232": 40},
    7: {"L08921": 45, "L09024": 38, "L46455": 38, "L09826": 38, "L13617": 38},
    8: {"L46263": 45, "L47508": 35, "L08975": 35, "L08980": 35, "L09019": 35},
    9: {"L09017": 42, "L09019": 42, "L09005": 42, "L09214": 42, "L09215": 42, "L08980": 42},
    10: {"L13311": 45, "L46455": 38, "L09546": 38, "L09276": 38},
}


# ============================================================
# 34 MECANICAS
# Las que estan marcadas con `descripcion` "PENDIENTE" deben cargarse desde el
# PDF "Mecanicas de premios" (boton de carga en la app o editar este archivo).
# ============================================================
MECANICAS: list[Mecanica] = [
    # ---------- REFOR ----------
    Mecanica(1,  "REFOR (todas las familias)",
             tipo="monetary", umbral=800, tipo_premio="EFECTIVO", valor_premio=50,
             premio_descripcion="EFECTIVO $50 + BUZO REFOR"),
    Mecanica(2,  "REFOR CONSUMIBLES",
             tipo="monetary", umbral=120, tipo_premio="EFECTIVO", valor_premio=5,
             premio_descripcion="EFECTIVO $5"),
    Mecanica(3,  "REFOR HERRAJES",
             tipo="monetary", umbral=150, tipo_premio="EFECTIVO", valor_premio=5,
             premio_descripcion="EFECTIVO $5"),
    Mecanica(4,  "REFOR ELECTRICO",
             tipo="monetary", umbral=200, tipo_premio="EFECTIVO", valor_premio=5,
             premio_descripcion="EFECTIVO $5"),
    Mecanica(5,  "REFOR SEGURIDAD",
             tipo="monetary", umbral=150, tipo_premio="EFECTIVO", valor_premio=5,
             premio_descripcion="EFECTIVO $5"),
    Mecanica(6,  "REFOR FREGADEROS",
             tipo="unit", umbral=6, tipo_premio="CUPON", valor_premio=5,
             premio_descripcion="CUPON $5"),
    Mecanica(7,  "REFOR UPS",
             tipo="unit", umbral=6, tipo_premio="CUPON", valor_premio=15,
             premio_descripcion="CUPON $15"),
    Mecanica(8,  "REFOR BOTAS",
             tipo="unit", umbral=50, tipo_premio="CUPON", valor_premio=5,
             premio_descripcion="CUPON $5"),
    Mecanica(9,  "REFOR CASCOS",
             tipo="unit", umbral=50, tipo_premio="CUPON", valor_premio=5,
             premio_descripcion="CUPON $5"),
    Mecanica(10, "REFOR PROTECTOR DE VOLTAJE",
             tipo="unit", umbral=120, tipo_premio="CUPON", valor_premio=15,
             premio_descripcion="CUPON $15"),
    Mecanica(11, "REFOR BREAKER",
             tipo="unit", umbral=120, tipo_premio="CUPON", valor_premio=15,
             premio_descripcion="CUPON $15"),
    Mecanica(12, "REFOR INTERRUPTOR Y TOMACORRIENTE",
             tipo="monetary", umbral=200, tipo_premio="CUPON", valor_premio=5,
             premio_descripcion="CUPON $5"),
    Mecanica(13, "REFOR CERRADURA ELECTRICA",
             tipo="unit", umbral=12, tipo_premio="CUPON", valor_premio=5,
             premio_descripcion="CUPON $5"),
    # ---------- EMTOP ----------
    Mecanica(14, "EMTOP INALAMBRICA",
             tipo="monetary", umbral=150, tipo_premio="EFECTIVO", valor_premio=5,
             premio_descripcion="EFECTIVO $5"),
    Mecanica(15, "EMTOP MANUAL",
             tipo="monetary", umbral=300, tipo_premio="EFECTIVO", valor_premio=5,
             premio_descripcion="EFECTIVO $5"),
    Mecanica(16, "EMTOP ACCESORIOS",
             tipo="monetary", umbral=200, tipo_premio="EFECTIVO", valor_premio=5,
             premio_descripcion="EFECTIVO $5"),
    Mecanica(17, "EMTOP DISCOS",
             tipo="unit", umbral=60, tipo_premio="CUPON", valor_premio=5,
             premio_descripcion="CUPON $5"),
    Mecanica(18, "EMTOP BATERIAS",
             tipo="monetary", umbral=150, tipo_premio="EFECTIVO", valor_premio=5,
             premio_descripcion="EFECTIVO $5"),
    Mecanica(19, "EMTOP MOTOCULTOR",
             tipo="unit", umbral=1, tipo_premio="EFECTIVO", valor_premio=15,
             premio_descripcion="EFECTIVO $15"),
    Mecanica(20, "EMTOP COMPRESORES",
             tipo="unit", umbral=6, tipo_premio="CUPON", valor_premio=15,
             premio_descripcion="CUPON $15"),
    Mecanica(21, "EMTOP FUMIGADORA",
             tipo="single_sku", umbral=4, tipo_premio="CUPON", valor_premio=5,
             premio_descripcion="CUPON $5", skus=["L46448"]),
    Mecanica(22, "EMTOP KIT TALADRO + AMOLADORA",
             tipo="single_sku", umbral=1, tipo_premio="EFECTIVO", valor_premio=2,
             premio_descripcion="EFECTIVO $2", skus=["L47611"]),
    Mecanica(23, "EMTOP BOMBA DE AGUA 1/2 HP",
             tipo="single_sku", umbral=1, tipo_premio="EFECTIVO", valor_premio=1,
             premio_descripcion="EFECTIVO $1", skus=["L09223"]),
    Mecanica(24, "EMTOP COMBOS (10 combos)",
             tipo="combo", umbral=1, tipo_premio="EFECTIVO", valor_premio=2,
             premio_descripcion="EFECTIVO $2 por combo",
             config={"combos": list(COMBOS.keys())}),
    # ---------- TRAVEX ----------
    Mecanica(25, "TRAVEX CANDADOS",
             tipo="monetary", umbral=100, tipo_premio="EFECTIVO", valor_premio=5,
             premio_descripcion="EFECTIVO $5"),
    Mecanica(26, "TRAVEX CERRADURAS",
             tipo="monetary", umbral=500, tipo_premio="EFECTIVO", valor_premio=15,
             premio_descripcion="EFECTIVO $15"),
    Mecanica(27, "TRAVEX COMPLEMENTARIAS",
             tipo="monetary", umbral=150, tipo_premio="EFECTIVO", valor_premio=5,
             premio_descripcion="EFECTIVO $5"),
    Mecanica(28, "TRAVEX CERRADURA DE EMBUTIR",
             tipo="unit", umbral=2, tipo_premio="CUPON", valor_premio=15,
             premio_descripcion="CUPON $15"),
    Mecanica(29, "TRAVEX CERRADURA DE MANIJA",
             tipo="unit", umbral=12, tipo_premio="CUPON", valor_premio=5,
             premio_descripcion="CUPON $5"),
    # ---------- PICASSO ----------
    Mecanica(30, "PICASSO",
             tipo="monetary", umbral=200, tipo_premio="EFECTIVO", valor_premio=15,
             premio_descripcion="EFECTIVO $15"),
    # ---------- DHINO LED ----------
    Mecanica(31, "DHINO LED",
             tipo="monetary", umbral=600, tipo_premio="EFECTIVO", valor_premio=30,
             premio_descripcion="EFECTIVO $30"),
    Mecanica(32, "DHINO LED PANELES",
             tipo="monetary", umbral=300, tipo_premio="EFECTIVO", valor_premio=15,
             premio_descripcion="EFECTIVO $15"),
    Mecanica(33, "DHINO LED REFLECTORES",
             tipo="monetary", umbral=300, tipo_premio="EFECTIVO", valor_premio=15,
             premio_descripcion="EFECTIVO $15"),
    # ---------- COBERTURA ELITE ----------
    Mecanica(34, "ASESOR CON MAYOR COBERTURA EN FAMILIAS ELITE",
             tipo="coverage", umbral=150, tipo_premio="OTRO", valor_premio=0,
             premio_descripcion="CAMISETA DE LA TRI (solo #1)",
             config={"top_only": 1, "min_per_client": 150}),
]


MECANICAS_BY_NUM: dict[int, Mecanica] = {m.numero: m for m in MECANICAS}

REGIONALES: list[str] = [f"REGIONAL {i}" for i in range(1, 7)] + ["CALL CENTER"]


def mecanicas_to_rows() -> list[dict]:
    """Para sembrar Supabase: convierte MECANICAS a filas de la tabla `mecanicas`."""
    rows = []
    for m in MECANICAS:
        rows.append({
            "numero": m.numero,
            "descripcion": m.descripcion,
            "tipo": m.tipo,
            "umbral": m.umbral,
            "tipo_premio": m.tipo_premio,
            "valor_premio": m.valor_premio,
            "premio_descripcion": m.premio_descripcion,
            "skus": m.skus,
            "combo_id": m.combo_id,
            "config": m.config,
        })
    return rows


def combos_to_rows() -> list[dict]:
    """Para sembrar Supabase: convierte COMBOS a filas de la tabla `combos`."""
    rows = []
    for combo_num, items in COMBOS.items():
        for itemid, max_desc in items.items():
            rows.append({
                "combo_numero": combo_num,
                "itemid": itemid,
                "max_descuento_pct": max_desc,
            })
    return rows
