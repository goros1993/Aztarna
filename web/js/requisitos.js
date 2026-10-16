"use strict";
/* Modo «Requisitos»: formulario de cada requisito, su trazabilidad (qué
   pruebas lo cubren), el panel de cobertura y el campo «Requisitos» de las
   pruebas. Los cálculos están en trazabilidad.py. */

/* Campos del requisito (los define esquema.py). */
const REQ_CAMPOS_TEXTO = ["nombre", "id", "titulo", "descripcion", "fuente", "referencia", "tipo", "fase", "fecha", "version"];
const REQ_LISTAS = ["detalle", "contexto"];
const REQ_MULTIPLES = ["criterio_validacion"];

const COBERTURA_TXT = { cubierto: "Cubierto", sin_cobertura: "Sin cobertura", no_aplica: "No aplica" };
const COBERTURA_AYUDA = {
  cubierto: "Al menos una prueba lo cita en su campo «Requisitos».",
  sin_cobertura: "Se valida con pruebas (criterio «Test» o sin criterio) y ninguna prueba lo cita.",
  no_aplica: "Es informativo o se valida sin pruebas (inspección o análisis).",
};

/* ---- árbol ---- */
function marcaCobertura(c) {
  if (!c) return h("span", { class: "punto-cobertura", title: "ID repetido o vacío: no cuenta", role: "img", "aria-label": "Sin datos" });
  const texto = COBERTURA_TXT[c.estado] + (c.estado === "cubierto" ? ` (${plural(c.pruebas, "prueba", "pruebas")})` : "");
  return h("span", { class: "punto-cobertura c-" + c.estado, title: texto, role: "img", "aria-label": texto });
}

/** Por sección: requisitos que necesitan pruebas y cuántos las tienen (cuenta los de todas sus subsecciones). */
function coberturaPorSeccion(nodos) {
  const cuentas = new Map();
  const padres = new Map(nodos.map((n) => [n.indice, n.padre]));
  for (const n of nodos) {
    if (n.tipo !== "requisito" || !n.cobertura || n.cobertura.estado === "no_aplica") continue;
    for (let p = n.padre; p !== null && p !== undefined; p = padres.get(p)) {
      const c = cuentas.get(p) || { necesitan: 0, cubiertos: 0 };
      c.necesitan += 1;
      if (n.cobertura.estado === "cubierto") c.cubiertos += 1;
      cuentas.set(p, c);
    }
  }
  return cuentas;
}

function ponerCoberturaSeccion(fila, c) {
  const cuenta = fila.querySelector(".cuenta");
  if (!c) return;
  const completa = c.cubiertos === c.necesitan;
  const el = h("span", {
    class: "cuenta cobertura-seccion" + (completa ? " completa" : ""),
    text: `${c.cubiertos}/${c.necesitan}`,
    title: `${c.cubiertos} de ${plural(c.necesitan, "requisito con pruebas", "requisitos con pruebas")}`,
  });
  if (cuenta) cuenta.replaceWith(el); else fila.insertBefore(el, fila.querySelector(".marca-problema"));
}

function filtrarNodosCobertura(nodos) {
  if (!S.filtroCobertura) return nodos;
  const padres = new Map(nodos.map((n) => [n.indice, n.padre]));
  const quedan = new Set();
  for (const n of nodos) {
    if (n.tipo !== "requisito" || !n.cobertura) continue;
    const vale = S.filtroCobertura === "modificado" ? n.cobertura.modificado : n.cobertura.estado === S.filtroCobertura;
    if (!vale) continue;
    quedan.add(n.indice);
    for (let p = n.padre; p !== null && p !== undefined; p = padres.get(p)) quedan.add(p);
  }
  return nodos.filter((n) => quedan.has(n.indice));
}

