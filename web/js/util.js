"use strict";
/* Utilidades: DOM, llamadas a la API de Python, avisos y diálogos. */

const SVG_NS = "http://www.w3.org/2000/svg";
const $ = (selector, root = document) => root.querySelector(selector);

/** Crea un elemento. `h("div", {class: "x", onclick: fn}, hijo1, "texto")`. */
function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") el.className = value;
    else if (key === "text") el.textContent = value;
    else if (key === "dataset") Object.assign(el.dataset, value);
    else if (key === "style" && typeof value === "object") {
      for (const [name, v] of Object.entries(value)) {
        if (name.startsWith("--")) el.style.setProperty(name, v);
        else el.style[name] = v;
      }
    } else if (key.startsWith("on") && typeof value === "function") {
      el.addEventListener(key.slice(2), value);
    } else if (key === "for") el.htmlFor = value;
    else if (["value", "checked", "disabled", "selected", "draggable", "hidden", "tabIndex", "rows", "type", "placeholder", "readOnly"].includes(key)) {
      el[key] = value;
    } else el.setAttribute(key, value === true ? "" : String(value));
  }
  append(el, children);
  return el;
}

function append(parent, children) {
  for (const child of children) {
    if (child === null || child === undefined || child === false) continue;
    if (Array.isArray(child)) append(parent, child);
    else parent.appendChild(child instanceof Node ? child : document.createTextNode(String(child)));
  }
}

function icon(name, extra = "") {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", ("ico " + extra).trim());
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS(SVG_NS, "use");
  use.setAttribute("href", "#i-" + name);
  svg.appendChild(use);
  return svg;
}

function debounce(fn, ms) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

function autosize(textarea) {
  textarea.style.height = "auto";
  textarea.style.height = Math.max(textarea.scrollHeight + 2, 32) + "px";
}

function plural(n, uno, varios) {
  return `${n} ${n === 1 ? uno : varios}`;
}

/* ---- API de Python (pywebview) ---- */
class ApiError extends Error {}

const apiLista = new Promise((resolve) => {
  if (window.pywebview && window.pywebview.api) resolve();
  else window.addEventListener("pywebviewready", () => resolve(), { once: true });
});

/** `await api.metodo(...)` devuelve `datos` o lanza ApiError con el mensaje. */
const api = new Proxy({}, {
  get: (_target, name) => async (...args) => {
    await apiLista;
    const fin = ruletaAutomatica(name);
    let respuesta;
    try {
      respuesta = await window.pywebview.api[name](...args);
    } finally {
      fin();
    }
    if (!respuesta || !respuesta.ok) throw new ApiError((respuesta && respuesta.error) || "Error desconocido");
    return respuesta.datos;
  },
});

/* ---- ruleta automática: cualquier llamada que tarde se ve ---- */
const RULETA_RETRASO_MS = 400;
// Las que van en segundo plano (no deben tapar nada) y las que abren un diálogo de archivos.
const SIN_RULETA = new Set(["bloqueo", "bloquear", "soltar_bloqueos", "comprobar_version", "ejecucion_robot_progreso", "marcar_cambios",
  "preferencias", "guardar_preferencias", "validar_yaml", "zoom"]);
const MENSAJE_RULETA = {
  validacion_abrir: "Abriendo la validación…", validacion_estado: "Actualizando la validación…", validacion_crear: "Creando la validación…",
  validacion_anadir_ejecucion: "Añadiendo las ejecuciones…", validacion_quitar_ejecucion: "Actualizando la validación…",
  validacion_comparar_con: "Comparando con la otra validación…", validacion_nueva_ejecucion: "Creando la ejecución…",
  ejecucion_abrir: "Abriendo la ejecución…", ejecucion_comparar: "Comparando las ejecuciones…",
  iniciar: "Abriendo la carpeta…", recargar: "Recargando…", navegacion: "Cargando…", trazabilidad: "Calculando la trazabilidad…",
};
let ruletaVisible = null;
let ruletaPendientes = 0;

