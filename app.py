"""
MegaFeria 2026 — App principal (Streamlit).

Tabs:
  1) Carga
  2) Premios:
       subtabs: REGIONAL 1..6 | Todas | Resumen por mecanica | Totales | Ranking ELITE
  3) Pedidos
"""
from __future__ import annotations

import io
import math

import pandas as pd
import streamlit as st

import data_io
import db
import prizes
from config import MECANICAS, MECANICAS_BY_NUM, REGIONALES, combos_to_rows, mecanicas_to_rows


# ============================================================
# CONFIG GENERAL
# ============================================================
st.set_page_config(
    page_title="MegaFeria 2026 — Premios",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# ESTADO GLOBAL
# ============================================================
def _init_state():
    ss = st.session_state
    ss.setdefault("ventas", pd.DataFrame())
    ss.setdefault("productos", pd.DataFrame())
    ss.setdefault("resumen", pd.DataFrame())
    ss.setdefault("lineas", pd.DataFrame())
    ss.setdefault("filter_pedido", "")


def _supabase_available() -> bool:
    try:
        return db.has_connection()
    except Exception:
        return False


def _load_from_supabase() -> bool:
    try:
        v = db.fetch_all("ventas")
        p = db.fetch_all("productos")
        st.session_state.ventas = v
        st.session_state.productos = p
        _recompute()
        return True
    except Exception as exc:
        st.warning(f"No se pudo leer Supabase: {exc}")
        return False


def _recompute():
    v = st.session_state.ventas
    p = st.session_state.productos
    if v.empty or p.empty:
        st.session_state.resumen = pd.DataFrame()
        st.session_state.lineas = pd.DataFrame()
        return
    resumen, lineas = prizes.calcular_premios(v, p)
    st.session_state.resumen = resumen
    st.session_state.lineas = lineas


# ============================================================
# FORMATEADORES
# ============================================================
def _meta_str(m) -> str:
    """Texto humano de cuanto debe vender por premio."""
    if m.tipo == "monetary":
        return f"${m.umbral:,.0f}"
    if m.tipo in {"unit", "single_sku"}:
        return f"{int(m.umbral)} UND"
    if m.tipo == "combo":
        return "1 combo"
    if m.tipo == "coverage":
        return f"${m.umbral:,.0f}/cliente"
    return str(m.umbral)


def _premio_short(m) -> str:
    """Etiqueta compacta del premio."""
    if m.tipo_premio == "EFECTIVO":
        if m.numero == 1:
            return f"💵 ${m.valor_premio:.0f} + BUZO"
        return f"💵 ${m.valor_premio:.0f}"
    if m.tipo_premio == "CUPON":
        return f"🎟️ ${m.valor_premio:.0f}"
    if m.numero == 34:
        return "👕 CAMISETA TRI"
    return m.premio_descripcion


def _mec_label_short(m) -> str:
    desc = m.descripcion
    if len(desc) > 38:
        desc = desc[:36] + "…"
    return f"#{m.numero} — {desc}"


def _short_name(name) -> str:
    """Primer nombre + primer apellido en Title Case, conserva la inicial 'B.'.

    Por qué: el Excel viene en MAYÚSCULA y con nombre completo; en la UI queremos
    'B. Olivo' / 'Pedro Alarcon' (legible y compacto). El valor original se preserva
    para joins/lookups — esto es solo para mostrar.

    Heurística para 4+ tokens (convención LatAm 'Nombre1 Nombre2 Apellido1 Apellido2'):
    toma token 0 + token 2 para obtener 'Nombre1 Apellido1'.
    """
    if not name:
        return ""
    tokens = str(name).strip().split()
    if not tokens:
        return ""
    if len(tokens) == 1:
        return tokens[0].title()
    surname_idx = 2 if len(tokens) >= 4 else 1
    return f"{tokens[0].title()} {tokens[surname_idx].title()}"


def _fmt_ganado(row) -> str:
    """Para una fila de resumen, devuelve '$XX' segun ganados * valor_premio."""
    g = int(row["ganados"])
    if row["tipo"] == "coverage":
        # Cobertura: muestra # clientes calificados y 🥇 si gana
        clientes = int(row["valor_acumulado"])
        if g > 0:
            return f"🥇 {clientes} clientes"
        return f"{clientes} clientes" if clientes > 0 else "—"
    if g == 0:
        return "—"
    valor = g * float(row["valor_premio"])
    prefix = "💵" if row["tipo_premio"] == "EFECTIVO" else "🎟️"
    return f"{prefix} ${valor:,.0f}  ({g}x)"


def _fmt_falta(row) -> str:
    if row["tipo"] == "coverage":
        rank = int(row.get("rank") or 0)
        return f"#{rank} en regional" if rank else "—"
    faltante = row.get("faltante")
    if faltante is None or (isinstance(faltante, float) and math.isnan(faltante)):
        return "—"
    if row["tipo"] == "monetary":
        return f"${float(faltante):,.2f}"
    if row["tipo"] in {"unit", "single_sku"}:
        return f"{float(faltante):.0f} und"
    if row["tipo"] == "combo":
        return "1 combo"
    return f"{float(faltante):,.2f}"


# ============================================================
# HEADER
# ============================================================
def header():
    col1, col2, col3 = st.columns([5, 2, 2])
    with col1:
        st.title("🏆 MegaFeria 2026 — Tablero de Premios")
        st.caption("Carga ventas, ve premios por asesor, audita pedido por pedido.")
    with col2:
        n_v = len(st.session_state.ventas)
        n_p = len(st.session_state.productos)
        st.metric("Ventas cargadas", f"{n_v:,}")
        st.caption(f"{n_p:,} productos en catalogo")
    with col3:
        if _supabase_available():
            st.success("Supabase ✓", icon="✅")
        else:
            st.info("Solo memoria (sin Supabase)", icon="💾")
        if st.button("🔄 Recargar de Supabase"):
            _load_from_supabase()
            st.rerun()


# ============================================================
# TAB 1 — CARGA
# ============================================================
def tab_carga():
    st.subheader("📥 Carga de datos")

    with st.expander("ℹ️ Formato esperado", expanded=False):
        st.markdown("""
        **Ventas** (Excel): columnas
        `PEDIDO | FECHA | CLIENTE | RUC | ASESOR | REGIONAL | ITEMID | DESCRIPCION | PRECIO AUTORIZADOR | DESCUENTO | CANTIDAD | VENTA_NETA`
        - `REGIONAL` debe ser `REGIONAL 1` ... `REGIONAL 6`
        - `DESCUENTO` en fraccion (0.35) o porcentaje (35) — se autodetecta
        - **Cada carga REEMPLAZA todas las ventas anteriores**

        **Productos** (Excel): `ITEMID | DESCRIPCION | FAMILIA | ASIGNACION`
        """)

    pwd_ok = _gate_password()

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 📦 Productos (catalogo)")
        prod_file = st.file_uploader("Subir Excel de productos", type=["xlsx"], key="up_prod")
        if prod_file and pwd_ok:
            try:
                df = data_io.read_productos_excel(prod_file)
                st.session_state.productos = df
                st.success(f"Cargados {len(df):,} productos.")
                if _supabase_available():
                    if st.button("☁️ Guardar productos en Supabase"):
                        rows = data_io.productos_to_rows(df)
                        db.replace_table("productos", rows)
                        st.success("Productos guardados.")
            except Exception as exc:
                st.error(f"Error: {exc}")

    with col2:
        st.markdown("### 🧾 Ventas (reemplaza)")
        vent_file = st.file_uploader("Subir Excel de ventas", type=["xlsx"], key="up_vent")
        if vent_file and pwd_ok:
            try:
                df = data_io.read_ventas_excel(vent_file)
                st.session_state.ventas = df
                st.success(f"Cargadas {len(df):,} lineas.")
                _recompute()
                if _supabase_available():
                    if st.button("☁️ Guardar ventas en Supabase (REEMPLAZA)"):
                        rows = data_io.ventas_to_rows(df)
                        db.replace_table("ventas", rows)
                        st.success("Ventas reemplazadas.")
            except Exception as exc:
                st.error(f"Error: {exc}")

    st.divider()
    if _supabase_available():
        st.markdown("### ⚙️ Sembrar catalogos en Supabase (1 sola vez)")
        if st.button("Sembrar mecanicas + combos"):
            with st.spinner("Sembrando..."):
                db.replace_table("mecanicas", mecanicas_to_rows())
                db.replace_table("combos", combos_to_rows())
            st.success("Listo. 34 mecanicas + 10 combos cargados.")


def _gate_password() -> bool:
    try:
        expected = st.secrets["admin"]["upload_password"]
    except Exception:
        return True
    pwd = st.text_input("🔒 Password de admin", type="password")
    if pwd and pwd == expected:
        return True
    if pwd:
        st.error("Password incorrecto.")
    return False


# ============================================================
# TAB 2 — PREMIOS
# ============================================================
def tab_premios():
    resumen = st.session_state.resumen
    if resumen.empty:
        st.info("Carga ventas + productos en la pestania **Carga**.")
        return

    sub_tabs = st.tabs([
        *REGIONALES,
        "🌎 Todas",
        "📋 Resumen por mecanica",
        "📊 Totales",
        "🏆 Ranking ELITE",
    ])

    for i, regional in enumerate(REGIONALES):
        with sub_tabs[i]:
            _render_tabla_premios(resumen, [regional], title=regional)

    with sub_tabs[len(REGIONALES)]:
        _render_tabla_premios(resumen, REGIONALES, title="Todas las regionales")

    with sub_tabs[len(REGIONALES) + 1]:
        _render_resumen_mecanicas(resumen)

    with sub_tabs[len(REGIONALES) + 2]:
        _render_totales_por_tipo(resumen)

    with sub_tabs[len(REGIONALES) + 3]:
        _render_ranking_elite(resumen)


def _render_tabla_premios(resumen: pd.DataFrame, regionales: list[str], title: str):
    """Pivot sortable: subtotales (4 filas) + 34 mecanicas, 2 cols por asesor (G/F)."""
    sub = resumen[resumen["regional"].isin(regionales)]
    if sub.empty:
        st.info(f"Sin ventas en {title}.")
        return

    asesor_reg = dict(zip(sub["asesor"], sub["regional"]))
    asesores = (
        sub[["regional", "asesor"]]
        .drop_duplicates()
        .sort_values(["regional", "asesor"])
        ["asesor"].tolist()
    )

    # ----- subtotales por asesor -----
    def _sub_per_asesor(filter_fn):
        out = {}
        for a in asesores:
            sa = sub[(sub["asesor"] == a) & filter_fn(sub)]
            out[a] = float((sa["ganados"] * sa["valor_premio"]).sum())
        return out

    tot_efectivo = _sub_per_asesor(lambda d: d["tipo_premio"] == "EFECTIVO")
    tot_cupon5   = _sub_per_asesor(lambda d: (d["tipo_premio"] == "CUPON") & (d["valor_premio"] == 5))
    tot_cupon15  = _sub_per_asesor(lambda d: (d["tipo_premio"] == "CUPON") & (d["valor_premio"] == 15))
    tot_general  = {a: tot_efectivo[a] + tot_cupon5[a] + tot_cupon15[a] for a in asesores}

    FALTA = "·⏳"  # sufijo interno único para la columna de "falta"

    # ----- pivot DataFrame: filas = subtotales + mecanicas, columnas = G/F por asesor -----
    rows = []
    for label, data in [
        ("💵 TOTAL EFECTIVO",  tot_efectivo),
        ("🎟️ TOTAL CUPÓN $5",  tot_cupon5),
        ("🎟️ TOTAL CUPÓN $15", tot_cupon15),
        ("Σ TOTAL GENERAL",    tot_general),
    ]:
        row = {"Mecánica": label, "Meta": "", "Premio": ""}
        for a in asesores:
            v = data[a]
            row[a] = f"${v:,.0f}" if v else "—"
            row[a + FALTA] = ""
        rows.append(row)

    for m in MECANICAS:
        row = {
            "Mecánica": _mec_label_short(m),
            "Meta":     _meta_str(m),
            "Premio":   _premio_short(m),
        }
        for a in asesores:
            r = sub[(sub["mec_num"] == m.numero) & (sub["asesor"] == a)]
            if r.empty:
                row[a] = "—"
                row[a + FALTA] = "—"
                continue
            r0 = r.iloc[0]
            if m.tipo == "coverage":
                clientes = int(r0["valor_acumulado"])
                ganados  = int(r0["ganados"])
                rank     = int(r0.get("rank") or 0)
                if ganados > 0:
                    row[a] = f"🥇 {clientes}c"
                    row[a + FALTA] = "✓"
                elif clientes > 0:
                    row[a] = f"{clientes}c"
                    row[a + FALTA] = f"#{rank}" if rank else "—"
                else:
                    row[a] = "—"
                    row[a + FALTA] = "—"
            else:
                ganados = int(r0["ganados"])
                if ganados > 0:
                    icon = "💵" if r0["tipo_premio"] == "EFECTIVO" else "🎟️"
                    row[a] = f"{icon} ${ganados * float(r0['valor_premio']):,.0f}"
                    row[a + FALTA] = _fmt_falta(r0)
                else:
                    row[a] = "—"
                    row[a + FALTA] = _fmt_falta(r0)
        rows.append(row)

    df_pivot = pd.DataFrame(rows)

    # ----- Estilo: colores en celdas ganadoras + filas de subtotal -----
    def _cell_style(val):
        s = "" if val is None else str(val)
        if s.startswith("🥇"):
            return "background-color:#fde68a;color:#78350f;font-weight:700"
        if s.startswith("💵"):
            return "background-color:#dcfce7;color:#065f46;font-weight:600"
        if s.startswith("🎟️"):
            return "background-color:#fef3c7;color:#854d0e;font-weight:600"
        if s == "✓":
            return "background-color:#dcfce7;color:#065f46;font-weight:700;text-align:center"
        if s == "—":
            return "color:#9ca3af"
        return ""

    def _row_style(row):
        label = str(row["Mecánica"])
        if "Σ TOTAL GENERAL" in label:
            return ["background-color:#312e81;color:#fff;font-weight:700"] * len(row)
        if "TOTAL EFECTIVO" in label:
            return ["background-color:#1e3a8a;color:#fff;font-weight:700"] * len(row)
        if "TOTAL CUPÓN" in label:
            return ["background-color:#3730a3;color:#fff;font-weight:700"] * len(row)
        if label.startswith("#34"):
            return ["background-color:#fffbeb"] * len(row)
        return [""] * len(row)

    styled = df_pivot.style.map(_cell_style).apply(_row_style, axis=1)

    # ----- column_config: orden + anchos + labels cortos para la columna Falta -----
    column_order = ["Mecánica", "Meta", "Premio"]
    col_cfg = {
        "Mecánica": st.column_config.TextColumn(width=210, pinned=True),
        "Meta":     st.column_config.TextColumn(width=70,  pinned=True),
        "Premio":   st.column_config.TextColumn(width=125, pinned=True),
    }
    for a in asesores:
        column_order.append(a)
        column_order.append(a + FALTA)
        col_cfg[a] = st.column_config.TextColumn(
            label=_short_name(a), width=85,
            help=f"{a} · {asesor_reg.get(a, '?')} · Premio ganado",
        )
        col_cfg[a + FALTA] = st.column_config.TextColumn(
            label="⏳", width=55,
            help=f"Cuánto falta a {_short_name(a)} para el siguiente premio",
        )

    st.markdown(
        f"**{title}** · {len(asesores)} asesores · "
        "<span style='color:#6b7280;font-size:0.85em'>"
        "Subtotales arriba · 💵 EFECTIVO · 🎟️ CUPÓN · 🥇 TOP ELITE · ⏳ falta para próximo premio · click cabecera para ordenar"
        "</span>",
        unsafe_allow_html=True,
    )

    st.dataframe(
        styled,
        hide_index=True,
        height=min(len(rows) * 24 + 55, 1100),
        row_height=24,
        column_order=column_order,
        column_config=col_cfg,
        use_container_width=False,
    )

    # ----- Botón de descarga: asesores en FILAS, totales en COLUMNAS -----
    dl_rows = []
    for a in asesores:
        dl: dict = {"REGIONAL": asesor_reg.get(a, ""), "ASESOR": _short_name(a)}
        for m in MECANICAS:
            r = sub[(sub["mec_num"] == m.numero) & (sub["asesor"] == a)]
            if r.empty:
                val = 0.0
            else:
                r0 = r.iloc[0]
                if m.tipo == "coverage":
                    val = float(r0["valor_acumulado"])
                else:
                    val = float(r0["ganados"] * r0["valor_premio"])
            dl[f"Mec {m.numero:02d}"] = val
        dl["TOTAL EFECTIVO"]   = tot_efectivo[a]
        dl["TOTAL CUPON $5"]   = tot_cupon5[a]
        dl["TOTAL CUPON $15"]  = tot_cupon15[a]
        dl["TOTAL GENERAL"]    = tot_general[a]
        dl_rows.append(dl)

    df_dl = pd.DataFrame(dl_rows)
    buf = io.BytesIO()
    df_dl.to_excel(buf, index=False, engine="openpyxl")
    safe_name = title.lower().replace(" ", "_").replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    st.download_button(
        f"⬇️ Descargar Excel — asesores × totales ({title})",
        data=buf.getvalue(),
        file_name=f"premios_{safe_name}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"dl_{title}",
    )

    # ----- Drill-down -----
    st.markdown("#### 🔍 Drill-down: ver pedidos que aportan a un premio")
    c1, c2, c3 = st.columns([3, 2, 1])
    with c1:
        mec_opts = [m.numero for m in MECANICAS]
        mec_sel = st.selectbox(
            "Mecánica",
            mec_opts,
            format_func=lambda x: f"#{x} — {MECANICAS_BY_NUM[x].descripcion[:60]}",
            key=f"drill_mec_{title}",
        )
    with c2:
        asesor_sel = st.selectbox(
            "Asesor", asesores, format_func=_short_name,
            key=f"drill_asesor_{title}",
        )
    with c3:
        st.write(""); st.write("")
        ir = st.button("Ver pedidos →", key=f"go_{title}")
    if ir or st.session_state.get(f"drill_open_{title}"):
        st.session_state[f"drill_open_{title}"] = True
        _render_drilldown(mec_sel, asesor_sel)


def _render_drilldown(mec_num: int, asesor: str):
    lineas = st.session_state.lineas
    if lineas.empty:
        st.info("Sin lineas para mostrar.")
        return
    sub = lineas[(lineas["mec_num"] == mec_num) & (lineas["asesor"] == asesor)]
    if sub.empty:
        st.info("Este asesor no aporta a esta mecanica todavia.")
        return
    m = MECANICAS_BY_NUM[mec_num]
    if m.tipo == "monetary":
        st.metric("Acumulado $", f"${sub['contribucion'].sum():,.2f}")
    elif m.tipo in {"unit", "single_sku"}:
        st.metric("Unidades", f"{sub['contribucion'].sum():,.0f}")
    elif m.tipo == "combo":
        st.metric("Lineas de combo", f"{len(sub):,}")
    cols_show = ["pedido", "fecha", "cliente", "ruc", "itemid", "descripcion",
                 "cantidad", "descuento", "venta_neta", "contribucion"]
    cols_show = [c for c in cols_show if c in sub.columns]
    st.dataframe(
        sub[cols_show].sort_values("pedido"),
        use_container_width=True,
        height=320,
        column_config={
            "descuento": st.column_config.NumberColumn(format="percent"),
            "venta_neta": st.column_config.NumberColumn(format="$%.2f"),
            "contribucion": st.column_config.NumberColumn(format="%.2f"),
        },
    )
    if st.button("Ver estos pedidos en la pestania de Pedidos →", key=f"jump_{mec_num}_{asesor}"):
        pedidos = sorted(sub["pedido"].dropna().unique().tolist())
        st.session_state.filter_pedido = ",".join([p for p in pedidos if p != "(varios)"])
        st.toast("Filtros aplicados — abre la pestania **Pedidos**.", icon="🔎")


def _render_resumen_mecanicas(resumen: pd.DataFrame):
    """Tabla resumen: una fila por mecanica con totales agregados."""
    rows = []
    for m in MECANICAS:
        sub = resumen[resumen["mec_num"] == m.numero]
        if sub.empty:
            continue
        total_acum = sub["valor_acumulado"].sum() if m.tipo != "coverage" else sub["valor_acumulado"].max()
        n_asesores_ganando = int((sub["ganados"] > 0).sum())
        total_premios = int(sub["ganados"].sum())
        valor_total = float((sub["ganados"] * sub["valor_premio"]).sum())
        if m.tipo == "monetary":
            total_str = f"${total_acum:,.2f}"
        elif m.tipo in {"unit", "single_sku", "combo"}:
            total_str = f"{total_acum:,.0f} und"
        elif m.tipo == "coverage":
            total_str = f"{int(total_acum):,} clientes calificados"
        else:
            total_str = f"{total_acum:,.2f}"
        rows.append({
            "Mec.": _mec_label_short(m),
            "Tipo": m.tipo,
            "Meta": _meta_str(m),
            "Premio": _premio_short(m),
            "Total acumulado (todos los asesores)": total_str,
            "# Asesores ganando": n_asesores_ganando,
            "# Premios totales": total_premios,
            "Valor total $ entregado": f"${valor_total:,.0f}",
        })
    df = pd.DataFrame(rows)
    st.markdown("### 📋 Resumen agregado por mecánica")
    st.caption("Cada fila resume cómo va una mecánica considerando TODOS los asesores de todas las regionales.")
    st.dataframe(df, use_container_width=True, hide_index=True, height=min(40 * len(df) + 50, 1400))


def _render_totales_por_tipo(resumen: pd.DataFrame):
    if resumen.empty:
        st.info("Sin datos.")
        return
    pivot = prizes.totales_por_tipo(resumen)
    st.markdown("### Totales por asesor (EFECTIVO vs CUPON)")
    st.dataframe(
        pivot.style.format({
            "total_efectivo": "${:,.2f}",
            "total_cupon": "${:,.2f}",
            "total_general": "${:,.2f}",
        }),
        use_container_width=True,
        height=600,
        hide_index=True,
    )
    c1, c2, c3 = st.columns(3)
    c1.metric("💵 Total EFECTIVO", f"${pivot['total_efectivo'].sum():,.2f}")
    c2.metric("🎟️ Total CUPON",    f"${pivot['total_cupon'].sum():,.2f}")
    c3.metric("Σ Total",            f"${pivot['total_general'].sum():,.2f}")


def _render_ranking_elite(resumen: pd.DataFrame):
    cov = resumen[resumen["es_coverage"] == True]  # noqa: E712
    if cov.empty:
        st.info("Sin datos de cobertura ELITE.")
        return

    st.markdown("### 🏆 Ranking COBERTURA ELITE — mecánica #34")
    st.caption("El #1 de **cada regional** gana CAMISETA TRI. Tabla por regional + ranking global de referencia.")

    # Por regional (con TOP1)
    cols = st.columns(2)
    for i, regional in enumerate(REGIONALES):
        with cols[i % 2]:
            sub = cov[cov["regional"] == regional].copy()
            if sub.empty:
                continue
            sub = sub.sort_values("valor_acumulado", ascending=False).reset_index(drop=True)
            sub["posicion"] = sub.index + 1
            sub["🏅"] = sub["posicion"].map({1: "🥇", 2: "🥈", 3: "🥉"}).fillna("")
            sub["Gana camiseta"] = sub["ganados"].map({1: "✅ SÍ", 0: ""})
            sub["asesor"] = sub["asesor"].map(_short_name)
            show = sub[["🏅", "posicion", "asesor", "valor_acumulado", "Gana camiseta"]].rename(
                columns={"valor_acumulado": "Clientes ≥ $150"}
            )
            st.markdown(f"#### {regional}")
            def color_top(row):
                colors = {1: "#fde68a", 2: "#d1d5db", 3: "#fdba74"}
                c = colors.get(row["posicion"], "")
                return [f"background-color:{c}" if c else "" for _ in row]
            st.dataframe(
                show.style.apply(color_top, axis=1).format({"Clientes ≥ $150": "{:.0f}"}),
                use_container_width=True, hide_index=True,
            )


# ============================================================
# TAB 3 — PEDIDOS
# ============================================================
def tab_pedidos():
    v = st.session_state.ventas
    if v.empty:
        st.info("Sin ventas cargadas.")
        return

    st.subheader("🧾 Detalle de pedidos")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        regional = st.multiselect("Regional", REGIONALES)
    with c2:
        asesor = st.multiselect("Asesor", sorted(v["asesor"].dropna().unique()))
    with c3:
        cliente = st.text_input("Cliente contiene", "")
    with c4:
        pedido = st.text_input("Pedido(s) — CSV", value=st.session_state.filter_pedido)

    df = v.copy()
    if regional:
        df = df[df["regional"].isin(regional)]
    if asesor:
        df = df[df["asesor"].isin(asesor)]
    if cliente:
        df = df[df["cliente"].str.contains(cliente, case=False, na=False)]
    if pedido:
        pedidos = {p.strip() for p in pedido.split(",") if p.strip()}
        df = df[df["pedido"].isin(pedidos)]

    if st.button("🧹 Limpiar filtros"):
        st.session_state.filter_pedido = ""
        st.rerun()

    st.caption(f"{len(df):,} lineas | {df['pedido'].nunique():,} pedidos | ${df['venta_neta'].sum():,.2f}")

    st.dataframe(
        df.sort_values(["fecha", "pedido", "itemid"], na_position="last"),
        use_container_width=True,
        height=600,
        column_config={
            "fecha": st.column_config.DateColumn(format="YYYY-MM-DD"),
            "descuento": st.column_config.NumberColumn(format="percent"),
            "venta_neta": st.column_config.NumberColumn(format="$%.2f"),
            "precio_autorizador": st.column_config.NumberColumn(format="$%.2f"),
            "cantidad": st.column_config.NumberColumn(format="%.0f"),
        },
    )

    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    st.download_button("⬇️ Descargar filtro (xlsx)", data=buf.getvalue(),
                       file_name="pedidos_filtrados.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ============================================================
# MAIN
# ============================================================
def main():
    _init_state()
    if (st.session_state.ventas.empty and st.session_state.productos.empty
            and _supabase_available()):
        _load_from_supabase()

    header()
    tab1, tab2, tab3 = st.tabs(["📥 Carga", "🏆 Premios", "🧾 Pedidos"])
    with tab1:
        tab_carga()
    with tab2:
        tab_premios()
    with tab3:
        tab_pedidos()


if __name__ == "__main__":
    main()
