"use strict";
/* Estado global y arranque de la aplicación. */

const S = {
  carpeta: null,
  proyecto: null,       // nombre e id del proyecto de las pruebas abiertas (ver app/proyecto.py)
  capitulos: [],
  capitulo: 0,
  nodos: [],
  seleccion: null,      // {tipo, indice}
  consulta: "",
  colapsadas: new Set(),
  dirty: false,
  problemas: [],
  resumen: null,        // {errores, avisos}
  alcanceTodos: false,
  modo: "edicion",      // se pone el último usado al arrancar (preferencias)
  capituloPorModo: {},  // último capítulo abierto en pruebas y en requisitos
  hayRequisitos: false, // si la carpeta tiene requisitos (subcarpeta requisitos/)
  filtroCobertura: "",  // en requisitos: mostrar solo los de este estado de cobertura
  ejecucion: null,        // estado de la ejecución abierta (ver ejecucion_api.py)
  validacion: null,     // validación de versión abierta: resultado consolidado (ver validacion_core.py)
  cobertura: null,      // qué pruebas tienen test de Robot (ver web/js/robot.js)
  keywords: null,       // keywords de Robot que se proponen al escribir los pasos
  esquema: null,        // campos de las pruebas y sus opciones (esquema.py)
  filtroEstado: "",     // en ejecución: mostrar solo las pruebas con este estado
};

const enRequisitos = () => S.modo === "requisitos";
/** Colección que se edita en cada modo: los requisitos o las pruebas (también en ejecución). */
const coleccionDe = (modo) => (modo === "requisitos" ? "requisitos" : "pruebas");

function setDirty(valor) {
  const antes = S.dirty;
  S.dirty = Boolean(valor);
  if (S.dirty !== antes) api.marcar_cambios(S.dirty).catch(() => {});   // para avisar al cerrar la ventana
  if (S.dirty && !antes) tomarBloqueo();                                   // empieza a editar: el capítulo es suyo
  const barra = $("#estado-guardado");
  if (barra) barra.hidden = !S.dirty;
  const cab = $("#cab-sin-guardar");
  if (cab) cab.hidden = !S.dirty;
  const descartar = $("#cab-descartar");
  if (descartar) descartar.hidden = !S.dirty;
}

/** Si hay cambios sin guardar, pregunta qué hacer. Devuelve true si se puede continuar. */
async function guardia(salir = false) {
  if (!S.dirty) return true;
  const r = await dialogo({
    titulo: "Hay cambios sin guardar",
    cuerpo: salir
      ? "¿Quieres guardar los cambios antes de salir? Si sales sin guardar, se perderán."
      : "Si continúas, perderás los cambios que no hayas guardado.",
    botones: [
      { texto: "Seguir editando", valor: "quedar", tipo: "ghost" },
      { texto: salir ? "Salir sin guardar" : "Descartar cambios", valor: "descartar", tipo: "peligro" },
      { texto: salir ? "Guardar y salir" : "Guardar y continuar", valor: "guardar", tipo: "primary" },
    ],
  });
  if (r === "guardar") return await guardarActual();
  if (r === "descartar") { setDirty(false); return true; }
  return false;
}

/** Python la llama al cerrar la ventana con cambios pendientes (ver EditorApi._al_cerrar_ventana). */
let preguntandoCierre = false;
async function pedirCierre() {
  if (preguntandoCierre) return;            // ya hay un diálogo abierto
  preguntandoCierre = true;
  try {
    if (await guardia(true)) await api.cerrar();
  } catch (err) { fallo(err); } finally { preguntandoCierre = false; }
}