/** Empieza a esperar una llamada; si tarda, sale la ruleta. Devuelve la función que la termina. */
function ruletaAutomatica(nombre) {
  if (SIN_RULETA.has(nombre) || /elegir/.test(nombre)) return () => {};
  let lenta = false;
  const temporizador = setTimeout(() => {
    lenta = true;
    ruletaPendientes += 1;
    if (!ruletaVisible && !document.querySelector(".espera")) {       // con conEspera ya hay una
      ruletaVisible = capaEspera(MENSAJE_RULETA[nombre] || "Un momento…", "", { foco: false, ocultable: true });
    }
  }, RULETA_RETRASO_MS);
  return () => {
    clearTimeout(temporizador);
    if (!lenta) return;
    ruletaPendientes -= 1;
    if (ruletaPendientes === 0 && ruletaVisible) { ruletaVisible(); ruletaVisible = null; }
  };
}

/* ---- avisos ---- */
function aviso(mensaje, tipo = "info", accion = null) {
  const caja = $("#avisos");
  const el = h("div", { class: "aviso " + tipo, role: tipo === "error" ? "alert" : "status" },
    h("span", { text: mensaje }),
    accion ? h("button", { class: "btn peq", type: "button", text: accion.texto, onclick: () => { accion.hacer(); el.remove(); } }) : null);
  caja.appendChild(el);
  while (caja.children.length > 3) caja.firstElementChild.remove();
  setTimeout(() => el.remove(), tipo === "error" ? 9000 : 4500);
  return el;
}

function fallo(error) {
  aviso(error && error.message ? error.message : String(error), "error");
}

/* ---- diálogos ---- */
/**
 * Tapa la ventana con una ruleta y `mensaje` mientras dura `tarea()` (una
 * promesa); no deja hacer clic en nada hasta que termina, bien o con error.
 */
async function conEspera(mensaje, tarea, detalle = "") {
  const quitar = capaEspera(mensaje, detalle);
  try {
    return await tarea();
  } finally {
    quitar();
  }
}