/* ---- ir de una prueba a un requisito y al revés ---- */
async function irAElemento(modo, capitulo, indice, tipo) {
  if (S.modo !== modo) {
    await cambiarModo(modo);
    if (S.modo !== modo) return;          // se canceló por cambios sin guardar
  } else if (!(await guardia())) return;
  setDirty(false);
  S.filtroCobertura = ""; $("#filtro-cobertura").value = "";
  if (capitulo !== S.capitulo || S.consulta) {
    S.capitulo = capitulo;
    $("#sel-capitulo").value = String(capitulo);
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
  await seleccionar(tipo, indice);
}

async function irARequisito(id) {
  try {
    const r = await api.ir_a_requisito(id);
    await irAElemento("requisitos", r.capitulo, r.indice, "requisito");
  } catch (e) { fallo(e); }
}

async function irAPrueba(id) {
  try {
    const r = await api.ir_a_prueba(id);
    await irAElemento("edicion", r.capitulo, r.indice, "prueba");
  } catch (e) { fallo(e); }
}

/* ---- campo «Requisitos» de una prueba ---- */
/** Fichas con los IDs de requisito: propone los del catálogo y marca los que no existen o han cambiado. */
function campoRequisitos() {
  if (!S.hayRequisitos) {
    return campoFichas("requisitos", "Requisitos", { ayuda: "Uno por ficha: escribe y pulsa Enter.", completo: false });
  }
  let catalogo = null;
  const lista = api.requisitos_lista();
  const campo = campoFichas("requisitos", "Requisitos", {
    completo: false,
    ayuda: "Escribe el ID o parte del título y elige. Pulsa un requisito para abrirlo.",
    sugerir: () => lista.then((l) => l.map((r) => ({ texto: r.id, detalle: r.titulo }))),
    decorar: (id) => {
      if (!catalogo) return {};
      const r = catalogo.get(id);
      if (!r) return { clase: "no-valida", title: "No existe en el catálogo de requisitos" };
      if (r.modificado) return { clase: "cambiada", title: `${r.titulo}\nHa cambiado desde la última revisión: comprueba que esta prueba sigue cubriéndolo.`, onclick: () => irARequisito(id) };
      return { title: r.titulo, onclick: () => irARequisito(id) };
    },
  });
  lista.then((l) => {
    catalogo = new Map(l.map((r) => [r.id, r]));
    const fichas = campo.querySelector(".fichas");
    if (fichas && fichas.repintar) fichas.repintar();
  }, () => {});
  return campo;
}

/* ---- formulario del requisito ---- */
function valoresDeRequisito(el = {}) {
  const v = {};
  for (const k of REQ_CAMPOS_TEXTO) v[k] = el[k] === null || el[k] === undefined ? "" : String(el[k]);
  for (const k of REQ_LISTAS) v[k] = aLista(el[k]).map(filaDesde);
  for (const k of REQ_MULTIPLES) v[k] = aLista(el[k]).map(String);
  v.campos_adicionales = extrasDesde(el.campos_adicionales);
  return v;
}

function cuerpoRequisito(ubicacion) {
  const tipos = ((S.esquema && S.esquema.requisito.tipos) || []).map((t) => ({ valor: t, texto: t }));
  const cont = h("div", { class: "formulario" }, cabecera(), ubicacion);
  append(cont, [
    F.modo === "editar" ? bloqueTraza(F.traza) : null,
    h("section", { class: "bloque", "aria-label": "Datos del requisito" },
      h("div", { class: "bloque-cab" }, h("h3", { text: "Datos del requisito" })),
      h("div", { class: "rejilla" },
        campoTexto("id", "ID *", { mono: true }),
        campoTexto("nombre", "Encabezado en el documento", { ancho: true }),
        campoTexto("titulo", "Título *", { completo: true }),
        campoArea("descripcion", "Descripción"),
        campoTexto("fuente", "Fuente"),
        campoTexto("referencia", "Referencia", { ancho: true }))),
    editorLista("detalle", "Tablas e imágenes de la descripción", { ayuda: "Tablas, imágenes y párrafos que siguen a la descripción dentro de su celda.", conTablas: true }),
    h("section", { class: "bloque", "aria-label": "Clasificación" },
      h("div", { class: "rejilla" },
        campoSelect("tipo", "Tipo", tipos),
        campoOpciones("criterio_validacion", "Criterio validación"),
        h("p", { class: "ayuda completo", text: "Un requisito con el criterio «Test» (o sin criterio) necesita pruebas que lo citen; los informativos y los que solo se validan por inspección o análisis, no." }),
        campoTexto("fase", "Fase"),
        campoTexto("fecha", "Fecha"),
        campoTexto("version", "Versión"))),
    editorLista("contexto", "Contexto", { ayuda: "Texto y tablas que aparecen antes de la tabla del requisito.", conTablas: true }),
    editorExtras(),
  ]);
  return cont;
}

/** Estado de cobertura, pruebas que lo cubren y, si ha cambiado, el texto anterior. */
function bloqueTraza(traza) {
  if (!traza) {
    return h("section", { class: "bloque traza" }, h("p", { class: "aviso-panel", text: "Este requisito no tiene ID o lo tiene repetido: no cuenta para la trazabilidad hasta que lo corrijas." }));
  }
  const id = F.valores.id;
  const cambio = traza.modificado && traza.anterior ? h("div", { class: "aviso-cambio" },
    h("div", { class: "aviso-cambio-cab" },
      icon("alert"),
      h("strong", { text: "El requisito ha cambiado desde la última revisión de sus pruebas" }),
      h("button", { class: "btn peq", type: "button", onclick: () => marcarRevisado(id), title: "Las pruebas siguen cubriéndolo (o ya las has adaptado)" }, icon("check"), "Pruebas revisadas")),
    h("p", { class: "ayuda", text: "Comprueba que cada prueba de la lista sigue cubriéndolo. Texto que tenía en la última revisión:" }),
    h("dl", { class: "texto-anterior" },
      traza.anterior.titulo !== undefined ? [h("dt", { text: "Título" }), h("dd", { text: sinMarcas(traza.anterior.titulo) })] : null,
      traza.anterior.descripcion !== undefined ? [h("dt", { text: "Descripción" }), h("dd", { text: sinMarcas(traza.anterior.descripcion) })] : null,
      traza.anterior.contexto !== undefined ? [h("dt", { text: "Contexto" }), h("dd", { text: "(también ha cambiado el contexto)" })] : null)) : null;
  const pruebas = traza.pruebas.length
    ? h("ul", { class: "lista-traza" }, traza.pruebas.map((p) => h("li", {},
      h("button", { class: "enlace tid", type: "button", text: p.id || "(sin ID)", title: "Abrir la prueba", onclick: () => irAPrueba(p.id) }),
      h("span", { text: p.titulo }),
      h("span", { class: "muted", text: p.archivo }))))
    : h("p", { class: "muted", text: traza.necesita
      ? `Ninguna prueba lo cita. Para cubrirlo, añade «${id}» en el campo «Requisitos» de las pruebas que lo verifican.`
      : "No necesita pruebas." });
  return h("section", { class: "bloque traza", "aria-label": "Trazabilidad" },
    h("div", { class: "bloque-cab" },
      h("h3", { text: "Pruebas que lo cubren" }),
      h("span", { class: "chip-cobertura c-" + traza.estado, title: COBERTURA_AYUDA[traza.estado], text: COBERTURA_TXT[traza.estado] })),
    cambio, pruebas);
}

/** Texto sin las marcas de formato del YAML (negrita, cursiva, color). */
const sinMarcas = (texto) => String(texto ?? "").replace(/\[\[[^\]|]+\||\]\]|\*\*|\*/g, "");

