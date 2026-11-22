/* Puerto A&M | Interacciones de la página pública */

(function () {
  'use strict';

  // En GitHub Pages no hay backend: el sitio se muestra completo pero el chat
  // y el formulario se desactivan con un aviso en lugar de dar errores raros.
  var ES_STATICO = window.PUERTO_STATIC === true || /github\.io$/i.test(location.hostname);

  var cabecera = document.getElementById('site-header');
  var menuBtn = document.getElementById('menu-btn');
  var nav = document.getElementById('nav-principal');

  function alDesplazar() {
    if (cabecera) cabecera.classList.toggle('scrolled', window.scrollY > 8);
  }
  window.addEventListener('scroll', alDesplazar, { passive: true });
  alDesplazar();

  if (menuBtn && nav) {
    menuBtn.addEventListener('click', function () {
      var abierto = menuBtn.getAttribute('aria-expanded') === 'true';
      menuBtn.setAttribute('aria-expanded', String(!abierto));
      menuBtn.setAttribute('aria-label', abierto ? 'Abrir menú' : 'Cerrar menú');
      nav.hidden = abierto;
    });
    nav.addEventListener('click', function (evento) {
      if (evento.target.closest('a')) {
        nav.hidden = true;
        menuBtn.setAttribute('aria-expanded', 'false');
      }
    });
  }

  var anio = document.getElementById('anio');
  if (anio) anio.textContent = String(new Date().getFullYear());

  var observables = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window) {
    var observador = new IntersectionObserver(function (entradas) {
      entradas.forEach(function (entrada) {
        if (entrada.isIntersecting) {
          entrada.target.classList.add('visible');
          observador.unobserve(entrada.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
    observables.forEach(function (elemento) { observador.observe(elemento); });
  } else {
    observables.forEach(function (elemento) { elemento.classList.add('visible'); });
  }

  /* Configuración pública: sólo se muestra si el servidor la confirmó. */
  if (!ES_STATICO) fetch('/api/config-publica', { credentials: 'same-origin' })
    .then(function (respuesta) { return respuesta.ok ? respuesta.json() : {}; })
    .then(function (config) {
      Object.keys(config).forEach(function (clave) {
        var contenedor = document.querySelector('[data-config="' + clave + '"]');
        var valor = config[clave];
        if (!contenedor || !valor) return;
        var texto = contenedor.querySelector('span');
        if (texto) texto.textContent = valor;
        var enlace = contenedor.querySelector('a');
        if (enlace) {
          var digitos = String(valor).replace(/\D/g, '');
          enlace.href = digitos.length >= 8
            ? 'https://wa.me/' + digitos + '?text=' + encodeURIComponent('Hola Puerto A&M, tengo una pregunta.')
            : valor;
          enlace.textContent = valor;
        }
        contenedor.hidden = false;
      });
      var enlaceAdmin = document.querySelector('.admin-link');
      if (enlaceAdmin) enlaceAdmin.hidden = config.solo_landing === true;
    })
    .catch(function () { /* sin configuración: la página sigue funcionando */ });
  // En estático no hay fetch de configuración: el enlace de admin ya viene oculto.

  /* Widget de chat */
  var lanzador = document.getElementById('chat-lanzador');
  var panel = document.getElementById('chat-panel');
  var mensajes = document.getElementById('chat-mensajes');
  var sugerencias = document.getElementById('chat-sugerencias');
  var formulario = document.getElementById('chat-form');
  var entrada = document.getElementById('chat-input');
  var cerrar = document.getElementById('chat-cerrar');
  var enviando = false;

  function clienteId() {
    try {
      var guardado = localStorage.getItem('pa_cliente');
      if (guardado) return guardado;
      var bytes = new Uint8Array(12);
      crypto.getRandomValues(bytes);
      var nuevo = Array.from(bytes, function (b) { return b.toString(16).padStart(2, '0'); }).join('');
      localStorage.setItem('pa_cliente', nuevo);
      return nuevo;
    } catch (error) {
      return 'anonimo';
    }
  }

  function desplazarAlFinal() {
    if (mensajes) mensajes.scrollTop = mensajes.scrollHeight;
  }

  function agregarMensaje(texto, tipo) {
    var burbuja = document.createElement('div');
    burbuja.className = 'burbuja ' + tipo;
    burbuja.textContent = texto;
    mensajes.appendChild(burbuja);
    desplazarAlFinal();
    return burbuja;
  }

  function mostrarTyping() {
    var contenedor = document.createElement('div');
    contenedor.className = 'burbuja bot chat-typing';
    contenedor.setAttribute('aria-label', 'El asistente está escribiendo');
    for (var i = 0; i < 3; i += 1) contenedor.appendChild(document.createElement('i'));
    mensajes.appendChild(contenedor);
    desplazarAlFinal();
    return contenedor;
  }

  function pintarSugerencias(lista) {
    if (!sugerencias || !Array.isArray(lista)) return;
    sugerencias.replaceChildren();
    lista.slice(0, 3).forEach(function (texto) {
      var boton = document.createElement('button');
      boton.type = 'button';
      boton.textContent = texto;
      boton.addEventListener('click', function () { enviar(texto); });
      sugerencias.appendChild(boton);
    });
  }

  function abrirChat(pretexto, autoenviar) {
    if (!panel || !lanzador) return;
    panel.hidden = false;
    lanzador.classList.add('abierto');
    lanzador.setAttribute('aria-label', 'Cerrar asistente');
    lanzador.setAttribute('aria-expanded', 'true');
    desplazarAlFinal();
    if (pretexto) {
      if (entrada) entrada.value = pretexto;
      if (autoenviar) enviar(pretexto);
      else if (entrada) entrada.focus();
    } else if (entrada) {
      entrada.focus();
    }
  }

  function cerrarChat() {
    if (!panel || !lanzador) return;
    panel.hidden = true;
    lanzador.classList.remove('abierto');
    lanzador.setAttribute('aria-label', 'Abrir asistente');
    lanzador.setAttribute('aria-expanded', 'false');
  }

  function enviar(texto) {
    var mensaje = String(texto || '').trim();
    if (!mensaje || enviando) return;
    agregarMensaje(mensaje, 'user');
    if (ES_STATICO) {
      agregarMensaje(
        'Esta versión pública es estática: el asistente necesita el servidor y no está disponible aquí. '
        + 'Puedes explorar el menú y la información del restaurante en esta página.',
        'bot'
      );
      if (entrada) entrada.value = '';
      return;
    }
    enviando = true;
    if (entrada) entrada.value = '';
    var botonEnviar = formulario ? formulario.querySelector('button[type="submit"]') : null;
    if (botonEnviar) botonEnviar.disabled = true;
    var typing = mostrarTyping();

    fetch('/api/chat/publico', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mensaje: mensaje, clienteId: clienteId() })
    })
      .then(function (respuesta) {
        if (!respuesta.ok) throw new Error('No se pudo contactar el asistente.');
        return respuesta.json();
      })
      .then(function (datos) {
        typing.remove();
        agregarMensaje(datos.respuesta || 'No obtuve una respuesta.', 'bot');
        pintarSugerencias(datos.sugerencias);
      })
      .catch(function () {
        typing.remove();
        agregarMensaje('No pude conectar con el asistente en este momento. Intenta de nuevo.', 'error');
      })
      .finally(function () {
        enviando = false;
        if (botonEnviar) botonEnviar.disabled = false;
        if (entrada) entrada.focus();
      });
  }

  if (lanzador) lanzador.addEventListener('click', function () {
    if (panel && panel.hidden) abrirChat(); else cerrarChat();
  });
  if (cerrar) cerrar.addEventListener('click', cerrarChat);
  document.addEventListener('keydown', function (evento) {
    if (evento.key === 'Escape' && panel && !panel.hidden) cerrarChat();
  });
  if (formulario) formulario.addEventListener('submit', function (evento) {
    evento.preventDefault();
    enviar(entrada ? entrada.value : '');
  });

  document.querySelectorAll('[data-chat]').forEach(function (boton) {
    boton.addEventListener('click', function () { abrirChat(boton.getAttribute('data-chat'), true); });
  });
  pintarSugerencias(['Apartar una mesa', 'Quiero pedir ceviche', '¿Qué me recomiendas?']);

  /* Filtro del menú de demostración */
  var chipsMenu = document.querySelectorAll('.menu-chip');
  if (chipsMenu.length) {
    chipsMenu.forEach(function (chip) {
      chip.addEventListener('click', function () {
        var categoria = chip.getAttribute('data-categoria');
        chipsMenu.forEach(function (otro) {
          var activo = otro === chip;
          otro.classList.toggle('activo', activo);
          otro.setAttribute('aria-pressed', String(activo));
        });
        document.querySelectorAll('.menu-categoria').forEach(function (tarjeta) {
          var visible = categoria === 'todos' || tarjeta.getAttribute('data-categoria') === categoria;
          tarjeta.hidden = !visible;
          if (visible) tarjeta.classList.add('visible');
        });
      });
    });
  }

  /* Formulario de contacto */
  var formContacto = document.getElementById('form-contacto');
  var estado = document.getElementById('form-estado');
  if (formContacto) {
    formContacto.addEventListener('submit', function (evento) {
      evento.preventDefault();
      if (ES_STATICO) {
        estado.textContent = 'Esta versión pública es estática: el formulario requiere el servidor y no está disponible aquí.';
        estado.classList.add('error');
        return;
      }
      if (!formContacto.reportValidity()) return;
      var datos = new FormData(formContacto);
      var boton = formContacto.querySelector('button[type="submit"]');
      boton.disabled = true;
      estado.textContent = 'Enviando solicitud…';
      estado.classList.remove('error');

      fetch('/api/contacto', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nombre: datos.get('nombre'), correo: datos.get('correo'),
          telefono: datos.get('telefono'), mensaje: datos.get('mensaje'),
          website: datos.get('website')
        })
      })
        .then(function (respuesta) {
          if (!respuesta.ok) throw new Error('Error');
          return respuesta.json();
        })
        .then(function () {
          estado.textContent = 'Listo. Tu solicitud fue registrada; el equipo te responderá.';
          formContacto.reset();
        })
        .catch(function () {
          estado.textContent = 'No se pudo enviar. Revisa tus datos e inténtalo de nuevo.';
          estado.classList.add('error');
        })
        .finally(function () { boton.disabled = false; });
    });
  }
})();
