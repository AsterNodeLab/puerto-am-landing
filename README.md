# Puerto A&M | Portal público + Panel financiero

Aplicación completa de un solo proceso: landing pública, panel administrativo privado, agente financiero en lenguaje natural y adaptadores hacia n8n / Google Drive / Gmail.

**Estado de los datos:** la única fuente disponible es `data/Puerto_AM_Base_Datos_DEMO.xlsx` (360 ventas, ene–mar 2026), un archivo **ficticio** heredado del proyecto `puerto-am-bi`. El panel lo etiqueta como DEMO en todo momento. No hay datos operativos reales de CFDI, bancos, egresos, caja, proveedores ni National Soft: el agente **no inventa cifras** para esos dominios, indica qué workflow falta y espera a que se conecte.

## Despliegue público (GitHub Pages)

El repositorio público contiene todo el proyecto, pero GitHub Pages publica **sólo**
la landing (`frontend/landing.html`) mediante `.github/workflows/deploy-pages.yml`.
El backend, el panel y `.env` no se suben al sitio.

En un dominio `*.github.io` el script detecta el modo estático (`ES_STATICO`): el
chat y el formulario muestran un aviso en lugar de llamar a una API inexistente.
Para volver a tener IA hay que desplegar el backend FastAPI en otro servicio y
apuntar el frontend a esa URL; la clave de OpenRouter nunca debe ir al navegador.

## Modo actual: sólo landing + chat

`PUERTO_AM_SOLO_LANDING=1` está activo en el `.env`. En este modo:

- La landing y su chat de servicio al cliente funcionan normalmente.
- El chat **no llama a ningún webhook de n8n**: usa directamente OpenRouter y, si falla, la respuesta local de `knowledge/restaurante.md`.
- `/admin` y todas las rutas `/api/admin/*` devuelven 404, y el enlace «Área administrativa» no aparece en el pie de página.
- No se borra nada: para reactivar el panel y los workflows, cambia esa variable a `0` y reinicia.

## Menú demo, alma y atención autónoma

- `SOUL.md`: personalidad de **Marina**, la anfitriona. Define el tono cálido y
  persuasivo, las reglas de reserva/pedido y **incluye el menú costero completo** con
  sus precios ilustrativos. El agente lo carga en el prompt.
- `knowledge/menu-demo.md`: fuente editable del menú. La landing lo muestra en
  `#menu` con filtros por categoría, y el chat lo usa para recomendar y calcular.
- `backend/flujo.py`: reservas y pedidos en varias vueltas, sin n8n y sin cobros.
  - Reserva: «Quiero reservar mañana a las 20:00 para 4» → repite los datos →
    «sí» → guarda la solicitud.
  - Pedido: «Me llevo 2 ceviches y un pescado a la talla» → muestra el total
    ($625 MXN en la demo) → «confirmar» → guarda la solicitud.
  - Todo queda en `data/solicitudes.json` con `tipo: reserva | pedido`.

Los precios son ilustrativos y el asistente siempre lo aclara. No se piden tarjetas,
no se promete envío y no se inventan platillos fuera del menú demo.

## Memoria en Supabase

El chat recuerda a cada cliente por `clienteId`: guarda cada mensaje y cada respuesta,
y envía las últimas 12 intervenciones al modelo para dar continuidad (nombre,
preferencias, lo ya acordado). También persiste los borradores de reserva y pedido,
así que no se pierden al reiniciar. Si Supabase no está configurado o falla, todo
sigue funcionando con el archivo local `data/conversaciones.json`.

Puesta en marcha:

1. En el dashboard de Supabase, abre **SQL Editor** y ejecuta `supabase/schema.sql`.
   Crea `pa_memoria` y `pa_clientes` con RLS activo.
