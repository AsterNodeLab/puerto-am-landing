"""Flujos autónomos de Marina: reservas y pedidos sobre el menú de demostración.

No hay n8n ni cobros: todo se guarda como solicitud local. Los borradores por
cliente permiten completar la información en varias vueltas de conversación.
"""

from __future__ import annotations

import re
import time
from datetime import date, datetime, timedelta

from . import memoria, storage

_DRAFTS: dict[str, dict] = {}
_TTL = 1800

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}
DIAS = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6}
NUMEROS = {
    "un": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
}
ALIAS = {
    "Tostadas de atún": ("tostadas de atun", "tostada de atun"),
    "Ceviche de pescado": ("ceviche",),
    "Camarones al ajillo": ("camarones al ajillo", "ajillo"),
    "Sopa de mariscos": ("sopa de mariscos",),
    "Crema de langostinos": ("langostinos",),
    "Pescado a la talla": ("pescado a la talla", "a la talla"),
    "Camarones a la diabla": ("camarones a la diabla", "a la diabla", "diabla"),
    "Pulpo al carbón": ("pulpo",),
    "Arroz a la tumbada": ("tumbada",),
    "Pie de limón": ("pie de limon",),
    "Flan de coco": ("flan",),
    "Agua de jamaica": ("jamaica",),
    "Limonada de coco": ("limonada",),
    "Café de olla": ("cafe de olla",),
}
VERBOS_PEDIDO = (
    "me llevo", "llevo", "pedir", "pedido", "ordeno", "ordenar",
    "agregar", "agrega", "anadir", "dame", "quiero", "apartame",
)


def _limpiar() -> None:
    ahora = time.monotonic()
    for clave in [c for c, d in _DRAFTS.items() if ahora - d.get("actualizado", 0) > _TTL]:
        _DRAFTS.pop(clave, None)


def _entero(token: str) -> int | None:
    token = token.strip()
    if token.isdigit():
        return int(token)
    return NUMEROS.get(token)


def extraer_fecha(texto: str) -> str | None:
    hoy = date.today()
    if "pasado mañana" in texto or "pasado manana" in texto:
        return (hoy + timedelta(days=2)).isoformat()
    if "mañana" in texto or "manana" in texto:
        return (hoy + timedelta(days=1)).isoformat()
    if re.search(r"\bhoy\b", texto):
        return hoy.isoformat()
    fecha = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", texto)
    if fecha:
        try:
            return date(int(fecha.group(1)), int(fecha.group(2)), int(fecha.group(3))).isoformat()
        except ValueError:
            return None
    fecha = re.search(r"\b(\d{1,2})[/-](\d{1,2})\b", texto)
    if fecha:
        try:
            return date(hoy.year, int(fecha.group(2)), int(fecha.group(1))).isoformat()
        except ValueError:
            return None
    fecha = re.search(r"\b(\d{1,2})\s+de\s+([a-z]+)", texto)
    if fecha and fecha.group(2) in MESES:
        try:
            return date(hoy.year, MESES[fecha.group(2)], int(fecha.group(1))).isoformat()
        except ValueError:
            return None
    for nombre, indice in DIAS.items():
        if nombre in texto:
            delta = (indice - hoy.weekday()) % 7 or 7
            return (hoy + timedelta(days=delta)).isoformat()
    return None


def extraer_hora(texto: str) -> str | None:
    hora = re.search(r"\b(\d{1,2}):(\d{2})\b", texto)
    if hora:
        h, m = int(hora.group(1)), int(hora.group(2))
        if 0 <= h <= 23 and 0 <= m <= 59:
            return f"{h:02d}:{m:02d}"
    meridiano = re.search(r"\b(\d{1,2})\s*(am|pm)\b", texto)
    if meridiano:
        h = int(meridiano.group(1))
        if 1 <= h <= 12:
            if meridiano.group(2) == "pm" and h < 12:
                h += 12
            if meridiano.group(2) == "am" and h == 12:
                h = 0
            return f"{h:02d}:00"
    simple = re.search(r"(?:a las|para las|las)\s+(\d{1,2})\b", texto)
    if simple:
        h = int(simple.group(1))
        if 1 <= h <= 23:
            if h <= 7 and not re.search(r"\b(am|mañana|manana)\b", texto):
                h += 12  # en un restaurante, "a las 8" normalmente cena
            return f"{h:02d}:00"
    return None


def extraer_personas(texto: str) -> int | None:
    patron = r"\b(\d+|un|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)\s*(?:personas?|comensales?|pax)\b"
    encontrado = re.search(patron, texto)
    if not encontrado:
        encontrado = re.search(r"\bpara\s+(\d+|un|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)\b(?!\s+las)", texto)
    return _entero(encontrado.group(1)) if encontrado else None


