"""Lectura del Excel y cálculo de todos los indicadores del dashboard.

Regla de oro: el backend vuelve a abrir el archivo en cada petición, así que
cualquier cambio guardado en Excel se refleja al pulsar «Actualizar datos».
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

MESES_ES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


class ExcelError(Exception):
    """El archivo no existe o no tiene la estructura esperada."""


def _normalizar(texto: object) -> str:
    txt = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", txt.lower())


def _clave(cabecera: object) -> str | None:
    n = _normalizar(cabecera)
    if not n:
        return None
    if n.startswith("fecha"):
        return "fecha"
    if "pedido" in n:
        return "pedido"
    if n.startswith("producto"):
        return "producto"
    if "categoria" in n:
        return "categoria"
    if "cantidad" in n:
        return "cantidad"
    if n.startswith("precio"):
        return "precio"
    if n.startswith("costo"):
        return "costo"
    if "canal" in n:
        return "canal"
    if "pago" in n:
        return "metodo_pago"
    return None


def _fecha(valor: object, fila: int) -> date:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str):
        texto = valor.strip()
        for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(texto, formato).date()
            except ValueError:
                continue
    raise ExcelError(f"Fila {fila}: fecha no válida ({valor!r}). Usa dd/mm/yyyy.")


def _numero(valor: object, fila: int, campo: str) -> float:
    if isinstance(valor, bool):
        raise ExcelError(f"Fila {fila}: {campo} no válido.")
    if isinstance(valor, (int, float)):
        return float(valor)
    if isinstance(valor, str):
        limpio = valor.strip().replace("$", "").replace(",", "").replace(" ", "")
        try:
            return float(limpio)
        except ValueError:
            pass
    raise ExcelError(f"Fila {fila}: {campo} no válido ({valor!r}). Debe ser numérico.")


def _texto(valor: object) -> str:
    return "" if valor is None else str(valor).strip()


def _localizar_cabeceras(ws) -> tuple[int, dict[str, int]]:
    for fila in range(1, min(ws.max_row, 15) + 1):
        mapa: dict[str, int] = {}
        for col in range(1, ws.max_column + 1):
            clave = _clave(ws.cell(row=fila, column=col).value)
            if clave and clave not in mapa:
                mapa[clave] = col
        if len(mapa) >= 8:
            return fila, mapa
    raise ExcelError("No se encontró la fila de encabezados en la hoja 'Ventas'.")


def leer_excel(ruta: Path) -> dict:
    """Abre el Excel y devuelve ventas, catálogo, metas y metadatos."""
    if not ruta.exists():
        raise ExcelError(f"No se encontró el archivo: {ruta}")

    try:
        wb = load_workbook(ruta, data_only=True, read_only=True)
    except Exception as exc:  # noqa: BLE001 - error de archivo abierto/corrupto
        raise ExcelError(f"No se pudo abrir el Excel: {exc}") from exc

    try:
        if "Ventas" not in wb.sheetnames:
            raise ExcelError("Falta la hoja 'Ventas'.")

        ws = wb["Ventas"]
        fila_inicio, columnas = _localizar_cabeceras(ws)
        requeridas = {"fecha", "pedido", "producto", "categoria", "cantidad", "precio", "costo"}
        faltantes = requeridas - columnas.keys()
        if faltantes:
            raise ExcelError(f"Faltan columnas en Ventas: {', '.join(sorted(faltantes))}")

        ventas = []
        for numero, fila in enumerate(
            ws.iter_rows(min_row=fila_inicio + 1, values_only=True), start=fila_inicio + 1
        ):
            def valor(clave: str):
                idx = columnas.get(clave)
                return fila[idx - 1] if idx and idx <= len(fila) else None

            if valor("fecha") is None and valor("pedido") is None:
                continue
            cantidad = _numero(valor("cantidad"), numero, "Cantidad")
            precio = _numero(valor("precio"), numero, "Precio")
            costo = _numero(valor("costo"), numero, "Costo unitario")
            if cantidad <= 0:
                raise ExcelError(f"Fila {numero}: la Cantidad debe ser mayor que cero.")
            ingreso = cantidad * precio
            costo_total = cantidad * costo
            ventas.append({
                "fecha": _fecha(valor("fecha"), numero).isoformat(),
                "pedido": _texto(valor("pedido")),
                "producto": _texto(valor("producto")),
                "categoria": _texto(valor("categoria")),
                "cantidad": int(cantidad) if cantidad.is_integer() else round(cantidad, 2),
                "precio": round(precio, 2),
                "costo": round(costo, 2),
                "ingreso": round(ingreso, 2),
                "costo_total": round(costo_total, 2),
                "utilidad": round(ingreso - costo_total, 2),
                "canal": _texto(valor("canal")),
                "metodo_pago": _texto(valor("metodo_pago")),
            })

        if not ventas:
            raise ExcelError("La hoja 'Ventas' no contiene registros.")

        productos = []
        if "Productos" in wb.sheetnames:
            for fila in wb["Productos"].iter_rows(min_row=5, values_only=True):
                if not fila or not fila[0]:
                    continue
                productos.append({
                    "sku": _texto(fila[0]),
                    "producto": _texto(fila[1]) if len(fila) > 1 else "",
                    "categoria": _texto(fila[2]) if len(fila) > 2 else "",
                    "precio": _numero(fila[3], 0, "Precio") if len(fila) > 3 and fila[3] is not None else 0.0,
                    "costo": _numero(fila[4], 0, "Costo") if len(fila) > 4 and fila[4] is not None else 0.0,
                })

        metas = []
        if "Metas" in wb.sheetnames:
            for fila in wb["Metas"].iter_rows(min_row=5, values_only=True):
                if not fila or fila[0] is None:
                    continue
                mes = _fecha(fila[0], 0).replace(day=1)
                metas.append({
                    "mes": mes.isoformat(),
                    "meta_ventas": _numero(fila[1], 0, "Meta de ventas"),
                    "meta_utilidad": _numero(fila[2], 0, "Meta de utilidad"),
                    "meta_pedidos": _numero(fila[3], 0, "Meta de pedidos"),
                })

        return {
            "ventas": ventas,
            "productos": productos,
            "metas": sorted(metas, key=lambda m: m["mes"]),
            "fuente": {
                "archivo": ruta.name,
                "modificado": datetime.fromtimestamp(ruta.stat().st_mtime).isoformat(timespec="seconds"),
                "registros_totales": len(ventas),
                "simulacion": True,
            },
        }
    finally:
        wb.close()


def filtrar(ventas: list[dict], desde: str | None, hasta: str | None,
            producto: str | None, categoria: str | None) -> list[dict]:
    resultado = []
    for v in ventas:
        if desde and v["fecha"] < desde:
            continue
        if hasta and v["fecha"] > hasta:
            continue
        if producto and v["producto"].casefold() != producto.casefold():
            continue
        if categoria and v["categoria"].casefold() != categoria.casefold():
            continue
        resultado.append(v)
    return resultado


def _etiqueta(mes: str) -> str:
    """Recibe 'AAAA-MM' y devuelve 'Ene 2026'."""
    anio, numero = mes.split("-")[:2]
    return f"{MESES_ES[int(numero) - 1]} {anio}"


def calcular(datos: dict, filtros: dict) -> dict:
    """Construye el payload completo: KPIs, gráficos, tabla y exportaciones."""
    todas = datos["ventas"]
    filtradas = filtrar(todas, filtros["desde"], filtros["hasta"],
                        filtros["producto"], filtros["categoria"])
    metas = datos["metas"]

    ingresos = round(sum(v["ingreso"] for v in filtradas), 2)
    costos = round(sum(v["costo_total"] for v in filtradas), 2)
    utilidad = round(ingresos - costos, 2)
    pedidos = len({v["pedido"] for v in filtradas if v["pedido"]}) or len(filtradas)
    unidades = sum(v["cantidad"] for v in filtradas)

    por_mes: dict[str, dict] = defaultdict(lambda: {
        "ingresos": 0.0, "costos": 0.0, "utilidad": 0.0, "unidades": 0, "pedidos": set(),
    })
    por_producto: dict[str, dict] = defaultdict(lambda: {
        "unidades": 0, "ingresos": 0.0, "utilidad": 0.0, "pedidos": set(), "categoria": "",
    })
    por_categoria: dict[str, float] = defaultdict(float)

    for v in filtradas:
        mes = v["fecha"][:7]
        m = por_mes[mes]
        m["ingresos"] += v["ingreso"]
        m["costos"] += v["costo_total"]
        m["utilidad"] += v["utilidad"]
        m["unidades"] += v["cantidad"]
        m["pedidos"].add(v["pedido"])

        p = por_producto[v["producto"]]
        p["unidades"] += v["cantidad"]
        p["ingresos"] += v["ingreso"]
        p["utilidad"] += v["utilidad"]
        p["pedidos"].add(v["pedido"])
        p["categoria"] = v["categoria"]
        por_categoria[v["categoria"]] += v["ingreso"]

    meses = sorted(por_mes)
    crecimiento = None
    if len(meses) >= 2:
        anterior = por_mes[meses[-2]]["ingresos"]
        actual = por_mes[meses[-1]]["ingresos"]
        if anterior:
            crecimiento = round((actual - anterior) / anterior * 100, 1)

    ranking = sorted(
        ({"producto": k, "categoria": v["categoria"], "unidades": v["unidades"],
          "ingresos": round(v["ingresos"], 2), "utilidad": round(v["utilidad"], 2),
          "pedidos": len(v["pedidos"])} for k, v in por_producto.items()),
        key=lambda x: x["unidades"], reverse=True,
    )

    metas_mes = {m["mes"][:7]: m for m in metas}
    meses_meta = [mes for mes in meses if mes in metas_mes]
    meta_ventas_total = sum(metas_mes[mes]["meta_ventas"] for mes in meses_meta)
    real_ventas_total = sum(por_mes[mes]["ingresos"] for mes in meses_meta)
    cumplimiento = round(real_ventas_total / meta_ventas_total * 100, 1) if meta_ventas_total else None

    metas_detalle = []
    for mes in meses_meta:
        objetivo = metas_mes[mes]
        real = por_mes[mes]
        metas_detalle.append({
            "mes": mes,
            "etiqueta": _etiqueta(mes),
            "meta_ventas": round(objetivo["meta_ventas"], 2),
            "real_ventas": round(real["ingresos"], 2),
            "cumplimiento": round(real["ingresos"] / objetivo["meta_ventas"] * 100, 1)
            if objetivo["meta_ventas"] else None,
            "meta_pedidos": round(objetivo["meta_pedidos"]),
            "real_pedidos": len(real["pedidos"]),
        })

    etiquetas = [_etiqueta(mes) for mes in meses]
    categorias_ordenadas = sorted(por_categoria.items(), key=lambda x: x[1], reverse=True)
    productos_top = sorted(por_producto.items(), key=lambda x: x[1]["ingresos"], reverse=True)[:8]

    return {
        "fuente": datos["fuente"],
        "filtros": filtros,
        "opciones": {
            "productos": sorted({v["producto"] for v in todas}),
            "categorias": sorted({v["categoria"] for v in todas}),
            "fecha_min": min(v["fecha"] for v in todas),
            "fecha_max": max(v["fecha"] for v in todas),
        },
        "kpis": {
            "ventas_totales": ingresos,
            "pedidos": pedidos,
            "ticket_promedio": round(ingresos / pedidos, 2) if pedidos else 0,
            "unidades": unidades,
            "costos": costos,
            "utilidad_bruta": utilidad,
            "margen_bruto": round(utilidad / ingresos * 100, 1) if ingresos else 0,
            "crecimiento_mensual": crecimiento,
            "cumplimiento_metas": cumplimiento,
            "productos_unicos": len(por_producto),
        },
        "graficos": {
            "evolucion": {
                "etiquetas": etiquetas,
                "ventas": [round(por_mes[mes]["ingresos"], 2) for mes in meses],
                "utilidad": [round(por_mes[mes]["utilidad"], 2) for mes in meses],
            },
            "ingresos_costos": {
                "etiquetas": etiquetas,
                "ingresos": [round(por_mes[mes]["ingresos"], 2) for mes in meses],
                "costos": [round(por_mes[mes]["costos"], 2) for mes in meses],
            },
            "categorias": {
                "etiquetas": [k for k, _ in categorias_ordenadas],
                "valores": [round(v, 2) for _, v in categorias_ordenadas],
            },
            "productos_top": {
                "etiquetas": [k for k, _ in productos_top],
                "valores": [round(v["ingresos"], 2) for _, v in productos_top],
            },
            "metas_resultados": {
                "etiquetas": [m["etiqueta"] for m in metas_detalle],
                "metas": [m["meta_ventas"] for m in metas_detalle],
                "resultados": [m["real_ventas"] for m in metas_detalle],
            },
        },
        "top_productos": ranking[:5],
        "metas_detalle": metas_detalle,
        "ventas": filtradas,
        "registros_filtrados": len(filtradas),
    }


COLUMNAS_CSV = [
    ("fecha", "Fecha"), ("pedido", "Pedido"), ("producto", "Producto"),
    ("categoria", "Categoría"), ("cantidad", "Cantidad"), ("precio", "Precio unitario (MXN)"),
    ("costo", "Costo unitario (MXN)"), ("ingreso", "Ingreso (MXN)"),
    ("costo_total", "Costo (MXN)"), ("utilidad", "Utilidad (MXN)"),
    ("canal", "Canal"), ("metodo_pago", "Método de pago"),
]


def exportar_csv(payload: dict) -> bytes:
    salida = io.StringIO(newline="")
    writer = csv.writer(salida)
    writer.writerow([titulo for _, titulo in COLUMNAS_CSV])
    for venta in payload["ventas"]:
        writer.writerow([venta[clave] for clave, _ in COLUMNAS_CSV])
    return b"\xef\xbb\xbf" + salida.getvalue().encode("utf-8")


def exportar_excel(payload: dict) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Reporte de ventas"
    for i, (_, titulo) in enumerate(COLUMNAS_CSV, start=1):
        c = ws.cell(row=1, column=i, value=titulo)
        c.fill = PatternFill("solid", fgColor="0F3043")
        c.font = Font(name="Aptos", bold=True, color="FFFFFF")
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for r, venta in enumerate(payload["ventas"], start=2):
        for i, (clave, _) in enumerate(COLUMNAS_CSV, start=1):
            ws.cell(row=r, column=i, value=venta[clave])
    for i in range(1, len(COLUMNAS_CSV) + 1):
        ws.column_dimensions[get_column_letter(i)].width = 20
    ws.freeze_panes = "A2"
    ws.sheet_view.showGridLines = False

    kpi = wb.create_sheet("Resumen")
    kpi["A1"] = "PUERTO A&M | RESUMEN EJECUTIVO"
    kpi["A1"].font = Font(name="Aptos", size=14, bold=True, color="0F3043")
    kpi["A2"] = "SIMULACIÓN ACADÉMICA · Datos ficticios · Top Learning"
    kpi["A2"].font = Font(name="Aptos", size=10, italic=True, color="5C6B73")
    etiquetas = [
        ("Ventas totales (MXN)", "ventas_totales"), ("Pedidos", "pedidos"),
        ("Ticket promedio (MXN)", "ticket_promedio"), ("Unidades vendidas", "unidades"),
        ("Costos (MXN)", "costos"), ("Utilidad bruta (MXN)", "utilidad_bruta"),
        ("Margen bruto (%)", "margen_bruto"), ("Crecimiento mensual (%)", "crecimiento_mensual"),
        ("Cumplimiento de metas (%)", "cumplimiento_metas"),
    ]
    for r, (texto, clave) in enumerate(etiquetas, start=4):
        kpi.cell(row=r, column=1, value=texto).font = Font(name="Aptos", bold=True, color="26333A")
        valor = payload["kpis"][clave]
        kpi.cell(row=r, column=2, value=valor if valor is not None else "N/D").number_format = '#,##0.00'
    kpi.column_dimensions["A"].width = 32
    kpi.column_dimensions["B"].width = 20

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
