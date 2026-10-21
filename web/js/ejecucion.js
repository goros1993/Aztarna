"use strict";
/* Modo «Ejecución»: ejecuciones, resultado de cada prueba y resumen.
   Los YAML de pruebas solo se leen; los resultados van a la carpeta de la
   ejecución (ver ejecucion_core.py). */

const ESTADOS = ["ok", "no_ok", "bloqueada", "no_aplica", "pendiente"];
const ESTADO_TXT = { pendiente: "Pendiente", ok: "OK", no_ok: "NO OK", bloqueada: "Bloqueada", no_aplica: "No aplica" };
const ESTADO_AYUDA = {
  ok: "Se ejecutó y el resultado es el esperado.",
  no_ok: "Se ejecutó y el producto no se comporta como se espera.",
  bloqueada: "No se pudo ejecutar por algo ajeno al producto: banco, hardware, otra prueba que falló…",
  no_aplica: "No aplica a esta versión o configuración.",
  pendiente: "Todavía sin ejecutar.",
};
const AUTOMATIZABLE_TXT = { si: "Sí", no: "No", corto: "Corto", medio: "Medio", largo: "Largo", hecho: "Hecho" };

let R = null;   // resultado que se está editando: {id, estado, observaciones, incidencia, evidencias, ejecutor}

const enEjecucion = () => S.modo === "ejecucion";
const cerrada = () => Boolean(S.ejecucion && S.ejecucion.cerrada);

/** Estado de cada prueba: el de la ejecución abierta o, sin ejecución, el consolidado de la validación. */
function mapaEstados() {
  if (S.ejecucion) return new Map(S.ejecucion.resumen.pruebas.map((p) => [p.id, p.estado]));
  return new Map(S.validacion ? S.validacion.pruebas.map((p) => [p.id, claseEstado(p.estado)]) : []);
}

/* ---- modo ---- */
function pintarModo() {
  const ej = enEjecucion();
  $("#app").classList.toggle("modo-ejecucion", ej);
  $("#app").classList.toggle("modo-requisitos", enRequisitos());
  $("#modo-edicion").setAttribute("aria-pressed", String(S.modo === "edicion"));
  $("#modo-requisitos").setAttribute("aria-pressed", String(enRequisitos()));
  $("#modo-ejecucion").setAttribute("aria-pressed", String(ej));
  $("#txt-nueva").textContent = enRequisitos() ? "Requisito" : "Prueba";
  $("#buscar").placeholder = enRequisitos() ? "Buscar requisito por ID o texto" : "Buscar por ID o texto";
  pintarRuta();
  pintarFranja();
  pintarTituloLateral();
  pintarVolver();
  $("#filtro-estado").value = S.filtroEstado;
  etiquetarCapitulos();
}

/* ---- dónde estás: ruta de la barra, franja, título del árbol y vuelta ---- */
let migaPrueba = null;      // ID de la prueba abierta en el modo Validar (último tramo de la ruta)

/** Ruta de la barra: validación › ejecución › prueba. */
function pintarRuta() {
  const v = S.validacion, e = S.ejecucion;
  $("#validacion-nombre").textContent = v ? v.datos.nombre : "Sin validación";
  $("#btn-validacion").title = !v ? "Crear o abrir la validación de una versión"
    : e || migaPrueba ? `Volver al resumen de la validación\n${v.carpeta}` : `Cambiar de validación\n${v.carpeta}`;
  $("#btn-validacion").classList.toggle("actual", Boolean(v && !e && !migaPrueba));
  const boton = $("#btn-ejecucion");
  boton.classList.toggle("vacia", !e);
  boton.classList.toggle("actual", Boolean(e && !migaPrueba));
  $("#ejecucion-punto").className = "punto-miga" + (e ? (e.cerrada ? " cerrada" : " abierta") : "");
  $("#ejecucion-nombre").textContent = e ? nombreCorto(e.datos) : v ? `Elegir ejecución (${v.ejecuciones.filter((x) => x.encontrada).length})` : "Sin ejecución";
  $("#ejecucion-detalle").textContent = e ? `${e.cerrada ? "Cerrada" : "Abierta"} · ${e.resumen.ejecutadas}/${e.resumen.total}` : "";
  boton.title = e ? `${e.datos.nombre}\n${[e.datos.entorno_pruebas, e.datos.entorno, e.datos.responsable].filter(Boolean).join(" · ")}\n${e.carpeta}\nPulsa para cambiar de ejecución.`
    : "Elegir, abrir o crear una ejecución";
  $("#sep-prueba").hidden = !migaPrueba;
  $("#miga-prueba").hidden = !migaPrueba;
  $("#miga-prueba").textContent = migaPrueba || "";
}

/** Nombre de una ejecución para la barra: el banco y el responsable, si los tiene (si no, su nombre). */
function nombreCorto(d) {
  const persona = String(d.responsable || "").trim().split(/\s+/)[0];
  const banco = String(d.entorno || d.entorno_pruebas || "").trim();
  return banco && persona ? `${banco} · ${persona}` : String(d.nombre || "");
}

function ponerMigaPrueba(id) {
  migaPrueba = id || null;
  pintarRuta();
}

/** Franja bajo la barra con la ejecución en la que se apuntan los resultados. */
function pintarFranja() {
  const franja = $("#franja-contexto");
  const e = enEjecucion() ? S.ejecucion : null;
  franja.hidden = !e;
  if (!e) { franja.replaceChildren(); return; }
  const d = e.datos;
  franja.classList.toggle("cerrada", e.cerrada);
  const detalle = [d.entorno_pruebas ? `entorno ${d.entorno_pruebas}` : "sin entorno de pruebas", d.entorno ? `banco ${d.entorno}` : null, d.responsable || null].filter(Boolean).join(" · ");
  franja.replaceChildren(
    icon(e.cerrada ? "candado" : "check"),
    h("span", { class: "franja-texto" },
      e.cerrada ? "Ejecución cerrada, solo lectura: " : "Apuntando resultados en ",
      h("strong", { text: `«${d.nombre}»` }), ` · ${detalle}`,
      S.validacion && e.en_validacion === false ? h("span", { class: "franja-nota", text: " · no forma parte de la validación" }) : null),
    h("span", { class: "relleno" }),
    S.validacion ? h("button", { type: "button", class: "enlace franja-volver", onclick: volverAValidacion }, "← Volver a la validación") : null);
}

/** Encima del árbol: qué pruebas se están viendo. */
function pintarTituloLateral() {
  let tit = "", sub = "";
  const capitulo = S.capitulos[S.capitulo];
  if (enEjecucion() && S.ejecucion) {
    const r = S.ejecucion.resumen;
    tit = "Pruebas de esta ejecución";
    sub = `${r.ejecutadas} de ${r.total} ejecutadas` + (r.totales.pendiente ? ` · ${plural(r.totales.pendiente, "pendiente", "pendientes")}` : "");
  } else if (enEjecucion() && S.validacion) {
    tit = "Pruebas de la validación";
    sub = `${plural(S.validacion.total, "prueba", "pruebas")} · ${S.validacion.totales.validada} validadas`;
  } else if (enEjecucion()) {
    tit = "Pruebas";
  } else {
    tit = enRequisitos() ? "Todos los requisitos" : "Todas las pruebas";
    if (capitulo) sub = `Capítulo «${capitulo.nombre}» · ${plural(capitulo.pruebas, enRequisitos() ? "requisito" : "prueba", enRequisitos() ? "requisitos" : "pruebas")}`;
  }
  if (S.filtroEstado && enEjecucion()) sub += ` · filtro: ${$("#filtro-estado").selectedOptions[0]?.textContent || S.filtroEstado}`;
  $("#titulo-lateral-tit").textContent = tit;
  $("#titulo-lateral-sub").textContent = sub;
}

/** Pastilla para volver a la ejecución o a la validación tras «Editar esta prueba». */
function pintarVolver() {
  const boton = $("#btn-volver");
  const visible = Boolean(S.volverA && !enEjecucion());
  boton.hidden = !visible;
  boton.replaceChildren(...(visible ? [h("span", { text: `← Volver a ${S.volverA.texto}` })] : []));
  boton.title = visible ? `Volver al modo Validar, a la prueba ${S.volverA.id}` : "";
}

/** Desde el modo Validar: edita la prueba (en Editar pruebas) y deja la pastilla para volver. */
async function editarPruebaDesdeValidacion(id) {
  const p = (S.ejecucion && S.ejecucion.resumen.pruebas.find((x) => x.id === id))
    || (S.validacion && S.validacion.pruebas.find((x) => x.id === id));
  if (!p || !p.archivo) { aviso(`La prueba ${id} no está en los YAML de pruebas`, "error"); return; }
  if (S.soloLectura) {
    aviso("La ejecución está cerrada y muestra sus pruebas congeladas: vuelve a la validación (o abre la carpeta de pruebas) para editarla", "error");
    return;
  }
  const volverA = { id, texto: S.ejecucion ? nombreCorto(S.ejecucion.datos) : "la validación" };
  await cambiarModo("edicion");
  if (S.modo !== "edicion") return;           // cambios sin guardar: se quedó donde estaba
  S.volverA = volverA;
  pintarVolver();
  await irAPruebaEnEdicion(p.archivo, p.indice);
}

