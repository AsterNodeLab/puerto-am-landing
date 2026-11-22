"""Configuración central del portal Puerto A&M.

Todas las credenciales se leen de variables de entorno. Nunca se imprimen ni se
devuelven al navegador: la API sólo expone si cada integración está configurada.
"""

from __future__ import annotations

import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def _cargar_env() -> None:
    """Lee .env sin dependencias. Las variables del sistema tienen prioridad."""
    ruta = RAIZ / ".env"
    if not ruta.exists():
        return
    try:
        lineas = ruta.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for linea in lineas:
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        clave, valor = clave.strip(), valor.strip().strip('"').strip("'")
        if clave and clave not in os.environ:
            os.environ[clave] = valor


_cargar_env()


def _texto(nombre: str, valor_por_defecto: str = "") -> str:
    return os.environ.get(nombre, valor_por_defecto).strip()


def _booleano(nombre: str, valor_por_defecto: bool = False) -> bool:
    valor = os.environ.get(nombre)
    if valor is None:
        return valor_por_defecto
    return valor.strip().lower() in {"1", "true", "si", "yes", "on"}


RUTA_EXCEL = Path(_texto("PUERTO_AM_EXCEL", str(RAIZ / "data" / "Puerto_AM_Base_Datos_DEMO.xlsx")))
RUTA_DATOS = Path(_texto("PUERTO_AM_DATOS", str(RAIZ / "data")))
RUTA_CONOCIMIENTO = RAIZ / "knowledge"
RUTA_ALMA = RAIZ / "SOUL.md"
RUTA_FRONTEND = RAIZ / "frontend"

AMBIENTE = _texto("PUERTO_AM_ENV", "development")
# Modo actual: sólo sitio público con chat. Desactiva rutas del panel y cualquier
# llamada a n8n, aunque haya URLs configuradas en el entorno.
SOLO_LANDING = _booleano("PUERTO_AM_SOLO_LANDING", False)
SECRETO_SESION = _texto("PUERTO_AM_SESSION_SECRET")
HORAS_SESION = int(_texto("PUERTO_AM_HORAS_SESION", "8") or 8)
COOKIES_SEGURAS = _booleano("PUERTO_AM_SECURE_COOKIES", AMBIENTE == "production")
LIMITE_LOGIN = int(_texto("PUERTO_AM_LIMITE_LOGIN", "8") or 8)
LIMITE_CHAT = int(_texto("PUERTO_AM_LIMITE_CHAT", "30") or 30)

# Datos públicos del restaurante. Sólo se envían al navegador si están definidos;
# nunca se inventan dirección, teléfono, horarios ni precios.
WHATSAPP_PUBLICO = _texto("PUERTO_AM_WHATSAPP")
EMAIL_PUBLICO = _texto("PUERTO_AM_EMAIL")
DIRECCION_PUBLICA = _texto("PUERTO_AM_DIRECCION")
HORARIO_PUBLICO = _texto("PUERTO_AM_HORARIO")

# n8n: un webhook por dominio. El secreto se usa para firmar cada petición.
N8N = {
    "chat_publico": _texto("N8N_PUBLIC_CHAT_URL"),
    "finanzas": _texto("N8N_FINANZAS_URL"),
    "facturas": _texto("N8N_FACTURAS_URL"),
    "bancos": _texto("N8N_BANCOS_URL"),
    "pagos": _texto("N8N_PAGOS_URL"),
    "proveedores": _texto("N8N_PROVEEDORES_URL"),
    "caja": _texto("N8N_CAJA_URL"),
    "national_soft": _texto("N8N_NATIONAL_SOFT_URL"),
    "reportes": _texto("N8N_REPORTES_URL"),
    "contacto": _texto("N8N_CONTACTO_URL"),
}
N8N_SECRETO = _texto("N8N_WEBHOOK_SECRET")
N8N_TIMEOUT = float(_texto("N8N_TIMEOUT", "8") or 8)

# Modelo de lenguaje opcional para redactar respuestas del asistente público.
OPENROUTER_API_KEY = _texto("OPENROUTER_API_KEY")
OPENROUTER_MODEL = _texto("OPENROUTER_MODEL")
# Varios modelos separados por coma: se usa el primero y se rota ante error de cuota.
OPENROUTER_MODELOS = [modelo.strip() for modelo in OPENROUTER_MODEL.split(",") if modelo.strip()]
OPENROUTER_BASE = _texto("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_TIMEOUT = float(_texto("OPENROUTER_TIMEOUT", "20") or 20)

# Destino permitido para envíos de reportes por correo (n8n + Gmail).
GMAIL_DESTINO = _texto("PUERTO_AM_GMAIL_DESTINO")

# Supabase: memoria de conversaciones. La clave se usa SOLO en el servidor.
SUPABASE_URL = _texto("SUPABASE_URL").rstrip("/")
SUPABASE_KEY = _texto("SUPABASE_KEY")
SUPABASE_TIMEOUT = float(_texto("SUPABASE_TIMEOUT", "8") or 8)
SUPABASE_HISTORIAL = int(_texto("SUPABASE_HISTORIAL", "12") or 12)


def usar_openrouter() -> bool:
    return bool(OPENROUTER_API_KEY and OPENROUTER_MODELOS)


def estado_integraciones() -> dict:
    """Estado booleano de cada conexión. No revela URLs ni secretos."""
    return {
        "n8n": {
            nombre: bool(url) for nombre, url in N8N.items()
        },
        "n8n_firmado": bool(N8N_SECRETO),
        "openrouter": usar_openrouter(),
        "gmail": bool(N8N.get("reportes") and GMAIL_DESTINO),
        "google_drive": bool(N8N.get("reportes")),
        "supabase": bool(SUPABASE_URL and SUPABASE_KEY),
        "datos_locales": RUTA_EXCEL.exists(),
    }


PENDIENTES = {
    "facturas": "Workflow de facturas CFDI (n8n → Drive)",
    "bancos": "Workflow de conciliación bancaria (n8n)",
    "pagos": "Workflow de pagos pendientes / cuentas por cobrar (n8n)",
    "proveedores": "Workflow de proveedores (n8n)",
    "caja": "Workflow de movimientos de caja (n8n)",
    "national_soft": "Conector de reportes National Soft (n8n)",
    "gastos": "Workflow de egresos operativos (n8n)",
    "gmail": "Envío de reportes por Gmail vía n8n",
    "google_drive": "Archivo de reportes en Google Drive vía n8n",
    "openrouter": "Modelo de lenguaje para redacción libre (OpenRouter)",
    "supabase": "Supabase: memoria de conversaciones por cliente",
}
