"use strict";
/* Validación de una versión: varias ejecuciones consolidadas por prueba y
   entorno de pruebas (ver validacion_core.py). Vive en el modo «Validación»
   junto a las ejecuciones: con una validación abierta y ninguna ejecución, el
   panel y el árbol muestran el resultado consolidado. */

const VAL_TXT = { validada: "Validada", no_ok: "NO OK", bloqueada: "Bloqueada", pendiente: "Pendiente", no_aplica: "No aplica" };
const VAL_ORDEN = ["validada", "no_ok", "bloqueada", "pendiente", "no_aplica"];
const CELDA_TXT = { ok: "OK", no_ok: "NO OK", bloqueada: "Bloqueada", no_aplica: "No aplica", pendiente: "Pendiente", sin_planificar: "Sin planificar" };
/** Clase de color de un estado (los de la validación usan los colores de los resultados). */
const claseEstado = (e) => ({ validada: "ok", sin_planificar: "pendiente" }[e] || e);

/* ---- abrir, crear, recientes ---- */
function recientesValidacion() {
  try { return JSON.parse(leerLocal("validaciones-recientes") || "[]"); } catch (_e) { return []; }
}

function recordarValidacion() {
  const lista = recientesValidacion().filter((r) => r.carpeta !== S.validacion.carpeta);
  lista.unshift({ carpeta: S.validacion.carpeta, nombre: S.validacion.datos.nombre });
  guardarLocal("validaciones-recientes", JSON.stringify(lista.slice(0, 8)));
}

/** Al entrar en el modo: la validación que tenga abierta Python o, si no, la última usada. */
async function recuperarValidacion() {
  try {
    const actual = await api.validacion_estado();
    if (actual) { S.validacion = actual; return; }
    if (leerLocal("sin-validacion") === "1") return;
    const ultima = recientesValidacion()[0];
    if (ultima) await usarValidacion(await api.validacion_abrir(ultima.carpeta), { silencio: true });
  } catch (_e) { /* ya no existe: se elegirá otra */ }
}

async function usarValidacion(r, { silencio = false } = {}) {
  if (!r || r.cancelado) return;
  if (r.carpeta_pruebas) {        // la validación usa otra carpeta de pruebas: se abre esa
    cacheImagenes.clear();
    S.capitulo = 0; S.consulta = ""; $("#buscar").value = ""; S.colapsadas.clear();
    aplicarResumen(r.carpeta_pruebas);
    await cargarCobertura();
    S.campana = null;
  }
  S.validacion = r;
  guardarLocal("sin-validacion", "0");
  recordarValidacion();
  pintarModo();
  if (!silencio) {
    S.seleccion = null;
    await cargarNavegacion();
    mostrarVacio();
    aviso(`Validación «${r.datos.nombre}» abierta`, "ok");
  }
}

async function refrescarValidacion() {
  if (!S.validacion) return;
  try { S.validacion = await api.validacion_estado(); } catch (e) { fallo(e); }
  pintarModo();
}

async function abrirValidacion(carpeta = null) {
  if (!(await guardia())) return;
  setDirty(false);
  try { await usarValidacion(await api.validacion_abrir(carpeta)); } catch (e) { fallo(e); }
}

async function soltarValidacion() {
  if (!(await guardia())) return;
  setDirty(false);
  try { await api.validacion_soltar(); } catch (e) { fallo(e); return; }
  S.validacion = null;
  guardarLocal("sin-validacion", "1");
  pintarModo();
  S.seleccion = null;
  await cargarNavegacion();
  mostrarVacio();
}

async function menuValidacion() {
  const lista = recientesValidacion().filter((r) => !S.validacion || r.carpeta !== S.validacion.carpeta);
  const cuerpo = h("div", { class: "menu-campana" },
    h("p", { class: "muted", text: "Una validación agrupa las ejecuciones de una versión (en Automático, Maqueta, Torre…) y da el resultado de cada prueba en cada entorno." }),
    S.validacion ? h("p", {}, "Abierta: ", h("strong", { text: S.validacion.datos.nombre }), h("br"), h("span", { class: "muted", text: S.validacion.carpeta })) : null,
    lista.length ? h("p", { class: "muted", text: "Recientes" }) : null,
    lista.map((r) => h("button", {
      type: "button", class: "btn ghost reciente", title: r.carpeta,
      onclick: (e) => e.target.closest("dialog").close("reciente:" + r.carpeta),
    }, h("span", { text: r.nombre }), h("span", { class: "muted", text: r.carpeta }))));
  const botones = [{ texto: "Cerrar", valor: "", tipo: "ghost" }];
  if (S.validacion) botones.push({ texto: "Trabajar sin validación", valor: "soltar", tipo: "" });
  botones.push({ texto: "Abrir validación…", valor: "abrir", tipo: "" }, { texto: "Nueva validación…", valor: "nueva", tipo: "primary" });
  const r = await dialogo({ titulo: "Validaciones de versión", cuerpo, botones });
  if (r === "nueva") await nuevaValidacion();
  else if (r === "abrir") await abrirValidacion();
  else if (r === "soltar") await soltarValidacion();
  else if (r && r.startsWith("reciente:")) await abrirValidacion(r.slice(9));
}