/** Abre una prueba en el modo de edición (por su capítulo e índice). */
async function irAPruebaEnEdicion(archivo, indice) {
  const ci = S.capitulos.findIndex((c) => c.archivo === archivo);
  if (ci < 0) return;
  if (ci !== S.capitulo || S.consulta) {
    S.capitulo = ci;
    $("#sel-capitulo").value = String(ci);
    S.consulta = ""; $("#buscar").value = "";
  }
  await cargarNavegacion();
  const nodo = S.nodos.find((n) => n.indice === indice);
  for (let padre = nodo ? nodo.padre : null; padre !== null && padre !== undefined;) {
    const sec = S.nodos.find((n) => n.indice === padre);
    if (!sec) break;
    S.colapsadas.delete(claveColapso(sec));
    padre = sec.padre;
  }
  S.seleccion = null;
  await seleccionar("prueba", indice);
}

/** Vuelve al modo Validar, a la prueba (en la ejecución abierta o en la validación). */
async function verPruebaEnValidar(id) {
  await cambiarModo("ejecucion");
  if (!enEjecucion()) return;
  if (S.ejecucion && S.ejecucion.resumen.pruebas.some((x) => x.id === id)) { await irAPruebaEjecucion(id); return; }
  const p = !S.ejecucion && S.validacion && S.validacion.pruebas.find((x) => x.id === id);
  if (p) await irAPruebaValidacion(p);
}

async function volverDeEdicion() {
  const destino = S.volverA;
  if (destino) await verPruebaEnValidar(destino.id);
}

async function cambiarModo(modo) {
  if (modo === S.modo) return;
  if (!(await guardia())) return;
  setDirty(false);
  const cambiaColeccion = (modo === "requisitos") !== enRequisitos();
  S.capituloPorModo[coleccionDe(S.modo)] = S.capitulo;
  S.modo = modo;
  guardarLocal("modo", modo);
  S.seleccion = null;
  S.volverA = null;
  migaPrueba = null;
  S.filtroEstado = "";
  S.filtroCobertura = "";
  R = null;
  if (cambiaColeccion) {
    try {
      S.consulta = ""; $("#buscar").value = "";
      S.capitulo = S.capituloPorModo[coleccionDe(modo)] || 0;
      aplicarResumen(await api.coleccion(coleccionDe(modo)));
      await cambioDeCapitulo();
      if (S.capitulo >= S.capitulos.length) S.capitulo = 0;
      $("#sel-capitulo").value = String(S.capitulo);
      S.problemas = []; S.resumen = null; renderResumenProblemas(); renderProblemas();
    } catch (e) { fallo(e); }
  }
  if (modo === "ejecucion") await actualizarResultados();
  if (modo === "ejecucion" && !S.validacion) await recuperarValidacion();
  if (modo === "ejecucion" && !S.ejecucion && !S.validacion) await recuperarEjecucion();
  pintarModo();
  await cargarNavegacion();
  mostrarVacio();
  if (cambiaColeccion) validarEnSegundoPlano();
}

/** Vuelve a calcular la ejecución y la validación abiertas: las pruebas pueden haber cambiado al editarlas. */
async function actualizarResultados() {
  try {
    if (S.ejecucion) S.ejecucion = (await api.ejecucion_estado()) || S.ejecucion;
    if (S.validacion) S.validacion = (await api.validacion_estado()) || S.validacion;
  } catch (e) { fallo(e); }
}

/** Texto de cada capítulo en el selector: en ejecución, cuántas pruebas de la ejecución quedan. */
function textoCapitulo(c) {
  if (enEjecucion() && !S.ejecucion && S.validacion) {
    const suyas = S.validacion.pruebas.filter((p) => p.archivo === c.archivo);
    if (!suyas.length) return `${c.nombre} (fuera de la validación)`;
    const validadas = suyas.filter((p) => p.estado === "validada").length;
    return `${c.nombre} (${validadas} de ${suyas.length} validadas)`;
  }
  if (!enEjecucion() || !S.ejecucion) return `${c.nombre} (${c.pruebas})`;
  const suyas = S.ejecucion.resumen.pruebas.filter((p) => p.archivo === c.archivo);
  if (!suyas.length) return `${c.nombre} (fuera de la ejecución)`;
  const pendientes = suyas.filter((p) => p.estado === "pendiente").length;
  return `${c.nombre} (${pendientes ? `${pendientes} de ${suyas.length} pendientes` : `${suyas.length} ejecutadas`})`;
}

function etiquetarCapitulos() {
  const opciones = $("#sel-capitulo").options;
  for (const c of S.capitulos) if (opciones[c.indice]) opciones[c.indice].textContent = textoCapitulo(c);
}

/**
 * Pruebas que han cambiado después de ejecutarse: ID -> explicación.
 * Con una ejecución abierta, las de esa ejecución; si no, las de la validación.
 */
let cacheCambiadas = { fuente: null, mapa: new Map() };
function pruebasCambiadas() {
  const fuente = S.ejecucion ? S.ejecucion.resumen : S.validacion;
  if (cacheCambiadas.fuente === fuente) return cacheCambiadas.mapa;
  const mapa = new Map();
  if (S.ejecucion) {
    for (const p of S.ejecucion.resumen.pruebas) {
      if (p.cambiada) mapa.set(p.id, "La prueba ha cambiado después de ejecutarse en esta ejecución: revisa si hay que repetirla.");
    }
  } else if (S.validacion) {
    for (const p of S.validacion.pruebas) {
      if ((p.cambiada_en || []).length) mapa.set(p.id, `La prueba ha cambiado después de ejecutarse en ${p.cambiada_en.join(", ")}: revisa si hay que repetirla.`);
    }
  }
  cacheCambiadas = { fuente, mapa };
  return mapa;
}

/** Triángulo de aviso para una prueba cambiada después de ejecutarse (o null). */
function marcaCambiada(id) {
  const motivo = pruebasCambiadas().get(id);
  return motivo ? h("span", { class: "marca-cambio", title: motivo, role: "img", "aria-label": motivo }, icon("alert")) : null;
}

/** Pruebas de la validación con resultados distintos sin triar: ID -> entornos. */
function pruebasPorTriar() {
  return new Map(S.validacion ? S.validacion.pruebas.filter((p) => (p.por_triar || []).length).map((p) => [p.id, p.por_triar]) : []);
}

/** Balanza junto a una prueba con resultados distintos sin triar (o null). */
function marcaTriaje(id) {
  const entornos = pruebasPorTriar().get(id);
  if (!entornos) return null;
  const motivo = `Resultados distintos en ${entornos.join(", ")} (NO OK y OK): cuenta como NO OK hasta que se trie.`;
  return h("span", { class: "marca-triaje", title: motivo, role: "img", "aria-label": motivo }, icon("balanza"));
}

/** Aviso de prueba cambiada después de ejecutarse, con el botón para quitarlo (si se puede). */
function avisoCambiada(texto, alRevisar) {
  return h("div", { class: "aviso-panel aviso-cambiada" },
    h("span", { text: texto }),
    alRevisar ? h("button", {
      type: "button", class: "btn peq", text: "No hay que repetirla",
      title: "El cambio no afecta a lo que se probó: el resultado vale para la prueba actual y deja de avisar (hasta que vuelva a cambiar)",
      onclick: alRevisar,
    }) : null);
}

async function darPorRevisadaEnEjecucion() {
  if (!R || !(await guardia())) return;
  const id = R.id, indice = S.seleccion && S.seleccion.indice;
  try {
    S.ejecucion = await api.ejecucion_dar_por_revisada(id);
    setDirty(false);
    pintarModo();
    await cargarNavegacion();
    aviso(`${id}: el resultado vale para la prueba actual`, "ok");
    if (indice !== null && indice !== undefined) { S.seleccion = null; await seleccionar("prueba", indice); }
  } catch (e) { fallo(e); }
}

/** En ejecución el árbol solo muestra las pruebas de la ejecución (y las secciones que las contienen). */
function filtrarNodosEjecucion(nodos) {
  if (!S.ejecucion && !S.validacion) return [];
  const estados = mapaEstados();
  const padres = new Map(nodos.map((n) => [n.indice, n.padre]));
  const quedan = new Set();
  for (const n of nodos) {
    if (n.tipo !== "prueba" || !estados.has(n.id)) continue;
    if (S.filtroEstado === "cambiada" ? !pruebasCambiadas().has(n.id)
      : S.filtroEstado === "por_triar" ? !pruebasPorTriar().has(n.id)
        : S.filtroEstado && estados.get(n.id) !== S.filtroEstado) continue;
    quedan.add(n.indice);
    for (let p = n.padre; p !== null && p !== undefined; p = padres.get(p)) quedan.add(p);
  }
  return nodos.filter((n) => quedan.has(n.indice));
}

function marcaEstado(id) {
  const estado = mapaEstados().get(id) || "pendiente";
  const texto = !S.ejecucion && S.validacion ? VAL_TXT[(S.validacion.pruebas.find((p) => p.id === id) || {}).estado] || ESTADO_TXT[estado] : ESTADO_TXT[estado];
  return h("span", { class: "punto-estado e-" + estado, title: texto, role: "img", "aria-label": texto });
}

/* ---- ejecuciones: abrir, crear, recientes ---- */
function recientes() {
  try { return JSON.parse(leerLocal("ejecuciones-recientes") || leerLocal("campanas-recientes") || "[]"); } catch (_e) { return []; }
}

