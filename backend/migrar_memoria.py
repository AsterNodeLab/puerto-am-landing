"""Sube el historial local del chat a Supabase.

    python -m backend.migrar_memoria

Requiere SUPABASE_URL y SUPABASE_KEY en .env y las tablas de supabase/schema.sql.
No borra nada: sólo inserta mensajes que aún no estaban en Supabase.
"""

from __future__ import annotations

import sys

from . import memoria, storage


def main() -> int:
    if not memoria.disponible():
        print("Faltan SUPABASE_URL o SUPABASE_KEY en .env", file=sys.stderr)
        return 1
    registros = storage.ultimos("conversaciones.json", 100_000)
    por_cliente: dict[str, list[dict]] = {}
    for registro in registros:
        cliente = str(registro.get("usuario") or "anonimo")
        por_cliente.setdefault(cliente, []).append(registro)

    subidos = 0
    for cliente, mensajes in por_cliente.items():
        for mensaje in mensajes:
            modo = str(mensaje.get("modo") or "local")
            if mensaje.get("mensaje") and memoria.guardar(cliente, "user", mensaje["mensaje"], modo):
                subidos += 1
            if mensaje.get("respuesta") and memoria.guardar(cliente, "asistente", mensaje["respuesta"], modo):
                subidos += 1
    print(f"Subidos {subidos} mensajes de {len(por_cliente)} clientes a Supabase")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