2. En **Project Settings → API**, copia el **Project URL** y la **service_role key**.
3. Pégalos en `.env` como `SUPABASE_URL` y `SUPABASE_KEY` (nunca en el frontend).
4. Reinicia el servidor. `/api/salud` debe devolver `"memoria": true`.
5. Opcional: `python -m backend.migrar_memoria` sube el historial local acumulado.

La service_role key sortea RLS y sólo vive en el servidor; no se crean políticas
públicas, así que nadie puede leer conversaciones desde el navegador.

## Arrancar

```bat
iniciar.bat
```

Abre `http://127.0.0.1:8000` (landing) y `http://127.0.0.1:8000/admin` (panel). El script usa el entorno virtual del proyecto o el de `puerto-am-bi` si ya existe; si no, crea uno e instala `requirements.txt`.

Crear la primera cuenta administradora (sin contraseñas en el código):

```bat
python -m backend.setup_admin --correo admin@ejemplo.com
```

La contraseña se pide por consola, se guarda como hash scrypt y nunca se imprime. Si no hay cuentas, el login lo indica.

## Qué está implementado

| Pieza | Estado | Detalle |
|---|---|---|
| Landing pública | Funcional | Hero, experiencia, servicios, FAQ, formulario de contacto y chat. |
| Asistente público | Funcional | Responde desde `knowledge/restaurante.md`, rechaza preguntas financieras, registra solicitudes. Cadena de proveedores: n8n → OpenRouter → resolución local. |
| Panel administrativo | Funcional | 8 KPIs, 5 gráficas, filtros, tabla paginada, alertas y exportaciones, Calculado con el lector `backend/excel_reader.py` reutilizado del proyecto existente. |
| Agente financiero | Funcional | Consulta ventas, costos, utilidad, márgenes, productos, metas y anomalías con cifras reales del Excel. Explica indicadores. |
| Autenticación | Funcional | Sesión firmada HMAC-SHA256 en cookie `httpOnly`/`SameSite=Lax`, hash scrypt, límite de intentos y validación de `Origin`. |
| Seguridad | Funcional | CSP, `X-Frame-Options`, `nosniff`, `Referrer-Policy`, separación total pública/privada, secretos sólo en servidor. |
| n8n / Drive / Gmail | **Adaptadores listos, sin conectar** | Requieren URLs de webhook y secretos en `.env`. El panel muestra «Pendiente» hasta que se configuren. |

## Integraciones pendientes

No existen URLs de webhook ni credenciales en este entorno, así que estas conexiones quedan declaradas pero inactivas:

- `N8N_PUBLIC_CHAT_URL` — asistente público.
- `N8N_FACTURAS_URL` — facturas CFDI.
- `N8N_BANCOS_URL` — conciliación bancaria.
- `N8N_PAGOS_URL` — pagos pendientes.
- `N8N_PROVEEDORES_URL` — proveedores.
- `N8N_CAJA_URL` — movimientos de caja.
- `N8N_NATIONAL_SOFT_URL` — reportes de National Soft.
- `N8N_FINANZAS_URL` — consultas financieras externas.
- `N8N_REPORTES_URL` + `PUERTO_AM_GMAIL_DESTINO` — reportes en Drive y envío por Gmail.
- `N8N_CONTACTO_URL` — reenvío de solicitudes del formulario.
- `OPENROUTER_API_KEY` / `OPENROUTER_MODEL` — redacción libre del asistente público. En la demo ya están configurados y funcionando; ver detalle abajo.
- Datos públicos confirmados del restaurante: `PUERTO_AM_WHATSAPP`, `PUERTO_AM_EMAIL`, `PUERTO_AM_DIRECCION`, `PUERTO_AM_HORARIO` (si no se definen, la landing no muestra dirección, teléfono ni horarios inventados).

Copia `.env.example` como `.env` y completa sólo lo que vayas a usar. `.env` está en `.gitignore`.

### Contrato de los webhooks