async function nuevaValidacion() {
  if (!S.capitulos.length) { aviso("Abre primero la carpeta de pruebas", "error"); return; }
  if (!(await guardia())) return;
  setDirty(false);
  let opciones;
  try { opciones = await api.campana_opciones(); } catch (e) { fallo(e); return; }
  const filtro = {};
  const { grupos, vista } = selectorFiltro(opciones, filtro, " hay que pasar para validar la versión:");
  const campo = (id, etiqueta, ayuda = "") => h("div", { class: "campo" },
    h("label", { for: id, text: etiqueta }), h("input", { id, type: "text", autocomplete: "off", placeholder: ayuda }));
  const cuerpo = h("div", { class: "nueva-campana" },
    h("div", { class: "rejilla" },
      campo("v-nombre", "Nombre *", "Validación v2.3"),
      campo("v-version", "Versión", "Firmware 2.3.0")),
    h("h3", { text: "Qué pruebas hay que pasar" }),
    h("p", { class: "muted", text: "Cada prueba tendrá que pasarse en los entornos que indica (Automático, Maqueta, Torre). Sin marcar nada entran todas." }),
    grupos, vista);
  const r = await dialogo({
    titulo: "Nueva validación de versión", cuerpo, ancho: true,
    botones: [{ texto: "Cancelar", valor: "no", tipo: "ghost" }, { texto: "Elegir carpeta y crear…", valor: "si", tipo: "primary" }],
  });
  if (r !== "si") return;
  const nombre = cuerpo.querySelector("#v-nombre").value.trim();
  if (!nombre) { aviso("La validación necesita un nombre", "error"); return; }
  try {
    aviso("Elige la carpeta donde guardar la validación (se creará una subcarpeta)…");
    const v = await api.validacion_crear(nombre, cuerpo.querySelector("#v-version").value, filtro);
    if (v.cancelado) return;
    S.campana = null;
    await usarValidacion(v);
  } catch (e) { fallo(e); }
}

async function editarValidacion() {
  const d = S.validacion.datos;
  const campo = (id, etiqueta, valor) => h("div", { class: "campo" },
    h("label", { for: id, text: etiqueta }), h("input", { id, type: "text", autocomplete: "off", value: valor || "" }));
  const cuerpo = h("div", { class: "rejilla" }, campo("ve-nombre", "Nombre *", d.nombre), campo("ve-version", "Versión", d.version));
  const r = await dialogo({
    titulo: "Datos de la validación", cuerpo,
    botones: [{ texto: "Cancelar", valor: "no", tipo: "ghost" }, { texto: "Guardar", valor: "si", tipo: "primary" }],
  });
  if (r !== "si") return;
  try {
    S.validacion = await api.validacion_editar({ nombre: cuerpo.querySelector("#ve-nombre").value, version: cuerpo.querySelector("#ve-version").value });
    recordarValidacion();
    pintarModo();
    mostrarVacio();
  } catch (e) { fallo(e); }
}

async function informeValidacion() {
  let conPdf = null;
  try { conPdf = await api.campana_pdf_disponible(); } catch (_e) { /* sin PDF */ }
  const casilla = h("input", { type: "checkbox", id: "informe-val-pdf", disabled: !conPdf });
  casilla.checked = Boolean(conPdf) && leerLocal("informe-pdf") === "si";
  const r = await dialogo({
    titulo: S.validacion.borrador ? "Informe de validación (borrador)" : "Informe de validación",
    cuerpo: h("div", {},
      h("p", { text: "Un documento de Word con los datos de la versión, el resultado consolidado, las ejecuciones, el resultado por entorno, las pruebas no validadas y la tabla de cada prueba en cada entorno. El detalle de cada prueba está en el informe de cada ejecución." }),
      S.validacion.borrador ? h("p", { class: "aviso-panel", text: "Alguna ejecución sigue abierta: el informe saldrá marcado como BORRADOR." }) : null,
      h("p", {}, h("label", { class: "casilla" }, casilla, " Generar también el PDF"),
        conPdf ? h("span", { class: "muted", text: ` (con ${conPdf})` }) : h("span", { class: "muted", text: " (necesita LibreOffice o Microsoft Word)" }))),
    botones: [{ texto: "Cancelar", valor: "no", tipo: "ghost" }, { texto: "Elegir destino…", valor: "si", tipo: "primary" }],
  });
  if (r !== "si") return;
  guardarLocal("informe-pdf", casilla.checked ? "si" : "no");
  try {
    const destino = await api.validacion_elegir_destino_informe();
    if (destino.cancelado) return;
    const d = await conEspera(casilla.checked ? "Generando el informe y el PDF…" : "Generando el informe…",
      () => api.validacion_informe(destino.archivo, casilla.checked));
    const respuesta = await dialogo({
      titulo: "Informe generado",
      cuerpo: h("div", {},
        h("p", { text: `${plural(d.pruebas, "prueba", "pruebas")} en el informe.` }),
        h("p", { class: "muted", text: d.archivo }),
        d.pdf ? h("p", { class: "muted", text: d.pdf }) : null,
        d.aviso_pdf ? h("p", { class: "aviso-panel", text: d.aviso_pdf }) : null),
      botones: [{ texto: "Mostrar en la carpeta", valor: "mostrar", tipo: "" }, { texto: "Cerrar", valor: "", tipo: "primary" }],
    });
    if (respuesta === "mostrar") await api.mostrar_en_carpeta(d.pdf || d.archivo).catch(fallo);
  } catch (e) { fallo(e); }
}

