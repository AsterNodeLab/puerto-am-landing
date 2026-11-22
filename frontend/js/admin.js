/* Puerto A&M | Panel administrativo */

(function () {
  'use strict';

  var $ = function (id) { return document.getElementById(id); };
  var COLOR = {
    navy: '#0B2545', accent: '#3B6FE8', gold: '#C9A227',
    muted: '#6B7C8F', Verde: '#0E9F6E', rojo: '#D2543B'
  };
  var estado = {
    datos: null, integraciones: null,
    pagina: 1, tamano: 10, graficas: {}, enviando: false
  };

  var TITULOS = {
    resumen: 'Resumen ejecutivo', ventas: 'Ventas', analisis: 'Análisis',
    alertas: 'Alertas', asistente: 'Agente financiero',
    integraciones: 'Integraciones', solicitudes: 'Solicitudes'
  };

  function mxn(valor) {
    if (valor === null || valor === undefined) return '—';
    return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', minimumFractionDigits: 2 }).format(valor);
  }
  function numero(valor) {
    if (valor === null || valor === undefined) return '—';
    return new Intl.NumberFormat('es-MX', { maximumFractionDigits: 0 }).format(valor);
  }
  function porcentaje(valor) {
    return valor === null || valor === undefined ? '—' : Number(valor).toFixed(1) + '%';
  }
  function fechaCorta(texto) {
    if (!texto) return '—';
    var partes = String(texto).slice(0, 10).split('-');
    return partes.length === 3 ? partes[2] + '/' + partes[1] + '/' + partes[0] : texto;
  }
  function fechaHora(texto) {
    if (!texto) return '—';
    var f = new Date(texto);
    return isNaN(f.getTime()) ? texto : f.toLocaleString('es-MX', { dateStyle: 'short', timeStyle: 'short' });
  }

  function avisar(texto) {
    var toast = $('toast');
    if (!toast) return;
    toast.textContent = texto;
    toast.classList.add('visible');
    clearTimeout(avisar.temporizador);
    avisar.temporizador = setTimeout(function () { toast.classList.remove('visible'); }, 3200);
  }

  function parametros() {
    var p = new URLSearchParams();
    [['desde', 'f-desde'], ['hasta', 'f-hasta'], ['producto', 'f-producto'], ['categoria', 'f-categoria']]
      .forEach(function (par) {
        var elemento = $(par[1]);
        if (elemento && elemento.value) p.set(par[0], elemento.value);
      });
    return p;
  }

  function ponerTexto(id, valor) {
    var elemento = $(id);
    if (elemento) elemento.textContent = valor;
  }

  function opcionesSelect(id, lista, etiqueta) {
    var select = $(id);
    if (!select) return;
    var actual = select.value;
    select.replaceChildren();
    var primero = document.createElement('option');
    primero.value = '';
    primero.textContent = etiqueta;
    select.appendChild(primero);
    (lista || []).forEach(function (valor) {
      var opcion = document.createElement('option');
      opcion.value = valor;
      opcion.textContent = valor;
      select.appendChild(opcion);
    });
    if ((lista || []).indexOf(actual) !== -1) select.value = actual;
  }

  function dibujarGrafica(id, config) {
    var lienzo = $(id);
    if (!lienzo || typeof Chart === 'undefined') return;
    if (estado.graficas[id]) estado.graficas[id].destroy();
    estado.graficas[id] = new Chart(lienzo, config);
  }

  function baseLinea(titulos, conjunto, opciones) {
    return {
      type: 'line',
      data: { labels: titulos, datasets: conjunto },
      options: Object.assign({
        responsive: true, maintainAspectRatio: false, interaction: { intersect: false, mode: 'index' },
        plugins: { legend: { labels: { usePointStyle: true, boxWidth: 8, font: { size: 11 } } } },
        scales: {
          x: { grid: { display: false }, ticks: { font: { size: 11 } } },
          y: { grid: { color: 'rgba(120,140,160,.14)' }, ticks: { font: { size: 11 }, callback: function (v) { return '$' + new Intl.NumberFormat('es-MX', { notation: 'compact' }).format(v); } } }
        }
      }, opciones || {})
    };
  }

  function pintarGraficas(datos) {
    var g = datos.graficos || {};
    var evol = g.evolucion || {};
    dibujarGrafica('chart-evolucion', baseLinea(evol.etiquetas || [], [
      { label: 'Ventas', data: evol.ventas || [], borderColor: COLOR.accent, backgroundColor: 'rgba(59,111,232,.12)', fill: true, tension: .35, pointRadius: 3, borderWidth: 2 },
      { label: 'Utilidad', data: evol.utilidad || [], borderColor: COLOR.gold, backgroundColor: 'transparent', tension: .35, pointRadius: 3, borderWidth: 2 }
    ]));

    var cat = g.categorias || {};
    dibujarGrafica('chart-categorias', {
      type: 'doughnut',
      data: {
        labels: cat.etiquetas || [],
        datasets: [{ data: cat.valores || [], backgroundColor: [COLOR.navy, COLOR.accent, COLOR.gold, COLOR.muted, '#7FA8E8'], borderWidth: 0, hoverOffset: 6 }]
      },
      options: { responsive: true, maintainAspectRatio: false, cutout: '68%', plugins: { legend: { position: 'bottom', labels: { usePointStyle: true, boxWidth: 8, font: { size: 11 } } } } }
    });

    var metas = g.metas_resultados || {};
    dibujarGrafica('chart-metas', baseLinea(metas.etiquetas || [], [
      { label: 'Meta', data: metas.metas || [], borderColor: COLOR.muted, borderDash: [5, 4], tension: .3, pointRadius: 3, borderWidth: 2 },
      { label: 'Real', data: metas.resultados || [], borderColor: COLOR.accent, backgroundColor: 'rgba(59,111,232,.12)', fill: true, tension: .3, pointRadius: 3, borderWidth: 2 }
    ]));

    var prod = g.productos_top || {};
    dibujarGrafica('chart-productos', {
      type: 'bar',
      data: {
        labels: prod.etiquetas || [],
        datasets: [{ label: 'Ingresos', data: prod.valores || [], backgroundColor: COLOR.navy, borderRadius: 5, maxBarThickness: 34 }]
      },
      options: {
        responsive: true, maintainAspectRatio: false, indexAxis: 'y',
        plugins: { legend: { display: false } },
        scales: { x: { grid: { color: 'rgba(120,140,160,.14)' }, ticks: { font: { size: 10 }, callback: function (v) { return '$' + new Intl.NumberFormat('es-MX', { notation: 'compact' }).format(v); } } }, y: { grid: { display: false }, ticks: { font: { size: 10 } } } }
      }
    });

    var ing = g.ingresos_costos || {};
    dibujarGrafica('chart-ingresos-costos', baseLinea(ing.etiquetas || [], [
      { label: 'Ingresos', data: ing.ingresos || [], borderColor: COLOR.accent, backgroundColor: 'rgba(59,111,232,.12)', fill: true, tension: .3, pointRadius: 3, borderWidth: 2 },
      { label: 'Costos', data: ing.costos || [], borderColor: COLOR.rojo, backgroundColor: 'transparent', tension: .3, pointRadius: 3, borderWidth: 2 }
    ]));
  }

  function pintarKpis(datos) {
    var k = datos.kpis || {};
    ponerTexto('kpi-ventas', mxn(k.ventas_totales));
    ponerTexto('kpi-pedidos', numero(k.pedidos));
    ponerTexto('kpi-ticket', mxn(k.ticket_promedio));
    ponerTexto('kpi-unidades', numero(k.unidades));
    ponerTexto('kpi-costos', mxn(k.costos));
    ponerTexto('kpi-utilidad', mxn(k.utilidad_bruta));
    ponerTexto('kpi-margen', porcentaje(k.margen_bruto));
    ponerTexto('kpi-crecimiento', k.crecimiento_mensual === null ? '—' : (k.crecimiento_mensual > 0 ? '+' : '') + porcentaje(k.crecimiento_mensual));
    var op = datos.opciones || {};
    ponerTexto('periodo-texto', (op.fecha_min || '—') + ' — ' + (op.fecha_max || '—'));
    var fuente = datos.fuente || {};
    ponerTexto('fuente-texto', (fuente.archivo || '—') + ' · ' + (fuente.registros_totales || 0) + ' registros');

    var filtros = datos.filtros || {};
    var activos = [filtros.desde, filtros.hasta, filtros.producto, filtros.categoria].filter(Boolean);
    ponerTexto('filtros-activos', activos.length ? activos.join(' · ') : 'Sin filtros · ' + (datos.registros_filtrados || 0) + ' registros');
  }

  function pintarAlertas(alertas) {
    var lista = $('alertas-lista');
    var resumen = $('alertas-resumen');
    var contador = $('nav-alertas');
    if (!lista) return;
    lista.replaceChildren();
    (alertas || []).forEach(function (alerta) {
      var articulo = document.createElement('article');
      articulo.className = 'alerta' + (alerta.severidad === 'alta' ? ' alta' : '');
      var icono = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      icono.setAttribute('class', 'icon'); icono.setAttribute('aria-hidden', 'true');
      var uso = document.createElementNS('http://www.w3.org/2000/svg', 'use');
      uso.setAttribute('href', '#i-warn'); icono.appendChild(uso);
      var cuerpo = document.createElement('div');
      var titulo = document.createElement('h3'); titulo.textContent = alerta.titulo;
      var detalle = document.createElement('p'); detalle.textContent = alerta.detalle;
      cuerpo.append(titulo, detalle);
      var sev = document.createElement('span'); sev.className = 'severidad'; sev.textContent = alerta.severidad;
      articulo.append(icono, cuerpo, sev);
      lista.appendChild(articulo);
    });
    if (!(alertas || []).length) {
      var vacio = document.createElement('div');
      vacio.className = 'vacio-alertas';
      vacio.textContent = 'No detecté desviaciones relevantes con los datos disponibles.';
      lista.appendChild(vacio);
    }
    if (contador) {
      contador.hidden = !(alertas || []).length;
      contador.textContent = String((alertas || []).length);
    }
    if (resumen) {
      resumen.hidden = !(alertas || []).length;
      if ((alertas || []).length) {
        resumen.replaceChildren();
        var ico = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        ico.setAttribute('class', 'icon'); ico.setAttribute('aria-hidden', 'true');
        var u = document.createElementNS('http://www.w3.org/2000/svg', 'use'); u.setAttribute('href', '#i-warn'); ico.appendChild(u);
        var txt = document.createElement('span');
        txt.textContent = 'Hay ' + alertas.length + ' señal(es) que conviene revisar: ' + alertas[0].titulo + '.';
        var boton = document.createElement('button');
        boton.type = 'button'; boton.textContent = 'Ver alertas';
        boton.addEventListener('click', function () { mostrarSeccion('alertas'); });
        resumen.append(ico, txt, boton);
      }
    }
  }

  function pintarRanking(datos) {
    var lista = $('ranking-productos');
    if (!lista) return;
    lista.replaceChildren();
    var productos = datos.top_productos || [];
    var maximo = productos.reduce(function (m, p) { return Math.max(m, p.ingresos || 0); }, 0) || 1;
    productos.forEach(function (producto, indice) {
      var li = document.createElement('li');
      var pos = document.createElement('span'); pos.className = 'pos'; pos.textContent = String(indice + 1).padStart(2, '0');
      var cuerpo = document.createElement('div');
      var nombre = document.createElement('strong'); nombre.style.fontSize = '.82rem'; nombre.textContent = producto.producto;
      var barra = document.createElement('div'); barra.className = 'barra';
      var relleno = document.createElement('i'); relleno.style.width = Math.round((producto.ingresos / maximo) * 100) + '%';
      barra.appendChild(relleno); cuerpo.append(nombre, barra);
      var monto = document.createElement('span'); monto.className = 'monto'; monto.textContent = mxn(producto.ingresos);
      li.append(pos, cuerpo, monto); lista.appendChild(li);
    });
  }

  function pintarMetas(datos) {
    var lista = $('metas-lista');
    if (!lista) return;
    lista.replaceChildren();
    (datos.metas_detalle || []).forEach(function (meta) {
      var li = document.createElement('li');
      var etiqueta = document.createElement('span'); etiqueta.textContent = meta.etiqueta;
      var valor = document.createElement('strong'); valor.textContent = porcentaje(meta.cumplimiento);
      li.append(etiqueta, valor); lista.appendChild(li);
    });
  }

  function pintarTabla(datos) {
    var cuerpo = $('tabla-ventas');
    if (!cuerpo) return;
    estado.pagina = Math.max(1, estado.pagina);
    var filas = datos.ventas || [];
    var inicio = (estado.pagina - 1) * estado.tamano;
    var pagina = filas.slice(inicio, inicio + estado.tamano);
    cuerpo.replaceChildren();
    if (!pagina.length) {
      var tr = document.createElement('tr');
      var td = document.createElement('td'); td.colSpan = 9; td.className = 'vacio'; td.textContent = 'No hay registros con los filtros aplicados.';
      tr.appendChild(td); cuerpo.appendChild(tr);
    }
    pagina.forEach(function (venta) {
      var tr = document.createElement('tr');
      [fechaCorta(venta.fecha), venta.pedido, venta.producto, venta.categoria,
        numero(venta.cantidad), mxn(venta.ingreso), mxn(venta.costo_total), mxn(venta.utilidad), venta.canal || '—']
        .forEach(function (valor, i) {
          var td = document.createElement('td');
          if (i >= 4 && i <= 7) td.className = 'num';
          td.textContent = valor; tr.appendChild(td);
        });
      cuerpo.appendChild(tr);
    });
    var totalPaginas = Math.max(1, Math.ceil(filas.length / estado.tamano));
    ponerTexto('contador-ventas', numero(filas.length));
    ponerTexto('tabla-info', 'Mostrando ' + (inicio + 1) + '–' + Math.min(inicio + estado.tamano, filas.length) + ' de ' + filas.length + ' · página ' + estado.pagina + ' de ' + totalPaginas);
  }

  function cargarDatos() {
    var estadoEl = $('estado');
    var textoEstado = $('estado-texto');
    if (textoEstado) textoEstado.textContent = 'Cargando datos…';
    fetch('/api/admin/datos?' + parametros().toString(), { credentials: 'same-origin' })
      .then(function (respuesta) {
        if (respuesta.status === 401) { cerrarSesion(true); throw new Error('Sesión expirada'); }
        if (!respuesta.ok) throw new Error('No se pudo cargar la base');
        return respuesta.json();
      })
      .then(function (datos) {
        estado.datos = datos;
        estado.pagina = 1;
        pintarKpis(datos);
        pintarGraficas(datos);
        pintarAlertas(datos.alertas || []);
        pintarRanking(datos);
        pintarMetas(datos);
        pintarTabla(datos);
        opcionesSelect('f-producto', datos.opciones.productos, 'Todos los productos');
        opcionesSelect('f-categoria', datos.opciones.categorias, 'Todas las categorías');
        var desde = $('f-desde'), hasta = $('f-hasta');
        if (desde && !desde.min) desde.min = datos.opciones.fecha_min;
        if (desde && !desde.max) desde.max = datos.opciones.fecha_max;
        if (hasta && !hasta.min) hasta.min = datos.opciones.fecha_min;
        if (hasta && !hasta.max) hasta.max = datos.opciones.fecha_max;
        if (estadoEl) estadoEl.classList.remove('error');
        if (textoEstado) textoEstado.textContent = 'Base conectada · DEMO';
      })
      .catch(function (error) {
        if (textoEstado) textoEstado.textContent = 'Sin conexión con la base';
        if (estadoEl) estadoEl.classList.add('error');
        if (error.message !== 'Sesión expirada') avisar('No se pudo cargar la base de datos.');
      });
  }

  function mostrarSeccion(nombre) {
    document.querySelectorAll('.panel-seccion').forEach(function (seccion) {
      seccion.hidden = seccion.id !== nombre;
      seccion.classList.toggle('activa', seccion.id === nombre);
    });
    document.querySelectorAll('.nav-link').forEach(function (enlace) {
      enlace.classList.toggle('activo', enlace.getAttribute('data-seccion') === nombre);
    });
    ponerTexto('titulo-seccion', TITULOS[nombre] || nombre);
    var barra = $('sidebar');
    if (barra) barra.classList.remove('abierta');
    var overlay = $('overlay');
    if (overlay) overlay.hidden = true;
  }

  function cerrarSesion(sinRecargar) {
    fetch('/api/admin/logout', { method: 'POST', credentials: 'same-origin' })
      .finally(function () {
        if (sinRecargar) {
          var app = $('app'), login = $('login-pantalla');
          if (app) app.hidden = true;
          if (login) login.hidden = false;
        } else {
          window.location.reload();
        }
      });
  }

  /* Chat del agente */
  function agregarMensaje(texto, clase) {
    var cuerpo = $('chat-mensajes-admin');
    if (!cuerpo) return;
    var burbuja = document.createElement('div');
    burbuja.className = 'mensaje ' + clase;
    burbuja.textContent = texto;
    cuerpo.appendChild(burbuja);
    cuerpo.scrollTop = cuerpo.scrollHeight;
    return burbuja;
  }

  function typing() {
    var cuerpo = $('chat-mensajes-admin');
    var elemento = document.createElement('div');
    elemento.className = 'mensaje bot chat-typing';
    for (var i = 0; i < 3; i += 1) elemento.appendChild(document.createElement('i'));
    cuerpo.appendChild(elemento);
    cuerpo.scrollTop = cuerpo.scrollHeight;
    return elemento;
  }

  function pintarSugerencias(lista) {
    var contenedor = $('chat-sugerencias-admin');
    if (!contenedor) return;
    contenedor.replaceChildren();
    (lista || []).slice(0, 4).forEach(function (texto) {
      var boton = document.createElement('button');
      boton.type = 'button'; boton.textContent = texto;
      boton.addEventListener('click', function () { preguntar(texto); });
      contenedor.appendChild(boton);
    });
  }

  function preguntar(texto) {
    var mensaje = String(texto || '').trim();
    if (!mensaje || estado.enviando) return;
    estado.enviando = true;
    agregarMensaje(mensaje, 'user');
    var input = $('chat-input-admin');
    if (input) input.value = '';
    var boton = $('chat-enviar-admin');
    if (boton) boton.disabled = true;
    var espera = typing();
    var cuerpo = JSON.stringify(Object.assign({ mensaje: mensaje }, Object.fromEntries(parametros())));

    fetch('/api/admin/chat', {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' }, body: cuerpo
    })
      .then(function (respuesta) {
        if (!respuesta.ok) throw new Error('Error');
        return respuesta.json();
      })
      .then(function (datos) {
        espera.remove();
        var burbuja = agregarMensaje(datos.respuesta || 'Sin respuesta.', 'bot');
        var nota = document.createElement('span');
        nota.className = 'fuente-chat';
        nota.textContent = 'Modo: ' + (datos.modo || 'local') + ' · Intención: ' + (datos.accion || 'general');
        burbuja.appendChild(nota);
        pintarSugerencias(datos.sugerencias);
      })
      .catch(function () {
        espera.remove();
        agregarMensaje('No pude completar la consulta. Revisa la conexión e inténtalo de nuevo.', 'error');
      })
      .finally(function () {
        estado.enviando = false;
        if (boton) boton.disabled = false;
        if (input) input.focus();
      });
  }

  /* Integraciones */
  function cargarIntegraciones() {
    fetch('/api/admin/integraciones', { credentials: 'same-origin' })
      .then(function (r) { return r.ok ? r.json() : {}; })
      .then(function (info) {
        estado.integraciones = info;
        var grid = $('integraciones-grid');
        if (!grid) return;
        grid.replaceChildren();
        var n = info.n8n || {};
        var tarjetas = [
          ['Base de datos local', info.datos_locales, 'Excel del panel'],
          ['n8n · chat público', n.chat_publico, 'Atención en landing'],
          ['n8n · finanzas', n.finanzas, 'Consultas externas'],
          ['n8n · facturas CFDI', n.facturas, 'Comprobantes'],
          ['n8n · bancos', n.bancos, 'Conciliación'],
          ['n8n · pagos', n.pagos, 'Cuentas por cobrar'],
          ['n8n · proveedores', n.proveedores, 'Catálogo'],
          ['n8n · caja', n.caja, 'Movimientos'],
          ['n8n · National Soft', n.national_soft, 'Reportes'],
          ['n8n · reportes / Drive', n.reportes, 'PDF y Excel'],
          ['Gmail', info.gmail, 'Envío autorizado'],
          ['Modelo de lenguaje', info.modelo_lenguaje, 'Redacción libre']
        ];
        tarjetas.forEach(function (tarjeta) {
          var articulo = document.createElement('article');
          articulo.className = 'integracion';
          var icono = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
          icono.setAttribute('class', 'icon'); icono.setAttribute('aria-hidden', 'true');
          var uso = document.createElementNS('http://www.w3.org/2000/svg', 'use');
          uso.setAttribute('href', '#i-plug'); icono.appendChild(uso);
          var texto = document.createElement('div');
          var titulo = document.createElement('strong'); titulo.textContent = tarjeta[0];
          var sub = document.createElement('small'); sub.textContent = tarjeta[2];
          texto.append(titulo, sub);
          var chip = document.createElement('span');
          chip.className = 'estado-chip ' + (tarjeta[1] ? 'si' : 'no');
          chip.textContent = tarjeta[1] ? 'Conectado' : 'Pendiente';
          articulo.append(icono, texto, chip);
          grid.appendChild(articulo);
        });
        var pendientes = $('pendientes-lista');
        if (pendientes) {
          pendientes.replaceChildren();
          (info.pendientes || []).forEach(function (item) {
            var li = document.createElement('li'); li.textContent = item.nombre; pendientes.appendChild(li);
          });
        }
      })
      .catch(function () { /* el panel sigue funcionando sin este detalle */ });
  }

  function cargarSolicitudes() {
    fetch('/api/admin/solicitudes', { credentials: 'same-origin' })
      .then(function (r) { return r.ok ? r.json() : { solicitudes: [] }; })
      .then(function (info) {
        var cuerpo = $('solicitudes-tabla');
        if (!cuerpo) return;
        cuerpo.replaceChildren();
        var lista = info.solicitudes || [];
        if (!lista.length) {
          var tr = document.createElement('tr');
          var td = document.createElement('td'); td.colSpan = 5; td.className = 'vacio'; td.textContent = 'Todavía no hay solicitudes registradas.';
          tr.appendChild(td); cuerpo.appendChild(tr);
          return;
        }
        lista.forEach(function (s) {
          var tr = document.createElement('tr');
          [fechaHora(s.fecha), s.nombre, s.correo, s.telefono || '—', s.mensaje].forEach(function (valor) {
            var td = document.createElement('td'); td.textContent = valor; tr.appendChild(td);
          });
          cuerpo.appendChild(tr);
        });
      })
      .catch(function () { /* sin cambios */ });
  }

  /* Arranque */
  function iniciarApp() {
    var app = $('app'), login = $('login-pantalla');
    if (app) app.hidden = false;
    if (login) login.hidden = true;
    cargarDatos();
    cargarIntegraciones();
    cargarSolicitudes();
    pintarSugerencias(['¿Cómo van las ventas?', '¿Cuánto gastamos este mes?', '¿Qué facturas faltan?', 'Detecta anomalías']);
  }

  fetch('/api/admin/sesion', { credentials: 'same-origin' })
    .then(function (r) { return r.json(); })
    .then(function (info) {
      if (info.autenticado) {
        iniciarApp();
        ponerTexto('usuario-correo', info.correo || 'admin');
        var avatar = $('avatar-usuario');
        if (avatar && info.correo) avatar.textContent = info.correo.charAt(0).toUpperCase();
      } else {
        var app = $('app');
        if (app) app.hidden = true;
        var login = $('login-pantalla');
        if (login) login.hidden = false;
      }
    })
    .catch(function () { /* se muestra el acceso por defecto */ });

  var formLogin = $('login-form');
  if (formLogin) formLogin.addEventListener('submit', function (evento) {
    evento.preventDefault();
    var error = $('login-error');
    if (error) error.hidden = true;
    fetch('/api/admin/login', {
      method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ correo: $('login-correo').value, contrasena: $('login-contrasena').value })
    })
      .then(function (respuesta) {
        if (!respuesta.ok) throw new Error('Credenciales incorrectas');
        return respuesta.json();
      })
      .then(function () { iniciarApp(); })
      .catch(function () {
        if (error) { error.textContent = 'Correo o contraseña incorrectos.'; error.hidden = false; }
      });
  });

  document.querySelectorAll('.nav-link').forEach(function (enlace) {
    enlace.addEventListener('click', function () { mostrarSeccion(enlace.getAttribute('data-seccion')); });
  });
  var menu = $('menu-btn');
  if (menu) menu.addEventListener('click', function () {
    var barra = $('sidebar');
    var abierta = barra.classList.toggle('abierta');
    menu.setAttribute('aria-expanded', String(abierta));
    var overlay = $('overlay');
    if (overlay) overlay.hidden = !abierta;
  });
  var overlay = $('overlay');
  if (overlay) overlay.addEventListener('click', function () {
    $('sidebar').classList.remove('abierta');
    overlay.hidden = true;
  });
  var salir = $('btn-logout');
  if (salir) salir.addEventListener('click', function () { cerrarSesion(false); });
  var actualizar = $('btn-actualizar');
  if (actualizar) actualizar.addEventListener('click', function () {
    cargarDatos(); cargarIntegraciones(); cargarSolicitudes(); avisar('Datos actualizados desde el servidor.');
  });

  ['f-desde', 'f-hasta', 'f-producto', 'f-categoria'].forEach(function (id) {
    var elemento = $(id);
    if (elemento) {
      elemento.addEventListener('change', function () { estado.pagina = 1; cargarDatos(); });
    }
  });
  var limpiar = $('btn-limpiar');
  if (limpiar) limpiar.addEventListener('click', function () {
    ['f-desde', 'f-hasta', 'f-producto', 'f-categoria'].forEach(function (id) { var e = $(id); if (e) e.value = ''; });
    estado.pagina = 1; cargarDatos();
  });
  var tamano = $('tamano-pagina');
  if (tamano) tamano.addEventListener('change', function () {
    estado.tamano = Number(tamano.value) || 10; estado.pagina = 1;
    if (estado.datos) pintarTabla(estado.datos);
  });
  [['btn-csv', 'csv'], ['btn-xlsx', 'xlsx']].forEach(function (par) {
    var boton = $(par[0]);
    if (boton) boton.addEventListener('click', function () {
      window.location.assign('/api/admin/exportar/' + par[1] + '?' + parametros().toString());
    });
  });

  var formChat = $('chat-form-admin');
  if (formChat) formChat.addEventListener('submit', function (evento) {
    evento.preventDefault();
    preguntar($('chat-input-admin') ? $('chat-input-admin').value : '');
  });
  document.querySelectorAll('[data-pregunta]').forEach(function (boton) {
    boton.addEventListener('click', function () {
      mostrarSeccion('asistente');
      preguntar(boton.getAttribute('data-pregunta'));
    });
  });
})();
