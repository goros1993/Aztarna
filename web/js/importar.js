"use strict";
/* Asistente de importación (⋯ → Importar…): documento, familias de tablas,
   campos y revisión. La lógica está en app/importacion.py; el mapeo elegido
   se recuerda para la próxima vez. */

const PASOS_IMPORTAR = ["Documento", "Tablas", "Campos", "Revisar"];
const TIPO_PLURAL = { prueba: "pruebas", requisito: "requisitos" };
let IMP = null;

function importarDisponible() {
  return S.modo !== "ejecucion";
}

async function asistenteImportar() {
  if (!(await guardia())) return;
  setDirty(false);
  IMP = { paso: 0, archivo: "", preferido: enRequisitos() ? "requisito" : "prueba", modo: "nuevo", nombre: "",
    analisis: null, mapeo: null, revision: null, ids: {} };
  const dlg = h("dialog", { class: "ancho asistente", "aria-label": "Importar desde Word" });
  dlg.addEventListener("close", () => { dlg.remove(); IMP = null; });
  dlg.addEventListener("cancel", (e) => { if (document.querySelector(".espera")) e.preventDefault(); });
  document.body.appendChild(dlg);
  IMP.dlg = dlg;
  pintarAsistente();
  dlg.showModal();
}

function pintarAsistente() {
  const pasos = h("ol", { class: "asistente-pasos" }, PASOS_IMPORTAR.map((p, i) => h("li", {
    class: i === IMP.paso ? "activo" : i < IMP.paso ? "hecho" : "", text: `${i + 1}. ${p}`,
    "aria-current": i === IMP.paso ? "step" : null,
  })));
  const cuerpo = [pasoDocumento, pasoTablas, pasoCampos, pasoRevisar][IMP.paso]();
  const boton = (texto, tipo, accion, extra = {}) => h("button", { type: "button", class: "btn " + tipo, text: texto, onclick: accion, ...extra });
  const pie = h("div", { class: "dlg-pie" },
    boton("Cancelar", "ghost", () => IMP.dlg.close()),
    IMP.paso > 0 ? boton("Atrás", "", () => { IMP.paso -= 1; pintarAsistente(); }) : null,
    IMP.paso < 3
      ? boton("Siguiente", "primary", () => siguientePaso().catch(fallo), { disabled: IMP.paso === 0 && !IMP.archivo })
      : boton(IMP.modo === "nuevo" ? "Elegir carpeta e importar…" : "Importar", "primary", () => ejecutarImportacion().catch(fallo),
        { disabled: !IMP.revision || !Object.keys(IMP.revision.tipos).length }));
  IMP.dlg.replaceChildren(
    h("div", { class: "dlg-cab" }, "Importar desde Word", pasos),
    h("div", { class: "dlg-cuerpo asistente-cuerpo" }, cuerpo),
    pie);
  const primero = IMP.dlg.querySelector(".dlg-pie .btn.primary:not([disabled])");
  if (primero) primero.focus();
}

async function siguientePaso() {
  if (IMP.paso === 0) {
    const a = await conEspera("Analizando las tablas del documento…", () => api.importar_analizar(IMP.archivo, IMP.preferido), "Con documentos grandes puede tardar unos minutos; no cierres la ventana.");
    IMP.analisis = a;
    IMP.mapeo = a.mapeo;
    if (!IMP.nombre) IMP.nombre = a.nombre_propuesto;
  } else if (IMP.paso === 1) {
    if (!tiposElegidos().length) { aviso("Ninguna familia es de pruebas ni de requisitos: no hay nada que importar", "error"); return; }
  } else if (IMP.paso === 2) {
    IMP.revision = await conEspera("Preparando la vista previa…", () => api.importar_revisar(IMP.archivo, IMP.mapeo, IMP.modo), "Se lee todo el documento con el mapeo elegido. Con documentos grandes puede tardar unos minutos; no cierres la ventana.");
    IMP.ids = {};
    for (const [tipo, datos] of Object.entries(IMP.revision.tipos)) {
      IMP.ids[tipo] = Object.fromEntries(datos.ids.filter((p) => p.propuesta).map((p) => [String(p.orden), p.propuesta]));
    }
  }
  IMP.paso += 1;
  pintarAsistente();
}

function tiposElegidos() {
  const tipos = new Set(IMP.analisis.familias.map((f) => IMP.mapeo.tipos[f.firma]));
  return ["prueba", "requisito"].filter((t) => tipos.has(t));
}

