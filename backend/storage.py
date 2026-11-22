"""Almacenamiento JSON local y atómico.

Adecuado para una instalación de un solo servidor. Para producción con varias
instancias se sustituye por PostgreSQL sin cambiar las interfaces de este módulo.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path

from . import config, security

_BLOQUEO = threading.Lock()


def _ruta(nombre: str) -> Path:
    config.RUTA_DATOS.mkdir(parents=True, exist_ok=True)
    return config.RUTA_DATOS / nombre


def _leer(nombre: str, defecto):
    ruta = _ruta(nombre)
    if not ruta.exists():
        return defecto
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return defecto


def _escribir(nombre: str, datos) -> None:
    ruta = _ruta(nombre)
    with _BLOQUEO:
        fd, temporal = tempfile.mkstemp(prefix=f".{nombre}.", suffix=".tmp", dir=str(ruta.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as archivo:
                json.dump(datos, archivo, ensure_ascii=False, indent=2)
                archivo.flush()
                os.fsync(archivo.fileno())
            os.replace(temporal, ruta)
        finally:
            if os.path.exists(temporal):
                os.unlink(temporal)


def listar_usuarios() -> list[dict]:
    usuarios = _leer("usuarios.json", [])
    return usuarios if isinstance(usuarios, list) else []


def buscar_usuario(correo: str) -> dict | None:
    correo = correo.strip().casefold()
    return next((u for u in listar_usuarios() if u.get("correo", "").casefold() == correo), None)


def crear_usuario(correo: str, contrasena: str, nombre: str = "Administrador", rol: str = "admin") -> dict:
    if rol != "admin":
        raise ValueError("Rol no permitido")
    if len(contrasena) < 12:
        raise ValueError("La contraseña debe tener al menos 12 caracteres")
    usuarios = listar_usuarios()
    if any(u.get("correo", "").casefold() == correo.strip().casefold() for u in usuarios):
        raise ValueError("Ya existe una cuenta con ese correo")
    usuario = {
        "correo": correo.strip().casefold(),
        "nombre": nombre.strip() or "Administrador",
        "rol": rol,
        "hash": security.hash_contrasena(contrasena),
        "creado": security.ahora_iso(),
    }
    usuarios.append(usuario)
    _escribir("usuarios.json", usuarios)
    return {k: usuario[k] for k in ("correo", "nombre", "rol", "creado")}


def hay_usuarios() -> bool:
    return bool(listar_usuarios())


def agregar(nombre: str, registro: dict, limite: int = 300) -> None:
    registros = _leer(nombre, [])
    if not isinstance(registros, list):
        registros = []
    registro = dict(registro)
    registro.setdefault("fecha", security.ahora_iso())
    registros.append(registro)
    _escribir(nombre, registros[-limite:])


def ultimos(nombre: str, cantidad: int = 20) -> list[dict]:
    registros = _leer(nombre, [])
    if not isinstance(registros, list):
        return []
    return list(reversed(registros[-cantidad:]))


def registrar_solicitud(datos: dict) -> dict:
    registro = {
        "id": security._b64url(os.urandom(9)),
        "nombre": str(datos.get("nombre", ""))[:120],
        "correo": str(datos.get("correo", ""))[:160],
        "telefono": str(datos.get("telefono", ""))[:40],
        "mensaje": str(datos.get("mensaje", ""))[:2000],
        "origen": str(datos.get("origen", "formulario"))[:40],
        "tipo": str(datos.get("tipo", "contacto"))[:30],
    }
    agregar("solicitudes.json", registro)
    return {"id": registro["id"], "recibido": True}


def registrar_conversacion(datos: dict) -> None:
    agregar("conversaciones.json", {
        "canal": str(datos.get("canal", "publico"))[:20],
        "usuario": str(datos.get("usuario", "anonimo"))[:80],
        "mensaje": str(datos.get("mensaje", ""))[:1000],
        "respuesta": str(datos.get("respuesta", ""))[:2000],
        "modo": str(datos.get("modo", "local"))[:30],
    }, limite=500)


def registrar_auditoria(datos: dict) -> None:
    agregar("auditoria.json", {
        "accion": str(datos.get("accion", ""))[:60],
        "usuario": str(datos.get("usuario", ""))[:120],
        "detalle": str(datos.get("detalle", ""))[:300],
    }, limite=500)