/* ---- sus ejecuciones ---- */
async function anadirEjecucionExistente() {
  try {
    aviso("Elige la carpeta de una ejecución, o una carpeta con varias (por ejemplo, la compartida donde las deja cada persona)…");
    const r = await api.validacion_anadir_ejecucion();
    if (r.cancelado) return;
    const { anadidas, ya_estaban: estaban, campana, ...estado } = r;
    if (campana) S.campana = campana;
    S.validacion = estado;
    pintarModo();
    await cargarNavegacion();
    mostrarVacio();
    if (anadidas.length) aviso(`${plural(anadidas.length, "ejecución añadida", "ejecuciones añadidas")}${estaban.length ? ` (${estaban.length} ya estaban)` : ""}`, "ok");
    else aviso(estaban.length > 1 ? "Esas ejecuciones ya estaban en la validación" : "Esa ejecución ya estaba en la validación", "error");
  } catch (e) { fallo(e); }
}

async function quitarEjecucion(e) {
  const ok = await confirmar("Quitar la ejecución",
    `«${e.nombre || e.ruta}» dejará de contar para esta validación. La ejecución no se borra: se puede volver a añadir.`, "Quitar", true);
  if (!ok) return;
  try {
    S.validacion = await api.validacion_quitar_ejecucion(e.indice);
    if (S.campana && e.carpeta && S.campana.carpeta === e.carpeta) S.campana = null;
    pintarModo();
    await cargarNavegacion();
    mostrarVacio();
  } catch (err) { fallo(err); }
}

/** Abre una ejecución de la validación (y, si se indica, una de sus pruebas). */
async function abrirEjecucionDeValidacion(carpeta, testId = null) {
  if (!(await guardia())) return;
  setDirty(false);
  try {
    await usarCampana(await api.campana_abrir(carpeta), { silencio: Boolean(testId) });
    if (testId) {
      await cargarNavegacion();
      await irAPruebaCampana(testId);
    }
  } catch (e) { fallo(e); }
}

/** Añade a la validación abierta la ejecución abierta (que se abrió por su cuenta). */
async function anadirAbiertaAValidacion() {
  try {
    const { anadidas, ya_estaban: _estaban, campana, ...estado } = await api.validacion_anadir_ejecucion(S.campana.carpeta);
    S.validacion = estado;
    if (campana) S.campana = campana;
    pintarModo();
    mostrarVacio();
    if (anadidas.length) aviso(`Ejecución añadida a la validación «${estado.datos.nombre}»`, "ok");
  } catch (e) { fallo(e); }
}

/** Desde una ejecución: volver al resumen de su validación. */
async function volverAValidacion() {
  if (!(await guardia())) return;
  setDirty(false);
  let r;
  try { r = await api.campana_soltar(); } catch (e) { fallo(e); return; }
  if (r && r.carpeta_pruebas) {
    cacheImagenes.clear();
    S.capitulo = 0; S.consulta = ""; $("#buscar").value = "";
    aplicarResumen(r.carpeta_pruebas);
  }
  S.campana = null;
  R = null;
  S.seleccion = null;
  S.filtroEstado = ""; $("#filtro-estado").value = "";
  await refrescarValidacion();
  await cargarNavegacion();
  mostrarVacio();
}

/* ---- árbol ---- */
function mapaValidacion() {
  return new Map(S.validacion ? S.validacion.pruebas.map((p) => [p.id, p.estado]) : []);
}

/* ---- panel de la validación ---- */
function chipEstadoValidacion(estado, extra = "") {
  return h("span", { class: `chip-estado e-${claseEstado(estado)} ${extra}`, text: VAL_TXT[estado] || CELDA_TXT[estado] || estado });
}

/** Celda de la tabla prueba × entorno. */
function celdaEntorno(p, entorno) {
  const c = p.entornos[entorno];
  if (!c) return h("td", { class: "celda-entorno no-pide", text: p.requeridos.length && !p.requeridos.includes(entorno) ? "" : "—" });
  const v = c.vigente;
  const titulo = [
    c.cuenta ? null : "Este entorno no lo pide la prueba: se muestra, pero no cuenta.",
    v && v.estado !== "pendiente" ? `${CELDA_TXT[v.estado]} en «${v.ejecucion}» (${fechaCorta(v.fecha)}${v.ejecutor ? ", " + v.ejecutor : ""})` : null,
    v && v.estado === "pendiente" ? `Planificada en «${v.ejecucion}», sin ejecutar` : null,
    !v ? "Ninguna ejecución de este entorno la incluye" : null,
    c.historial.length > 1 ? `${c.historial.length - 1} resultado(s) anterior(es) en este entorno` : null,
  ].filter(Boolean).join("\n");
  return h("td", { class: "celda-entorno" + (c.cuenta ? "" : " no-cuenta"), title: titulo },
    h("span", { class: `chip-estado peq e-${claseEstado(c.estado)}`, text: CELDA_TXT[c.estado] || c.estado }),
    c.historial.length > 1 ? h("span", { class: "muted historial-n", text: ` +${c.historial.length - 1}` }) : null);
}