def extraer_nombre(texto: str) -> str | None:
    for patron in (r"(?:me llamo|soy)\s+([a-záéíóúñ]{2,20})", r"a nombre de\s+([a-záéíóúñ]{2,20})"):
        hallado = re.search(patron, texto)
        if hallado:
            return hallado.group(1).title()
    return None


def _cantidad(texto: str, inicio: int, alias: str) -> int:
    antes = texto[max(0, inicio - 16):inicio]
    previo = re.search(r"(\d+|un|una|dos|tres|cuatro|cinco|seis)\s*$", antes)
    if previo:
        return _entero(previo.group(1)) or 1
    despues = texto[inicio + len(alias):inicio + len(alias) + 14]
    siguiente = re.match(r"\s*(?:x|por|de)\s*(\d+|un|una|dos|tres|cuatro)", despues)
    if siguiente:
        return _entero(siguiente.group(1)) or 1
    return 1


def platos_en(texto: str, menu: dict) -> dict[str, int]:
    """Devuelve {platillo: cantidad} reconociendo alias sin duplicar menciones."""
    encontrados: dict[str, int] = {}
    usado: list[tuple[int, int]] = []
    for nombre, platos in menu.items():
        for plato in platos:
            alias = ALIAS.get(plato["nombre"], (plato["nombre"].lower(),))
            for palabra in alias:
                for coincidencia in re.finditer(re.escape(palabra), texto):
                    inicio, fin = coincidencia.span()
                    if any(inicio < u[1] and fin > u[0] for u in usado):
                        continue
                    usado.append((inicio, fin))
                    cantidad = _cantidad(texto, inicio, palabra)
                    encontrados[plato["nombre"]] = encontrados.get(plato["nombre"], 0) + cantidad
                    break
    return encontrados


def _precio(menu: dict, nombre: str) -> int:
    for platos in menu.values():
        for plato in platos:
            if plato["nombre"] == nombre:
                return int(plato["precio"]) if str(plato["precio"]).isdigit() else 0
    return 0


def _es_pedido(texto: str, menu: dict) -> bool:
    if not any(verbo in texto for verbo in VERBOS_PEDIDO):
        return False
    # "Quiero recordar que me gusta..." es una preferencia, no una orden.
    if any(p in texto for p in ("recordar", "me gusta", "saber", "pregunta", "recomiend", "opina", "cuesta")):
        return False
    if "?" in texto and not any(v in texto for v in ("me llevo", "pedir", "agregar", "agrega", "anadir", "ordeno")):
        return False
    return bool(platos_en(texto, menu))


