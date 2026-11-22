"""Primitivas de seguridad: contraseñas, sesiones firmadas y cookies.

Sin dependencias externas: scrypt para contraseñas y HMAC-SHA256 para sesiones.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, timezone


def _b64url(bytes_: bytes) -> str:
    return base64.urlsafe_b64encode(bytes_).rstrip(b"=").decode("ascii")


def _deb64url(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def hash_contrasena(contrasena: str) -> str:
    sal = secrets.token_bytes(16)
    derivada = hashlib.scrypt(contrasena.encode("utf-8"), salt=sal, n=2**14, r=8, p=1, maxmem=64 * 1024 * 1024)
    return f"scrypt${_b64url(sal)}${_b64url(derivada)}"


def verificar_contrasena(contrasena: str, guardada: str) -> bool:
    try:
        algoritmo, sal, esperado = guardada.split("$")
        if algoritmo != "scrypt":
            return False
        derivada = hashlib.scrypt(
            contrasena.encode("utf-8"), salt=_deb64url(sal), n=2**14, r=8, p=1, maxmem=64 * 1024 * 1024
        )
        return hmac.compare_digest(_b64url(derivada), esperado)
    except (ValueError, TypeError):
        return False


def crear_sesion(usuario: str, rol: str, secreto: str, horas: int) -> tuple[str, int]:
    ahora = int(time.time())
    expira = ahora + horas * 3600
    carga = {"sub": usuario, "rol": rol, "iat": ahora, "exp": expira}
    cuerpo = _b64url(json.dumps(carga, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    firma = _b64url(hmac.new(secreto.encode("utf-8"), cuerpo.encode("ascii"), hashlib.sha256).digest())
    return f"{cuerpo}.{firma}", expira


def leer_sesion(token: str, secreto: str) -> dict | None:
    try:
        cuerpo, firma = token.split(".")
        esperada = _b64url(hmac.new(secreto.encode("utf-8"), cuerpo.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(firma, esperada):
            return None
        carga = json.loads(_deb64url(cuerpo))
        if int(carga.get("exp", 0)) <= int(time.time()):
            return None
        if carga.get("rol") != "admin":
            return None
        return carga
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None


def secreto_persistente(ruta) -> str:
    """Crea un secreto local la primera vez; en producción debe venir del entorno."""
    if ruta.exists():
        valor = ruta.read_text(encoding="utf-8").strip()
        if valor:
            return valor
    valor = secrets.token_urlsafe(48)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(valor, encoding="utf-8")
    try:
        ruta.chmod(0o600)
    except OSError:
        pass  # Windows no expone chmod POSIX
    return valor


def ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Limite:
    """Limitador en memoria por IP. En producción sustituir por Redis compartido."""

    def __init__(self) -> None:
        self._eventos: dict[str, list[float]] = {}

    def permitir(self, clave: str, maximo: int, ventana: int = 60) -> bool:
        ahora = time.monotonic()
        eventos = [e for e in self._eventos.get(clave, []) if ahora - e < ventana]
        if len(eventos) >= maximo:
            self._eventos[clave] = eventos
            return False
        eventos.append(ahora)
        self._eventos[clave] = eventos
        return True