let filtroTablaValidacion = "";
let filtroRequisitosValidacion = "";
let filtroComparacion = null;          // null: todas menos «sin cambios»

/* ---- requisitos de la validación ---- */
const REQ_VAL_TXT = { fallido: "Fallidos", bloqueado: "Bloqueados", pendiente: "Pendientes", verificado: "Verificados",
  sin_pruebas: "Sin pruebas aquí", no_aplica: "No aplica" };
const REQ_VAL_UNO = { fallido: "Fallido", bloqueado: "Bloqueado", pendiente: "Pendiente", verificado: "Verificado",
  sin_pruebas: "Sin pruebas aquí", no_aplica: "No aplica" };
const REQ_VAL_ORDEN = ["verificado", "fallido", "bloqueado", "pendiente", "sin_pruebas", "no_aplica"];
/** Color de un estado de requisito: el del resultado de prueba equivalente. */
const claseRequisito = (e) => claseEstado({ fallido: "no_ok", bloqueado: "bloqueada", pendiente: "pendiente", verificado: "validada",
  sin_pruebas: "sin_planificar", no_aplica: "no_aplica" }[e]);

function bloqueRequisitosValidacion(v) {
  const r = v.requisitos;
  if (!r) return null;
  const t = r.totales;
  const caja = h("div", {});
  const pintar = () => {
    const filas = r.lista.filter((x) => !filtroRequisitosValidacion || x.estado === filtroRequisitosValidacion);
    const pruebaPorId = new Map(v.pruebas.map((p) => [p.id, p]));
    caja.replaceChildren(
      h("div", { class: "barra-progreso", role: "img", "aria-label": `${t.verificado} requisitos verificados` },
        REQ_VAL_ORDEN.map((e) => t[e] ? h("span", { class: "e-" + claseRequisito(e), style: { flexGrow: String(t[e]) }, title: `${REQ_VAL_TXT[e]}: ${t[e]}` }) : null)),
      h("div", { class: "tarjetas" }, REQ_VAL_ORDEN.map((e) => h("button", {
        type: "button", class: `tarjeta pulsable e-${claseRequisito(e)}${filtroRequisitosValidacion === e ? " activa" : ""}`,
        title: "Ver solo estos (vuelve a pulsar para verlos todos)",
        onclick: () => { filtroRequisitosValidacion = filtroRequisitosValidacion === e ? "" : e; pintar(); },
      }, h("span", { class: "t-tit", text: REQ_VAL_TXT[e] }), h("span", { class: "t-val", text: String(t[e]) }),
      e === "verificado" ? h("span", { class: "t-extra", text: `${r.porcentaje_verificados} %` }) : null))),
      r.impacto.length ? h("div", { class: "aviso-panel aviso-fuera" },
        h("span", { text: `${plural(r.modificados, "requisito ha cambiado", "requisitos han cambiado")} desde la última revisión de sus pruebas: conviene volver a pasar ${plural(r.impacto.length, "prueba", "pruebas")}.` }),
        h("button", { class: "btn peq", type: "button", text: "Ejecución de impacto…", onclick: () => nuevaEjecucionImpacto(r.impacto) })) : null,
      h("table", { class: "tabla-estados tabla-requisitos-val" },
        h("thead", {}, h("tr", {}, h("th", { text: "Requisito" }), h("th", { class: "centro", text: "Estado" }), h("th", { text: "Pruebas en esta validación" }))),
        h("tbody", {}, filas.slice(0, 1500).map((x) => h("tr", {},
          h("td", {}, h("span", { class: "tid", text: x.id }), " ", h("span", { class: "muted", text: x.titulo }),
            x.modificado ? h("span", { class: "marca-cambio", title: "Ha cambiado: revisa sus pruebas" }, icon("alert")) : null),
          h("td", { class: "centro" }, h("span", { class: `chip-estado peq e-${claseRequisito(x.estado)}`, text: REQ_VAL_UNO[x.estado] })),
          h("td", {}, h("div", { class: "pruebas-requisito" },
            x.pruebas.map((p) => h("button", { type: "button", class: `chip-estado peq e-${claseEstado(p.estado)} pulsable`, text: p.id,
              title: `${VAL_TXT[p.estado]}: ver la prueba`, onclick: () => { const q = pruebaPorId.get(p.id); if (q) irAPruebaValidacion(q); } })),
            x.fuera.length ? h("span", { class: "muted peq", text: ` +${x.fuera.length} fuera de la validación`, title: x.fuera.join(", ") } ) : null,
            !x.pruebas.length && x.necesita && !x.fuera.length ? h("span", { class: "muted peq", text: "ninguna prueba lo cita" }) : null)))))),
      filas.length > 1500 ? h("p", { class: "muted", text: `Se muestran los 1500 primeros de ${filas.length}.` }) : null);
  };
  pintar();
  return h("section", { class: "bloque" },
    h("div", { class: "bloque-cab" }, h("h3", { text: "Requisitos" }),
      h("p", { class: "ayuda", text: "Un requisito está verificado cuando todas las pruebas de esta validación que lo citan están validadas; falla si alguna es NO OK. «Sin pruebas aquí»: necesita pruebas, pero ninguna de esta validación lo cita." })),
    caja);
}