/** Capa gris con la ruleta, el mensaje y el tiempo que lleva. Devuelve la función que la quita. */
function capaEspera(mensaje, detalle = "", { foco = true, ocultable = false } = {}) {
  const tiempo = h("p", { class: "espera-tiempo", "aria-live": "off" });
  // La ruleta automática se puede ocultar si tarda mucho (la operación sigue; lo que llegue se verá al terminar).
  const ocultar = ocultable ? h("button", { class: "btn ghost peq", type: "button", hidden: true, text: "Ocultar y seguir trabajando",
    onclick: () => capa.remove() }) : null;
  const capa = h("div", { class: "espera", role: "alert", "aria-busy": "true", "aria-live": "assertive" },
    h("div", { class: "espera-caja" }, h("div", { class: "ruleta", "aria-hidden": "true" }), h("p", { text: mensaje }),
      detalle ? h("p", { class: "espera-detalle", text: detalle }) : null, tiempo, ocultar));
  const anterior = document.activeElement;
  // Dentro del diálogo abierto, si lo hay: un diálogo modal tapa todo lo que está fuera de él.
  const abiertos = document.querySelectorAll("dialog[open]");
  (abiertos.length ? abiertos[abiertos.length - 1] : document.body).appendChild(capa);
  if (foco) {
    capa.tabIndex = -1;
    capa.focus();
  }
  const inicio = Date.now();
  const reloj = setInterval(() => {
    const s = Math.round((Date.now() - inicio) / 1000);
    tiempo.textContent = s < 3 ? "" : `Lleva ${s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${s % 60} s`}`;
    if (ocultar && s >= 8) ocultar.hidden = false;
  }, 1000);
  return () => {
    clearInterval(reloj);
    capa.remove();
    if (foco && anterior && anterior.focus) anterior.focus();
  };
}

function dialogo({ titulo, cuerpo, botones, ancho = false }) {
  return new Promise((resolve) => {
    const dlg = h("dialog", { class: ancho ? "ancho" : "", "aria-label": titulo });
    const pie = h("div", { class: "dlg-pie" }, botones.map((b) => h("button", {
      type: "button", class: "btn " + (b.tipo || ""), text: b.texto,
      onclick: () => dlg.close(b.valor),
    })));
    append(dlg, [
      titulo ? h("div", { class: "dlg-cab", text: titulo }) : null,
      h("div", { class: "dlg-cuerpo" }, typeof cuerpo === "string" ? h("p", { text: cuerpo }) : cuerpo),
      botones.length ? pie : null,
    ]);
    dlg.addEventListener("close", () => { dlg.remove(); resolve(dlg.returnValue || null); });
    document.body.appendChild(dlg);
    dlg.showModal();
    const primero = dlg.querySelector(".btn.primary, .btn.solido") || dlg.querySelector(".dlg-pie .btn:last-child");
    if (primero) primero.focus();
  });
}

async function confirmar(titulo, texto, textoBoton, peligro = false) {
  const r = await dialogo({
    titulo, cuerpo: texto,
    botones: [
      { texto: "Cancelar", valor: "no", tipo: "ghost" },
      { texto: textoBoton, valor: "si", tipo: peligro ? "peligro solido" : "primary" },
    ],
  });
  return r === "si";
}

/* ---- imágenes ---- */
const cacheImagenes = new Map();

/** Datos de una imagen (miniatura o tamaño completo); recuerda los resultados. */
function datosImagen(ruta, ancho) {
  const clave = ruta + "|" + ancho;
  if (!cacheImagenes.has(clave)) {
    const promesa = api.imagen(ruta, ancho);
    cacheImagenes.set(clave, promesa);
    promesa.catch(() => cacheImagenes.delete(clave));
  }
  return cacheImagenes.get(clave);
}

function leerComoDataUrl(archivo) {
  return new Promise((resolve, reject) => {
    const lector = new FileReader();
    lector.onload = () => resolve(lector.result);
    lector.onerror = () => reject(new Error("No se pudo leer el archivo."));
    lector.readAsDataURL(archivo);
  });
}

/** Guarda en `imagenes/` los archivos de imagen pegados o soltados. */
async function importarArchivos(archivos) {
  const rutas = [];
  for (const archivo of archivos) {
    if (!archivo.type.startsWith("image/") && !/\.(bmp|emf|gif|jpe?g|png|tiff?)$/i.test(archivo.name)) continue;
    const datos = await leerComoDataUrl(archivo);
    const r = await api.importar_imagen_base64(archivo.name || "captura.png", datos);
    rutas.push(...r.rutas);
  }
  return rutas;
}

const tieneArchivos = (e) => e.dataTransfer && [...e.dataTransfer.types].includes("Files");

/* Evita que soltar un archivo fuera de una zona navegue a él. */
window.addEventListener("dragover", (e) => { if (tieneArchivos(e)) e.preventDefault(); });
window.addEventListener("drop", (e) => { if (tieneArchivos(e)) e.preventDefault(); });

function visorImagen(ruta, nombre, fuente = datosImagen) {
  const img = h("img", { alt: nombre || ruta });
  const visor = h("div", { class: "visor" }, "Cargando…");
  fuente(ruta, 0).then((d) => { img.src = d.uri; visor.replaceChildren(img); },
    (e) => { visor.textContent = e.message; });
  return dialogo({
    titulo: nombre || ruta, cuerpo: visor, ancho: true,
    botones: [{ texto: "Cerrar", valor: "cerrar", tipo: "primary" }],
  });
}

/* ---- preferencias de la interfaz ----
   Se guardan en los ajustes del PC (Python), porque pywebview borra el
   almacenamiento del navegador al cerrar la ventana. Se cargan una vez al
   arrancar (cargarPreferencias) y desde entonces se leen de memoria. */
const PREFS = {};

async function cargarPreferencias() {
  try { Object.assign(PREFS, await api.preferencias()); } catch (_e) { /* se usan los valores por defecto */ }
}

function guardarLocal(clave, valor) {
  const texto = valor === null || valor === undefined ? null : String(valor);
  if (PREFS[clave] === texto) return;
  if (texto === null) delete PREFS[clave]; else PREFS[clave] = texto;
  api.guardar_preferencias({ [clave]: texto }).catch(() => { /* no poder guardarla no impide trabajar */ });
}

function leerLocal(clave) {
  return Object.prototype.hasOwnProperty.call(PREFS, clave) ? PREFS[clave] : null;
}

/* ---- formato de texto en línea ----
   Es el mismo que entiende el exportador a Word (yaml_a_docx.py):
   **negrita**, *cursiva*, [[rojo|texto]], [[#1F4E79|texto]], [[res:amarillo|texto]].
   El editor no enseña las marcas: trabaja con una lista de caracteres, cada uno
   con su formato ({c, n, k, color, res}), y la vuelve a convertir en marcas al
   cambiar. Así se ve el formato mientras se escribe. */
const TOKEN_FORMATO = /(\[\[[^\]|]+\||\]\]|\*\*|\*)/;
const COLORES_TEXTO = { rojo: "#c62828", azul: "#0070c0", verde: "#00873d" };
const RESALTADOS_TEXTO = {
  amarillo: "#fff176", yellow: "#fff176", verde: "#b9f6ca", bright_green: "#b9f6ca",
  cian: "#a5f3f3", turquoise: "#a5f3f3",
};
const SIN_FORMATO = Object.freeze({ n: false, k: false, color: null, res: null });

/** Texto con marcas -> lista de caracteres con formato. */
function marcasACaracteres(texto) {
  const caracteres = [];
  let n = false;
  let k = false;
  const pila = [];
  for (const trozo of String(texto ?? "").split(TOKEN_FORMATO)) {
    if (!trozo) continue;
    if (trozo === "**") n = !n;
    else if (trozo === "*") k = !k;
    else if (trozo.startsWith("[[") && trozo.endsWith("|")) {
      const clave = trozo.slice(2, -1);
      pila.push(clave.startsWith("res:") ? ["res", clave.slice(4)] : ["color", clave]);
    } else if (trozo === "]]") pila.pop();
    else {
      let color = null;
      let res = null;
      for (const [tipo, valor] of pila) {
        if (tipo === "color") color = valor; else res = valor;
      }
      for (let i = 0; i < trozo.length; i++) caracteres.push({ c: trozo[i], n, k, color, res });
    }
  }
  return caracteres;
}

/** Lista de caracteres con formato -> texto con marcas. */
function caracteresAMarcas(caracteres) {
  let salida = "";
  let n = false;
  let k = false;
  let abiertos = [];
  const envoltorios = (f) => [f.res ? "res:" + f.res : null, f.color].filter(Boolean);
  const cambiar = (f) => {
    // Primero se cierra lo que termina y después se abre lo que empieza, sin
    // cruzar marcas: «[[rojo|**a**]]**b**» en vez de «[[rojo|**a]]b**».
    const quiere = envoltorios(f);
    const otroColor = quiere.join("\0") !== abiertos.join("\0");
    if (n && (!f.n || otroColor)) { salida += "**"; n = false; }
    if (k && (!f.k || otroColor)) { salida += "*"; k = false; }
    if (otroColor) {
      salida += "]]".repeat(abiertos.length) + quiere.map((q) => "[[" + q + "|").join("");
      abiertos = quiere;
    }
    if (!n && f.n) { salida += "**"; n = true; }
    if (!k && f.k) { salida += "*"; k = true; }
  };
  // Un salto de línea no tiene formato propio: toma el de lo que le sigue, para
  // que las marcas no lo envuelvan («[[rojo|a]]\nb», no «[[rojo|a\n]]b»).
  let siguiente = SIN_FORMATO;
  const formatos = new Array(caracteres.length);
  for (let i = caracteres.length - 1; i >= 0; i--) {
    if (caracteres[i].c !== "\n") siguiente = caracteres[i];
    formatos[i] = caracteres[i].c === "\n" ? siguiente : caracteres[i];
  }
  caracteres.forEach((car, i) => {
    cambiar(formatos[i]);
    salida += car.c;
  });
  cambiar(SIN_FORMATO);
  return salida;
}

const mismoFormato = (a, b) => a.n === b.n && a.k === b.k && a.color === b.color && a.res === b.res;
const formatoDe = (car) => ({ n: car.n, k: car.k, color: car.color, res: car.res });

function aplicarEstilo(span, f) {
  if (f.n) span.style.fontWeight = "700";
  if (f.k) span.style.fontStyle = "italic";
  if (f.color) {
    const hex = f.color.replace(/^#/, "");
    span.style.color = COLORES_TEXTO[f.color] || (/^[0-9a-f]{6}$/i.test(hex) ? "#" + hex : "");
  }
  if (f.res && RESALTADOS_TEXTO[f.res]) {
    span.style.background = RESALTADOS_TEXTO[f.res];
    span.style.color = span.style.color || "#18242b";
  }
}

/** Pinta los caracteres en `raiz`: texto suelto o <span data-fmt> por tramo con el mismo formato. */
function pintarCaracteres(raiz, caracteres) {
  raiz.replaceChildren();
  for (let i = 0; i < caracteres.length;) {
    let j = i + 1;
    while (j < caracteres.length && mismoFormato(caracteres[i], caracteres[j])) j++;
    const texto = caracteres.slice(i, j).map((car) => car.c).join("");
    const f = formatoDe(caracteres[i]);
    if (mismoFormato(f, SIN_FORMATO)) raiz.appendChild(document.createTextNode(texto));
    else {
      const span = document.createElement("span");
      span.dataset.fmt = JSON.stringify(f);
      aplicarEstilo(span, f);
      span.textContent = texto;
      raiz.appendChild(span);
    }
    i = j;
  }
  // Un salto de línea final no se ve sin un <br> detrás.
  if (caracteres.length && caracteres[caracteres.length - 1].c === "\n") {
    raiz.appendChild(h("br", { "data-fin": "" }));
  }
}

/** Lee los caracteres de un nodo editable (o de un fragmento copiado de él). */
function leerCaracteres(nodo) {
  const caracteres = [];
  const recorrer = (padre, f) => {
    for (const hijo of padre.childNodes) {
      if (hijo.nodeType === Node.TEXT_NODE) {
        const texto = hijo.data.replace(/ /g, " ");
        for (let i = 0; i < texto.length; i++) caracteres.push({ c: texto[i], ...f });
      } else if (hijo.nodeName === "BR") {
        if (!hijo.hasAttribute("data-fin")) caracteres.push({ c: "\n", ...f });
      } else if (hijo.nodeType === Node.ELEMENT_NODE) {
        // Bloques que el navegador pueda crear (al pegar o soltar): cada uno en su línea.
        if (/^(DIV|P|LI|H\d)$/.test(hijo.nodeName) && caracteres.length && caracteres[caracteres.length - 1].c !== "\n") {
          caracteres.push({ c: "\n", ...f });
        }
        let propio = f;
        if (hijo.dataset && hijo.dataset.fmt) {
          try { propio = { ...f, ...JSON.parse(hijo.dataset.fmt) }; } catch (_e) { /* se ignora */ }
        }
        recorrer(hijo, propio);
      }
    }
  };
  recorrer(nodo, SIN_FORMATO);
  return caracteres;
}

/** Posición (en caracteres) de un punto del DOM dentro de `raiz`. */
function desplazamiento(raiz, nodo, offset) {
  const rango = document.createRange();
  rango.setStart(raiz, 0);
  rango.setEnd(nodo, offset);
  return leerCaracteres(rango.cloneContents()).length;
}

function seleccionEn(raiz) {
  const sel = window.getSelection();
  if (!sel || !sel.rangeCount) return null;
  const rango = sel.getRangeAt(0);
  if (!raiz.contains(rango.startContainer) || !raiz.contains(rango.endContainer)) return null;
  const a = desplazamiento(raiz, rango.startContainer, rango.startOffset);
  return [a, rango.collapsed ? a : desplazamiento(raiz, rango.endContainer, rango.endOffset)];
}

/** Punto del DOM para una posición en caracteres (al final de un tramo, mejor que al principio del siguiente). */
function puntoEn(raiz, posicion) {
  const paseo = document.createTreeWalker(raiz, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
  let cuenta = 0;
  for (let nodo = paseo.nextNode(); nodo; nodo = paseo.nextNode()) {
    if (nodo.nodeType === Node.TEXT_NODE) {
      if (posicion <= cuenta + nodo.data.length) return [nodo, posicion - cuenta];
      cuenta += nodo.data.length;
    } else if (nodo.nodeName === "BR") {
      if (nodo.hasAttribute("data-fin") || posicion <= cuenta) {
        return [nodo.parentNode, [...nodo.parentNode.childNodes].indexOf(nodo)];
      }
      cuenta += 1;
    }
  }
  return [raiz, raiz.childNodes.length];
}

function ponerSeleccion(raiz, a, b = a) {
  const sel = window.getSelection();
  const rango = document.createRange();
  rango.setStart(...puntoEn(raiz, a));
  rango.setEnd(...puntoEn(raiz, b));
  sel.removeAllRanges();
  sel.addRange(rango);
}

/* La barra de formato refleja el formato del cursor en el editor activo. */
document.addEventListener("selectionchange", () => {
  const activo = document.activeElement;
  if (activo && activo.classList && activo.classList.contains("editable") && activo.controlFormato) {
    activo.controlFormato.alMoverCursor();
  }
});

const BOTONES_FORMATO = [
  { texto: "N", titulo: "Negrita (Ctrl+B)", prop: "n", valor: true, clase: "n" },
  { texto: "K", titulo: "Cursiva (Ctrl+I)", prop: "k", valor: true, clase: "k" },
  null,
  { texto: "A", titulo: "Texto rojo", prop: "color", valor: "rojo", clase: "c-rojo" },
  { texto: "A", titulo: "Texto azul", prop: "color", valor: "azul", clase: "c-azul" },
  { texto: "A", titulo: "Texto verde", prop: "color", valor: "verde", clase: "c-verde" },
  null,
  { texto: "ab", titulo: "Resaltar en amarillo", prop: "res", valor: "amarillo", clase: "r-amarillo" },
  { texto: "ab", titulo: "Resaltar en verde", prop: "res", valor: "verde", clase: "r-verde" },
  { texto: "ab", titulo: "Resaltar en cian", prop: "res", valor: "cian", clase: "r-cian" },
  null,
  { texto: "⌫", titulo: "Quitar formato", prop: null, clase: "quitar" },
];

/**
 * Campo de texto con formato que se ve mientras se escribe.
 * `alCambiar(texto)` recibe el texto con marcas. Devuelve el contenedor; el área
 * editable (`.editable`) lleva `controlFormato` con `valor`, `alFinal()`, `reemplazar()`, `deshacer()`…
 */
function editorFormato({ valor = "", alCambiar = () => {}, id, etiqueta, onkeydown, onpaste } = {}) {
  let caracteres = marcasACaracteres(valor);
  let pendiente = null;          // formato para lo próximo que se escriba (botón pulsado sin selección)
  let pendienteEn = null;
  const historia = [{ caracteres, texto: String(valor ?? ""), sel: [caracteres.length, caracteres.length], tipo: null, t: 0 }];
  let pos = 0;

  const area = h("div", {
    class: "editable", contenteditable: "true", role: "textbox", "aria-multiline": "true",
    spellcheck: "true", id, "aria-label": etiqueta,
  });
  pintarCaracteres(area, caracteres);

  const botones = [];
  const barra = h("div", { class: "formato", role: "toolbar", "aria-label": "Formato de texto" },
    BOTONES_FORMATO.map((b) => {
      if (!b) return h("span", { class: "sep" });
      const boton = h("button", {
        type: "button", class: "fmt " + b.clase, title: b.titulo, "aria-label": b.titulo, tabIndex: -1,
        onmousedown: (e) => e.preventDefault(),   // no quita el foco ni la selección del texto
        onclick: () => (b.prop ? alternar(b.prop, b.valor) : quitarFormato()),
      }, b.texto);
      if (b.prop) { boton.setAttribute("aria-pressed", "false"); botones.push([boton, b]); }
      return boton;
    }));

  const seleccion = () => seleccionEn(area) || [caracteres.length, caracteres.length];
  const formatoEn = (posicion) => {
    const car = caracteres[posicion - 1] && caracteres[posicion - 1].c !== "\n" ? caracteres[posicion - 1] : caracteres[posicion];
    return car && car.c !== "\n" ? formatoDe(car) : { ...SIN_FORMATO };
  };
  const tiene = (f, prop, valor) => (prop === "n" || prop === "k" ? f[prop] : f[prop] === valor);

  function registrar(tipo, sel) {
    const ahora = Date.now();
    const texto = caracteresAMarcas(caracteres);
    const ultimo = historia[pos];
    historia.length = pos + 1;
    // Lo que se escribe (o se borra) seguido se deshace de una vez.
    if (tipo && tipo === ultimo.tipo && (tipo === "escribir" || tipo === "borrar") && ahora - ultimo.t < 1000 && pos > 0) {
      Object.assign(ultimo, { caracteres, texto, sel, t: ahora });
    } else {
      historia.push({ caracteres, texto, sel, tipo, t: ahora });
      pos++;
      if (historia.length > 300) { historia.shift(); pos--; }
    }
    alCambiar(texto);
  }

  function aplicar(nuevos, sel, tipo) {
    caracteres = nuevos;
    pintarCaracteres(area, caracteres);
    ponerSeleccion(area, ...sel);
    registrar(tipo, sel);
    actualizarBarra();
  }

  function irA(indice) {
    if (indice < 0 || indice >= historia.length) return;
    const anterior = historia[pos].texto;
    pos = indice;
    const estado = historia[pos];
    caracteres = estado.caracteres;
    pendiente = null;
    pintarCaracteres(area, caracteres);
    area.focus();
    ponerSeleccion(area, ...estado.sel.map((p) => Math.min(p, caracteres.length)));
    if (estado.texto !== anterior) alCambiar(estado.texto);
    actualizarBarra();
  }
  const deshacer = () => irA(pos - 1);
  const rehacer = () => irA(pos + 1);

  function insertarTexto(texto, tipo = "escribir") {
    const [a, b] = seleccion();
    const f = pendiente || formatoEn(a);
    pendiente = null;
    const nuevos = [];
    for (let i = 0; i < texto.length; i++) nuevos.push({ c: texto[i], ...f });
    aplicar([...caracteres.slice(0, a), ...nuevos, ...caracteres.slice(b)], [a + texto.length, a + texto.length], tipo);
  }

  function alternar(prop, valor) {
    const [a, b] = seleccion();
    const vacio = prop === "n" || prop === "k" ? false : null;
    if (a === b) {
      const base = pendiente || formatoEn(a);
      pendiente = { ...base, [prop]: tiene(base, prop, valor) ? vacio : valor };
      pendienteEn = a;
      actualizarBarra();
      return;
    }
    const tramo = caracteres.slice(a, b).filter((car) => car.c !== "\n");
    const quitar = tramo.length > 0 && tramo.every((car) => tiene(car, prop, valor));
    aplicar(caracteres.map((car, i) => (i >= a && i < b && car.c !== "\n" ? { ...car, [prop]: quitar ? vacio : valor } : car)),
      [a, b], "formato");
  }

  function quitarFormato() {
    const [a, b] = seleccion();
    if (a === b) { pendiente = { ...SIN_FORMATO }; pendienteEn = a; actualizarBarra(); return; }
    aplicar(caracteres.map((car, i) => (i >= a && i < b ? { c: car.c, ...SIN_FORMATO } : car)), [a, b], "formato");
  }

  function actualizarBarra() {
    const [a, b] = seleccionEn(area) || [caracteres.length, caracteres.length];
    const tramo = caracteres.slice(a, b).filter((car) => car.c !== "\n");
    for (const [boton, def] of botones) {
      const activo = a === b || !tramo.length
        ? tiene(pendiente || formatoEn(a), def.prop, def.valor)
        : tramo.every((car) => tiene(car, def.prop, def.valor));
      boton.classList.toggle("activo", activo);
      boton.setAttribute("aria-pressed", String(activo));
    }
  }

  area.addEventListener("beforeinput", (e) => {
    const tipo = e.inputType;
    if (tipo === "historyUndo") { e.preventDefault(); deshacer(); }
    else if (tipo === "historyRedo") { e.preventDefault(); rehacer(); }
    else if (tipo === "formatBold") { e.preventDefault(); alternar("n", true); }
    else if (tipo === "formatItalic") { e.preventDefault(); alternar("k", true); }
    else if (tipo.startsWith("format")) e.preventDefault();             // subrayado, etc.: no existen en el formato
    else if (tipo === "insertParagraph" || tipo === "insertLineBreak") {
      // La línea nueva sigue con el formato que se estaba usando.
      e.preventDefault();
      const f = pendiente || formatoEn(seleccion()[0]);
      insertarTexto("\n", "linea");
      pendiente = f;
      pendienteEn = seleccion()[0];
    }
    else if (tipo === "insertText" && pendiente && e.data) { e.preventDefault(); insertarTexto(e.data); }
  });

  area.addEventListener("input", (e) => {
    caracteres = leerCaracteres(area);
    // El navegador deja un <br> de relleno al vaciar el campo: no es un salto de línea.
    const ultimo = area.lastChild;
    if (ultimo && ultimo.nodeName === "BR" && !ultimo.hasAttribute("data-fin") && caracteres.length && caracteres[caracteres.length - 1].c === "\n") {
      caracteres = caracteres.slice(0, -1);
    }
    // Si el navegador ha metido sus propias etiquetas (al pegar o soltar), se vuelve a pintar limpio.
    if (!e.isComposing && area.querySelector(":scope *:not(span[data-fmt]):not(br[data-fin]), :scope span span")) {
      const sel = seleccion();
      pintarCaracteres(area, caracteres);
      ponerSeleccion(area, ...sel.map((p) => Math.min(p, caracteres.length)));
    }
    const tipo = (e.inputType || "").startsWith("delete") ? "borrar" : (e.inputType || "").startsWith("insertText") || e.inputType === "insertCompositionText" ? "escribir" : "otro";
    registrar(tipo, seleccion());
    actualizarBarra();
  });

  area.addEventListener("keydown", (e) => {
    if (e.isComposing || !(e.ctrlKey || e.metaKey) || e.altKey) return;
    const tecla = e.key.toLowerCase();
    if (tecla === "z") { e.preventDefault(); if (e.shiftKey) rehacer(); else deshacer(); }
    else if (tecla === "y" && !e.shiftKey) { e.preventDefault(); rehacer(); }
    else if (tecla === "b" && !e.shiftKey) { e.preventDefault(); alternar("n", true); }
    else if (tecla === "i" && !e.shiftKey) { e.preventDefault(); alternar("k", true); }
    else if (tecla === "u" && !e.shiftKey) e.preventDefault();
  });

  area.addEventListener("paste", (e) => {
    const datos = e.clipboardData;
    if (!datos) return;
    // Las imágenes las gestiona quien usa el editor (onpaste).
    if ([...(datos.files || [])].some((f) => f.type.startsWith("image/"))) return;
    e.preventDefault();
    const texto = datos.getData("text/plain").replace(/\r\n?/g, "\n");
    if (texto) insertarTexto(texto, "pegar");
  });
  if (onkeydown) area.addEventListener("keydown", onkeydown);
  if (onpaste) area.addEventListener("paste", onpaste);

  area.controlFormato = {
    get valor() { return historia[pos].texto; },
    alFinal() { area.focus(); ponerSeleccion(area, caracteres.length); },
    /** Sustituye todo el texto (se deshace con Ctrl+Z) y deja seleccionado [a, b]. */
    reemplazar(texto, a = null, b = a) {
      const nuevos = marcasACaracteres(texto);
      area.focus();
      aplicar(nuevos, [a ?? nuevos.length, b ?? a ?? nuevos.length], "otro");
    },
    alMoverCursor() {
      const sel = seleccionEn(area);
      if (pendiente && (!sel || sel[0] !== pendienteEn || sel[1] !== pendienteEn)) pendiente = null;
      actualizarBarra();
    },
    alternar, quitarFormato, deshacer, rehacer,
  };
  area.addEventListener("focus", actualizarBarra);
  return h("div", { class: "con-formato" }, area, barra);
}