def _fecha_bonita(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m/%Y")
    except ValueError:
        return iso


def _persistir(cliente: str, borrador: dict | None) -> None:
    """Guarda el borrador en Supabase para no perderlo entre reinicios."""
    contexto = {}
    if borrador:
        contexto = {
            "draft": {
                "tipo": borrador.get("tipo"),
                "datos": borrador.get("datos", {}),
                "listo": bool(borrador.get("listo")),
            }
        }
    memoria.guardar_contexto(cliente, contexto)


def _guardar(cliente: str, borrador: dict) -> None:
    datos = borrador["datos"]
    if borrador["tipo"] == "reserva":
        mensaje = (
            f"Reserva: {_fecha_bonita(datos['fecha'])} a las {datos['hora']}, "
            f"{datos['personas']} personas. Nombre: {datos.get('nombre', 'sin nombre')}."
        )
        titulo = "reserva"
    else:
        partes = [f"{cant} × {nombre}" for nombre, cant in datos["items"].items()]
        total = sum(_precio(_menu_actual, nombre) * cant for nombre, cant in datos["items"].items())
        mensaje = "Pedido: " + "; ".join(partes) + f". Total ilustrativo: ${total:,} MXN."
        titulo = "pedido"
    storage.registrar_solicitud({
        "nombre": datos.get("nombre") or "Cliente del chat",
        "correo": "", "telefono": "", "mensaje": mensaje,
        "origen": "chat-" + titulo, "tipo": titulo,
    })
    _DRAFTS.pop(cliente, None)


_menu_actual: dict = {}


def procesar(texto: str, cliente: str, menu: dict) -> dict | None:
    """Devuelve una respuesta cuando el mensaje es reserva, pedido, confirmación o cancelación."""
    global _menu_actual
    _menu_actual = menu
    _limpiar()
    cliente = cliente or "anonimo"
    borrador = _DRAFTS.get(cliente)
    if not borrador:
        guardado = memoria.obtener_contexto(cliente)
        if isinstance(guardado, dict) and isinstance(guardado.get("draft"), dict):
            borrador = guardado["draft"]
            borrador["actualizado"] = time.monotonic()
            _DRAFTS[cliente] = borrador

    if borrador and re.fullmatch(
        r"(s[ií]|vale|ok|listo|confirmar|confirmo|adelante|aceptar|correcto|asi es|claro)[.!\s]*", texto
    ):
        if borrador.get("listo"):
            _guardar(cliente, borrador)
            _persistir(cliente, None)
            if borrador["tipo"] == "reserva":
                return {
                    "respuesta": "Listo: tu reserva quedó registrada. Anota el día y la hora que te dijimos; "
                                 "si cambia algo, escríbenos y la ajustamos. El ceviche y el pescado a la talla "
                                 "son una gran forma de empezar. (Menú de demostración; precios ilustrativos.)",
                    "tipo": "reserva", "accion": "guardado",
                }
            return {
                "respuesta": "Pedido registrado. Es una solicitud de demostración: no se realiza ningún cobro "
                             "ni envío. Si quieres sumar un flan de coco para cerrar, dime cuántos. "
                             "Precios ilustrativos del menú demo.",
                "tipo": "pedido", "accion": "guardado",
            }
        return {"respuesta": "Antes de guardarlo, dime los datos que faltan.", "tipo": borrador["tipo"], "accion": "pendiente"}

    if any(p in texto for p in ("cancelar", "olvida", "descarta", "no gracias")):
        _DRAFTS.pop(cliente, None)
        _persistir(cliente, None)
        return {
            "respuesta": "Sin problema, descarté esa solicitud. ¿Te ayudo con otra cosa?",
            "tipo": "cancelado", "accion": "cancelado",
        }

    if any(p in texto for p in ("reserv", "apartar", "mesa", "agendar")):
        borrador = _DRAFTS.setdefault(cliente, {"tipo": "reserva", "datos": {}, "actualizado": time.monotonic()})
        datos = borrador["datos"]
        fecha, hora, personas = extraer_fecha(texto), extraer_hora(texto), extraer_personas(texto)
        if fecha:
            datos["fecha"] = fecha
        if hora:
            datos["hora"] = hora
        if personas:
            datos["personas"] = personas
        nombre = extraer_nombre(texto)
        if nombre:
            datos["nombre"] = nombre
        borrador["actualizado"] = time.monotonic()
        _persistir(cliente, borrador)
        faltan = [c for c in ("fecha", "hora", "personas") if c not in datos]
        if faltan:
            preguntas = {
                "fecha": "¿qué día te gustaría?",
                "hora": "¿a qué hora?",
                "personas": "¿cuántas personas serían?",
            }
            return {
                "respuesta": "Con gusto te lo aparto. " + " ".join(preguntas[c] for c in faltan),
                "tipo": "reserva", "accion": "pendiente",
            }
        borrador["listo"] = True
        return {
            "respuesta": (
                f"Perfecto: {_fecha_bonita(datos['fecha'])} a las {datos['hora']}, "
                f"{datos['personas']} personas"
                + (f" a nombre de {datos['nombre']}" if datos.get("nombre") else "")
                + ". ¿Confirmo la reserva?"
            ),
            "tipo": "reserva", "accion": "pendiente",
        }

    if _es_pedido(texto, menu):
        borrador = _DRAFTS.setdefault(cliente, {"tipo": "pedido", "datos": {"items": {}}, "actualizado": time.monotonic()})
        items = borrador["datos"].setdefault("items", {})
        encontrados = platos_en(texto, menu)
        for nombre, cantidad in encontrados.items():
            items[nombre] = items.get(nombre, 0) + cantidad
        borrador["actualizado"] = time.monotonic()
        if not items:
            return None
        lineas = [f"{cant} × {nombre} (${_precio(menu, nombre) * cant:,})" for nombre, cant in items.items()]
        total = sum(_precio(menu, nombre) * cant for nombre, cant in items.items())
        sugerencia = next(
            (p["nombre"] for platos in menu.values() for p in platos
             if p["nombre"] not in items and "postres" not in p["nombre"].lower()),
            None,
        )
        respuesta = (
            "Anotado en tu pedido:\n" + "\n".join("- " + línea for línea in lineas)
            + f"\nTotal ilustrativo: ${total:,} MXN."
            + (f" ¿Agregamos {sugerencia} para compartir?" if sugerencia else "")
            + "\n¿Confirmas el pedido? Precios de demostración, sin cobro real."
        )
        borrador["listo"] = True
        _persistir(cliente, borrador)
        return {"respuesta": respuesta, "tipo": "pedido", "accion": "pendiente"}

    return None