/** Ejecución con las pruebas de los requisitos que han cambiado (dentro de la validación). */
async function nuevaEjecucionImpacto(ids) {
  const nombre = h("input", { id: "imp-nombre-ej", type: "text", autocomplete: "off", value: "Impacto de requisitos cambiados" });
  let entorno = "";
  const responsable = h("input", { id: "imp-responsable", type: "text", autocomplete: "off", value: leerLocal("ejecutor") || "" });
  const r = await dialogo({
    titulo: "Ejecución de impacto", ancho: true,
    cuerpo: h("div", { class: "nueva-campana" },
      h("p", { text: `Una ejecución nueva, dentro de la validación, con las ${plural(ids.length, "prueba", "pruebas")} de los requisitos que han cambiado: ${ids.join(", ")}.` }),
      h("div", { class: "rejilla" },
        h("div", { class: "campo completo" }, h("label", { for: "imp-nombre-ej", text: "Nombre *" }), nombre),
        selectorEntorno("imp-entorno-ej", "", (_a, n) => { entorno = n; }),
        h("div", { class: "campo" }, h("label", { for: "imp-responsable", text: "Responsable" }), responsable))),
    botones: [{ texto: "Cancelar", valor: "no", tipo: "ghost" }, { texto: "Crear ejecución", valor: "si", tipo: "primary" }],
  });
  if (r !== "si") return;
  if (!nombre.value.trim()) { aviso("La ejecución necesita un nombre", "error"); return; }
  if (!entorno) { aviso("Indica en qué entorno de pruebas se ejecuta", "error"); return; }
  try {
    await usarCampana(await api.validacion_nueva_ejecucion(nombre.value.trim(), { solo_ids: ids }, { entorno_pruebas: entorno, responsable: responsable.value }));
    await refrescarValidacion();
  } catch (e) { fallo(e); }
}

/* ---- comparar con otra validación (o ejecución) ---- */
const CMP_TXT = { nuevo_fallo: "Nuevos fallos", arreglada: "Arregladas", sigue_fallando: "Siguen fallando", otros_cambios: "Otros cambios",
  nueva: "Nuevas", ya_no_esta: "Ya no están", sin_cambios: "Sin cambios" };
const CMP_CLASE = { nuevo_fallo: "no_ok", arreglada: "ok", sigue_fallando: "no_ok", otros_cambios: "bloqueada", nueva: "pendiente",
  ya_no_esta: "no_aplica", sin_cambios: "no_aplica" };

/** Cifras y tabla de una comparación. `alPulsar(fila)` abre la prueba (si se puede). */
function tablaComparacion(c, alPulsar = null) {
  const caja = h("div", {});
  const pintar = () => {
    const orden = Object.keys(CMP_TXT);
    const filas = c.filas.filter((f) => (filtroComparacion ? f.categoria === filtroComparacion : f.categoria !== "sin_cambios"))
      .sort((x, y) => orden.indexOf(x.categoria) - orden.indexOf(y.categoria));
    caja.replaceChildren(
      h("div", { class: "tarjetas tarjetas-7" }, Object.keys(CMP_TXT).map((k) => h("button", {
        type: "button", class: `tarjeta pulsable e-${CMP_CLASE[k]}${filtroComparacion === k ? " activa" : ""}`,
        title: "Ver solo estas (vuelve a pulsar para ver todos los cambios)",
        onclick: () => { filtroComparacion = filtroComparacion === k ? null : k; pintar(); },
      }, h("span", { class: "t-tit", text: CMP_TXT[k] }), h("span", { class: "t-val", text: String(c.cuentas[k]) })))),
      filas.length ? h("table", { class: "tabla-estados" },
        h("thead", {}, h("tr", {}, h("th", { text: "Prueba" }), h("th", { class: "centro", text: "Antes" }), h("th", { class: "centro", text: "Ahora" }), h("th", { text: "Cambio" }))),
        h("tbody", {}, filas.slice(0, 1500).map((f) => h("tr", alPulsar && f.ahora ? { class: "pulsable", title: "Ver la prueba", onclick: () => alPulsar(f) } : {},
          h("td", {}, h("span", { class: "tid", text: f.id }), " ", h("span", { class: "muted", text: f.titulo })),
          h("td", { class: "centro" }, f.antes ? chipEstadoValidacion(f.antes, "peq") : h("span", { class: "muted", text: "—" })),
          h("td", { class: "centro" }, f.ahora ? chipEstadoValidacion(f.ahora, "peq") : h("span", { class: "muted", text: "—" })),
          h("td", { text: CMP_TXT[f.categoria] })))))
        : h("p", { class: "muted", text: filtroComparacion ? "Ninguna." : "Ningún cambio respecto a la anterior." }));
  };
  pintar();
  return caja;
}