/* ---- carga de datos ---- */
function aplicarResumen(resumen) {
  S.carpeta = resumen.carpeta;
  S.capitulos = resumen.capitulos;
  S.hayRequisitos = Boolean(resumen.hay_requisitos);
  S.errorRequisitos = resumen.error_requisitos || null;
  if (resumen.esquema) S.esquema = resumen.esquema;   // las opciones son del proyecto abierto
  const boton = $("#carpeta-ruta");
  S.soloLectura = Boolean(resumen.solo_lectura);
  S.avisoFormato = resumen.aviso_formato || null;
  S.proyecto = resumen.proyecto || null;
  boton.textContent = S.carpeta ? (S.soloLectura ? "Pruebas congeladas (solo lectura)" : S.carpeta) : "Sin carpeta";
  boton.title = S.soloLectura
    ? "Pruebas tal como estaban al cerrar la ejecución. No se pueden editar; para editar, abre la carpeta de pruebas."
    : S.carpeta || "";
  const proyecto = $("#proyecto-nombre");
  proyecto.textContent = S.proyecto ? S.proyecto.nombre : "";
  proyecto.hidden = !S.proyecto;
  $("#btn-carpeta").title = S.carpeta
    ? `${S.proyecto ? `Proyecto: ${S.proyecto.nombre}\n` : ""}Carpeta de pruebas: ${S.carpeta}\nPulsa para cambiarla.` : "Cambiar de carpeta";
  const sel = $("#sel-capitulo");
  sel.replaceChildren(...S.capitulos.map((c) => h("option", {
    value: String(c.indice), text: textoCapitulo(c), selected: c.indice === S.capitulo,
  })));
  sel.disabled = !S.capitulos.length;
  const [uno, varios] = resumen.coleccion === "requisitos" ? ["requisito", "requisitos"] : ["prueba", "pruebas"];
  $("#resumen-datos").textContent = S.capitulos.length
    ? `${plural(S.capitulos.length, "capítulo", "capítulos")} · ${plural(S.capitulos.reduce((a, c) => a + c.pruebas, 0), uno, varios)}`
    : "";
  for (const id of ["btn-nueva-prueba", "btn-nueva-seccion", "btn-recargar", "btn-problemas"]) {
    $("#" + id).disabled = !S.capitulos.length;
  }
}

async function cargarNavegacion() {
  await comprobarBloqueo();
  if (!S.capitulos.length) { S.nodos = []; renderArbol(); return; }
  S.nodos = await api.navegacion(S.capitulo, S.consulta);
  if (S.modo === "ejecucion") S.nodos = filtrarNodosEjecucion(S.nodos);
  if (enRequisitos()) S.nodos = filtrarNodosCobertura(S.nodos);
  renderArbol();
}

/** Recarga resumen, árbol y (opcionalmente) selecciona un elemento. */
async function refrescarTodo({ seleccionar: destino = undefined } = {}) {
  try {
    const resumen = await api.iniciar();
    aplicarResumen(resumen);
    if (S.capitulo >= S.capitulos.length) S.capitulo = 0;
    await cargarNavegacion();
    if (destino) await abrir(destino.tipo, destino.indice);
    else if (S.seleccion && !S.nodos.some((n) => n.indice === S.seleccion.indice && n.tipo === S.seleccion.tipo)) {
      S.seleccion = null;
      mostrarVacio();
    } else if (!S.seleccion) mostrarVacio();
    validarEnSegundoPlano();
  } catch (e) { fallo(e); }
}

async function abrir(tipo, indice) {
  try {
    const datos = await api.obtener(S.capitulo, indice);
    S.seleccion = { tipo: datos.tipo, indice };
    if (S.modo === "ejecucion") await mostrarEnEjecucion(datos);
    else mostrarElemento(datos);
    renderArbol();
    enfocarSeleccion();
  } catch (e) {
    fallo(e);
    S.seleccion = null;
    await cargarNavegacion();
    mostrarVacio();
  }
}

async function seleccionar(tipo, indice) {
  if (S.seleccion && S.seleccion.tipo === tipo && S.seleccion.indice === indice && !formularioNuevo()) return;
  if (!(await guardia())) return;
  setDirty(false);
  await abrir(tipo, indice);
}

const formularioNuevo = () => { const f = formularioActual(); return f && f.modo === "nueva"; };

async function reabrirSeleccion() {
  if (S.seleccion) await abrir(S.seleccion.tipo, S.seleccion.indice);
  else mostrarVacio();
}