function recordarReciente() {
  const lista = recientes().filter((r) => r.carpeta !== S.ejecucion.carpeta);
  lista.unshift({ carpeta: S.ejecucion.carpeta, nombre: S.ejecucion.datos.nombre });
  guardarLocal("ejecuciones-recientes", JSON.stringify(lista.slice(0, 8)));
}

/** Al entrar en ejecución: la ejecución que tenga abierta Python o, si no, la última usada. */
async function recuperarEjecucion() {
  try {
    const actual = await api.ejecucion_estado();
    if (actual) { S.ejecucion = actual; return; }
    const ultima = recientes()[0];
    if (ultima) await usarEjecucion(await api.ejecucion_abrir(ultima.carpeta), { silencio: true });
  } catch (_e) { /* la última ejecución ya no existe: se elegirá otra */ }
}

async function usarEjecucion(r, { silencio = false } = {}) {
  if (!r || r.cancelado) return;
  if (r.faltan_pruebas) {
    if (silencio) return;
    const respuesta = await dialogo({
      titulo: "No se encuentran las pruebas de la ejecución",
      cuerpo: h("div", {},
        h("p", {}, "La ejecución ", h("strong", { text: r.nombre }), " no encuentra su carpeta de pruebas. Puede que se haya movido o que la ejecución sea de otra persona, con las pruebas en otra ruta."),
        h("p", { class: "muted", text: "Se buscó en: " + r.rutas.join("  ·  ") }),
        h("p", { text: "Indica dónde está la carpeta de pruebas en este PC (la que contiene indice.yaml). Este PC lo recordará; la ejecución no cambia para los demás." })),
      botones: [{ texto: "Cancelar", valor: "no", tipo: "ghost" }, { texto: "Buscar la carpeta…", valor: "si", tipo: "primary" }],
    });
    if (respuesta !== "si") return;
    try { await usarEjecucion(await api.ejecucion_reubicar(r.carpeta), { silencio }); } catch (e) { fallo(e); }
    return;
  }
  if (r.carpeta_pruebas) {      // la ejecución usa otra carpeta de pruebas: se abre esa
    cacheImagenes.clear();
    S.capitulo = 0; S.consulta = ""; $("#buscar").value = ""; S.colapsadas.clear();
    aplicarResumen(r.carpeta_pruebas);
    await cargarCobertura();
  }
  S.ejecucion = r;
  S.seleccion = null;
  S.filtroEstado = "";
  R = null;
  recordarReciente();
  pintarModo();
  if (!silencio) {
    await cargarNavegacion();
    mostrarVacio();
    validarEnSegundoPlano();
    aviso(`Ejecución «${r.datos.nombre}» abierta`, "ok");
  }
}

async function abrirEjecucion(carpeta = null) {
  if (!(await guardia())) return;
  setDirty(false);
  try { await usarEjecucion(await api.ejecucion_abrir(carpeta)); } catch (e) { fallo(e); }
}

async function menuEjecucion() {
  if (S.validacion) { await menuEjecucionesValidacion(); return; }
  const lista = recientes().filter((r) => !S.ejecucion || r.carpeta !== S.ejecucion.carpeta);
  const cuerpo = h("div", { class: "menu-ejecucion" },
    S.ejecucion ? h("p", {}, "Abierta: ", h("strong", { text: S.ejecucion.datos.nombre }), h("br"), h("span", { class: "muted", text: S.ejecucion.carpeta })) : null,
    lista.length ? h("p", { class: "muted", text: "Recientes" }) : null,
    lista.map((r) => h("button", {
      type: "button", class: "btn ghost reciente", title: r.carpeta,
      onclick: (e) => e.target.closest("dialog").close("reciente:" + r.carpeta),
    }, h("span", { text: r.nombre }), h("span", { class: "muted", text: r.carpeta }))));
  const r = await dialogo({
    titulo: "Ejecuciones", cuerpo,
    botones: [
      { texto: "Cerrar", valor: "", tipo: "ghost" },
      { texto: "Abrir ejecución…", valor: "abrir", tipo: "" },
      { texto: "Nueva ejecución…", valor: "nueva", tipo: "primary" },
    ],
  });
  if (r === "nueva") await nuevaEjecucion();
  else if (r === "abrir") await abrirEjecucion();
  else if (r && r.startsWith("reciente:")) await abrirEjecucion(r.slice(9));
}

/** Las ejecuciones de la validación, agrupadas por entorno, para cambiar de una a otra. */
async function menuEjecucionesValidacion() {
  const v = S.validacion;
  const actual = S.ejecucion && S.ejecucion.carpeta;
  const grupos = new Map();
  for (const e of v.ejecuciones) {
    const clave = e.encontrada ? e.entorno_pruebas || "(sin entorno)" : "No se encuentran";
    if (!grupos.has(clave)) grupos.set(clave, []);
    grupos.get(clave).push(e);
  }
  const fila = (e) => {
    const esta = e.encontrada && e.carpeta === actual;
    const pct = e.total ? Math.round(100 * e.ejecutadas / e.total) : 0;
    return h("button", {
      type: "button", class: "fila-ejecucion" + (esta ? " actual" : ""), disabled: !e.encontrada, title: e.carpeta || e.ruta,
      "aria-current": esta ? "true" : null,
      onclick: (ev) => ev.target.closest("dialog").close("ejecucion:" + e.indice),
    },
    h("span", { class: "punto-miga " + (e.cerrada ? "cerrada" : "abierta") }),
    h("span", { class: "fe-nombre" }, h("strong", { text: e.encontrada ? e.nombre : e.ruta }),
      h("span", { class: "muted", text: [e.banco, e.responsable, esta ? "estás aquí" : null].filter(Boolean).join(" · ") })),
    e.encontrada ? h("span", { class: "chip-estado " + (e.cerrada ? "cerrada" : "abierta"), text: e.cerrada ? "Cerrada" : "Abierta" }) : h("span"),
    e.encontrada ? h("span", { class: "fe-avance" }, h("span", { class: "fe-barra" }, h("span", { style: { width: pct + "%" } })), `${e.ejecutadas}/${e.total}`) : h("span"));
  };
  const cuerpo = h("div", { class: "menu-ejecucion menu-ejecuciones-val" },
    v.ejecuciones.length
      ? [...grupos].map(([entorno, lista]) => h("div", { class: "grupo-ejecuciones" }, h("h4", { text: entorno }), lista.map(fila)))
      : h("p", { class: "muted", text: "La validación todavía no tiene ejecuciones: crea una o añade las que ha hecho cada persona." }));
  const r = await dialogo({
    titulo: `Ejecuciones de «${v.datos.nombre}»`, cuerpo, ancho: true,
    botones: [
      { texto: "Cerrar", valor: "", tipo: "ghost" },
      ...(S.ejecucion ? [{ texto: "Resumen de la validación", valor: "resumen", tipo: "" }] : []),
      { texto: "Abrir una ejecución suelta…", valor: "abrir", tipo: "" },
      { texto: "Nueva ejecución…", valor: "nueva", tipo: "primary" },
    ],
  });
  if (r === "nueva") await nuevaEjecucion({ enValidacion: true });
  else if (r === "abrir") await abrirEjecucion();
  else if (r === "resumen") await volverAValidacion();
  else if (r && r.startsWith("ejecucion:")) {
    const e = v.ejecuciones[Number(r.slice(10))];
    if (e && e.carpeta !== actual) await abrirEjecucionDeValidacion(e.carpeta);
  }
}

/** La validación de la ruta: vuelve a su resumen o, si ya se está en él, permite cambiar de validación. */
async function pulsarMigaValidacion() {
  if (!S.validacion || (!S.ejecucion && !migaPrueba)) { await menuValidacion(); return; }
  if (S.ejecucion) { await volverAValidacion(); return; }
  if (!(await guardia())) return;
  setDirty(false);
  S.seleccion = null;
  renderArbol();
  mostrarVacio();
}

/**
 * Fichas para elegir qué pruebas entran (tags, automatizable, entorno…) y la
 * vista previa de las que cumplen el criterio. Cambia `filtro` en el sitio.
 */
function selectorFiltro(opciones, filtro, textoLista) {
  const nombres = Object.fromEntries(S.capitulos.map((c) => [c.archivo, c.nombre]));
  const claves = [
    ["etiquetas", "Tags (basta con uno)"], ["automatizable", "Automatizable"], ["entorno", "Entorno de pruebas (basta con uno)"],
    ["maniobra", "Maniobra (basta con una)"], ["capitulos", "Capítulos"], ["robot", "Automatización"],
  ].filter(([clave]) => (opciones[clave] || []).length);
  const vista = h("div", { class: "vista-seleccion" });
  const actualizar = debounce(async () => {
    try {
      const lista = await api.ejecucion_previsualizar(filtro);
      vista.replaceChildren(
        h("p", {}, h("strong", { text: plural(lista.length, "prueba", "pruebas") }), lista.length ? textoLista : " cumplen el criterio."),
        h("ul", {}, lista.slice(0, 300).map((p) => h("li", {}, h("span", { class: "tid", text: p.id }), " ", p.titulo))));
    } catch (e) { vista.replaceChildren(h("p", { class: "error-campo", text: e.message })); }
  }, 150);
  const fichasGrupo = (clave, valores) => h("div", { class: "fichas-filtro" }, valores.map((v) => h("button", {
    type: "button", class: "ficha-filtro", "aria-pressed": String((filtro[clave] || []).includes(v)), dataset: { grupo: clave, valor: v },
    text: clave === "capitulos" ? nombres[v] || v : clave === "automatizable" ? AUTOMATIZABLE_TXT[v] || v
      : clave === "robot" ? { con: "Con test de Robot", sin: "Sin test de Robot" }[v] : v,
    onclick: (e) => {
      const lista = filtro[clave] || (filtro[clave] = []);
      const i = lista.indexOf(v);
      if (i >= 0) lista.splice(i, 1); else lista.push(v);
      if (!lista.length) delete filtro[clave];
      e.currentTarget.setAttribute("aria-pressed", String(i < 0));
      actualizar();
    },
  })));
  actualizar();
  const grupos = claves.map(([clave, titulo]) => h("div", { class: "grupo-filtro" }, h("span", { class: "etiqueta", text: titulo }), fichasGrupo(clave, opciones[clave])));
  return { grupos, vista };
}