function bloqueComparacion(v) {
  const c = v.comparacion;
  const botones = (...b) => h("div", { class: "fila-botones" }, ...b);
  const elegir = h("button", { class: "btn peq", type: "button", text: c ? "Cambiar…" : "Comparar con otra validación…", onclick: () => compararValidacionCon() });
  let cuerpo;
  if (!c) cuerpo = [h("p", { class: "muted", text: "Compárala con la validación de la versión anterior para ver los nuevos fallos y lo que se ha arreglado. Sale también en el informe." }), botones(elegir)];
  else if (!c.encontrada) cuerpo = [h("p", { class: "aviso-panel", text: `No se encuentra la validación con la que se compara (${c.ruta}).` }), botones(elegir, botonQuitarComparacion())];
  else {
    cuerpo = [
      h("p", { class: "ayuda" }, "Con ", h("strong", { text: c.nombre }), c.version ? ` (${c.version})` : "", ". ",
        "«Nuevos fallos»: NO OK ahora y no antes; «Arregladas»: NO OK antes y bien ahora."),
      tablaComparacion(c, (f) => { const p = v.pruebas.find((x) => x.id === f.id); if (p) irAPruebaValidacion(p); }),
      botones(elegir, botonQuitarComparacion()),
    ];
  }
  return h("section", { class: "bloque" }, h("div", { class: "bloque-cab" }, h("h3", { text: "Comparación con la anterior" })), cuerpo);
}

function botonQuitarComparacion() {
  return h("button", { class: "btn ghost peq", type: "button", text: "Quitar", onclick: async () => {
    try { S.validacion = await api.validacion_quitar_comparacion(); mostrarVacio(); } catch (e) { fallo(e); }
  } });
}

async function compararValidacionCon() {
  try {
    aviso("Elige la carpeta de la otra validación (normalmente, la de la versión anterior)…");
    const r = await api.validacion_comparar_con();
    if (r.cancelado) return;
    S.validacion = r;
    filtroComparacion = null;
    mostrarVacio();
  } catch (e) { fallo(e); }
}

/** Desde el resumen de una ejecución: compararla con otra (la anterior). */
async function compararEjecucion() {
  let r;
  try {
    aviso("Elige la carpeta de la otra ejecución (la anterior)…");
    r = await api.campana_comparar();
  } catch (e) { fallo(e); return; }
  if (r.cancelado) return;
  filtroComparacion = null;
  await dialogo({
    titulo: `Comparación: «${r.anterior.nombre}» → «${r.actual.nombre}»`, ancho: true,
    cuerpo: h("div", {}, h("p", { class: "ayuda", text: "«Nuevos fallos»: NO OK ahora y no antes; «Arregladas»: NO OK antes y OK (o No aplica) ahora." }),
      tablaComparacion(r)),
    botones: [{ texto: "Cerrar", valor: "", tipo: "primary" }],
  });
}