async function elegirCarpeta() {
  if (!(await guardia())) return;
  try {
    const r = await api.elegir_carpeta();
    if (r.cancelado) return;
    setDirty(false);
    S.capitulo = 0; S.seleccion = null; S.consulta = ""; $("#buscar").value = "";
    S.colapsadas.clear(); cacheImagenes.clear(); S.capituloPorModo = {};
    aplicarResumen(r);
    if (S.validacion || S.ejecucion) await soltarLoDeOtroProyecto();
    await cargarCobertura();
    await cargarNavegacion();
    mostrarVacio();
    validarEnSegundoPlano();
  } catch (e) { fallo(e); }
}

async function cambiarCapitulo(valor) {
  if (!(await guardia())) { $("#sel-capitulo").value = String(S.capitulo); return; }
  setDirty(false);
  S.capitulo = Number(valor);
  S.seleccion = null;
  await cambioDeCapitulo();
  await cargarNavegacion();
  mostrarVacio();
  if (!S.alcanceTodos) renderProblemas();
}

async function nuevaPrueba() {
  if (!S.capitulos.length) return;
  if (!(await guardia())) return;
  setDirty(false);
  if (enRequisitos()) await mostrarNuevoRequisito();
  else await mostrarNuevaPrueba();
}

async function nuevaSeccion() {
  if (!S.capitulos.length) return;
  if (!(await guardia())) return;
  setDirty(false);
  await mostrarNuevaSeccion();
}

/* ---- validación ---- */
async function validarEnSegundoPlano() {
  if (!S.capitulos.length) return;
  try {
    const r = await api.validar();
    S.problemas = r.problemas;
    S.resumen = { errores: r.errores, avisos: r.avisos };
    renderResumenProblemas();
    renderProblemas();
    renderArbol();
  } catch (e) { fallo(e); }
}

function renderResumenProblemas() {
  const el = $("#resumen-problemas");
  const r = S.resumen;
  if (!r) { el.textContent = "Sin validar"; return; }
  if (!r.errores && !r.avisos) { el.textContent = "Validación sin problemas"; return; }
  el.replaceChildren(...[
    r.errores ? h("span", { class: "peligro-num", text: plural(r.errores, "error", "errores") }) : null,
    r.errores && r.avisos ? " · " : null,
    r.avisos ? plural(r.avisos, "aviso", "avisos") : null,
  ].filter((x) => x !== null));
}

function renderProblemas() {
  const ul = $("#lista-problemas");
  ul.replaceChildren();
  const lista = S.problemas.filter((p) => S.alcanceTodos || p.capitulo === S.capitulo);
  if (!lista.length) {
    ul.appendChild(h("li", { class: "vacia", text: S.alcanceTodos ? "No hay problemas en ningún capítulo." : "No hay problemas en este capítulo." }));
    return;
  }
  for (const p of lista) {
    ul.appendChild(h("li", {
      title: "Ir al elemento",
      onclick: () => irAProblema(p),
    },
    h("span", { class: "sev " + p.severidad, role: "img", "aria-label": p.severidad === "error" ? "Error" : "Aviso" }),
    h("span", { class: "donde", text: [S.alcanceTodos ? p.archivo : null, p.id || (p.indice === null ? "capítulo" : "elemento " + p.indice)].filter(Boolean).join(" · ") }),
    h("span", { text: p.mensaje })));
  }
}

async function irAProblema(p) {
  if (p.indice === null) return;
  if (p.capitulo !== S.capitulo) {
    if (!(await guardia())) return;
    setDirty(false);
    S.capitulo = p.capitulo;
    $("#sel-capitulo").value = String(p.capitulo);
    S.consulta = ""; $("#buscar").value = "";
    await cargarNavegacion();
  }
  if (S.consulta) { S.consulta = ""; $("#buscar").value = ""; await cargarNavegacion(); }
  const nodo = S.nodos.find((n) => n.indice === p.indice);
  if (nodo) {
    let padre = nodo.padre;
    while (padre !== null && padre !== undefined) {
      const sec = S.nodos.find((n) => n.indice === padre);
      if (!sec) break;
      S.colapsadas.delete(claveColapso(sec));
      padre = sec.padre;
    }
    await seleccionar(nodo.tipo, nodo.indice);
  }
}

