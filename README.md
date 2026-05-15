# MegaFeria 2026 — Tablero de Premios

App Streamlit para registrar, en vivo, los premios ganados por los asesores en los 6 stands regionales durante la feria nacional de Megaprofer.

## Estructura

```
megaferia/
├── app.py            # UI Streamlit (3 tabs + 6 subtabs + ranking ELITE)
├── prizes.py         # Motor de cálculo (monetary/unit/single_sku/combo/coverage)
├── data_io.py        # Lectura/validación de Excels
├── config.py         # 34 mecánicas + 10 combos EMTOP
├── db.py             # Cliente Supabase (con paginación >1000)
├── sample_data.py    # Genera Excels de ejemplo
├── schema.sql        # Esquema para Supabase
├── requirements.txt
├── .streamlit/
│   ├── config.toml
│   └── secrets.toml.example
└── data/             # (generado) excels de ejemplo
```

## Setup local (Windows + Python 3.14)

```powershell
cd C:\Users\diego.rondon\megaferia
python -m venv .venv
.venv\Scripts\activate
pip install --only-binary=:all: -r requirements.txt
python sample_data.py     # genera data/ejemplo_productos.xlsx y data/ejemplo_ventas.xlsx
streamlit run app.py
```

Abre <http://localhost:8501>. Sube los dos Excels de ejemplo y revisa las tres pestañas.

## Setup Supabase (opcional pero recomendado para que persista entre sesiones)

1. Crear proyecto en <https://supabase.com>.
2. Ir a **SQL Editor** y pegar todo el contenido de `schema.sql`. Ejecutar.
3. En **Project Settings → API**, copiar `URL` y `anon public key`.
4. Copiar `.streamlit/secrets.toml.example` a `.streamlit/secrets.toml` y completar.
5. En la app: pestaña **Carga** → botón **Sembrar mecánicas + combos** (una sola vez).

## Despliegue público (Streamlit Cloud — link único)

1. Crear cuenta en <https://share.streamlit.io> con GitHub.
2. Subir esta carpeta a un repo (público o privado).
3. **New app** → seleccionar repo y `app.py`.
4. En **Advanced settings → Secrets**, pegar el contenido de `.streamlit/secrets.toml`.
5. Deploy. Obtienes una URL `https://<nombre>.streamlit.app` — esa es la que mandas a los supervisores.

> Si quieres un subdominio Megaprofer (ej. `feria.megaprofer.com`), después puedes apuntar un CNAME desde Cloudflare al dominio de Streamlit Cloud — pero la URL `*.streamlit.app` ya es pública y suficiente para mañana.

## Mecánicas pendientes de completar

`config.py` tiene encoded:
- ✅ Mecánica 1 (REFOR todas, $800 → EFECTIVO $50 + BUZO)
- ✅ Mecánica 6 (REFOR FREGADEROS, 6 uds → CUPÓN $5)
- ✅ Mecánicas 21, 22, 23 (SKUs específicos EMTOP)
- ✅ Mecánica 24 (10 combos EMTOP, regla: pedido único con todos los códigos a descuento ≤ máximo permitido por código)
- ✅ Mecánica 34 (COBERTURA ELITE, TOP 3 + CAMISETA TRI #1)

Las **demás 28 mecánicas** están como `PENDIENTE` en `config.py`. Editar a mano antes de la feria con los datos del PDF "Mecanicas de premios". Para cada una basta llenar:

```python
Mecanica(2, "DESCRIPCION REAL",
         tipo="monetary",  # o unit / single_sku / combo / coverage
         umbral=500,       # USD o cantidad
         tipo_premio="EFECTIVO",  # o CUPON / OTRO
         valor_premio=25,  # USD que vale un premio (para totales)
         premio_descripcion="EFECTIVO $25",
         skus=[],          # si tipo=single_sku
        )
```

Cualquier cambio se aplica al reiniciar la app (`Ctrl+C` y volver a `streamlit run app.py`).

## Notas de implementación

- **Descuento**: el motor auto-detecta si la columna `DESCUENTO` viene en fracción (0.35) o porcentaje (35) y normaliza a fracción.
- **Combos (mec 24)**: un combo cuenta como 1 cuando un mismo `PEDIDO` contiene **todos** los códigos del combo, cada uno con `DESCUENTO ≤` el máximo permitido. Si el cliente quiere otra regla (p.ej. combos parciales), ajustar `_count_combos_completed` en `prizes.py`.
- **Acumulación cruzada**: una misma línea de venta aporta a todas las mecánicas listadas en `ASIGNACION` del producto (sumando el mismo valor a cada una).
- **Reemplazo de ventas**: cada upload reescribe todo. El catálogo de productos persiste.