/* ---- nueva ejecución ---- */
/** Nueva ejecución. Desde una validación (`enValidacion`) parte de su criterio y se guarda dentro de ella. */
async function nuevaEjecucion({ enValidacion = false } = {}) {
  if (!S.capitulos.length) { aviso("Abre primero la carpeta de pruebas", "error"); return; }
  if (!(await guardia())) return;
  setDirty(false);
  let opciones;
  try { opciones = await api.ejecucion_opciones(); } catch (e) { fallo(e); return; }
  const filtro = enValidacion && S.validacion ? JSON.parse(JSON.stringify(S.validacion.datos.seleccion || {})) : {};
  const campo = (id, etiqueta, ayuda = "") => h("div", { class: "campo" },
    h("label", { for: id, text: etiqueta }), h("input", { id, type: "text", autocomplete: "off", placeholder: ayuda }));
  const { grupos, vista } = selectorFiltro(opciones, filtro, " entrarán en la ejecución:");
  // El entorno de pruebas de la ejecución marca (o desmarca) el mismo entorno en el filtro de pruebas.
  const selEntorno = selectorEntorno("c-entorno-pruebas", "", (anterior, nuevo) => {
    for (const [v, marcar] of [[anterior, false], [nuevo, true]]) {
      const ficha = v && cuerpo.querySelector(`.ficha-filtro[data-grupo="entorno"][data-valor="${v}"]`);
      if (ficha && (ficha.getAttribute("aria-pressed") === "true") !== marcar) ficha.click();
    }
  });
  const cuerpo = h("div", { class: "nueva-ejecucion" },
    h("div", { class: "rejilla" },
      Object.assign(campo("c-nombre", "Nombre *", "Regresión v2.3 en Torre"), { className: "campo completo" }),
      campo("c-objeto", "Qué se prueba", "Firmware 2.3.0-rc2"),
      selEntorno,
      campo("c-entorno", "Banco / instalación", "Banco HIL nº 2"),
      campo("c-responsable", "Responsable")),
    h("h3", { text: "Qué pruebas entran" }),
    h("p", { class: "muted", text: (enValidacion ? "Parte del criterio de la validación; al elegir el entorno se marcan las pruebas que lo piden. " : "")
      + "Sin marcar nada entran todas. Dentro de cada grupo basta con cumplir una opción; entre grupos, todas." }),
    grupos,
    vista,
    !opciones.git ? null : opciones.git.cambios
      ? h("p", { class: "aviso-panel", text: `Tu copia de las pruebas tiene cambios sin commit (${opciones.git.texto}). La ejecución lo apuntará, pero en otras copias esas pruebas pueden ser distintas: haz commit (o descártalos) antes de ejecutar.` })
      : h("p", { class: "muted", text: `Versión de las pruebas: ${opciones.git.texto}. La ejecución la apuntará.` }));
  const responsable = cuerpo.querySelector("#c-responsable");
  responsable.value = leerLocal("ejecutor") || "";
  const r = await dialogo({
    titulo: enValidacion ? `Nueva ejecución en «${S.validacion.datos.nombre}»` : "Nueva ejecución", cuerpo, ancho: true,
    botones: [{ texto: "Cancelar", valor: "no", tipo: "ghost" },
      { texto: enValidacion ? "Crear ejecución" : "Elegir carpeta y crear…", valor: "si", tipo: "primary" }],
  });
  if (r !== "si") return;
  const nombre = cuerpo.querySelector("#c-nombre").value.trim();
  if (!nombre) { aviso("La ejecución necesita un nombre", "error"); return; }
  const entornoPruebas = cuerpo.querySelector("#c-entorno-pruebas").value;
  if (!entornoPruebas) { aviso("Indica en qué entorno de pruebas se ejecuta", "error"); return; }
  const datos = {
    objeto: cuerpo.querySelector("#c-objeto").value,
    entorno_pruebas: entornoPruebas,
    entorno: cuerpo.querySelector("#c-entorno").value,
    responsable: responsable.value,
  };
  try {
    if (enValidacion) {
      await usarEjecucion(await api.validacion_nueva_ejecucion(nombre, filtro, datos));
      await refrescarValidacion();
      return;
    }
    aviso("Elige la carpeta donde guardar la ejecución (se creará una subcarpeta)…");
    await usarEjecucion(await api.ejecucion_crear(nombre, filtro, datos));
  } catch (e) { fallo(e); }
}

/** Selector del entorno de pruebas de una ejecución (Automático, Maqueta, Torre). */
function selectorEntorno(id, valor, alCambiar = null) {
  const opciones = (S.esquema && S.esquema.opciones.entorno) || [];
  let anterior = valor;
  const select = h("select", {
    id, onchange: (e) => { if (alCambiar) alCambiar(anterior, e.target.value); anterior = e.target.value; },
  }, h("option", { value: "", text: "(elige uno)", selected: !valor }),
  opciones.map((o) => h("option", { value: o, text: o, selected: o === valor })));
  return h("div", { class: "campo" }, h("label", { for: id, text: "Entorno de pruebas *" }), select,
    h("span", { class: "ayuda", text: "Dónde se pasan las pruebas. Para validar una versión, cada prueba tiene que pasarse en sus entornos." }));
}

/** Cambiar los datos de la ejecución abierta. */
async function editarDatosEjecucion() {
  if (!S.ejecucion || S.ejecucion.cerrada) return;
  const d = S.ejecucion.datos;
  const campo = (id, etiqueta, valor) => h("div", { class: "campo" },
    h("label", { for: id, text: etiqueta }), h("input", { id, type: "text", autocomplete: "off", value: valor || "" }));
  const cuerpo = h("div", { class: "rejilla" },
    campo("d-objeto", "Qué se prueba", d.objeto),
    selectorEntorno("d-entorno-pruebas", d.entorno_pruebas || ""),
    campo("d-entorno", "Banco / instalación", d.entorno),
    campo("d-responsable", "Responsable", d.responsable));
  const r = await dialogo({
    titulo: "Datos de la ejecución", cuerpo,
    botones: [{ texto: "Cancelar", valor: "no", tipo: "ghost" }, { texto: "Guardar", valor: "si", tipo: "primary" }],
  });
  if (r !== "si") return;
  try {
    S.ejecucion = await api.ejecucion_editar_datos({
      objeto: cuerpo.querySelector("#d-objeto").value,
      entorno_pruebas: cuerpo.querySelector("#d-entorno-pruebas").value,
      entorno: cuerpo.querySelector("#d-entorno").value,
      responsable: cuerpo.querySelector("#d-responsable").value,
    });
    pintarModo();
    mostrarVacio();
    aviso("Datos de la ejecución guardados", "ok");
  } catch (e) { fallo(e); }
}

/* ---- navegación entre pruebas de la ejecución ---- */
async function irAPruebaEjecucion(id) {
  const p = S.ejecucion && S.ejecucion.resumen.pruebas.find((x) => x.id === id);
  if (!p || !p.archivo) { aviso(`La prueba ${id} ya no está en los YAML de pruebas`, "error"); return; }
  const ci = S.capitulos.findIndex((c) => c.archivo === p.archivo);
  if (ci < 0) return;
  if (S.filtroEstado && p.estado !== S.filtroEstado) { S.filtroEstado = ""; $("#filtro-estado").value = ""; }
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
  S.seleccion = null;      // fuerza a abrirla aunque fuera la seleccionada
  await seleccionar("prueba", p.indice);
}

/** Desde el resumen: abre el capítulo y su primera prueba pendiente (o la primera, si no queda ninguna). */
async function irACapituloEjecucion(ci) {
  const archivo = S.capitulos[ci] && S.capitulos[ci].archivo;
  const suyas = S.ejecucion ? S.ejecucion.resumen.pruebas.filter((p) => p.archivo === archivo) : [];
  const destino = suyas.find((p) => p.estado === "pendiente") || suyas[0];
  if (destino) { await irAPruebaEjecucion(destino.id); return; }
  if (ci !== S.capitulo) { $("#sel-capitulo").value = String(ci); await cambiarCapitulo(String(ci)); }
}

async function siguientePendiente(desdeId = null) {
  const lista = S.ejecucion ? S.ejecucion.resumen.pruebas : [];
  const inicio = desdeId ? lista.findIndex((p) => p.id === desdeId) : -1;
  const orden = [...lista.slice(inicio + 1), ...lista.slice(0, inicio + 1)];
  const siguiente = orden.find((p) => p.estado === "pendiente" && p.archivo);
  if (!siguiente) {
    aviso("No quedan pruebas pendientes", "ok");
    S.seleccion = null;
    await cargarNavegacion();
    mostrarVacio();
    return;
  }
  await irAPruebaEjecucion(siguiente.id);
}