function alternarPanelProblemas(abrir) {
  const panel = $("#problemas");
  const boton = $("#btn-problemas");
  const mostrarPanel = abrir === undefined ? panel.hidden : abrir;
  panel.hidden = !mostrarPanel;
  boton.setAttribute("aria-expanded", String(mostrarPanel));
  if (mostrarPanel) renderProblemas();
}

function fijarAlcance(todos) {
  S.alcanceTodos = todos;
  $("#alcance-todos").setAttribute("aria-pressed", String(todos));
  $("#alcance-capitulo").setAttribute("aria-pressed", String(!todos));
  renderProblemas();
}

/* ---- exportación ---- */
async function exportarDocx() {
  if (!(await guardia())) return;
  setDirty(false);
  const campo = h("input", { type: "number", min: "1", value: "1", style: { width: "90px" }, id: "primer-capitulo" });
  const r = await dialogo({
    titulo: "Exportar a Word",
    cuerpo: h("div", {},
      h("p", { text: `Se exportarán los ${plural(S.capitulos.length, "capítulo", "capítulos")} de ${enRequisitos() ? "requisitos" : "pruebas"} de la carpeta, en el orden del índice.` }),
      h("p", {}, h("label", { for: "primer-capitulo", text: "Número del primer título 1: " }), campo)),
    botones: [{ texto: "Cancelar", valor: "no", tipo: "ghost" }, { texto: "Elegir destino…", valor: "si", tipo: "primary" }],
  });
  if (r !== "si") return;
  try {
    const destino = await api.elegir_destino_docx();
    if (destino.cancelado) return;
    const d = await conEspera("Generando el documento de Word…",
      () => api.exportar_docx(Math.max(1, Number(campo.value) || 1), destino.archivo));
    const cuerpo = h("div", {},
      h("p", { text: (d.resumen || "Documento generado.").replace(/\s*->.*$/, ".") }),   // la ruta va en la línea de abajo
      h("p", { class: "muted", text: d.archivo }),
      d.avisos.length ? h("div", {}, h("p", { text: plural(d.avisos.length, "aviso del exportador:", "avisos del exportador:") }),
        h("ul", { class: "avisos-docx" }, d.avisos.slice(0, 40).map((a) => h("li", { text: a.replace(/^AVISO:\s*/, "") })))) : null);
    const botones = [{ texto: "Cerrar", valor: "cerrar", tipo: "primary" }];
    botones.unshift({ texto: "Mostrar en la carpeta", valor: "mostrar", tipo: "" });
    const respuesta = await dialogo({ titulo: "Documento exportado", cuerpo, botones });
    if (respuesta === "mostrar") await api.mostrar_en_carpeta(d.archivo).catch(fallo);
  } catch (e) { fallo(e); }
}

/* ---- panel lateral redimensionable ---- */
function iniciarDivisor() {
  const divisor = $("#divisor");
  const lateral = $("#lateral");
  const guardado = Number(leerLocal("ancho-lateral"));
  if (guardado >= 220) lateral.style.setProperty("--ancho-lateral", guardado + "px");
  const poner = (px) => {
    const ancho = Math.min(Math.max(px, 220), window.innerWidth * 0.7);
    lateral.style.setProperty("--ancho-lateral", ancho + "px");
    return ancho;
  };
  divisor.addEventListener("pointerdown", (e) => {
    divisor.setPointerCapture(e.pointerId);
    divisor.classList.add("activo");
    const mover = (ev) => poner(ev.clientX - lateral.getBoundingClientRect().left);
    const soltar = () => {
      divisor.classList.remove("activo");
      divisor.removeEventListener("pointermove", mover);
      divisor.removeEventListener("pointerup", soltar);
      guardarLocal("ancho-lateral", String(Math.round(lateral.getBoundingClientRect().width)));
    };
    divisor.addEventListener("pointermove", mover);
    divisor.addEventListener("pointerup", soltar);
  });
  divisor.addEventListener("keydown", (e) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    const nuevo = poner(lateral.getBoundingClientRect().width + (e.key === "ArrowRight" ? 24 : -24));
    guardarLocal("ancho-lateral", String(Math.round(nuevo)));
  });
}