async function marcarRevisado(id) {
  try {
    await api.revisar_requisito(id);
    await refrescarTodo({ seleccionar: { tipo: "requisito", indice: F.indice } });
    aviso("Pruebas marcadas como revisadas", "ok");
  } catch (e) { fallo(e); }
}

function mostrarRequisito(datos) {
  const el = datos.elemento;
  F = {
    modo: "editar", tipo: "requisito", indice: datos.indice, valores: valoresDeRequisito(el), cambios: new Set(),
    nivel: el.nivel, vista: "form", idOriginal: String(el.id || ""), traza: datos.traza,
  };
  mostrar(cuerpoRequisito(null));
  setDirty(false);
}

async function mostrarNuevoRequisito(inicial = null, porDefecto = null) {
  F = { modo: "nueva", tipo: "requisito", indice: null, valores: inicial || valoresDeRequisito({}), cambios: new Set(), nivel: 3, vista: "form" };
  const ubicacion = await selectorUbicacion(false, porDefecto);
  mostrar(cuerpoRequisito(ubicacion));
  setDirty(Boolean(inicial));
  const campo = $("#f-id"); if (campo) campo.focus();
}

async function guardarRequisito(cambios) {
  const { indice } = F;
  let renombrar = false;
  const nuevo = "id" in cambios ? String(cambios.id).trim() : null;
  if (F.idOriginal && nuevo !== null && nuevo !== F.idOriginal) {
    const { pruebas } = await api.requisito_usos(F.idOriginal);
    const botones = [{ texto: "Cancelar", valor: "no", tipo: "ghost" }];
    if (pruebas.length) {
      botones.push({ texto: "Cambiar solo el requisito", valor: "solo", tipo: "" });
      botones.push({ texto: `Cambiar también en ${plural(pruebas.length, "prueba", "pruebas")}`, valor: "todas", tipo: "primary" });
    } else botones.push({ texto: "Cambiar el ID", valor: "solo", tipo: "primary" });
    const r = await dialogo({
      titulo: "¿Cambiar el ID del requisito?",
      cuerpo: h("div", {},
        h("p", { text: `El ID pasará de «${F.idOriginal}» a «${nuevo}».` }),
        pruebas.length
          ? h("p", { text: `${plural(pruebas.length, "prueba lo cita", "pruebas lo citan")} (${pruebas.slice(0, 8).join(", ")}${pruebas.length > 8 ? "…" : ""}). Si cambias solo el requisito, esas pruebas apuntarán a un ID que ya no existe.` })
          : h("p", { text: "Ninguna prueba lo cita." })),
      botones,
    });
    if (r === "no" || r === undefined || r === null) return false;
    renombrar = r === "todas";
  }
  const d = await api.guardar_requisito(S.capitulo, indice, cambios, renombrar);
  setDirty(false);
  await refrescarTodo({ seleccionar: { tipo: "requisito", indice } });
  aviso(d.pruebas_actualizadas ? `Requisito guardado; ID cambiado en ${plural(d.pruebas_actualizadas, "prueba", "pruebas")}` : "Requisito guardado", "ok");
  return true;
}