/* ---- panel de la ejecución (sin prueba seleccionada) ---- */
function mostrarPanelEjecucion() {
  R = null;
  ponerMigaPrueba(null);
  if (!S.ejecucion && S.validacion) { mostrarPanelValidacion(); return; }
  if (!S.ejecucion) {
    const lista = recientes();
    mostrar(h("div", { class: "centro" },
      h("h2", { text: "Validación de una versión" }),
      h("p", { text: "Una validación agrupa las ejecuciones de una versión (una por entorno: Automático, Maqueta, Torre) y da el resultado de cada prueba en cada entorno. Cada ejecución guarda sus resultados en su carpeta; los YAML de pruebas no se tocan." }),
      h("div", { class: "fila-botones" },
        h("button", { class: "btn primary", type: "button", onclick: nuevaValidacion, text: "Nueva validación" }),
        h("button", { class: "btn", type: "button", onclick: () => abrirValidacion(), text: "Abrir validación…" })),
      h("p", { class: "muted", text: "También puedes trabajar con una ejecución suelta, sin validación:" }),
      h("div", { class: "fila-botones" },
        h("button", { class: "btn", type: "button", onclick: () => nuevaEjecucion(), text: "Nueva ejecución" }),
        h("button", { class: "btn", type: "button", onclick: () => abrirEjecucion(), text: "Abrir ejecución…" })),
      lista.length ? h("div", { class: "recientes" }, h("p", { class: "muted", text: "Recientes" }),
        lista.map((r) => h("button", { type: "button", class: "btn ghost reciente", title: r.carpeta, onclick: () => abrirEjecucion(r.carpeta) },
          h("span", { text: r.nombre }), h("span", { class: "muted", text: r.carpeta })))) : null));
    return;
  }
  const c = S.ejecucion;
  const r = c.resumen;
  const d = c.datos;
  const barra = h("div", { class: "barra-progreso", role: "img", "aria-label": `Avance ${r.progreso} %` },
    ESTADOS.map((e) => r.totales[e] ? h("span", { class: "e-" + e, style: { flexGrow: String(r.totales[e]) }, title: `${ESTADO_TXT[e]}: ${r.totales[e]}` }) : null));
  const tarjeta = (titulo, valor, extra = "", clase = "") => h("div", { class: "tarjeta " + clase },
    h("span", { class: "t-tit", text: titulo }), h("span", { class: "t-val", text: String(valor) }), extra ? h("span", { class: "t-extra", text: extra }) : null);
  const tabla = (titulo, datos) => h("table", { class: "tabla-estados tabla-capitulos" },
    h("thead", {}, h("tr", {}, h("th", { text: titulo }), ESTADOS.map((e) => h("th", { class: "num", text: ESTADO_TXT[e] })))),
    h("tbody", {}, Object.entries(datos).map(([nombre, t]) => {
      const ci = S.capitulos.findIndex((cap) => cap.nombre === nombre);
      return h("tr", ci < 0 ? {} : { class: "pulsable", title: "Ir a este capítulo", onclick: () => irACapituloEjecucion(ci) },
        h("td", { text: nombre }),
        ESTADOS.map((e) => h("td", { class: "num" + (t[e] ? " e-txt-" + e : ""), text: t[e] ? String(t[e]) : "·" })));
    })));
  const criterio = Object.entries(d.seleccion || {}).map(([k, v]) => (k === "solo_ids" ? `${[].concat(v).length} pruebas elegidas una a una`
    : k === "importado_de" ? `resultados importados de ${v}` : `${k}: ${[].concat(v).join(", ")}`)).join(" · ") || "todas las pruebas";
  const problemas = r.problemas.length
    ? h("ul", { class: "lista-problemas en-panel" }, r.problemas.map((p) => h("li", { title: p.id ? "Ir a la prueba" : "", onclick: () => { if (p.id) irAPruebaEjecucion(p.id); } },
      h("span", { class: "sev " + p.tipo }), h("span", { class: "donde", text: p.id || "ejecución" }), h("span", { text: p.mensaje }))))
    : h("p", { class: "muted", text: "Sin avisos." });
  mostrar(h("div", { class: "formulario panel-ejecucion" },
    S.validacion ? h("button", { class: "btn ghost peq volver", type: "button", onclick: volverAValidacion },
      icon("up"), `Validación «${S.validacion.datos.nombre}»`) : null,
    S.validacion && c.en_validacion === false ? h("div", { class: "aviso-panel aviso-fuera" },
      h("span", { text: `Esta ejecución no forma parte de la validación «${S.validacion.datos.nombre}»: sus resultados no cuentan en ella.` }),
      h("button", { class: "btn peq", type: "button", onclick: anadirAbiertaAValidacion, text: "Añadirla a la validación" })) : null,
    h("div", { class: "acciones" },
      h("div", { class: "titulo" }, h("span", { class: "nombre", text: d.nombre }),
        h("span", { class: "ruta", text: [d.objeto, d.entorno_pruebas, d.entorno, d.responsable].filter(Boolean).join(" · ") || c.carpeta })),
      h("span", { class: "chip-estado " + (c.cerrada ? "cerrada" : "abierta"), text: c.cerrada ? "Cerrada" : "Abierta" }),
      c.cerrada || !S.cobertura ? null : h("button", { class: "btn", type: "button", onclick: ejecutarRobot, title: "Lanzar Robot Framework con las pruebas de la ejecución que tienen test automático" }, icon("play"), "Ejecutar Robot…"),
      c.cerrada ? null : h("button", { class: "btn", type: "button", onclick: () => importarRobot(), text: "Importar Robot…", title: "Apuntar los resultados de un output.xml de Robot Framework" }),
      h("button", { class: "btn", type: "button", onclick: generarInforme, text: "Generar informe…", title: c.cerrada ? "Informe con las pruebas congeladas al cerrar" : "Borrador: la ejecución sigue abierta" }),
      h("button", { class: "btn", type: "button", onclick: compararEjecucion, text: "Comparar con…", title: "Comparar con otra ejecución (la anterior): nuevos fallos y arreglos" }),
      c.cerrada ? null : h("button", { class: "btn", type: "button", onclick: cerrarEjecucion, text: "Cerrar ejecución…" }),
      c.cerrada || !r.totales.pendiente ? null : h("button", { class: "btn primary", type: "button", onclick: () => siguientePendiente(), text: "Siguiente pendiente" })),
    h("section", { class: "bloque" },
      h("div", { class: "bloque-cab" }, h("h3", { text: "Avance" }),
        h("p", { class: "ayuda", text: `${r.ejecutadas} de ${r.total} ejecutadas (${r.progreso} %) · inicio ${String(d.inicio || "").replace("T", " ")}${d.fin ? " · fin " + String(d.fin).replace("T", " ") : ""}` })),
      barra,
      h("div", { class: "tarjetas" },
        tarjeta("OK", r.totales.ok, `${r.porcentaje_ok} % de las que aplican`, "e-ok"),
        tarjeta("NO OK", r.totales.no_ok, "", "e-no_ok"),
        tarjeta("Bloqueadas", r.totales.bloqueada, "", "e-bloqueada"),
        tarjeta("No aplica", r.totales.no_aplica, "", "e-no_aplica"),
        tarjeta("Pendientes", r.totales.pendiente, "", "e-pendiente"))),
    h("section", { class: "bloque" }, h("div", { class: "bloque-cab" }, h("h3", { text: "Por capítulo" })), tabla("Capítulo", r.por_capitulo)),
    h("section", { class: "bloque" }, h("div", { class: "bloque-cab" }, h("h3", { text: "Avisos" })), problemas),
    h("section", { class: "bloque" },
      h("div", { class: "bloque-cab" }, h("h3", { text: "Ejecución" }),
        c.cerrada ? null : h("button", { class: "btn ghost peq", type: "button", onclick: editarDatosEjecucion, text: "Cambiar datos…", title: "Qué se prueba, entorno de pruebas, banco y responsable" }),
        c.cerrada ? null : h("button", { class: "btn ghost peq", type: "button", onclick: resincronizar, text: "Resincronizar", title: "Añadir las pruebas nuevas que cumplen el criterio" })),
      d.entorno_pruebas ? null : h("p", { class: "aviso-panel", text: "Esta ejecución no indica su entorno de pruebas (Automático, Maqueta o Torre): en la validación de la versión sus resultados no contarán para ningún entorno. Indícalo con «Cambiar datos…»." }),
      h("dl", { class: "datos-ejecucion" },
        h("dt", { text: "Entorno de pruebas" }), h("dd", { text: d.entorno_pruebas || "(sin indicar)" }),
        d.entorno ? [h("dt", { text: "Banco / instalación" }), h("dd", { text: d.entorno })] : null,
        h("dt", { text: "Criterio" }), h("dd", { text: criterio }),
        h("dt", { text: "Carpeta" }), h("dd", {}, h("button", { class: "enlace", type: "button", text: c.carpeta, onclick: () => api.mostrar_en_carpeta(c.archivo).catch(fallo) })),
        h("dt", { text: "Pruebas" }), h("dd", { text: String(d.pruebas_yaml || d.pruebas_yaml_absoluta || "") }),
        c.version_pruebas ? [h("dt", { text: "Versión de las pruebas" }), h("dd", { text: c.version_pruebas })] : null))));
}