Cada llamada es `POST` con JSON y, si defines `N8N_WEBHOOK_SECRET`, la cabecera `X-Puerto-Signature` contiene el HMAC-SHA256 del cuerpo en hexadecimal. Verificación en n8n (nodo Code):

```javascript
const crypto = require('crypto');
const firma = crypto.createHmac('sha256', $env.N8N_WEBHOOK_SECRET)
  .update($request.bodyRaw ?? JSON.stringify($json))
  .digest('hex');
if (firma !== $headers['x-puerto-signature']) throw new Error('Firma inválida');
return $input.all();
```

Cuerpo enviado: `{ "accion": "...", "mensaje": "...", ... }`. La respuesta puede ser `{"respuesta": "texto"}` o `{"datos": ...}`; el agente la muestra con etiqueta de origen n8n. Para reportes se envía `accion: "generar_y_enviar_reporte"` y el destino **siempre** se toma de `PUERTO_AM_GMAIL_DESTINO`, nunca del chat.

## Modelos gratuitos de OpenRouter (demo)

El `.env` local contiene una clave **de demostración** que el usuario proporcionó. Nunca se envía al navegador ni se devuelve en ninguna API: `/api/salud` sólo reporta `modelo_lenguaje: true`.

Modelos verificados con esa clave el 2026-11-22 (todos respondieron HTTP 200 con «OK»):

1. `openrouter/free` — enrutador gratuito de OpenRouter; es el preferido.
2. `liquid/lfm-3-1.7b:free`
3. `particle-ai/particle-1:free`
4. `inclusionai/ling-3.2-flash:free`

`google/gemma-4-31b-it:free` y `nvidia/nemotron-3.5-lightning:free` se descartaron: el primero respondió 429 y el segundo devolvía `content` vacío incluso con 900 tokens. `inclusionai/ling-3.2-flash:free` quedó de último porque agotó su cuota durante las pruebas. Si un modelo falla por cuota o disponibilidad, el servidor rota automáticamente al siguiente; las respuestas se reutilizan 10 minutos en caché para cuidar el límite diario. Los modelos gratuitos razonan antes de responder, por eso `max_tokens` es 900: con 300 el razonamiento agotaba el límite y `content` llegaba vacío. Sus topes diarios no se pueden eludir: para uso intensivo, añade otro modelo a la lista o cambia a uno de pago.

El agente financiero del panel **no** delega las cifras al modelo: calcula con el Excel y muestra la fuente. El modelo sólo redacta las respuestas del asistente público.

## API

Pública: `GET /`, `/admin`, `/api/salud`, `/api/config-publica`; `POST /api/chat/publico`, `/api/contacto`.

Privada (cookie de sesión): `GET /api/admin/sesion`, `/api/admin/datos`, `/api/admin/alertas`, `/api/admin/integraciones`, `/api/admin/solicitudes`, `/api/admin/auditoria`, `GET /api/admin/exportar/{csv|xlsx}`; `POST /api/admin/login`, `/api/admin/logout`, `/api/admin/chat`.

## Producción

- Define `PUERTO_AM_ENV=production`, `PUERTO_AM_SESSION_SECRET` y `PUERTO_AM_SECURE_COOKIES=1` detrás de HTTPS.
- Sustituye el almacenamiento JSON (`backend/storage.py`) por PostgreSQL cuando haya varias instancias; el limitador en memoria por Redis.
- Sirve con un reverse proxy (TLS) y mantén `.env` fuera del repositorio.
- Revisa que los workflows de n8n validen la firma antes de ejecutar acciones.

## Verificación realizada

22/22 pruebas de integración del portal completo y 15/15 pruebas del modo sólo landing: menú visible, admin oculto (404), reserva en dos vueltas, pedido con total real y confirmación guardada, recomendaciones con menú y privacidad financiera. JavaScript validado con `node --check`; HTML/CSS/JS sin referencias rotas. No se tomaron capturas: este entorno no tiene herramienta de navegador.