async function crearRequisito() {
  if (!F.valores.id.trim()) { mostrarErrorCampo("id", "El ID es obligatorio."); return false; }
  const r = await api.crear_requisito(S.capitulo, F.ubicacion, recogerCambios());
  setDirty(false);
  await refrescarTodo({ seleccionar: { tipo: "requisito", indice: r.indice } });
  aviso("Requisito creado", "ok");
  return true;
}

/* ---- panel de cobertura ---- */
async function mostrarPanelTrazabilidad() {
  if (S.errorRequisitos) {
    mostrar(h("div", { class: "centro" }, h("h2", { text: "No se pueden leer los requisitos" }), h("p", { text: S.errorRequisitos })));
    return;
  }
  if (!S.hayRequisitos) {
    mostrar(h("div", { class: "centro" },
      h("h2", { text: "Esta carpeta no tiene requisitos" }),
      h("p", { text: "Los requisitos se guardan en la carpeta «requisitos», junto a la carpeta «pruebas» (o dentro de la carpeta de pruebas, si no se llama así), con capítulos y secciones igual que las pruebas. Las pruebas los citan por su ID en el campo «Requisitos»." }),
      h("div", { class: "fila-botones" },
        h("button", { class: "btn primary", type: "button", onclick: crearCatalogo, text: "Crear requisitos" }))));
    return;
  }
  let d;
  try { d = await api.trazabilidad(); } catch (e) { fallo(e); return; }
  if (F || !enRequisitos()) return;      // mientras tanto se abrió otra cosa
  const t = d.total;
  const necesitan = t.cubierto + t.sin_cobertura;
  const barra = (c) => h("div", { class: "barra-progreso", role: "img", "aria-label": `${c.cubierto} de ${c.cubierto + c.sin_cobertura} cubiertos` },
    c.cubierto ? h("span", { class: "c-cubierto", style: { flexGrow: String(c.cubierto) }, title: `Cubiertos: ${c.cubierto}` }) : null,
    c.sin_cobertura ? h("span", { class: "c-sin_cobertura", style: { flexGrow: String(c.sin_cobertura) }, title: `Sin cobertura: ${c.sin_cobertura}` }) : null);
  const tarjeta = (titulo, valor, extra = "", clase = "", filtro = null) => h(filtro ? "button" : "div", {
    class: "tarjeta " + clase + (filtro ? " pulsable" : ""), type: filtro ? "button" : null,
    title: filtro ? "Ver solo estos en el panel izquierdo" : null,
    onclick: filtro ? () => filtrarCobertura(filtro) : null,
  }, h("span", { class: "t-tit", text: titulo }), h("span", { class: "t-val", text: String(valor) }), extra ? h("span", { class: "t-extra", text: extra }) : null);
  const reqLink = (r) => h("button", { class: "enlace tid", type: "button", text: r.id, title: "Abrir el requisito", onclick: () => irARequisito(r.id) });
  const listaReqs = (reqs, vacio) => reqs.length
    ? h("ul", { class: "lista-traza" }, reqs.map((r) => h("li", {}, reqLink(r), h("span", { text: r.titulo }),
      h("span", { class: "muted", text: [r.nombre_capitulo, ...r.seccion].join(" › ") }))))
    : h("p", { class: "muted", text: vacio });
  const sin = d.requisitos.filter((r) => r.estado === "sin_cobertura");
  const cambiados = d.requisitos.filter((r) => r.modificado);

  mostrar(h("div", { class: "formulario panel-campana panel-traza" },
    h("div", { class: "acciones" },
      h("div", { class: "titulo" }, h("span", { class: "nombre", text: "Cobertura de requisitos" }),
        h("span", { class: "ruta", text: `${plural(t.requisitos, "requisito", "requisitos")} en ${plural(d.capitulos.length, "capítulo", "capítulos")}` })),
      h("button", { class: "btn", type: "button", onclick: exportarMatriz, title: "Una fila por requisito con las pruebas que lo cubren (se abre con Excel)" }, icon("export"), "Exportar matriz…"),
      h("button", { class: "btn primary", type: "button", onclick: () => nuevaPrueba() }, icon("plus"), "Nuevo requisito")),
    h("section", { class: "bloque" },
      h("div", { class: "bloque-cab" }, h("h3", { text: "Cobertura" }),
        h("p", { class: "ayuda", text: necesitan ? `${t.cubierto} de ${necesitan} requisitos que se validan con pruebas tienen al menos una (${t.porcentaje} %).` : "Ningún requisito se valida con pruebas." })),
      barra(t),
      h("div", { class: "tarjetas" },
        tarjeta("Cubiertos", t.cubierto, t.porcentaje !== null ? `${t.porcentaje} %` : "", "c-cubierto", "cubierto"),
        tarjeta("Sin cobertura", t.sin_cobertura, "", "c-sin_cobertura", "sin_cobertura"),
        tarjeta("No aplica", t.no_aplica, "informativos o sin test", "c-no_aplica", "no_aplica"),
        tarjeta("Cambiados", t.modificados, "pruebas por revisar", "c-modificado", "modificado"))),
    h("section", { class: "bloque" },
      h("div", { class: "bloque-cab" }, h("h3", { text: "Por capítulo" })),
      h("table", { class: "tabla-estados tabla-cobertura" },
        h("thead", {}, h("tr", {}, ["Capítulo", "Requisitos", "Cubiertos", "Sin cobertura", "No aplica", "Cambiados", ""].map((x, i) => h("th", { class: i && i < 6 ? "num" : "", text: x })))),
        h("tbody", {}, d.capitulos.map((c) => h("tr", { class: "pulsable", title: "Abrir el capítulo", onclick: () => abrirCapituloRequisitos(c.capitulo) },
          h("td", { text: c.nombre }),
          h("td", { class: "num", text: String(c.requisitos) }),
          h("td", { class: "num", text: c.cubierto ? String(c.cubierto) : "·" }),
          h("td", { class: "num" + (c.sin_cobertura ? " c-txt-sin_cobertura" : ""), text: c.sin_cobertura ? String(c.sin_cobertura) : "·" }),
          h("td", { class: "num", text: c.no_aplica ? String(c.no_aplica) : "·" }),
          h("td", { class: "num" + (c.modificados ? " c-txt-modificado" : ""), text: c.modificados ? String(c.modificados) : "·" }),
          h("td", { class: "celda-barra" }, c.cubierto + c.sin_cobertura ? barra(c) : null)))))),
    h("section", { class: "bloque" },
      h("div", { class: "bloque-cab" }, h("h3", { text: `Sin cobertura (${sin.length})` })),
      listaReqs(sin, "Todos los requisitos que se validan con pruebas tienen al menos una.")),
    h("section", { class: "bloque" },
      h("div", { class: "bloque-cab" }, h("h3", { text: `Cambiados, con pruebas por revisar (${cambiados.length})` })),
      listaReqs(cambiados, "Ninguno.")),
    h("section", { class: "bloque" },
      h("div", { class: "bloque-cab" }, h("h3", { text: `Referencias a requisitos que no existen (${d.huerfanas.length})` }),
        h("p", { class: "ayuda", text: "Pruebas que citan un ID que no está en el catálogo: corrige el ID en la prueba o crea el requisito." })),
      d.huerfanas.length
        ? h("ul", { class: "lista-traza" }, d.huerfanas.map((x) => h("li", {},
          h("button", { class: "enlace tid", type: "button", text: x.id || "(sin ID)", title: "Abrir la prueba", onclick: () => irAPrueba(x.id) }),
          h("span", { text: `cita «${x.requisito}»` }), h("span", { class: "muted", text: x.archivo }))))
        : h("p", { class: "muted", text: "Ninguna." })),
    h("section", { class: "bloque" },
      h("details", { class: "plegable" },
        h("summary", { text: `Pruebas sin requisito (${d.sin_requisito.length})` }),
        d.sin_requisito.length
          ? h("ul", { class: "lista-traza" }, d.sin_requisito.map((x) => h("li", {},
            h("button", { class: "enlace tid", type: "button", text: x.id || "(sin ID)", title: "Abrir la prueba", onclick: () => irAPrueba(x.id) }),
            h("span", { text: x.titulo }), h("span", { class: "muted", text: x.archivo }))))
          : h("p", { class: "muted", text: "Todas las pruebas citan algún requisito." })))));
}