/* ---- resultados de Robot Framework ---- */
async function importarRobot(ruta = null) {
  if (!S.ejecucion || S.ejecucion.cerrada) return;
  if (!(await guardia())) return;
  setDirty(false);
  try {
    const elegido = typeof ruta === "string" ? { ruta } : await api.ejecucion_robot_elegir();
    if (elegido.cancelado) return;
    const plan = await api.ejecucion_robot_previsualizar(elegido.ruta);
    const t = plan.totales;
    const lista = (titulo, ids, clase = "") => ids.length ? h("div", { class: "aviso-robot " + clase },
      h("strong", { text: `${titulo} (${ids.length})` }), h("span", { text: ids.join(", ") })) : null;
    const cuerpo = h("div", { class: "importar-robot" },
      h("p", { class: "muted", text: `${elegido.ruta} · ${plural(plan.tests_robot, "test", "tests")} · ${plan.generador}` }),
      plan.resultados.length
        ? h("table", { class: "tabla-estados" },
          h("thead", {}, h("tr", {}, h("th", { text: "Prueba" }), h("th", { text: "Resultado" }), h("th", { text: "Antes" }), h("th", { text: "Tests de Robot" }))),
          h("tbody", {}, plan.resultados.map((r) => h("tr", {},
            h("td", { class: "tid", text: r.id }),
            h("td", {}, h("span", { class: "chip-estado e-" + r.estado, text: ESTADO_TXT[r.estado] })),
            h("td", { class: "muted", text: r.anterior ? ESTADO_TXT[r.anterior] || r.anterior : "—" }),
            h("td", { text: r.tests.join(" · ") })))))
        : h("p", { class: "aviso-panel", text: "Ninguna prueba de esta ejecución tiene resultados en ese archivo. ¿Llevan los tests de Robot la etiqueta id:<ID>?" }),
      lista("Sustituyen un resultado manual (el manual queda en el historial)", plan.sustituyen_manual, "atencion"),
      lista("Tests de Robot sin etiqueta id:", plan.sin_id),
      lista("IDs que no existen en las pruebas", plan.inexistentes, "atencion"),
      lista("IDs que no están en esta ejecución", plan.fuera_de_ejecucion),
      lista("Pruebas de la ejecución sin resultado en este archivo (siguen como están)", plan.sin_robot));
    const r = await dialogo({
      titulo: "Importar resultados de Robot Framework", cuerpo, ancho: true,
      botones: [
        { texto: "Cancelar", valor: "no", tipo: "ghost" },
        plan.resultados.length ? { texto: `Importar ${plural(plan.resultados.length, "resultado", "resultados")}`, valor: "si", tipo: "primary" } : null,
      ].filter(Boolean),
    });
    if (r !== "si") return;
    const estado = await api.ejecucion_robot_importar(elegido.ruta);
    S.ejecucion = estado;
    S.seleccion = null;
    R = null;
    pintarModo();
    await cargarNavegacion();
    mostrarVacio();
    aviso(`Importados: ${t.ok} OK, ${t.no_ok} NO OK, ${t.no_aplica} no aplica`, "ok");
  } catch (e) { fallo(e); }
}

/* ---- cierre e informe ---- */
async function cerrarEjecucion() {
  if (!S.ejecucion || S.ejecucion.cerrada) return;
  if (!(await guardia())) return;
  setDirty(false);
  const t = S.ejecucion.resumen.totales;
  if (t.pendiente) {
    await dialogo({
      titulo: "Aún no se puede cerrar",
      cuerpo: `Quedan ${plural(t.pendiente, "prueba pendiente", "pruebas pendientes")}. Ejecútalas o márcalas como «No aplica» antes de cerrar la ejecución.`,
      botones: [{ texto: "Entendido", valor: "", tipo: "primary" }],
    });
    return;
  }
  const r = await dialogo({
    titulo: "Cerrar la ejecución",
    cuerpo: h("div", {},
      h("p", { text: "Al cerrarla:" }),
      h("ul", {},
        h("li", { text: "Se guarda una copia de sus pruebas tal como están ahora (con sus imágenes) dentro de la carpeta de la ejecución. El informe y la revisión usarán esa copia aunque las pruebas cambien después." }),
        h("li", { text: "Los resultados ya no se podrán cambiar." })),
      h("p", { text: `Resultado: ${t.ok} OK, ${t.no_ok} NO OK, ${plural(t.bloqueada, "bloqueada", "bloqueadas")}, ${plural(t.no_aplica, "no aplica", "no aplican")}.` })),
    botones: [{ texto: "Cancelar", valor: "no", tipo: "ghost" }, { texto: "Cerrar ejecución", valor: "si", tipo: "primary" }],
  });
  if (r !== "si") return;
  try {
    const estado = await api.ejecucion_cerrar();
    if (estado.carpeta_pruebas) { cacheImagenes.clear(); S.capitulo = 0; aplicarResumen(estado.carpeta_pruebas); }
    S.ejecucion = estado;
    S.seleccion = null;
    R = null;
    pintarModo();
    await cargarNavegacion();
    mostrarVacio();
    aviso("Ejecución cerrada", "ok");
    await generarInforme();
  } catch (e) { fallo(e); }
}

