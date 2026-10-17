"use strict";
/* Menú «…» de la barra superior: lo que no se usa a diario (importar, exportar,
   manual, acerca de) y la versión de la barra inferior. */

const REPOSITORIO = "https://github.com/goros1993/Aztarna";

/** Opciones del menú según el modo y lo que haya abierto. */
function opcionesMenu() {
  const conCapitulos = S.capitulos.length > 0;
  return [
    {
      texto: "Importar desde Word…", icono: "import", accion: asistenteImportar, desactivada: !importarDisponible(),
      ayuda: importarDisponible() ? "Importar pruebas o requisitos de un documento de Word" : "Cambia al modo Pruebas o Requisitos para importar",
    },
    S.modo === "ejecucion" ? null : {
      texto: enRequisitos() ? "Exportar DOCX de requisitos…" : "Exportar DOCX…", icono: "export", accion: exportarDocx,
      desactivada: !conCapitulos, ayuda: "Generar el documento de Word con todos los capítulos",
    },
    "-",
    "zoom",
    { texto: "Ajustes…", icono: "engranaje", accion: abrirAjustes, ayuda: "Tu nombre, dónde se publica el programa y la dirección de las incidencias" },
    { texto: "Manual de usuario", icono: "libro", accion: abrirManual, ayuda: "Abrir el manual en una ventana aparte" },
    { texto: "Acerca de…", icono: "info", accion: acercaDe },
  ].filter(Boolean);
}

let menuAbierto = null;

function cerrarMenu() {
  if (!menuAbierto) return;
  menuAbierto.remove();
  menuAbierto = null;
  $("#btn-menu").setAttribute("aria-expanded", "false");
}

function abrirMenu() {
  if (menuAbierto) { cerrarMenu(); return; }
  const boton = $("#btn-menu");
  const items = opcionesMenu().map((o) => o === "-"
    ? h("div", { class: "menu-separador", role: "separator" })
    : o === "zoom" ? filaZoom()
    : h("button", {
      type: "button", class: "menu-opcion", role: "menuitem", disabled: Boolean(o.desactivada), title: o.ayuda || null,
      onclick: async () => { cerrarMenu(); try { await o.accion(); } catch (e) { fallo(e); } },
    }, icon(o.icono), o.texto));
  menuAbierto = h("div", { class: "menu-flotante", role: "menu", "aria-label": "Más opciones" }, items);
  document.body.appendChild(menuAbierto);
  const caja = boton.getBoundingClientRect();
  menuAbierto.style.top = `${caja.bottom + 4}px`;
  menuAbierto.style.right = `${Math.max(8, window.innerWidth - caja.right)}px`;
  boton.setAttribute("aria-expanded", "true");
  const primera = menuAbierto.querySelector(".menu-opcion:not([disabled])");
  if (primera) primera.focus();
}

/* ---- zoom: todo más grande o más pequeño (Ctrl + rueda, Ctrl +, Ctrl −, Ctrl 0) ---- */
const PASOS_ZOOM = [0.67, 0.75, 0.8, 0.9, 1, 1.1, 1.25, 1.5, 1.75, 2, 2.5, 3];
let ZOOM = 1;
let avisoZoom = null;
let zoomPropio = true;      // false: el zoom propio no funciona aquí; Ctrl+rueda lo hace el navegador

async function ponerZoom(nivel, { avisar = true } = {}) {
  let r;
  try { r = await api.zoom(nivel); } catch (e) { fallo(e); return; }
  if (!r.aplicado) {
    zoomPropio = false;
    if (avisar) aviso(`No se ha podido cambiar el tamaño (${r.motivo || "sin motivo"}). Prueba con Ctrl + rueda del ratón.`, "error");
    return;
  }
  ZOOM = r.nivel;
  guardarLocal("zoom", ZOOM === 1 ? null : ZOOM);
  const texto = $("#zoom-valor");
  if (texto) texto.textContent = `${Math.round(ZOOM * 100)} %`;
  if (avisar) {
    if (avisoZoom) avisoZoom.remove();
    avisoZoom = aviso(`Tamaño ${Math.round(ZOOM * 100)} % (Ctrl+0 para volver al normal)`);
  }
}

/** Un paso más grande (+1) o más pequeño (−1). */
function pasoZoom(sentido) {
  const i = PASOS_ZOOM.reduce((mejor, p, k) => (Math.abs(p - ZOOM) < Math.abs(PASOS_ZOOM[mejor] - ZOOM) ? k : mejor), 0);
  const destino = PASOS_ZOOM[Math.min(Math.max(i + sentido, 0), PASOS_ZOOM.length - 1)];
  if (destino !== ZOOM) ponerZoom(destino);
}

