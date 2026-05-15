-- ============================================================
-- MegaFeria 2026 — Schema Supabase
-- Ejecutar en SQL Editor del proyecto Supabase.
-- ============================================================

-- 1) Catalogo de productos: una fila por ITEMID con su ASIGNACION (lista de mecanicas)
CREATE TABLE IF NOT EXISTS productos (
  itemid TEXT PRIMARY KEY,
  descripcion TEXT,
  familia TEXT,
  asignacion INTEGER[] NOT NULL DEFAULT '{}',
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_productos_asignacion ON productos USING GIN (asignacion);

-- 2) Mecanicas de premios (34 mecanicas)
CREATE TABLE IF NOT EXISTS mecanicas (
  numero INTEGER PRIMARY KEY,
  descripcion TEXT NOT NULL,
  tipo TEXT NOT NULL CHECK (tipo IN ('monetary','unit','single_sku','combo','coverage')),
  umbral NUMERIC NOT NULL,                -- $ o cantidad por premio
  tipo_premio TEXT NOT NULL CHECK (tipo_premio IN ('EFECTIVO','CUPON','OTRO')),
  valor_premio NUMERIC NOT NULL DEFAULT 0, -- $ que vale UN premio (para sumar totales por TIPO)
  premio_descripcion TEXT,                -- texto humano: "EFECTIVO $50 + BUZO REFOR"
  skus TEXT[],                            -- usado en single_sku
  combo_id INTEGER,                       -- usado en combo (id del combo)
  config JSONB DEFAULT '{}'::jsonb        -- extra: {"top_only":1, "min_per_client":150}
);

-- 3) Definicion de combos (10 combos de EMTOP, mecanica 24)
CREATE TABLE IF NOT EXISTS combos (
  id SERIAL PRIMARY KEY,
  combo_numero INTEGER NOT NULL,          -- 1..10
  itemid TEXT NOT NULL,
  max_descuento_pct NUMERIC NOT NULL,     -- como porcentaje, ej 48 = 48%
  UNIQUE (combo_numero, itemid)
);

CREATE INDEX IF NOT EXISTS idx_combos_combo_numero ON combos(combo_numero);

-- 4) Ventas (cada subida REEMPLAZA todo)
CREATE TABLE IF NOT EXISTS ventas (
  id BIGSERIAL PRIMARY KEY,
  pedido TEXT NOT NULL,
  fecha DATE,
  cliente TEXT,
  ruc TEXT,
  asesor TEXT NOT NULL,
  regional TEXT NOT NULL,
  itemid TEXT NOT NULL,
  descripcion TEXT,
  precio_autorizador NUMERIC,
  descuento NUMERIC,                      -- porcentaje 0..1 (lo normalizamos al cargar)
  cantidad NUMERIC NOT NULL,
  venta_neta NUMERIC NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ventas_asesor ON ventas(asesor);
CREATE INDEX IF NOT EXISTS idx_ventas_regional ON ventas(regional);
CREATE INDEX IF NOT EXISTS idx_ventas_itemid ON ventas(itemid);
CREATE INDEX IF NOT EXISTS idx_ventas_pedido ON ventas(pedido);

-- 5) RLS — lectura publica, escritura solo con service_role
ALTER TABLE productos ENABLE ROW LEVEL SECURITY;
ALTER TABLE mecanicas ENABLE ROW LEVEL SECURITY;
ALTER TABLE combos    ENABLE ROW LEVEL SECURITY;
ALTER TABLE ventas    ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "read_productos" ON productos;
CREATE POLICY "read_productos" ON productos FOR SELECT TO anon USING (true);
DROP POLICY IF EXISTS "read_mecanicas" ON mecanicas;
CREATE POLICY "read_mecanicas" ON mecanicas FOR SELECT TO anon USING (true);
DROP POLICY IF EXISTS "read_combos" ON combos;
CREATE POLICY "read_combos" ON combos FOR SELECT TO anon USING (true);
DROP POLICY IF EXISTS "read_ventas" ON ventas;
CREATE POLICY "read_ventas" ON ventas FOR SELECT TO anon USING (true);

-- Para que la app escriba con la anon key (sin login), agrega tambien INSERT/DELETE.
-- Si prefieres usar service_role en secrets, omite las siguientes:
DROP POLICY IF EXISTS "write_productos" ON productos;
CREATE POLICY "write_productos" ON productos FOR ALL TO anon USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS "write_mecanicas" ON mecanicas;
CREATE POLICY "write_mecanicas" ON mecanicas FOR ALL TO anon USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS "write_combos" ON combos;
CREATE POLICY "write_combos" ON combos FOR ALL TO anon USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS "write_ventas" ON ventas;
CREATE POLICY "write_ventas" ON ventas FOR ALL TO anon USING (true) WITH CHECK (true);