/* ---- 1. documento ---- */
function pasoDocumento() {
  const radio = (nombre, valor, texto, actual, alCambiar, deshabilitado = false) => h("label", { class: "opcion-radio" + (deshabilitado ? " deshabilitada" : "") },
    h("input", { type: "radio", name: nombre, value: valor, checked: actual === valor, disabled: deshabilitado, onchange: () => alCambiar(valor) }),
    h("span", {}, texto));
  const abierto = S.carpeta && !S.soloLectura ? S.carpeta : null;
  if (!abierto && IMP.modo === "anadir") IMP.modo = "nuevo";
  const nombre = h("input", { type: "text", id: "imp-nombre", value: IMP.nombre, placeholder: "Nombre de la carpeta del proyecto",
    disabled: IMP.modo !== "nuevo", oninput: (e) => { IMP.nombre = e.target.value; } });
  return h("div", { class: "asistente-documento" },
    h("p", { class: "muted", text: "El editor busca las tablas del documento, las agrupa por sus etiquetas («Descripción:», «Pasos:»…) y te deja decidir a qué campo va cada una. No cambia nada hasta el último paso." }),
    h("div", { class: "campo" },
      h("label", { text: "Documento de Word" }),
      h("div", { class: "fila-archivo" },
        h("button", { type: "button", class: "btn", onclick: async () => {
          try {
            const r = await api.importar_elegir_documento();
            if (r.cancelado) return;
            if (r.archivo !== IMP.archivo) {
              IMP.archivo = r.archivo;
              IMP.nombre = r.archivo.split(/[\\/]/).pop().replace(/\.docx$/i, "").replace(/\s+/g, "_");
              IMP.analisis = null;
            }
            pintarAsistente();
          } catch (e) { fallo(e); }
        } }, icon("import"), IMP.archivo ? "Cambiar…" : "Elegir documento…"),
        h("span", { class: "ruta-archivo", text: IMP.archivo || "Ningún documento elegido", title: IMP.archivo || "" }))),
    h("fieldset", { class: "grupo-radio" },
      h("legend", { text: "¿Qué contiene?" }),
      radio("imp-tipo", "prueba", "Pruebas", IMP.preferido, (v) => { IMP.preferido = v; }),
      radio("imp-tipo", "requisito", "Requisitos", IMP.preferido, (v) => { IMP.preferido = v; }),
      radio("imp-tipo", "", "Lo decide el editor (pruebas y requisitos en el mismo documento)", IMP.preferido || "", (v) => { IMP.preferido = v || null; }),
      h("p", { class: "ayuda", text: "Solo sirve para proponer; en el siguiente paso eliges qué es cada grupo de tablas." })),
    h("fieldset", { class: "grupo-radio" },
      h("legend", { text: "¿Dónde se importa?" }),
      radio("imp-modo", "nuevo", "En un proyecto nuevo", IMP.modo, (v) => { IMP.modo = v; nombre.disabled = false; }),
      h("div", { class: "campo sangrado" }, nombre),
      radio("imp-modo", "anadir", abierto ? `Añadirlo al proyecto abierto (${abierto})` : "Añadirlo al proyecto abierto (no hay ninguno)", IMP.modo,
        (v) => { IMP.modo = v; nombre.disabled = true; }, !abierto),
      h("p", { class: "ayuda", text: "Al añadir, los capítulos del documento van al final del índice y los IDs que ya existen en el proyecto se marcan para cambiarlos." })));
}

/* ---- 2. familias de tablas ---- */
function pasoTablas() {
  const a = IMP.analisis;
  const tarjetas = a.familias.map((f) => {
    const sel = h("select", { "aria-label": `Qué es la familia ${f.numero}`, onchange: (e) => { IMP.mapeo.tipos[f.firma] = e.target.value; } },
      a.tipos.map((t) => h("option", { value: t.valor, text: t.texto, selected: IMP.mapeo.tipos[f.firma] === t.valor })));
    const etiquetas = f.etiquetas.filter((e) => e.inicio);
    const visibles = etiquetas.slice(0, 14);
    return h("li", { class: "familia" },
      h("div", { class: "familia-cab" },
        h("strong", { text: `Familia ${f.numero}` }),
        h("span", { class: "muted", text: plural(f.tablas, "tabla", "tablas") }),
        h("span", { class: "hueco" }),
        sel),
      h("p", { class: "familia-ejemplos", text: "Por ejemplo: " + f.ejemplos.join(" · ") }),
      etiquetas.length
        ? h("div", { class: "fichas-etiquetas" }, visibles.map((e) => h("span", { class: "ficha", text: e.etiqueta, title: `En ${plural(e.tablas, "tabla", "tablas")}` })),
          etiquetas.length > visibles.length ? h("span", { class: "muted", text: `y ${etiquetas.length - visibles.length} más` }) : null)
        : h("p", { class: "muted", text: "Sin etiquetas: parece una tabla de datos (historial, parámetros…)." }),
      f.anidadas ? h("p", { class: "ayuda", text: `${plural(f.anidadas, "tabla", "tablas")} dentro de celdas: en un requisito van a «Tablas e imágenes de la descripción»; en una prueba, a su contexto.` }) : null);
  });
  return h("div", {},
    h("p", { class: "muted", text: `${plural(a.tablas, "tabla", "tablas")} en ${plural(a.familias.length, "familia", "familias")}. Una familia son las tablas con las mismas etiquetas (o casi). Elige qué es cada una: las «tablas informativas» se conservan tal cual, en el texto de su sección.` }),
    h("ul", { class: "familias" }, tarjetas));
}

