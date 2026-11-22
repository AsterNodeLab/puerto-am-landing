"""Capa de datos del panel: reutiliza el lector real del proyecto puerto-am-bi.

El Excel se vuelve a abrir en cada petición: si el archivo cambia, el panel lo
refleja sin tocar código. Los datos son FICTICIOS y se etiquetan como tal.
"""

from __future__ import annotations

from datetime import date, datetime

from . import config
from .excel_reader import ExcelError, calcular, exportar_csv, exportar_excel, leer_excel

__all__ = [
    "ExcelError", "cargar", "payload", "validar_filtros", "mxn",
    "anomalias", "exportar_csv", "exportar_excel", "etiqueta_periodo",
]


def cargar() -> dict:
    return leer_excel(config.RUTA_EXCEL)


def validar_filtros(desde: str | None, hasta: str | None, producto: str | None, categoria: str | None) -> dict:
    for nombre, valor in (("desde", desde), ("hasta", hasta)):
        if valor:
            try:
                date.fromisoformat(valor)
            except ValueError as exc:
                raise ValueError(f"{nombre} debe tener formato AAAA-MM-DD") from exc
    if desde and hasta and desde > hasta:
        raise ValueError("La fecha 'desde' no puede ser posterior a 'hasta'")
    return {
        "desde": desde or None,
        "hasta": hasta or None,
        "producto": producto or None,
        "categoria": categoria or None,
    }


def payload(filtros: dict) -> dict:
    return calcular(cargar(), filtros)


def mxn(valor: float | int | None) -> str:
    if valor is None:
        return "no disponible"
    return f"${float(valor):,.2f} MXN"


def etiqueta_periodo(datos: dict) -> str:
    opciones = datos.get("opciones", {})
    return f"{opciones.get('fecha_min', '—')} al {opciones.get('fecha_max', '—')}"


def anomalias(datos: dict) -> list[dict]:
    """Detecta irregularidades sobre cifras calculadas, sin inventar datos."""
    alertas: list[dict] = []
    kpis = datos.get("kpis", {})
    graficos = datos.get("graficos", {})
    productos = datos.get("top_productos", [])
    ventas = datos.get("ventas", [])

    evol = graficos.get("evolucion", {})
    etiquetas = evol.get("etiquetas", [])
    valores = evol.get("ventas", [])
    for i in range(1, len(valores)):
        anterior, actual = valores[i - 1], valores[i]
        if anterior > 0:
            cambio = (actual - anterior) / anterior * 100
            if abs(cambio) >= 20:
                alertas.append({
                    "tipo": "tendencia",
                    "titulo": f"Variación fuerte en {etiquetas[i]}",
                    "detalle": f"Las ventas cambiaron {cambio:+.1f}% respecto a {etiquetas[i-1]} "
                               f"({mxn(anterior)} → {mxn(actual)}).",
                    "severidad": "media" if cambio > 0 else "alta",
                })

    margen = kpis.get("margen_bruto")
    if margen is not None and 0 <= margen < 20:
        alertas.append({
            "tipo": "margen",
            "titulo": "Margen bruto bajo",
            "detalle": f"El margen bruto es {margen:.1f}%; por debajo del 20% de referencia.",
            "severidad": "alta",
        })

    for producto in productos:
        ingresos = producto.get("ingresos") or 0
        utilidad = producto.get("utilidad") or 0
        if ingresos > 0 and utilidad / ingresos < 0:
            alertas.append({
                "tipo": "producto",
                "titulo": f"Margen negativo: {producto.get('producto', 'producto')}",
                "detalle": f"Ingresos {mxn(ingresos)} vs. utilidad {mxn(utilidad)} en el periodo analizado.",
                "severidad": "alta",
            })

    total = kpis.get("ventas_totales") or 0
    if total > 0 and productos:
        lider = productos[0]
        proporcion = (lider.get("ingresos") or 0) / total * 100
        if proporcion >= 40:
            alertas.append({
                "tipo": "concentracion",
                "titulo": "Alta concentración de ingresos",
                "detalle": f"«{lider.get('producto', 'producto')}» representa {proporcion:.1f}% de las ventas del periodo.",
                "severidad": "media",
            })

    cumplimiento = kpis.get("cumplimiento_metas")
    if cumplimiento is not None and cumplimiento < 90:
        alertas.append({
            "tipo": "meta",
            "titulo": "Meta de ventas por debajo del objetivo",
            "detalle": f"El cumplimiento es {cumplimiento:.1f}% de la meta registrada en la base.",
            "severidad": "media",
        })

    ticket = kpis.get("ticket_promedio") or 0
    if ticket > 0:
        atipicos = [v for v in ventas if (v.get("ingreso") or 0) > ticket * 3]
        if atipicos:
            alertas.append({
                "tipo": "transaccion",
                "titulo": f"{len(atipicos)} movimiento(s) atípico(s)",
                "detalle": f"Hay {len(atipicos)} registros con ingreso superior a 3× el ticket promedio ({mxn(ticket)}). Revisar antes de concluir.",
                "severidad": "media",
            })

    fecha_max = datos.get("opciones", {}).get("fecha_max")
    if fecha_max:
        try:
            dias = (date.today() - date.fromisoformat(fecha_max)).days
            if dias > 45:
                alertas.append({
                    "tipo": "frescura",
                    "titulo": "Base de datos desactualizada",
                    "detalle": f"El último registro es del {fecha_max} ({dias} días atrás). Las cifras no reflejan la operación actual.",
                    "severidad": "alta",
                })
        except ValueError:
            pass

    orden = {"alta": 0, "media": 1, "baja": 2}
    return sorted(alertas, key=lambda a: orden.get(a["severidad"], 3))