function filaZoom() {
  return h("div", { class: "menu-zoom", role: "group", "aria-label": "Tamaño" },
    h("span", { class: "menu-zoom-tit" }, icon("search"), "Tamaño"),
    h("button", { type: "button", class: "btn peq", title: "Más pequeño (Ctrl −)", "aria-label": "Más pequeño", text: "−", onclick: () => pasoZoom(-1) }),
    h("button", { type: "button", class: "btn ghost peq", id: "zoom-valor", title: "Tamaño normal (Ctrl 0)", text: `${Math.round(ZOOM * 100)} %`, onclick: () => ponerZoom(1) }),
    h("button", { type: "button", class: "btn peq", title: "Más grande (Ctrl +)", "aria-label": "Más grande", text: "+", onclick: () => pasoZoom(1) }));
}

function iniciarZoom() {
  const guardado = Number(leerLocal("zoom"));
  if (guardado && guardado !== 1) ponerZoom(guardado, { avisar: false });
  let ultimo = 0;
  window.addEventListener("wheel", (e) => {
    if (!e.ctrlKey || !e.deltaY || !zoomPropio) return;     // sin zoom propio, lo hace el navegador
    e.preventDefault();
    const ahora = Date.now();
    if (ahora - ultimo < 120) return;           // un paso por «golpe» de rueda
    ultimo = ahora;
    pasoZoom(e.deltaY < 0 ? 1 : -1);
  }, { passive: false });
  document.addEventListener("keydown", (e) => {
    if (!(e.ctrlKey || e.metaKey) || e.altKey || !zoomPropio) return;
    if (["+", "=", "Add"].includes(e.key) || e.code === "NumpadAdd") { e.preventDefault(); pasoZoom(1); }
    else if (["-", "Subtract"].includes(e.key) || e.code === "NumpadSubtract") { e.preventDefault(); pasoZoom(-1); }
    else if (e.key === "0" || e.code === "Numpad0") { e.preventDefault(); ponerZoom(1); }
  });
}

async function abrirManual() {
  await api.abrir_manual();
}

async function acercaDe() {
  const d = await api.acerca_de();
  const fila = (etiqueta, valor) => [h("dt", { text: etiqueta }), h("dd", { text: valor })];
  await dialogo({
    titulo: `${d.nombre} ${d.version}`,
    cuerpo: h("div", { class: "acerca-de" },
      h("div", { class: "acerca-cab" }, h("img", { src: "img/icono.png", alt: "", width: "56", height: "56" }),
        h("p", { text: "Pruebas, requisitos, trazabilidad, ejecuciones y validación de versiones, con los datos en YAML." })),
      h("dl", { class: "datos-ejecucion" },
        fila("Versión", d.version), fila("Ajustes de este PC", d.ajustes), fila("Python", d.python), fila("Sistema", d.sistema)),
      h("p", {}, h("button", { class: "enlace", type: "button", text: "Novedades y código en GitHub", onclick: () => api.abrir_enlace(REPOSITORIO).catch(fallo) }))),
    botones: [{ texto: "Manual de usuario", valor: "manual", tipo: "" }, { texto: "Cerrar", valor: "", tipo: "primary" }],
  }).then((r) => (r === "manual" ? abrirManual() : null));
}

function iniciarMenu() {
  $("#btn-menu").addEventListener("click", (e) => { e.stopPropagation(); abrirMenu(); });
  document.addEventListener("click", (e) => { if (menuAbierto && !menuAbierto.contains(e.target)) cerrarMenu(); });
  document.addEventListener("keydown", (e) => {
    if (!menuAbierto) return;
    if (e.key === "Escape") { e.preventDefault(); cerrarMenu(); $("#btn-menu").focus(); return; }
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault();
    const opciones = [...menuAbierto.querySelectorAll(".menu-opcion:not([disabled])")];
    const i = opciones.indexOf(document.activeElement);
    const siguiente = opciones[(i + (e.key === "ArrowDown" ? 1 : opciones.length - 1)) % opciones.length];
    if (siguiente) siguiente.focus();
  });
  window.addEventListener("resize", cerrarMenu);
  // Versión en la barra inferior (abre «Acerca de»).
  const version = $("#btn-version");
  api.acerca_de().then((d) => { version.textContent = `v${d.version}`; }, () => { version.hidden = true; });
  version.addEventListener("click", () => (NUEVA_VERSION ? avisoNuevaVersion() : acercaDe()));
  cargarAjustesGenerales().then(comprobarVersion);
}

/* ---- ajustes de este PC ---- */
const AJUSTES = { persona: "", carpeta_versiones: "", url_incidencias: "" };
let NUEVA_VERSION = null;

async function cargarAjustesGenerales() {
  try { Object.assign(AJUSTES, await api.ajustes_generales()); } catch (_e) { /* sin ajustes */ }
}