/* ---- arranque ---- */
function conectar() {
  $("#btn-carpeta").addEventListener("click", elegirCarpeta);
  $("#sel-capitulo").addEventListener("change", (e) => cambiarCapitulo(e.target.value));
  $("#btn-recargar").addEventListener("click", async () => {
    if (!(await guardia())) return;
    setDirty(false);
    try {
      cacheImagenes.clear();
      aplicarResumen(await api.recargar());
      await cargarCobertura();
      await refrescarTodo({});
      aviso("Archivos recargados desde el disco", "ok");
    } catch (e) { fallo(e); }
  });
  iniciarMenu();
  iniciarBloqueos();
  $("#btn-nueva-prueba").addEventListener("click", nuevaPrueba);
  $("#btn-plegar-todo").addEventListener("click", () => plegarTodo(true));
  $("#btn-buscar-todo").addEventListener("click", buscarEnTodo);
  $("#btn-desplegar-todo").addEventListener("click", () => plegarTodo(false));
  $("#btn-nueva-seccion").addEventListener("click", nuevaSeccion);
  $("#filtro-cobertura").addEventListener("change", async (e) => {
    S.filtroCobertura = e.target.value;
    try { await cargarNavegacion(); } catch (err) { fallo(err); }
  });
  $("#btn-panel-traza").addEventListener("click", async () => {
    if (!(await guardia())) return;
    setDirty(false);
    S.seleccion = null;
    renderArbol();
    mostrarVacio();
  });
  $("#btn-problemas").addEventListener("click", () => alternarPanelProblemas());
  $("#btn-revalidar").addEventListener("click", validarEnSegundoPlano);
  $("#alcance-capitulo").addEventListener("click", () => fijarAlcance(false));
  $("#alcance-todos").addEventListener("click", () => fijarAlcance(true));
  $("#buscar").addEventListener("input", debounce(async (e) => {
    S.consulta = e.target.value.trim();
    try { await cargarNavegacion(); } catch (err) { fallo(err); }
  }, 180));
  iniciarArrastreArbol();
  iniciarDivisor();
  iniciarEjecucion();
  iniciarRobot();
  iniciarZoom();

  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
      e.preventDefault();
      guardarActual();
    } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "f" && !e.shiftKey) {
      if (!document.activeElement.closest(".cm-editor")) { e.preventDefault(); $("#buscar").focus(); $("#buscar").select(); }
    } else if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === "f" && !document.querySelector("dialog[open]")) {
      e.preventDefault();
      buscarEnTodo();
    }
  });
  window.addEventListener("beforeunload", (e) => { if (S.dirty) { e.preventDefault(); e.returnValue = ""; } });
}

async function arrancar() {
  await cargarPreferencias();
  if (["ejecucion", "requisitos"].includes(leerLocal("modo"))) S.modo = leerLocal("modo");
  conectar();
  pintarModo();
  mostrarSinCarpeta();
  try {
    S.esquema = await api.esquema();
    const resumen = await api.iniciar();
    aplicarResumen(enRequisitos() && resumen.carpeta ? await api.coleccion("requisitos") : resumen);
    if (resumen.aviso) aviso(resumen.aviso, "error");
    if (S.modo === "ejecucion") { await recuperarValidacion(); if (!S.validacion) await recuperarEjecucion(); }
    if (S.capitulos.length) {
      await cargarCobertura();
      await cargarNavegacion();
      mostrarVacio();
      validarEnSegundoPlano();
    } else if (enRequisitos() && S.carpeta) mostrarVacio();
  } catch (e) { fallo(e); }
}

arrancar();