async function filtrarCobertura(filtro) {
  S.filtroCobertura = filtro;
  $("#filtro-cobertura").value = filtro;
  try { await cargarNavegacion(); } catch (e) { fallo(e); }
}

async function abrirCapituloRequisitos(ci) {
  if (ci === S.capitulo) return;
  $("#sel-capitulo").value = String(ci);
  await cambiarCapitulo(String(ci));
}

async function crearCatalogo() {
  try {
    aplicarResumen(await api.crear_catalogo_requisitos());
    S.capitulo = 0;
    await cargarNavegacion();
    mostrarVacio();
    aviso("Carpeta de requisitos creada", "ok");
  } catch (e) { fallo(e); }
}

async function exportarMatriz() {
  try {
    const d = await api.exportar_matriz();
    if (d.cancelado) return;
    const r = await dialogo({
      titulo: "Matriz exportada",
      cuerpo: h("div", {}, h("p", { text: `${plural(d.requisitos, "requisito", "requisitos")} con sus pruebas.` }), h("p", { class: "muted", text: d.archivo })),
      botones: [{ texto: "Mostrar en la carpeta", valor: "mostrar", tipo: "" }, { texto: "Cerrar", valor: "cerrar", tipo: "primary" }],
    });
    if (r === "mostrar") await api.mostrar_en_carpeta(d.archivo).catch(fallo);
  } catch (e) { fallo(e); }
}