async function generarInforme() {
  if (!S.ejecucion) return;
  if (!(await guardia())) return;
  setDirty(false);
  let conPdf = null;
  try { conPdf = await api.ejecucion_pdf_disponible(); } catch (_e) { /* sin PDF */ }
  const casilla = h("input", { type: "checkbox", id: "informe-pdf", disabled: !conPdf });
  casilla.checked = Boolean(conPdf) && leerLocal("informe-pdf") === "si";
  const r = await dialogo({
    titulo: S.ejecucion.cerrada ? "Informe de la ejecución" : "Informe (borrador)",
    cuerpo: h("div", {},
      h("p", { text: "Un documento de Word con un resumen al principio (datos de la ejecución, totales, desglose por capítulo, fallos y bloqueos) y después cada prueba con su resultado, observaciones, evidencias e intentos anteriores." }),
      S.ejecucion.cerrada ? null : h("p", { class: "aviso-panel", text: "La ejecución sigue abierta: el informe saldrá marcado como BORRADOR." }),
      h("p", {}, h("label", { class: "casilla" }, casilla, " Generar también el PDF"),
        conPdf ? h("span", { class: "muted", text: ` (con ${conPdf})` }) : h("span", { class: "muted", text: " (necesita LibreOffice o Microsoft Word)" }))),
    botones: [{ texto: "Cancelar", valor: "no", tipo: "ghost" }, { texto: "Resultados en Excel (CSV)…", valor: "csv", tipo: "" },
      { texto: "Elegir destino…", valor: "si", tipo: "primary" }],
  });
  if (r === "csv") { await exportarResultadosCsv("ejecucion"); return; }
  if (r !== "si") return;
  guardarLocal("informe-pdf", casilla.checked ? "si" : "no");
  try {
    const destino = await api.ejecucion_elegir_destino_informe();
    if (destino.cancelado) return;
    const d = await conEspera(casilla.checked ? "Generando el informe y el PDF…" : "Generando el informe…",
      () => api.ejecucion_informe(destino.archivo, casilla.checked));
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

async function resincronizar() {
  try {
    const r = await api.ejecucion_resincronizar();
    S.ejecucion = r;
    const { añadidas, ya_no_cumplen: fuera } = r.cambios;
    aviso(añadidas.length ? `Añadidas: ${añadidas.join(", ")}` : "No hay pruebas nuevas que cumplan el criterio", "ok");
    if (fuera.length) aviso(`Ya no cumplen el criterio (se mantienen): ${fuera.join(", ")}`);
    pintarModo();
    await cargarNavegacion();
    mostrarVacio();
  } catch (e) { fallo(e); }
}

/* ---- ficha de una prueba en solo lectura ---- */
function textoConFormato(texto, clase = "") {
  const el = h("span", { class: ("fmt-texto " + clase).trim() });
  pintarCaracteres(el, marcasACaracteres(texto));
  return el;
}

function listaLectura(items, numerada) {
  const filas = aLista(items).map(filaDesde).filter((f) => f.texto || f.imagenes.length || f.forma === "tabla");
  if (!filas.length) return h("p", { class: "muted", text: "—" });
  let n = 0;
  return h("ol", { class: "lectura" }, filas.map((f) => {
    if (f.forma === "tabla") return h("li", { class: "con-tabla" }, h("div", {}, vistaTabla(f.tabla)));
    const marca = numerada && !f.nivel ? `${++n}.` : f.nivel ? "–" : "•";
    return h("li", { style: { "--nivel": String(f.nivel) } },
      h("span", { class: "vineta", text: marca }),
      h("div", {}, textoConFormato(f.texto),
        f.imagenes.length ? h("div", { class: "imagenes" }, f.imagenes.map((ruta) => miniatura(ruta, null))) : null));
  }));
}

function fichaPrueba(el) {
  const meta = [
    ["Maniobra", aLista(el.maniobra).join(" / ")], ["Automatizable", AUTOMATIZABLE_TXT[el.automatizable] || el.automatizable],
    ["Entorno de pruebas", aLista(el.entorno).join(" / ")], ["Requisitos", aLista(el.requisitos).join(", ")],
    ["Fecha", el.fecha], ["Versión", el.version],
  ].filter(([, v]) => v !== undefined && v !== null && String(v).trim());
  const extras = Object.entries(el.campos_adicionales || {});
  const bloque = (titulo, contenido) => h("section", { class: "bloque" }, h("div", { class: "bloque-cab" }, h("h3", { text: titulo })), contenido);
  // Compacta: los datos en una línea y los bloques juntos, para ver de una un ensayo de 20-30 pasos.
  return h("div", { class: "ficha-prueba compacta" },
    meta.length || aLista(el.etiquetas).length ? h("div", { class: "meta-linea" },
      meta.map(([k, v]) => h("span", { class: "meta-item" }, h("span", { class: "k", text: k }), h("span", { class: "v", text: String(v) }))),
      aLista(el.etiquetas).map((t) => h("span", { class: "ficha", text: t }))) : null,
    el.descripcion ? bloque("Descripción", h("p", {}, textoConFormato(String(el.descripcion)))) : null,
    aLista(el.contexto).length ? bloque("Contexto", listaLectura(el.contexto, false)) : null,
    aLista(el.parametrizacion).length ? bloque("Parametrización", listaLectura(el.parametrizacion, false)) : null,
    bloque("Situación inicial", listaLectura(el.situacion_inicial, false)),
    bloque("Ensayo", listaLectura(el.pasos, true)),
    extras.length ? bloque("Campos adicionales", h("dl", { class: "extras-lectura" }, extras.map(([k, v]) => [
      h("dt", { text: k }),
      h("dd", {}, Array.isArray(v) ? h("ul", {}, v.map((x) => h("li", {}, textoConFormato(String(x)))))
        : typeof v === "object" && v !== null ? h("pre", { text: JSON.stringify(v, null, 2) }) : textoConFormato(String(v ?? ""))),
    ]))) : null,
    aLista(el.imagenes).length ? bloque("Imágenes", h("div", { class: "imagenes" }, aLista(el.imagenes).map((ruta) => miniatura(String(ruta), null)))) : null);
}

/* ---- panel de resultado ---- */
const cacheEvidencias = new Map();
function datosEvidencia(ruta, ancho) {
  const clave = `${S.ejecucion.carpeta}|${ruta}|${ancho}`;
  if (!cacheEvidencias.has(clave)) {
    const promesa = api.ejecucion_imagen(ruta, ancho);
    cacheEvidencias.set(clave, promesa);
    promesa.catch(() => cacheEvidencias.delete(clave));
  }
  return cacheEvidencias.get(clave);
}

const esImagen = (ruta) => /\.(png|jpe?g|gif|bmp|tiff?)$/i.test(ruta);

async function mostrarEnEjecucion(datos) {
  F = null;
  if (!S.ejecucion && S.validacion && datos.tipo === "prueba") { mostrarPruebaValidacion(datos); return; }
  if (datos.tipo !== "prueba") {
    const sec = datos.elemento;
    R = null;
    ponerMigaPrueba(null);
    mostrar(h("div", { class: "formulario" },
      h("div", { class: "acciones" }, h("span", { class: "placa seccion" }, h("span", { class: "texto-placa", text: "Sección" })),
        h("div", { class: "titulo" }, h("span", { class: "nombre", text: sec.seccion }))),
      aLista(sec.contexto).length ? h("section", { class: "bloque" }, listaLectura(sec.contexto, false)) : h("p", { class: "muted", text: "Elige una prueba de la sección en el panel izquierdo." })));
    return;
  }
  const el = datos.elemento;
  const id = String(el.id || "");
  ponerMigaPrueba(id);
  const info = await api.ejecucion_resultado(id);
  const res = info.resultado;
  R = {
    id, original: res.estado || "pendiente", estado: res.estado || "pendiente",
    observaciones: String(res.observaciones || ""), incidencia: String(res.incidencia || ""),
    evidencias: aLista(res.evidencias).map(String),
    ejecutor: String(res.ejecutor || leerLocal("ejecutor") || S.ejecucion.datos.responsable || ""),
    intentos: aLista(res.intentos), fecha: res.fecha, cambiada: info.prueba_cambiada, enLaEjecucion: info.en_ejecucion,
    origen: res.origen || "",
  };
  mostrar(h("div", { class: "vista-ejecucion" },
    h("div", { class: "acciones" },
      h("span", { class: "placa" }, h("span", { class: "texto-placa", text: id || "(sin ID)" })),
      h("div", { class: "titulo" }, h("span", { class: "nombre", text: el.titulo || el.nombre || "" }),
        el.nombre && el.titulo ? h("span", { class: "ruta", text: el.nombre }) : null),
      botonEditarPrueba(id),
      h("span", { class: "chip-estado grande e-" + R.original, id: "estado-cabecera", text: ESTADO_TXT[R.original] })),
    h("div", { class: "columnas-ejecucion" }, fichaPrueba(el), panelResultado())));
}

/** «Editar esta prueba»: la abre en Editar pruebas (no con las pruebas congeladas de una ejecución cerrada). */
function botonEditarPrueba(id) {
  if (!id) return null;
  return h("button", {
    class: "btn", type: "button", disabled: S.soloLectura,
    title: S.soloLectura ? "La ejecución está cerrada y muestra sus pruebas congeladas: no se pueden editar" : "Abrir esta prueba en «Editar pruebas» (con una pastilla para volver aquí)",
    onclick: () => editarPruebaDesdeValidacion(id),
  }, "Editar esta prueba");
}

/** En el panel de resultado: lo que dicen de la prueba las otras ejecuciones de la validación. */
function restoDeLaValidacion(id) {
  const v = S.validacion;
  const p = v && S.ejecucion && S.ejecucion.en_validacion !== false && v.pruebas.find((x) => x.id === id);
  if (!p) return null;
  const actual = v.ejecuciones.findIndex((e) => e.carpeta === S.ejecucion.carpeta);
  const filas = [];
  for (const [entorno, c] of Object.entries(p.entornos)) {
    const suyos = c.historial.filter((r) => r.ejecucion_indice !== actual);
    if (!suyos.length) continue;
    const r = suyos[0];
    filas.push(h("li", {},
      h("span", { class: `punto-estado e-${claseEstado(r.estado)}` }),
      h("span", { text: `${entorno} · ${r.ejecucion}: ${CELDA_TXT[r.estado]}${r.estado === "pendiente" ? "" : " · " + fechaCorta(r.fecha)}${c.cuenta ? "" : " (no cuenta)"}` })));
  }
  return h("div", { class: "seccion-panel resto-validacion" },
    h("div", { class: "cab-panel" }, h("h3", { text: "En el resto de la validación" }),
      h("span", { class: `chip-estado e-${claseEstado(p.estado)}`, text: VAL_TXT[p.estado] })),
    filas.length ? h("ul", { class: "historial-entorno" }, filas) : h("p", { class: "muted", text: "Ninguna otra ejecución de la validación la incluye." }));
}

function panelResultado() {
  const panel = h("aside", { class: "panel-resultado", "aria-label": "Resultado de la prueba" });
  const bloqueada = cerrada() || !R.enLaEjecucion;
  function pintar() {
    const botones = ESTADOS.filter((e) => e !== "pendiente").map((e, i) => h("button", {
      type: "button", class: "estado-btn e-" + e, "aria-pressed": String(R.estado === e), disabled: bloqueada,
      title: `${ESTADO_AYUDA[e]} (tecla ${i + 1})`,
      onclick: () => cambiarEstado(e),
    }, ESTADO_TXT[e]));
    const evidencias = h("div", { class: "imagenes" }, R.evidencias.map((ruta, k) => {
      const quitar = bloqueada ? null : () => { R.evidencias.splice(k, 1); tocarResultado(); pintar(); };
      if (esImagen(ruta)) return miniatura(ruta, quitar, datosEvidencia);
      return h("div", { class: "archivo-evidencia" },
        h("button", { type: "button", class: "enlace", text: ruta.split("/").pop(), title: "Abrir con el programa del sistema", onclick: () => api.ejecucion_abrir_evidencia(ruta).catch(fallo) }),
        quitar ? h("button", { type: "button", class: "btn icono quitar", "aria-label": "Quitar evidencia", onclick: quitar }, icon("x")) : null);
    }));
    panel.replaceChildren();
    append(panel, [
      !R.enLaEjecucion ? h("p", { class: "aviso-panel", text: "Esta prueba no forma parte de la ejecución." }) : null,
      cerrada() ? h("p", { class: "aviso-panel", text: "La ejecución está cerrada: los resultados no se pueden cambiar." }) : null,
      R.origen === "robot" ? h("p", { class: "origen-panel", text: "Resultado importado de Robot Framework. Si lo cambias a mano, el importado queda en el historial." }) : null,
      tieneRobot(R.id) ? h("div", { class: "seccion-panel robot-panel" },
        h("div", { class: "cab-panel" }, h("h3", {}, icon("robot"), " Tests de Robot")), listaTestsRobot(R.id)) : null,
      R.cambiada ? avisoCambiada("La prueba ha cambiado después de ejecutarse. Revisa si hay que repetirla.",
        bloqueada ? null : darPorRevisadaEnEjecucion) : null,
      h("div", { class: "seccion-panel" },
        h("div", { class: "cab-panel" }, h("h3", { text: "Resultado" }),
          R.estado !== "pendiente" && !bloqueada ? h("button", {
            type: "button", class: "enlace", text: "Volver a pendiente", title: "Deshace el último resultado (tecla 0)",
            onclick: () => cambiarEstado("pendiente"),
          }) : null),
        h("div", { class: "estados", role: "group", "aria-label": "Resultado" }, botones),
        h("p", { class: "ayuda-estado", text: R.estado === "pendiente" ? "Todavía sin ejecutar. Elige un resultado (teclas 1 a 4)." : ESTADO_AYUDA[R.estado] })),
      h("div", { class: "seccion-panel seccion-observaciones" },
      h("label", { for: "r-observaciones", text: "Observaciones" }),
      h("textarea", {
        id: "r-observaciones", rows: 4, value: R.observaciones, disabled: bloqueada,
        placeholder: R.estado === "no_ok" || R.estado === "bloqueada" ? "Qué ha pasado (necesario para NO OK y Bloqueada)" : "",
        oninput: (e) => { R.observaciones = e.target.value; tocarResultado(); },
      }),
      h("div", { class: "rejilla-2" },
        h("div", { class: "campo" }, h("label", { for: "r-incidencia" }, "Incidencia ", enlacesIncidencia(R.incidencia)),
          h("input", { id: "r-incidencia", type: "text", value: R.incidencia, disabled: bloqueada, placeholder: "p. ej. BUG-123", oninput: (e) => { R.incidencia = e.target.value; tocarResultado(); } })),
        h("div", { class: "campo" }, h("label", { for: "r-ejecutor", text: "Ejecutor" }),
          h("input", { id: "r-ejecutor", type: "text", value: R.ejecutor, disabled: bloqueada, oninput: (e) => { R.ejecutor = e.target.value; tocarResultado(); } })))),
      h("div", { class: "seccion-panel" },
        h("div", { class: "cab-panel" }, h("h3", { text: "Evidencias" }),
          bloqueada ? null : h("button", { class: "btn ghost peq", type: "button", onclick: elegirEvidencias }, icon("plus"), "Añadir")),
        R.evidencias.length ? evidencias : h("p", { class: "ayuda-evidencias", text: bloqueada ? "Sin evidencias." : "Pega una captura (Ctrl+V) o suelta aquí capturas, logs u otros archivos." })),
      R.intentos.length ? h("details", { class: "historial" },
        h("summary", { text: `Historial (${R.intentos.length} ${R.intentos.length === 1 ? "intento anterior" : "intentos anteriores"})` }),
        h("ol", {}, [...R.intentos].reverse().map((i) => h("li", {},
          h("span", { class: "chip-estado e-" + i.estado, text: ESTADO_TXT[i.estado] || i.estado }), " ",
          h("span", { class: "muted", text: [String(i.fecha || "").replace("T", " "), i.ejecutor, i.incidencia].filter(Boolean).join(" · ") }),
          i.incidencia ? enlacesIncidencia(i.incidencia) : null,
          i.observaciones ? h("div", { text: i.observaciones }) : null)))) : null,
      restoDeLaValidacion(R.id),
      bloqueada ? null : h("div", { class: "acciones-resultado" },
        h("span", { class: "pie-resultado", text: R.fecha ? `Guardado ${fechaCorta(R.fecha)}` : "", title: R.fecha ? String(R.fecha).replace("T", " ") : "" }),
        h("button", { class: "btn", type: "button", onclick: () => guardarResultado(), title: "Ctrl+S", text: "Guardar" }),
        h("button", { class: "btn primary", type: "button", onclick: guardarYSiguiente, title: "Ctrl+Intro", text: "Guardar y siguiente" })),
    ]);
  }
  R.pintar = pintar;
  pintar();
  if (!bloqueada) {
    panel.addEventListener("paste", (e) => {
      const archivos = [...((e.clipboardData && e.clipboardData.files) || [])];
      if (!archivos.length) return;
      e.preventDefault();
      añadirEvidencias(archivos);
    });
    panel.addEventListener("dragover", (e) => { if (tieneArchivos(e)) { e.preventDefault(); panel.classList.add("suelta-archivo"); } });
    panel.addEventListener("dragleave", () => panel.classList.remove("suelta-archivo"));
    panel.addEventListener("drop", (e) => {
      if (!tieneArchivos(e)) return;
      e.preventDefault();
      panel.classList.remove("suelta-archivo");
      añadirEvidencias([...e.dataTransfer.files]);
    });
  }
  return panel;
}

function tocarResultado() { setDirty(true); }

/** «2026-11-03T10:00» -> «03/11 10:00». */
function fechaCorta(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}:\d{2}))?/.exec(String(iso || ""));
  return m ? `${m[3]}/${m[2]}${m[4] ? " " + m[4] : ""}` : String(iso || "");
}

