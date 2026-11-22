"""Memoria de conversaciones en Supabase, con respaldo local.

La clave vive sólo en el servidor (.env). Si Supabase no está configurado o falla,
el chat sigue funcionando: el historial se lee del archivo local de conversaciones.

Tablas esperadas (ver supabase/schema.sql):
    pa_memoria(cliente_id, rol, mensaje, modo, creado)
    pa_clientes(cliente_id, contexto, actualizado)
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from . import config, storage

_CONTEXTO_LOCAL: dict[str, dict] = {}


def disponible() -> bool:
    return bool(config.SUPABASE_URL and config.SUPABASE_KEY)


def _cabeceras(prefer: str | None = None) -> dict:
    cabeceras = {
        "apikey": config.SUPABASE_KEY,
        "Authorization": f"Bearer {config.SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if prefer:
        cabeceras["Prefer"] = prefer
    return cabeceras


def _peticion(ruta: str, metodo: str = "GET", cuerpo=None, prefer: str | None = None):
    datos = json.dumps(cuerpo, ensure_ascii=False).encode("utf-8") if cuerpo is not None else None
    peticion = urllib.request.Request(
        config.SUPABASE_URL + ruta, data=datos, method=metodo, headers=_cabeceras(prefer)
    )
    with urllib.request.urlopen(peticion, timeout=config.SUPABASE_TIMEOUT) as respuesta:
        crudo = respuesta.read(200_000).decode("utf-8", errors="replace")
    return json.loads(crudo) if crudo.strip() else None


def obtener(cliente: str, limite: int | None = None) -> list[dict]:
    """Historial cronológico [{rol, mensaje}] para dar contexto al modelo."""
    cliente = cliente or "anonimo"
    limite = limite or config.SUPABASE_HISTORIAL
    if disponible():
        try:
            consulta = urllib.parse.urlencode({
                "cliente_id": f"eq.{cliente}",
                "select": "rol,mensaje,creado",
                "order": "creado.desc",
                "limit": str(limite),
            })
            filas = _peticion(f"/rest/v1/pa_memoria?{consulta}") or []
            return [
                {"rol": fila.get("rol", "user"), "mensaje": fila.get("mensaje", "")}
                for fila in reversed(filas)
                if fila.get("mensaje")
            ]
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, TypeError, json.JSONDecodeError):
            pass  # se cae al respaldo local sin exponer el error

    registros = [
        r for r in storage.ultimos("conversaciones.json", 300)
        if r.get("usuario") == cliente
    ][-limite:]
    historial = []
    for registro in registros:
        if registro.get("mensaje"):
            historial.append({"rol": "user", "mensaje": registro["mensaje"]})
        if registro.get("respuesta"):
            historial.append({"rol": "asistente", "mensaje": registro["respuesta"]})
    return historial[-limite:]


def guardar(cliente: str, rol: str, mensaje: str, modo: str = "") -> bool:
    """Guarda un mensaje en Supabase. Devuelve True si se guardó ahí."""
    if not disponible() or not mensaje:
        return False
    try:
        _peticion("/rest/v1/pa_memoria", "POST", [{
            "cliente_id": cliente or "anonimo",
            "rol": "asistente" if rol in {"asistente", "bot", "modelo"} else "user",
            "mensaje": str(mensaje)[:4000],
            "modo": str(modo)[:40],
        }], prefer="return=minimal")
        return True
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, TypeError, json.JSONDecodeError):
        return False


def obtener_contexto(cliente: str) -> dict | None:
    """Borradores de reserva/pedido persistidos entre reinicios."""
    cliente = cliente or "anonimo"
    if disponible():
        try:
            consulta = urllib.parse.urlencode({
                "cliente_id": f"eq.{cliente}", "select": "contexto", "limit": "1"
            })
            filas = _peticion(f"/rest/v1/pa_clientes?{consulta}") or []
            if filas and isinstance(filas[0].get("contexto"), dict):
                return filas[0]["contexto"]
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, TypeError, json.JSONDecodeError):
            pass
    return _CONTEXTO_LOCAL.get(cliente)


def guardar_contexto(cliente: str, contexto: dict) -> bool:
    cliente = cliente or "anonimo"
    _CONTEXTO_LOCAL[cliente] = contexto
    if not disponible():
        return False
    try:
        _peticion("/rest/v1/pa_clientes", "POST", {
            "cliente_id": cliente, "contexto": contexto,
        }, prefer="resolution=merge-duplicates,return=minimal")
        return True
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, TypeError, json.JSONDecodeError):
        return False