function mostrarPanelValidacion() {
  const v = S.validacion;
  const d = v.datos;
  const t = v.totales;
  const barra = h("div", { class: "barra-progreso", role: "img", "aria-label": `${t.validada} de ${v.total} validadas` },
    VAL_ORDEN.map((e) => t[e] ? h("span", { class: "e-" + claseEstado(e), style: { flexGrow: String(t[e]) }, title: `${VAL_TXT[e]}: ${t[e]}` }) : null));
  const tarjeta = (estado, extra = "") => h("button", {
    type: "button", class: `tarjeta pulsable e-${claseEstado(estado)}`, title: "Ver solo estas en la tabla y en el árbol",
    onclick: () => filtrarValidacion(estado),
  }, h("span", { class: "t-tit", text: VAL_TXT[estado] }), h("span", { class: "t-val", text: String(t[estado]) }), extra ? h("span", { class: "t-extra", text: extra }) : null);

  const entornos = v.entornos;
  const tablaEntornos = h("table", { class: "tabla-estados" },
    h("thead", {}, h("tr", {}, ["Entorno", "Pruebas", "OK", "NO OK", "Bloqueada", "No aplica", "Pendiente", "Sin planificar"]
      .map((x, i) => h("th", { class: i ? "num" : "", text: x })))),
    h("tbody", {}, Object.entries(v.por_entorno).map(([e, c]) => h("tr", {},
      h("td", { text: e }), h("td", { class: "num", text: String(c.necesitan) }),
      ["ok", "no_ok", "bloqueada", "no_aplica", "pendiente", "sin_planificar"].map((k) =>
        h("td", { class: "num" + (c[k] ? " e-txt-" + claseEstado(k) : ""), text: c[k] ? String(c[k]) : "·" }))))));

  const ejecuciones = v.ejecuciones.length
    ? h("table", { class: "tabla-estados tabla-ejecuciones" },
      h("thead", {}, h("tr", {}, ["Ejecución", "Entorno", "Estado", "Avance", "Responsable", ""].map((x) => h("th", { text: x })))),
      h("tbody", {}, v.ejecuciones.map((e) => h("tr", { class: e.encontrada ? "pulsable" : "", title: e.encontrada ? "Abrir la ejecución" : e.ruta,
        onclick: (ev) => { if (e.encontrada && !ev.target.closest(".quitar")) abrirEjecucionDeValidacion(e.carpeta); } },
        h("td", { text: e.encontrada ? e.nombre : `${e.ruta} (no se encuentra)` }),
        h("td", { text: e.encontrada ? e.entorno_pruebas || "(sin indicar)" : "" }),
        h("td", {}, e.encontrada ? h("span", { class: "chip-estado " + (e.cerrada ? "cerrada" : "abierta"), text: e.cerrada ? "Cerrada" : "Abierta" }) : null),
        h("td", { text: e.encontrada ? `${e.ejecutadas}/${e.total}` : "" }),
        h("td", { text: e.responsable || "" }),
        h("td", { class: "acciones-fila" }, botonIcono("x", "Quitar de la validación", () => quitarEjecucion(e), "quitar"))))))
    : h("p", { class: "muted", text: "Todavía no hay ejecuciones. Añade las que ha hecho cada persona («Añadir ejecuciones…»: una, o una carpeta con varias) o crea una nueva." });

  const filas = v.pruebas.filter((p) => !filtroTablaValidacion || p.estado === filtroTablaValidacion);
  const selFiltro = h("select", {
    class: "peq", "aria-label": "Mostrar",
    onchange: (e) => filtrarValidacion(e.target.value),
  }, [["", "Todas las pruebas"], ...VAL_ORDEN.map((e) => [e, VAL_TXT[e]])].map(([val, txt]) => h("option", { value: val, text: txt, selected: val === filtroTablaValidacion })));
  const matriz = h("table", { class: "tabla-estados tabla-matriz" },
    h("thead", {}, h("tr", {}, h("th", { text: "Prueba" }), entornos.map((e) => h("th", { class: "centro", text: e })), h("th", { class: "centro", text: "Versión" }))),
    h("tbody", {}, filas.slice(0, 1500).map((p) => h("tr", { class: "pulsable", title: "Ver la prueba", onclick: () => irAPruebaValidacion(p) },
      h("td", {}, h("span", { class: "tid", text: p.id }), " ", h("span", { class: "muted", text: p.titulo })),
      entornos.map((e) => celdaEntorno(p, e)),
      h("td", { class: "centro" }, chipEstadoValidacion(p.estado))))));

  const avisos = v.avisos.length
    ? h("ul", { class: "lista-problemas en-panel" }, v.avisos.map((a) => h("li", {
      title: a.id ? "Ver la prueba" : "", onclick: () => { const p = v.pruebas.find((x) => x.id === a.id); if (p) irAPruebaValidacion(p); },
    }, h("span", { class: "sev " + a.tipo }), h("span", { class: "donde", text: a.id || "validación" }), h("span", { text: a.mensaje }))))
    : h("p", { class: "muted", text: "Sin avisos." });

  mostrar(h("div", { class: "formulario panel-campana panel-validacion" },
    h("div", { class: "acciones" },
      h("div", { class: "titulo" }, h("span", { class: "nombre", text: d.nombre }),
        h("span", { class: "ruta", text: [d.version, `${plural(v.total, "prueba", "pruebas")}`, plural(v.ejecuciones.length, "ejecución", "ejecuciones")].filter(Boolean).join(" · ") })),
      h("span", { class: "chip-estado " + (v.borrador ? "abierta" : "cerrada"), title: v.borrador ? "Alguna ejecución sigue abierta" : "Todas las ejecuciones están cerradas", text: v.borrador ? "En curso" : "Ejecuciones cerradas" }),
      h("button", { class: "btn", type: "button", onclick: anadirEjecucionExistente, title: "Añadir ejecuciones que ya existen (las de cada persona): elige una, o una carpeta que contenga varias" }, "Añadir ejecuciones…"),
      h("button", { class: "btn", type: "button", onclick: editarValidacion, text: "Cambiar datos…" }),
      h("button", { class: "btn", type: "button", onclick: informeValidacion, text: "Generar informe…",
        title: v.borrador ? "Borrador: alguna ejecución sigue abierta" : "Informe de la versión" }),
      h("button", { class: "btn primary", type: "button", onclick: () => nuevaCampana({ enValidacion: true }) }, icon("plus"), "Nueva ejecución")),
    h("section", { class: "bloque" },
      h("div", { class: "bloque-cab" }, h("h3", { text: "Resultado de la versión" }),
        h("p", { class: "ayuda", text: `${t.validada} de ${v.total - t.no_aplica} pruebas validadas (${v.porcentaje_validadas} %): OK en todos sus entornos.` })),
      barra,
      h("div", { class: "tarjetas" },
        tarjeta("validada", `${v.porcentaje_validadas} %`), tarjeta("no_ok"), tarjeta("bloqueada"), tarjeta("pendiente"), tarjeta("no_aplica"))),
    bloqueComparacion(v),
    bloqueRequisitosValidacion(v),
    h("section", { class: "bloque" }, h("div", { class: "bloque-cab" }, h("h3", { text: "Ejecuciones" })), ejecuciones),
    h("section", { class: "bloque" }, h("div", { class: "bloque-cab" }, h("h3", { text: "Por entorno" }),
      h("p", { class: "ayuda", text: "Cuántas pruebas piden cada entorno y su resultado en él. «Sin planificar»: ninguna ejecución de ese entorno las incluye." })), tablaEntornos),
    h("section", { class: "bloque" },
      h("div", { class: "bloque-cab" }, h("h3", { text: `Pruebas (${filas.length})` }), selFiltro,
        h("p", { class: "ayuda", text: "En gris, resultados en un entorno que la prueba no pide (no cuentan). Pasa el ratón por una celda para ver la ejecución." })),
      matriz,
      filas.length > 1500 ? h("p", { class: "muted", text: `Se muestran las 1500 primeras de ${filas.length}; usa el filtro.` }) : null),
    h("section", { class: "bloque" }, h("div", { class: "bloque-cab" }, h("h3", { text: `Avisos (${v.avisos.length})` })), avisos),
    h("section", { class: "bloque" },
      h("dl", { class: "datos-campana" },
        h("dt", { text: "Carpeta" }), h("dd", {}, h("button", { class: "enlace", type: "button", text: v.carpeta, onclick: () => api.mostrar_en_carpeta(v.carpeta + "/validacion.yaml").catch(fallo) })),
        h("dt", { text: "Pruebas" }), h("dd", { text: String(d.pruebas_yaml || "") })))));
}

