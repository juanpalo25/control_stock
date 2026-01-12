from pathlib import Path
import pandas as pd
from datetime import date
import calendar

BASE_DIR = Path(__file__).resolve().parent
VTAS_FILE = BASE_DIR / "vtas.xlsx"
STOCK_FILE = BASE_DIR / "stock.xlsx"

# Reglas de negocio (ajustables más adelante)
CRITICO_MESES = 0.5
SOBRESTOCK_MESES = 3.0


def to_number_ar(x):
    if pd.isna(x):
        return 0.0
    s = str(x).strip()
    if s == "" or s == ",00":
        return 0.0
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def classify(cobertura):
    if pd.isna(cobertura):
        return "SIN_DATO"
    if cobertura < CRITICO_MESES:
        return "CRITICO"
    if cobertura > SOBRESTOCK_MESES:
        return "SOBRESTOCK"
    return "OK"


def main():
    vtas = pd.read_excel(VTAS_FILE)
    stock = pd.read_excel(STOCK_FILE)

    # Normalizar columnas
    vtas.columns = vtas.columns.astype(str).str.strip().str.lower()
    stock.columns = stock.columns.astype(str).str.strip().str.lower()

    # Normalizar claves
    vtas["local"] = vtas["local"].astype(str).str.strip().str.upper()
    stock["local"] = stock["local"].astype(str).str.strip().str.upper()

    vtas["sku"] = vtas["sku"].astype("Int64")
    stock["sku"] = stock["sku"].astype("Int64")

    # Detectar columnas de meses (última = mes actual)
    month_cols = [c for c in vtas.columns if c not in ["local", "sku", "descripcion", "proveedor"]]
    if len(month_cols) < 2:
        raise ValueError(f"Necesito al menos 2 columnas de meses. Detecté: {month_cols}")

    current_month_col = month_cols[-1]      # mes actual (acumulado)
    closed_month_cols = month_cols[:-1]     # meses cerrados

    # Convertir ventas a numérico
    for c in month_cols:
        vtas[c] = pd.to_numeric(vtas[c], errors="coerce").fillna(0)

    # Calcular días: hasta AYER
    today = date.today()
    yesterday = today.replace(day=today.day)  # solo para claridad
    # días transcurridos del mes hasta ayer:
    days_elapsed = today.day - 1
    # días totales del mes:
    days_in_month = calendar.monthrange(today.year, today.month)[1]

    if days_elapsed <= 0:
        # Si es día 1, no hay "hasta ayer" en el mes actual => evitamos división por 0
        # En ese caso usamos el acumulado como proyección (o podrías excluir el mes actual)
        days_elapsed = 1

    # Proyección del mes actual a mes completo
    vtas["venta_mes_actual_acum"] = vtas[current_month_col]
    vtas["venta_mes_actual_proy"] = (vtas["venta_mes_actual_acum"] / days_elapsed) * days_in_month

    # Promedio mensual usando:
    # - meses cerrados tal cual
    # - mes actual proyectado
    if len(closed_month_cols) == 0:
        # caso extremo: solo hay mes actual
        vtas["vta_prom_mensual"] = vtas["venta_mes_actual_proy"]
    else:
        vtas["vta_prom_mensual"] = (vtas[closed_month_cols].sum(axis=1) + vtas["venta_mes_actual_proy"]) / (
            len(closed_month_cols) + 1
        )

    # Limpiar numéricos del stock
    stock["pvp"] = stock["pvp"].apply(to_number_ar)
    stock["costo"] = stock["costo"].apply(to_number_ar)
    stock["stock"] = stock["stock"].apply(to_number_ar)
    stock["stock"] = stock["stock"].clip(lower=0)  # negativos a 0

    # AGREGAR A NIVEL SKU (ignorando local)
    vtas_agg = vtas.groupby(["sku"], as_index=False).agg({
        "descripcion": "first",
        "proveedor": "first",
        "vta_prom_mensual": "sum",
        "venta_mes_actual_acum": "sum",
        "venta_mes_actual_proy": "sum",
    })

    stock_agg = stock.groupby(["sku"], as_index=False).agg({
        "descripcion": "first",
        "proveedor": "first",
        "pvp": "first",
        "costo": "first",
        "stock": "sum",
    })

    # Unir
    df = stock_agg.merge(
        vtas_agg[["sku", "vta_prom_mensual", "venta_mes_actual_acum", "venta_mes_actual_proy"]],
        on=["sku"],
        how="left"
    )
    df["vta_prom_mensual"] = df["vta_prom_mensual"].fillna(0)

    # Cobertura (meses)
    df["cobertura_meses"] = df.apply(
        lambda r: (r["stock"] / r["vta_prom_mensual"]) if r["vta_prom_mensual"] > 0 else 9999,
        axis=1
    )
    df["estado"] = df["cobertura_meses"].apply(classify)
    df["obsoleto"] = (df["vta_prom_mensual"] == 0) & (df["stock"] > 0)
    df_obsoletos = df[df["obsoleto"]].copy()
    df = df[~df["obsoleto"]].copy()
    # -----------------------
    # Flags de revisión (calidad de datos)
    # -----------------------
    df["revisar"] = False
    motivos = []

    # costo o pvp en 0 (valorización no confiable)
    m1 = (df["costo"] == 0) & (df["stock"] > 0)
    m2 = (df["pvp"] == 0) & (df["stock"] > 0)

    # ventas en 0 pero stock > 0 (ya sacamos obsoletos, esto sería raro si quedó algo)
    m3 = (df["vta_prom_mensual"] == 0) & (df["stock"] > 0)

    df.loc[m1 | m2 | m3, "revisar"] = True

    # Motivo simple (podés dejar uno principal)
    df["motivo_revisar"] = ""
    df.loc[m1, "motivo_revisar"] = "COSTO=0"
    df.loc[m2 & ~m1, "motivo_revisar"] = "PVP=0"
    df.loc[m3 & ~(m1 | m2), "motivo_revisar"] = "VENTA=0"

    # Mostrar diagnóstico del paso
    print("✅ Mes actual detectado (columna):", current_month_col)
    print(f"✅ Proyección usando hasta AYER: días transcurridos={today.day - 1} | días del mes={days_in_month}")
    print("✅ Ejemplo (primeras 3 filas) - ventas:")
    print(vtas[["local","sku","venta_mes_actual_acum","venta_mes_actual_proy","vta_prom_mensual"]].head(3))

    print("\n✅ Ejemplo (primeras 3 filas) - resultado final:")
    print(df[["sku","stock","vta_prom_mensual","cobertura_meses","estado"]].head(3))

    # -----------------------
    # NO MATCH (diagnóstico)
    # -----------------------
    # Stock que NO encontró ventas (por local+sku)
    no_match_stock = df[df["vta_prom_mensual"] == 0].copy()

    # Ventas que NO tienen stock (por local+sku)
    vtas_keys = vtas_agg[["sku", "vta_prom_mensual", "venta_mes_actual_acum", "venta_mes_actual_proy"]].copy()
    stock_keys = stock_agg[["sku", "stock"]].copy()
    no_match_vtas = vtas_keys.merge(stock_keys, on=["sku"], how="left")
    no_match_vtas = no_match_vtas[no_match_vtas["stock"].isna()].copy()

    # -----------------------
    # Exportar a Excel
    # -----------------------
    # -----------------------
    # Valorización + TOPS (definir SIEMPRE antes de exportar)
    # -----------------------
    df["stock_val_costo"] = df["stock"] * df["costo"]
    df["stock_val_pvp"] = df["stock"] * df["pvp"]
    resumen_proveedor = (
        df.groupby("proveedor", as_index=False)
        .agg(
            skus=("sku", "nunique"),
            stock_unidades=("stock", "sum"),
            stock_val_costo=("stock_val_costo", "sum"),
            criticos=("estado", lambda s: (s == "CRITICO").sum()),
            sobrestock=("estado", lambda s: (s == "SOBRESTOCK").sum()),
            revisar=("revisar", "sum"),
        )
        .sort_values("stock_val_costo", ascending=False)
    )

    top_criticos = (
        df[df["estado"] == "CRITICO"]
        .sort_values(["cobertura_meses", "stock_val_costo"], ascending=[True, False])
        .head(20)
        .copy()
    )

    top_sobrestock = (
        df[df["estado"] == "SOBRESTOCK"]
        .sort_values(["stock_val_costo", "stock"], ascending=[False, False])
        .head(20)
        .copy()
    )
    out_file = BASE_DIR / "output" / "alertas_stock.xlsx"
    with pd.ExcelWriter(out_file, engine="openpyxl") as writer:
        top_criticos.to_excel(writer, index=False, sheet_name="top_criticos")
        top_sobrestock.to_excel(writer, index=False, sheet_name="top_sobrestock")
        df.to_excel(writer, index=False, sheet_name="alertas")
        df[df["estado"] == "CRITICO"].to_excel(writer, index=False, sheet_name="criticos")
        df[df["estado"] == "SOBRESTOCK"].to_excel(writer, index=False, sheet_name="sobrestock")
        df["stock_val_costo"] = df["stock"] * df["costo"]
        df["stock_val_pvp"] = df["stock"] * df["pvp"]
        top_criticos.to_excel(writer, index=False, sheet_name="top_criticos")
        top_sobrestock.to_excel(writer, index=False, sheet_name="top_sobrestock")
        df[df["revisar"]].to_excel(writer, index=False, sheet_name="revisar")
        resumen_proveedor.to_excel(writer, index=False, sheet_name="resumen_proveedor")
        # Tops
        top_criticos = (
        df[df["estado"] == "CRITICO"]
        .sort_values(["cobertura_meses", "stock_val_costo"], ascending=[True, False])
        .head(20)
        .copy()
        )
        top_sobrestock = (
        df[df["estado"] == "SOBRESTOCK"]
        .sort_values(["stock_val_costo", "stock"], ascending=[False, False])
        .head(20)
        .copy()
        )
        df_obsoletos.to_excel(writer, index=False, sheet_name="obsoletos")
        no_match_stock.to_excel(writer, index=False, sheet_name="no_match_stock")
        no_match_vtas.to_excel(writer, index=False, sheet_name="no_match_vtas")

    print("\n✅ Exportado:", out_file)
    print("📌 Filas no_match_stock:", len(no_match_stock))
    print("📌 Filas no_match_vtas:", len(no_match_vtas))


if __name__ == "__main__":
    main()