/** Cambia el resultado. Las notas del resultado guardado no pasan a uno distinto
    (quedan en el historial); al volver al estado guardado se recuperan. */
function cambiarEstado(estado) {
  if (!R.guardadas) R.guardadas = { observaciones: R.observaciones, incidencia: R.incidencia, evidencias: [...R.evidencias] };
  const g = R.guardadas;
  const intactas = R.observaciones === g.observaciones && R.incidencia === g.incidencia
    && R.evidencias.join("\n") === g.evidencias.join("\n");
  if (R.original !== "pendiente" && intactas) {
    const vuelve = estado === R.original;
    R.observaciones = vuelve ? g.observaciones : "";
    R.incidencia = vuelve ? g.incidencia : "";
    R.evidencias = vuelve ? [...g.evidencias] : [];
  }
  R.estado = estado;
  tocarResultado();
  R.pintar();
}

async function añadirEvidencias(archivos) {
  if (!R) return;
  try {
    for (const archivo of archivos) {
      const datos = await leerComoDataUrl(archivo);
      const { ruta } = await api.ejecucion_evidencia_base64(R.id, archivo.name || "captura.png", datos);
      R.evidencias.push(ruta);
    }
    tocarResultado();
    R.pintar();
    aviso(plural(archivos.length, "evidencia añadida", "evidencias añadidas"), "ok");
  } catch (e) { fallo(e); }
}

async function elegirEvidencias() {
  try {
    const { rutas } = await api.ejecucion_elegir_evidencias(R.id);
    if (!rutas.length) return;
    R.evidencias.push(...rutas);
    tocarResultado();
    R.pintar();
  } catch (e) { fallo(e); }
}

/** Guarda el resultado en edición. Devuelve true si se puede continuar (como guardarActual). */
async function guardarResultado() {
  if (!R || !S.dirty) return true;
  if (R.estado === "pendiente" && R.original === "pendiente") {
    if (R.observaciones.trim() || R.incidencia.trim() || R.evidencias.length) {
      aviso("Elige un resultado (OK, NO OK…) antes de guardar las observaciones", "error");
      return false;
    }
    setDirty(false);
    return true;
  }
  try {
    S.ejecucion = await api.ejecucion_registrar(R.id, R.estado, R.observaciones, R.incidencia, R.evidencias, R.ejecutor);
    if (R.ejecutor.trim()) guardarLocal("ejecutor", R.ejecutor.trim());
    setDirty(false);
    pintarModo();
    const indice = S.seleccion && S.seleccion.indice;
    await cargarNavegacion();
    aviso(`${R.id}: ${ESTADO_TXT[R.estado]}`, "ok");
    if (indice !== null && S.nodos.some((n) => n.indice === indice)) {
      S.seleccion = null;
      await seleccionar("prueba", indice);
    } else {
      S.seleccion = null;
      mostrarVacio();
    }
    return true;
  } catch (e) { fallo(e); return false; }
}

async function guardarYSiguiente() {
  if (!R) return;
  const id = R.id;
  if (await guardarResultado()) await siguientePendiente(id);
}

/* ---- arranque ---- */
function iniciarEjecucion() {
  $("#modo-edicion").addEventListener("click", () => cambiarModo("edicion"));
  $("#modo-requisitos").addEventListener("click", () => cambiarModo("requisitos"));
  $("#modo-ejecucion").addEventListener("click", () => cambiarModo("ejecucion"));
  $("#btn-ejecucion").addEventListener("click", menuEjecucion);
  $("#btn-validacion").addEventListener("click", pulsarMigaValidacion);
  $("#btn-volver").addEventListener("click", volverDeEdicion);
  $("#btn-panel-ejecucion").addEventListener("click", async () => {
    if (!(await guardia())) return;
    setDirty(false);
    S.seleccion = null;
    renderArbol();
    mostrarVacio();
  });
  $("#filtro-estado").addEventListener("change", async (e) => {
    S.filtroEstado = e.target.value;
    await cargarNavegacion();
  });
  document.addEventListener("keydown", (e) => {
    if (!enEjecucion() || !R || cerrada() || !R.enLaEjecucion || document.querySelector("dialog[open]")) return;
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); guardarYSiguiente(); return; }
    const escribiendo = e.target.closest && e.target.closest("input, textarea, select, [contenteditable]");
    if (escribiendo || e.ctrlKey || e.metaKey || e.altKey) return;
    const estado = { 1: "ok", 2: "no_ok", 3: "bloqueada", 4: "no_aplica", 0: "pendiente" }[e.key];
    if (!estado) return;
    e.preventDefault();
    cambiarEstado(estado);
  });
}
