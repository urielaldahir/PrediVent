/* ui.js — SweetAlert2 sin modificar name, id, method ni action de tus formularios.
   Guárdalo en static/js/ui.js y cárgalo al final de cada plantilla. */

(function () {
  "use strict";

  /* Evita registrar los eventos dos veces si el script se carga duplicado
     (dos clics seguidos en el ojo dejarían la contraseña como estaba). */
  if (window.__uiShopEaseCargado) return;
  window.__uiShopEaseCargado = true;

  var estilos = {
    confirmButtonColor: "#0f6b8a",
    cancelButtonColor: "#5b6578"
  };

  function confirmar(mensaje) {
    return Swal.fire({
      title: mensaje,
      icon: "question",
      showCancelButton: true,
      confirmButtonText: "Sí, continuar",
      cancelButtonText: "Cancelar",
      confirmButtonColor: estilos.confirmButtonColor,
      cancelButtonColor: estilos.cancelButtonColor
    });
  }

  /* 1) Confirmación antes de enviar un formulario.
        Uso: agrega data-confirm="¿Eliminar este registro?" al <form>. */
  document.addEventListener("submit", function (e) {
    var form = e.target;
    var mensaje = form.getAttribute("data-confirm");
    if (!mensaje || form.dataset.confirmado === "1") return;

    e.preventDefault();
    var enviador = e.submitter;
    confirmar(mensaje).then(function (r) {
      if (r.isConfirmed) {
        form.dataset.confirmado = "1";
        /* requestSubmit conserva el botón que se pulsó (su name/value viaja al servidor) */
        if (form.requestSubmit) {
          form.requestSubmit(enviador || undefined);
        } else {
          form.submit();
        }
      }
    });
  });

  /* 2) Confirmación antes de seguir un enlace.
        Uso: agrega data-confirm="¿Deseas cerrar sesión?" al <a>. */
  document.addEventListener("click", function (e) {
    var enlace = e.target.closest("a[data-confirm]");
    if (!enlace) return;

    e.preventDefault();
    confirmar(enlace.getAttribute("data-confirm")).then(function (r) {
      if (r.isConfirmed) window.location.href = enlace.href;
    });
  });

  /* 3) Mostrar/ocultar contraseña.
        Uso: <button type="button" class="ver-clave" data-ver-clave> dentro de .campo */
  document.addEventListener("click", function (e) {
    var boton = e.target.closest("[data-ver-clave]");
    if (!boton) return;

    var campo = boton.closest(".campo");
    var input = campo && campo.querySelector("input");
    if (!input) return;

    var visible = input.type === "text";
    input.type = visible ? "password" : "text";
    var icono = boton.querySelector("i");
    if (icono) {
      icono.className = visible ? "fa-solid fa-eye" : "fa-solid fa-eye-slash";
    }
  });

  document.addEventListener("DOMContentLoaded", function () {
    /* 4) Errores de login ({{error}}) como modal: se lee el texto de .mensaje-error. */
    document.querySelectorAll(".mensaje-error").forEach(function (el) {
      var texto = el.textContent.trim();
      if (!texto || texto === "None") {
        el.textContent = "";
        return;
      }
      Swal.fire({
        icon: "error",
        title: el.getAttribute("data-titulo") || "No se pudo iniciar sesión",
        text: texto,
        confirmButtonColor: estilos.confirmButtonColor
      });
    });

    /* 4b) Mensajes de éxito (.mensaje-ok) como modal. */
    document.querySelectorAll(".mensaje-ok").forEach(function (el) {
      var texto = el.textContent.trim();
      if (!texto || texto === "None") {
        el.textContent = "";
        return;
      }
      Swal.fire({
        icon: "success",
        title: el.getAttribute("data-titulo") || "Listo",
        text: texto,
        confirmButtonColor: estilos.confirmButtonColor
      });
    });

    /* 5) Mensajes flash de Flask como toasts.
          <div class="flash-data" data-categoria="{{ category }}" data-mensaje="{{ message }}" hidden></div> */
    var iconos = { success: "success", error: "error", danger: "error", warning: "warning", info: "info" };
    document.querySelectorAll(".flash-data").forEach(function (el) {
      var categoria = el.getAttribute("data-categoria") || "info";
      Swal.fire({
        toast: true,
        position: "top-end",
        icon: iconos[categoria] || "info",
        title: el.getAttribute("data-mensaje"),
        showConfirmButton: false,
        timer: 3500,
        timerProgressBar: true
      });
    });

    /* 6) Marca el enlace activo del menú según la URL actual. */
    document.querySelectorAll("nav a").forEach(function (a) {
      if (a.pathname === window.location.pathname) {
        a.setAttribute("aria-current", "page");
      }
    });
  });

  /* 7) Buscador y contador para tablas de consulta.
        Estructura: .tabla-bloque > .barra-tabla (input.filtro-tabla + .contador-tabla) + tabla */
  function normalizar(t) {
    return (t || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  }

  function actualizarTabla(bloque) {
    var q = normalizar((bloque.querySelector(".filtro-tabla") || {}).value);
    var filas = bloque.querySelectorAll("tbody tr:not(.vacio)");
    var visibles = 0;
    filas.forEach(function (fila) {
      var coincide = !q || normalizar(fila.textContent).indexOf(q) !== -1;
      fila.style.display = coincide ? "" : "none";
      if (coincide) visibles++;
    });
    var contador = bloque.querySelector(".contador-tabla");
    if (contador) {
      contador.textContent = visibles + (visibles === 1 ? " registro" : " registros");
    }
  }

  document.addEventListener("input", function (e) {
    var input = e.target.closest(".filtro-tabla");
    if (!input) return;
    actualizarTabla(input.closest(".tabla-bloque"));
  });

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".tabla-bloque").forEach(actualizarTabla);
  });

  /* 8) Mostrar/ocultar un dato sensible borroso.
        Uso: <span class="secreto">…</span> + <button type="button" data-ver-secreto> */
  document.addEventListener("click", function (e) {
    var boton = e.target.closest("[data-ver-secreto]");
    if (!boton) return;

    var contenedor = boton.closest("li") || boton.parentElement;
    var dato = contenedor.querySelector(".secreto");
    if (!dato) return;

    var visible = dato.classList.toggle("visible");
    var icono = boton.querySelector("i");
    if (icono) {
      icono.className = visible ? "fa-solid fa-eye-slash" : "fa-solid fa-eye";
    }
  });
})();