/* ---- 3. etiquetas → campos ---- */
function pasoCampos() {
  const a = IMP.analisis;
  const bloques = tiposElegidos().map((tipo) => {
    const etiquetas = new Map();
    for (const f of a.familias) {
      if (IMP.mapeo.tipos[f.firma] !== tipo) continue;
      for (const e of f.etiquetas) {
        const previa = etiquetas.get(e.clave);
        if (previa) { previa.tablas += e.tablas; previa.inicio = previa.inicio || e.inicio; } else etiquetas.set(e.clave, { ...e });
      }
    }
    const filas = [...etiquetas.values()].sort((x, y) => (y.inicio - x.inicio) || (y.tablas - x.tablas));
    return h("section", { class: "bloque-mapeo" },
      h("h3", { text: tipo === "prueba" ? "Pruebas" : "Requisitos" }),
      h("p", { class: "ayuda", text: "Cabecera de la tabla: la primera celda es el ID y la segunda, el título." }),
      h("table", { class: "tabla-mapeo" },
        h("thead", {}, h("tr", {}, h("th", { text: "Etiqueta en el Word" }), h("th", { text: "Tablas" }), h("th", { text: "Va a" }))),
        h("tbody", {}, filas.map((e) => {
          const sel = h("select", { "aria-label": `Campo para «${e.etiqueta}»`, onchange: (ev) => { IMP.mapeo.campos[tipo][e.clave] = ev.target.value; marcar(); } },
            a.opciones[tipo].map((o) => h("option", { value: o.valor, text: o.texto, selected: IMP.mapeo.campos[tipo][e.clave] === o.valor })));
          const fila = h("tr", {},
            h("td", {}, h("span", { text: e.etiqueta }), e.inicio ? null : h("span", { class: "muted peq", text: " · en mitad de una celda" })),
            h("td", { class: "num", text: String(e.tablas) }),
            h("td", {}, sel));
          function marcar() { fila.classList.toggle("ignorada", sel.value === "ignorar"); }
          marcar();
          return fila;
        }))));
  });
  return h("div", {},
    h("p", { class: "muted", text: "A qué campo va cada etiqueta. «Campo adicional» la conserva con su nombre; «Parte del campo anterior» deja ese párrafo dentro del campo de antes (útil para una «Nota:» en mitad de un texto)." }),
    bloques);
}

/* ---- 4. revisión ---- */
function pasoRevisar() {
  const r = IMP.revision;
  const tipos = Object.entries(r.tipos);
  if (!tipos.length) return h("p", { class: "aviso-panel", text: "Con este mapeo no hay ninguna prueba ni ningún requisito que importar. Vuelve atrás y revisa qué es cada familia." });
  const destino = IMP.modo === "nuevo" ? `en el proyecto nuevo «${IMP.nombre || IMP.analisis.nombre_propuesto}»` : "en el proyecto abierto";
  const partes = tipos.map(([tipo, d]) => plural(d.total, tipo, TIPO_PLURAL[tipo]));
  return h("div", { class: "revision-importar" },
    h("p", { class: "resumen-importar" }, h("strong", { text: `Se importarán ${partes.join(" y ")}` }), ` ${destino}.`),
    tipos.map(([tipo, d]) => h("section", { class: "bloque-mapeo" },
      h("h3", { text: tipo === "prueba" ? "Pruebas" : "Requisitos" }),
      h("p", { class: "muted", text: d.capitulos.map((c) => `${c.nombre} (${c.elementos})`).join(" · ") }),
      tablaIds(tipo, d.ids),
      ejemplosImportar(tipo, d.ejemplos))),
    r.avisos.length ? h("section", { class: "bloque-mapeo" },
      h("h3", { text: "Avisos" }),
      r.avisos.map((g) => h("details", { class: "aviso-grupo g-" + g.gravedad },
        h("summary", {}, h("strong", { text: String(g.total) }), ` ${g.titulo}`),
        h("ul", {}, g.ejemplos.map((e) => h("li", {}, e.donde ? h("span", { class: "muted", text: e.donde + ": " }) : null, e.mensaje)),
          g.total > g.ejemplos.length ? h("li", { class: "muted", text: `y ${g.total - g.ejemplos.length} más` }) : null)))) : null);
}