async function filtrarValidacion(estado) {
  filtroTablaValidacion = estado;
  S.filtroEstado = estado ? claseEstado(estado) : "";
  $("#filtro-estado").value = S.filtroEstado;
  await cargarNavegacion();
  if (!S.seleccion) mostrarVacio();
}

async function irAPruebaValidacion(p) {
  const ci = S.capitulos.findIndex((c) => c.archivo === p.archivo);
  if (ci < 0) return;
  if (ci !== S.capitulo || S.consulta) {
    S.capitulo = ci;
    $("#sel-capitulo").value = String(ci);
    S.consulta = ""; $("#buscar").value = "";
  }
  await cargarNavegacion();
  const nodo = S.nodos.find((n) => n.indice === p.indice);
  for (let padre = nodo ? nodo.padre : null; padre !== null && padre !== undefined;) {
    const sec = S.nodos.find((n) => n.indice === padre);
    if (!sec) break;
    S.colapsadas.delete(claveColapso(sec));
    padre = sec.padre;
  }
  S.seleccion = null;
  await seleccionar("prueba", p.indice);
}

/** Ficha de una prueba con su resultado en cada entorno (sin ejecución abierta). */
function mostrarPruebaValidacion(datos) {
  F = null; R = null;
  const el = datos.elemento;
  const p = S.validacion.pruebas.find((x) => x.id === String(el.id || ""));
  const bloque = !p
    ? h("p", { class: "aviso-panel", text: "Esta prueba no entra en la validación (no cumple su criterio)." })
    : h("div", { class: "panel-resultado resultados-entorno" },
      h("h3", { text: "Resultado en la versión" }),
      chipEstadoValidacion(p.estado, "grande"),
      Object.entries(p.entornos).map(([entorno, c]) => h("div", { class: "entorno-resultado" + (c.cuenta ? "" : " no-cuenta") },
        h("div", { class: "entorno-cab" }, h("strong", { text: entorno }), h("span", { class: `chip-estado peq e-${claseEstado(c.estado)}`, text: CELDA_TXT[c.estado] }),
          c.cuenta ? null : h("span", { class: "muted", text: "no lo pide la prueba" })),
        c.historial.length
          ? h("ul", { class: "historial-entorno" }, c.historial.map((r, i) => h("li", { class: i ? "anterior" : "" },
            h("span", { class: `punto-estado e-${claseEstado(r.estado)}` }),
            h("span", { text: `${CELDA_TXT[r.estado]} · ${r.estado === "pendiente" ? "sin ejecutar" : fechaCorta(r.fecha)}${r.ejecutor ? " · " + r.ejecutor : ""}` }),
            h("button", { class: "enlace", type: "button", text: r.ejecucion, title: "Abrir esta prueba en la ejecución",
              onclick: () => abrirEjecucionDeValidacion(S.validacion.ejecuciones[r.ejecucion_indice].carpeta, p.id) }),
            r.observaciones ? h("span", { class: "muted obs", text: r.observaciones }) : null)))
          : h("p", { class: "muted", text: "Ninguna ejecución de este entorno la incluye." }))));
  mostrar(h("div", { class: "vista-ejecucion" },
    h("div", { class: "acciones" },
      h("span", { class: "placa" }, h("span", { class: "texto-placa", text: el.id || "(sin ID)" })),
      h("div", { class: "titulo" }, h("span", { class: "nombre", text: el.titulo || el.nombre || "" }),
        h("span", { class: "ruta", text: `Validación «${S.validacion.datos.nombre}»` })),
      p ? chipEstadoValidacion(p.estado, "grande") : null),
    h("div", { class: "columnas-ejecucion" }, fichaPrueba(el), bloque)));
}