async function abrirAjustes() {
  await cargarAjustesGenerales();
  const campo = (id, etiqueta, valor, ayuda, extra = null) => h("div", { class: "campo completo" },
    h("label", { for: id, text: etiqueta }),
    h("div", { class: "fila-archivo" }, h("input", { id, type: "text", autocomplete: "off", value: valor, placeholder: ayuda.ejemplo || "" }), extra),
    h("span", { class: "ayuda", text: ayuda.texto }));
  const elegir = h("button", { type: "button", class: "btn", text: "Elegir…", onclick: async () => {
    try { const r = await api.elegir_carpeta_versiones(); if (!r.cancelado) cuerpo.querySelector("#aj-versiones").value = r.carpeta; } catch (e) { fallo(e); }
  } });
  const cuerpo = h("div", { class: "rejilla ajustes" },
    campo("aj-persona", "Tu nombre", AJUSTES.persona, { ejemplo: AJUSTES.persona_sistema,
      texto: "Sale como ejecutor en los resultados y en el aviso cuando editas un capítulo. Vacío: tu usuario de Windows." }),
    campo("aj-versiones", "Carpeta con la última versión del programa", AJUSTES.carpeta_versiones, { ejemplo: "\\\\servidor\\pruebas\\programa",
      texto: "Donde se publican Aztarna.exe y version.txt. Al abrir el editor, avisa si allí hay una versión más nueva que la tuya." }, elegir),
    campo("aj-incidencias", "Dirección de las incidencias", AJUSTES.url_incidencias, { ejemplo: "https://jira.empresa.com/browse/{id}",
      texto: "Con {id} donde va el número. Las incidencias (BUG-123…) de los resultados se abren con un clic." }));
  const r = await dialogo({ titulo: "Ajustes de este PC", cuerpo, ancho: true,
    botones: [{ texto: "Cancelar", valor: "", tipo: "ghost" }, { texto: "Guardar", valor: "si", tipo: "primary" }] });
  if (r !== "si") return;
  try {
    Object.assign(AJUSTES, await api.guardar_ajustes_generales({
      persona: cuerpo.querySelector("#aj-persona").value,
      carpeta_versiones: cuerpo.querySelector("#aj-versiones").value,
      url_incidencias: cuerpo.querySelector("#aj-incidencias").value,
    }));
    if (AJUSTES.persona) guardarLocal("ejecutor", AJUSTES.persona);
    aviso("Ajustes guardados", "ok");
    comprobarVersion();
  } catch (e) { fallo(e); }
}

/* ---- versión nueva publicada ---- */
async function comprobarVersion() {
  let r;
  try { r = await api.comprobar_version(); } catch (_e) { return; }
  const boton = $("#btn-version");
  NUEVA_VERSION = r.nueva ? r : null;
  boton.classList.toggle("nueva", Boolean(r.nueva));
  boton.textContent = r.nueva ? `v${r.actual} · hay una versión nueva (${r.version})` : `v${r.actual}`;
  boton.title = r.nueva ? "Hay una versión nueva del programa: pulsa para ver cómo actualizar" : "Acerca de";
  if (r.nueva) aviso(`Hay una versión nueva del programa (${r.version}). Tienes la ${r.actual}.`, "info", { texto: "Ver", hacer: avisoNuevaVersion });
}

async function avisoNuevaVersion() {
  const r = NUEVA_VERSION;
  if (!r) return;
  const accion = await dialogo({
    titulo: `Versión nueva: ${r.version}`,
    cuerpo: h("div", {},
      h("p", {}, "Tienes la ", h("strong", { text: r.actual }), " y en la carpeta del programa está la ", h("strong", { text: r.version }), "."),
      h("p", { text: "Para actualizar: cierra el editor, copia Aztarna.exe de esa carpeta encima del tuyo y vuelve a abrirlo. Tus ajustes y tus datos no cambian." }),
      h("p", { class: "muted", text: r.carpeta })),
    botones: [{ texto: "Más tarde", valor: "", tipo: "ghost" }, { texto: "Abrir la carpeta", valor: "abrir", tipo: "primary" }],
  });
  if (accion === "abrir") api.mostrar_en_carpeta(`${r.carpeta}/version.txt`).catch(fallo);
}

/* ---- incidencias ---- */
const PATRON_INCIDENCIA = /[A-Za-z][A-Za-z0-9_]*-\d+/g;

/** Enlaces a las incidencias de un texto («BUG-123, BUG-130»), si hay dirección configurada. */
function enlacesIncidencia(texto) {
  const ids = [...new Set(String(texto || "").match(PATRON_INCIDENCIA) || [])];
  if (!AJUSTES.url_incidencias || !ids.length) return null;
  return h("span", { class: "enlaces-incidencia" }, ids.map((id) => h("button", {
    type: "button", class: "enlace", text: id, title: "Abrir la incidencia en el navegador",
    onclick: () => api.abrir_enlace(AJUSTES.url_incidencias.replace("{id}", encodeURIComponent(id))).catch(fallo),
  })));
}
