"""Crea la primera cuenta administradora sin contraseñas en el código.

    python -m backend.setup_admin --correo admin@ejemplo.com

La contraseña se pide por consola (getpass) o, sólo en automatizaciones locales,
se lee de PUERTO_AM_ADMIN_PASSWORD. Nunca se imprime ni se guarda en texto plano.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys

from . import storage


def main() -> int:
    analizador = argparse.ArgumentParser(description="Crear cuenta administradora de Puerto A&M")
    analizador.add_argument("--correo", required=True)
    analizador.add_argument("--nombre", default="Administrador")
    args = analizador.parse_args()

    contrasena = os.environ.get("PUERTO_AM_ADMIN_PASSWORD") or getpass.getpass("Contraseña (mínimo 12 caracteres): ")
    try:
        cuenta = storage.crear_usuario(args.correo, contrasena, args.nombre)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Cuenta creada: {cuenta['correo']} ({cuenta['nombre']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