function tablaIds(tipo, problemas) {
  if (!problemas.length) return h("p", { class: "ok-panel", text: "Todos los IDs son únicos." });
  return h("div", {},
    h("p", { class: "ayuda", text: `${plural(problemas.length, "ID que revisar", "IDs que revisar")}. Se propone el siguiente número libre de la serie; borra la propuesta para conservar el ID (el editor lo marcará como repetido).` }),
    h("table", { class: "tabla-mapeo" },
      h("thead", {}, h("tr", {}, h("th", { text: "ID" }), h("th", { text: "Título" }), h("th", { text: "Problema" }), h("th", { text: "ID nuevo" }))),
      h("tbody", {}, problemas.map((p) => h("tr", {},
        h("td", { class: "mono", text: p.id || "—" }),
        h("td", { text: p.titulo }),
        h("td", { class: "muted", text: p.motivo }),
        h("td", {}, h("input", { type: "text", class: "mono", value: IMP.ids[tipo][String(p.orden)] || "", "aria-label": `ID nuevo para ${p.id || "el elemento sin ID"}`,
          oninput: (e) => { IMP.ids[tipo][String(p.orden)] = e.target.value.trim(); } })))))));
}

function ejemplosImportar(tipo, ejemplos) {
  if (!ejemplos.length) return null;
  let i = 0;
  const caja = h("div", { class: "ejemplo-importar" });
  function pintar() {
    const e = ejemplos[i];
    caja.replaceChildren(
      h("div", { class: "ejemplo-cab" },
        h("strong", { text: `Así queda: ${e.id || "(sin ID)"} · ${e.titulo}` }),
        ejemplos.length > 1 ? h("button", { type: "button", class: "btn ghost peq", text: `Ver otro (${i + 1}/${ejemplos.length})`, onclick: () => { i = (i + 1) % ejemplos.length; pintar(); } }) : null),
      h("dl", {}, e.campos.map(([k, v]) => [h("dt", { text: k }), h("dd", { text: v })])));
  }
  pintar();
  return caja;
}

async function ejecutarImportacion() {
  let carpeta = null;
  if (IMP.modo === "nuevo") {
    aviso(`Elige dónde crear el proyecto (se creará la carpeta «${IMP.nombre || IMP.analisis.nombre_propuesto}»)…`);
    const elegida = await api.importar_elegir_carpeta(IMP.nombre || IMP.analisis.nombre_propuesto);
    if (elegida.cancelado) return;
    carpeta = elegida.carpeta;
  }
  const r = await conEspera("Importando…", () => api.importar_ejecutar(IMP.archivo, IMP.mapeo, IMP.modo, IMP.ids, IMP.nombre, carpeta),
    "Se lee el documento, se copian las imágenes y se escriben los YAML. Con documentos grandes puede tardar unos minutos; no cierres la ventana.");
  if (r.cancelado) return;
  IMP.dlg.close();
  const totales = Object.entries(r.resultado.totales).map(([t, n]) => plural(n, t, TIPO_PLURAL[t])).join(" y ");
  aviso(`Importados ${totales}${r.resultado.avisos ? ` (${plural(r.resultado.avisos, "aviso", "avisos")})` : ""}`);
  const soloRequisitos = !r.resultado.totales.prueba && r.resultado.totales.requisito;
  S.modo = soloRequisitos ? "requisitos" : "edicion";
  guardarLocal("modo", S.modo);
  setDirty(false);
  S.capitulo = 0; S.seleccion = null; S.consulta = ""; $("#buscar").value = "";
  S.colapsadas.clear(); cacheImagenes.clear(); S.capituloPorModo = {};
  aplicarResumen(r.carpeta);
  pintarModo();
  await cargarCobertura();
  await cargarNavegacion();
  mostrarVacio();
  validarEnSegundoPlano();
}
