# 📦 Control de Stock y Alertas

Proyecto en **Python** para analizar stock y ventas, detectar:
- 🟥 Stock crítico
- 🟨 Stock OK
- 🟩 Sobrestock

Incluye proyección automática del mes en curso y genera un Excel con alertas, tops y resúmenes.

---

## 🎯 ¿Qué hace este proyecto?

A partir de dos archivos Excel:
- `vtas.xlsx` (ventas históricas)
- `stock.xlsx` (stock actual)

El script:
1. Proyecta el **mes actual** de ventas hasta mes completo (usando ventas hasta ayer)
2. Calcula **venta promedio mensual**
3. Calcula **cobertura de stock (en meses)**
4. Clasifica cada SKU como:
   - **CRITICO**
   - **OK**
   - **SOBRESTOCK**
5. Valora el stock en dinero
6. Genera un Excel con:
   - Alertas generales
   - Top 20 críticos
   - Top 20 sobrestock
   - SKUs a revisar (calidad de datos)
   - Resumen por proveedor

---

## 🗂️ Estructura del proyecto

```
control_stock/
│
├─ main.py
├─ requirements.txt
├─ README.md
├─ .gitignore
│
├─ stock.xlsx        ← (NO se versiona)
├─ vtas.xlsx         ← (NO se versiona)
│
└─ output/
   └─ alertas_stock.xlsx
```

---

## 📊 Formato esperado de los archivos

### `vtas.xlsx`
- local
- sku
- descripcion
- proveedor
- columnas de meses (la última es el mes actual)

### `stock.xlsx`
- local
- sku
- descripcion
- proveedor
- pvp
- costo
- stock

---

## ⚙️ Requisitos
- Python 3.11+
- Windows + PowerShell

---

## 🚀 Instalación

```powershell
git clone https://github.com/juanpalo25/control_stock.git
cd control_stock
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

---

## ▶️ Ejecución

Copiar `stock.xlsx` y `vtas.xlsx` en la carpeta del proyecto y ejecutar:

```powershell
python main.py
```

Salida:
- `output/alertas_stock.xlsx`

---

## ✍️ Autor
Juan Pablo
