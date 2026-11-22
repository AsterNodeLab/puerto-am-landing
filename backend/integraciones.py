"""Adaptadores hacia n8n, Gmail y Google Drive.

Reglas:
- Si no hay URL configurada, la integración NO se llama y se reporta como pendiente.
- Si hay secreto, la petición se firma con HMAC-SHA256 para que el workflow pueda
  verificarla. La URL y el secreto nunca aparecen en respuestas ni en logs.
- Un fallo de red se traduce en un mensaje honesto; nunca se simula una respuesta.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import urllib.error
import urllib.request

from . import config


class IntegracionError(Exception):
    pass


def _firmar(cuerpo: bytes) -> str:
    return hmac.new(config.N8N_SECRETO.encode("utf-8"), cuerpo, hashlib.sha256).hexdigest()


def invocar(dominio: str, payload: dict) -> dict | None:
    """Devuelve None cuando el dominio no está configurado."""
    url = config.N8N.get(dominio)
    if not url:
        return None
    cuerpo = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    cabeceras = {"Content-Type": "application/json", "Accept": "application/json"}
    if config.N8N_SECRETO:
        cabeceras["X-Puerto-Signature"] = _firmar(cuerpo)
    peticion = urllib.request.Request(url, data=cuerpo, headers=cabeceras, method="POST")
    try:
        with urllib.request.urlopen(peticion, timeout=config.N8N_TIMEOUT) as respuesta:
            crudo = respuesta.read(200_000).decode("utf-8", errors="replace")
        if not crudo.strip():
            return {"ok": True}
        datos = json.loads(crudo)
        if not isinstance(datos, dict):
            raise IntegracionError("El workflow devolvió un formato inesperado.")
        return datos
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise IntegracionError(f"No se pudo contactar el workflow de {dominio}: {type(exc).__name__}.") from exc
    except json.JSONDecodeError as exc:
        raise IntegracionError(f"El workflow de {dominio} devolvió una respuesta no válida.") from exc


def texto_de(datos: dict | None, clave: str = "respuesta") -> str | None:
    if not datos:
        return None
    valor = datos.get(clave) or datos.get("texto") or datos.get("message")
    return str(valor).strip() if valor else None


def estado_detallado() -> dict:
    estado = config.estado_integraciones()
    return {
        "n8n": estado["n8n"],
        "firmado": estado["n8n_firmado"],
        "modelo_lenguaje": estado["openrouter"],
        "gmail": estado["gmail"],
        "google_drive": estado["google_drive"],
        "supabase": estado["supabase"],
        "datos_locales": estado["datos_locales"],
        "pendientes": [
            {"clave": clave, "nombre": config.PENDIENTES[clave]}
            for clave in config.PENDIENTES
            if not _configurado(clave)
        ],
    }


def _configurado(clave: str) -> bool:
    estado = config.estado_integraciones()
    if clave in config.PENDIENTES:
        if clave == "openrouter":
            return estado["openrouter"]
        if clave == "supabase":
            return estado["supabase"]
        if clave in {"gmail", "google_drive"}:
            return estado[clave]
        if clave == "gastos":
            return False  # no hay hoja de egresos en la base disponible
        return bool(config.N8N.get(clave))
    return False


def enviar_reporte(datos: dict, destino: str, nombre_archivo: str) -> dict:
    """Sólo envía a la dirección permitida en .env; nunca a un destino del chat."""
    if not config.N8N.get("reportes"):
        raise IntegracionError("El workflow de reportes (Google Drive / Gmail) no está configurado.")
    permitido = config.GMAIL_DESTINO.strip().casefold()
    if not permitido or destino.strip().casefold() != permitido:
        raise IntegracionError("El correo destino no está autorizado en la configuración del servidor.")
    return invocar("reportes", {
        "accion": "generar_y_enviar_reporte",
        "destino": permitido,
        "nombre_archivo": nombre_archivo[:120],
        "resumen": datos,
    }) or {}
