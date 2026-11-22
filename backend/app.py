"""Puerto A&M | Portal completo (público + panel administrativo).

Arrancar:
    python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import re
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import agentes, config, datos as datos_mod, integraciones, memoria, security, storage

SECRETO = config.SECRETO_SESION or security.secreto_persistente(config.RUTA_DATOS / ".session_secret")
LIMITE = security.Limite()
HASH_DUMMY = security.hash_contrasena("contrasena-inexistente-de-relleno")

CABECERAS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "img-src 'self' data: https:; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' data: https://fonts.gstatic.com; "
        "script-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; form-action 'self'"
    ),
}


@asynccontextmanager
async def vida(_app: FastAPI):
    config.RUTA_DATOS.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="Puerto A&M | Portal",
    description="Landing pública y panel financiero con agente de IA. Datos locales etiquetados como DEMO.",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    lifespan=vida,
)

app.mount("/assets", StaticFiles(directory=str(config.RUTA_FRONTEND)), name="assets")


@app.middleware("http")
async def cabeceras_y_origen(request: Request, llamar):
    if config.SOLO_LANDING and (
        request.url.path.startswith("/api/admin")
        or request.url.path in {"/admin", "/admin.html"}
    ):
        return JSONResponse({"error": "No encontrado"}, status_code=404)
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.url.path.startswith("/api/"):
        origen = request.headers.get("origin")
        if origen:
            host = request.headers.get("host", "")
            if urlsplit(origen).netloc != host:
                return JSONResponse({"error": "Origen no permitido"}, status_code=403)
    respuesta = await llamar(request)
    for clave, valor in CABECERAS.items():
        respuesta.headers.setdefault(clave, valor)
    if request.url.path.startswith("/admin"):
        respuesta.headers["Cache-Control"] = "no-store"
    return respuesta


@app.exception_handler(HTTPException)
async def error_http(_request: Request, exc: HTTPException):
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)


@app.exception_handler(Exception)
async def error_general(_request: Request, _exc: Exception):
    return JSONResponse({"error": "Ocurrió un error inesperado en el servidor."}, status_code=500)


def _ip(request: Request) -> str:
    return request.client.host if request.client else "desconocida"


def _usuario(request: Request) -> dict | None:
    return security.leer_sesion(request.cookies.get("pa_sesion", ""), SECRETO)


def _exigir_usuario(request: Request) -> dict:
    usuario = _usuario(request)
    if not usuario:
        raise HTTPException(401, "Sesión requerida")
    return usuario


async def _cuerpo(request: Request) -> dict:
    try:
        datos = await request.json()
    except Exception as exc:  # noqa: BLE001 - cuerpo inválido del cliente
        raise HTTPException(400, "Cuerpo JSON no válido") from exc
    return datos if isinstance(datos, dict) else {}


@app.get("/", response_class=HTMLResponse)
def pagina_publica():
    return FileResponse(config.RUTA_FRONTEND / "landing.html", media_type="text/html")


@app.get("/admin", response_class=HTMLResponse)
@app.get("/admin.html", response_class=HTMLResponse)
def pagina_admin():
    if config.SOLO_LANDING:
        raise HTTPException(404, "No encontrado")
    return FileResponse(config.RUTA_FRONTEND / "admin.html", media_type="text/html")


@app.get("/api/salud")
def salud():
    estado = config.estado_integraciones()
    return {
        "ok": True,
        "entorno": config.AMBIENTE,
        "datos": "demo",
        "datos_disponibles": estado["datos_locales"],
        "chat_n8n": estado["n8n"]["chat_publico"],
        "modelo_lenguaje": estado["openrouter"],
        "memoria": memoria.disponible(),
    }


@app.get("/api/config-publica")
def config_publica():
    return {
        "whatsapp": config.WHATSAPP_PUBLICO or None,
        "email": config.EMAIL_PUBLICO or None,
        "direccion": config.DIRECCION_PUBLICA or None,
        "horario": config.HORARIO_PUBLICO or None,
        "solo_landing": config.SOLO_LANDING,
        "hay_cuentas_admin": storage.hay_usuarios() if not config.SOLO_LANDING else False,
    }


@app.post("/api/chat/publico")
async def chat_publico(request: Request):
    if not LIMITE.permitir(f"chat:{_ip(request)}", config.LIMITE_CHAT):
        raise HTTPException(429, "Demasiados mensajes. Intenta de nuevo en un minuto.")
    cuerpo = await _cuerpo(request)
    mensaje = str(cuerpo.get("mensaje", "")).strip()
    if not mensaje or len(mensaje) > 500:
        raise HTTPException(400, "El mensaje debe tener entre 1 y 500 caracteres.")
    bruto = str(cuerpo.get("clienteId", ""))
    cliente = bruto if re.fullmatch(r"[A-Za-z0-9_-]{1,40}", bruto) else "anonimo"
    resultado = agentes.responder_publico(mensaje, cliente)
    storage.registrar_conversacion({
        "canal": "publico", "usuario": cliente, "mensaje": mensaje,
        "respuesta": resultado["respuesta"], "modo": resultado["modo"],
    })
    memoria.guardar(cliente, "user", mensaje, "publico")
    memoria.guardar(cliente, "asistente", resultado["respuesta"], resultado.get("modo", "local"))
    return resultado


@app.post("/api/contacto")
async def contacto(request: Request):
    if not LIMITE.permitir(f"contacto:{_ip(request)}", 6):
        raise HTTPException(429, "Demasiadas solicitudes. Intenta de nuevo en un minuto.")
    cuerpo = await _cuerpo(request)
    if str(cuerpo.get("website", "")).strip():  # honeypot
        return {"recibido": True, "id": "ok"}
    nombre = str(cuerpo.get("nombre", "")).strip()
    correo = str(cuerpo.get("correo", "")).strip()
    mensaje = str(cuerpo.get("mensaje", "")).strip()
    if not nombre or not mensaje or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", correo):
        raise HTTPException(400, "Nombre, correo válido y mensaje son obligatorios.")
    registro = storage.registrar_solicitud({
        "nombre": nombre, "correo": correo,
        "telefono": str(cuerpo.get("telefono", "")), "mensaje": mensaje,
    })
    if config.N8N.get("contacto"):
        try:
            integraciones.invocar("contacto", {"accion": "nueva_solicitud", "solicitud": registro})
        except integraciones.IntegracionError:
            pass  # la solicitud ya quedó guardada localmente
    return {"recibido": True, "id": registro["id"]}


@app.get("/api/admin/sesion")
def sesion(request: Request):
    usuario = _usuario(request)
    if not usuario:
        return {"autenticado": False}
    return {
        "autenticado": True,
        "correo": usuario.get("sub"),
        "rol": usuario.get("rol"),
        "expira": usuario.get("exp"),
    }


@app.post("/api/admin/login")
async def login(request: Request):
    if not LIMITE.permitir(f"login:{_ip(request)}", config.LIMITE_LOGIN):
        raise HTTPException(429, "Demasiados intentos. Espera un minuto.")
    cuerpo = await _cuerpo(request)
    correo = str(cuerpo.get("correo", "")).strip().casefold()
    contrasena = str(cuerpo.get("contrasena", ""))
    usuario = storage.buscar_usuario(correo)
    guardada = usuario["hash"] if usuario else HASH_DUMMY
    valido = security.verificar_contrasena(contrasena, guardada)
    if not usuario or not valido:
        raise HTTPException(401, "Correo o contraseña incorrectos.")
    token, expira = security.crear_sesion(usuario["correo"], usuario["rol"], SECRETO, config.HORAS_SESION)
    storage.registrar_auditoria({"accion": "login", "usuario": usuario["correo"], "detalle": "inicio de sesión"})
    respuesta = JSONResponse({"autenticado": True, "correo": usuario["correo"], "expira": expira})
    respuesta.set_cookie(
        "pa_sesion", token, max_age=config.HORAS_SESION * 3600, httponly=True,
        samesite="lax", secure=config.COOKIES_SEGURAS, path="/",
    )
    return respuesta


@app.post("/api/admin/logout")
def logout(request: Request):
    usuario = _usuario(request)
    if usuario:
        storage.registrar_auditoria({"accion": "logout", "usuario": usuario.get("sub", ""), "detalle": "cierre de sesión"})
    respuesta = JSONResponse({"autenticado": False})
    respuesta.delete_cookie("pa_sesion", path="/")
    return respuesta


def _filtros_de(request: Request) -> dict:
    q = request.query_params
    try:
        return datos_mod.validar_filtros(q.get("desde"), q.get("hasta"), q.get("producto"), q.get("categoria"))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/admin/datos")
def admin_datos(request: Request):
    _exigir_usuario(request)
    payload = datos_mod.payload(_filtros_de(request))
    payload["alertas"] = datos_mod.anomalias(payload)
    payload["demo"] = True
    return payload


@app.get("/api/admin/alertas")
def admin_alertas(request: Request):
    _exigir_usuario(request)
    return {"alertas": datos_mod.anomalias(datos_mod.payload(_filtros_de(request)))}


@app.get("/api/admin/exportar/{formato}")
def admin_exportar(formato: str, request: Request):
    _exigir_usuario(request)
    if formato not in {"csv", "xlsx"}:
        raise HTTPException(404, "Formato no soportado")
    payload = datos_mod.payload(_filtros_de(request))
    usuario = _usuario(request)
    storage.registrar_auditoria({
        "accion": f"exportar_{formato}", "usuario": usuario.get("sub", ""),
        "detalle": f"{payload['registros_filtrados']} registros",
    })
    if formato == "csv":
        return Response(
            datos_mod.exportar_csv(payload), media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="Puerto_AM_reporte.csv"'},
        )
    return Response(
        datos_mod.exportar_excel(payload),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="Puerto_AM_reporte.xlsx"'},
    )


@app.post("/api/admin/chat")
async def admin_chat(request: Request):
    usuario = _exigir_usuario(request)
    if not LIMITE.permitir(f"adminchat:{_ip(request)}", config.LIMITE_CHAT):
        raise HTTPException(429, "Demasiados mensajes. Intenta de nuevo en un minuto.")
    cuerpo = await _cuerpo(request)
    mensaje = str(cuerpo.get("mensaje", "")).strip()
    if not mensaje or len(mensaje) > 500:
        raise HTTPException(400, "El mensaje debe tener entre 1 y 500 caracteres.")
    try:
        filtros = datos_mod.validar_filtros(
            cuerpo.get("desde"), cuerpo.get("hasta"), cuerpo.get("producto"), cuerpo.get("categoria")
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    try:
        payload = datos_mod.payload(filtros)
    except datos_mod.ExcelError as exc:
        raise HTTPException(503, f"No se pudo leer la base de datos: {exc}") from exc
    resultado = agentes.responder_financiero(mensaje, payload)
    storage.registrar_conversacion({
        "canal": "admin", "usuario": usuario.get("sub", "admin"),
        "mensaje": mensaje, "respuesta": resultado["respuesta"], "modo": resultado["modo"],
    })
    return resultado


@app.get("/api/admin/integraciones")
def admin_integraciones(request: Request):
    _exigir_usuario(request)
    return integraciones.estado_detallado()


@app.get("/api/admin/solicitudes")
def admin_solicitudes(request: Request):
    _exigir_usuario(request)
    return {"solicitudes": storage.ultimos("solicitudes.json", 50)}


@app.get("/api/admin/auditoria")
def admin_auditoria(request: Request):
    _exigir_usuario(request)
    return {"eventos": storage.ultimos("auditoria.json", 50)}
