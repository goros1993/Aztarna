"use strict";
/* Asistente de importación (⋯ → Importar…): documento, familias de tablas
   (u hojas del Excel), campos y revisión. Importa pruebas o requisitos de un
   Word o un Excel (app/importacion.py, app/importacion_excel.py) o los
   resultados de una ejecución (app/importacion_resultados.py); el mapeo
   elegido se recuerda para la próxima vez. */

const PASOS_IMPORTAR = ["Documento", "Tablas", "Campos", "Revisar"];
const TIPO_PLURAL = { prueba: "pruebas", requisito: "requisitos" };
let IMP = null;

function importarDisponible() {
  return true;                 // en el modo Validación, solo resultados
}

const esResultados = () => IMP && IMP.preferido === "resultado";
const esExcel = () => IMP && /\.(xlsx|xlsm)$/i.test(IMP.archivo || "");

async function asistenteImportar() {
  if (!(await guardia())) return;
  setDirty(false);
  IMP = { paso: 0, archivo: "", preferido: S.modo === "ejecucion" ? "resultado" : enRequisitos() ? "requisito" : "prueba", modo: "nuevo", nombre: "",
    analisis: null, mapeo: null, revision: null, ids: {} };
  const dlg = h("dialog", { class: "ancho asistente", "aria-label": "Importar desde Word o Excel" });
  dlg.addEventListener("close", () => { dlg.remove(); if (IMP && IMP.dlg === dlg) IMP = null; });
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
      : esResultados()
        ? boton(IMP.enValidacion ? "Crear la ejecución" : "Elegir carpeta y crear la ejecución…", "primary", () => ejecutarImportacionResultados().catch(fallo),
          { disabled: !IMP.revision || !IMP.revision.pruebas })
        : boton(IMP.modo === "nuevo" ? "Elegir carpeta e importar…" : "Importar", "primary", () => ejecutarImportacion().catch(fallo),
          { disabled: !IMP.revision || !Object.keys(IMP.revision.tipos).length }));
  IMP.dlg.replaceChildren(
    h("div", { class: "dlg-cab" }, esExcel() ? "Importar desde Excel" : "Importar desde Word o Excel", pasos),
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
    if (!tiposElegidos().length) {
      aviso(esResultados() ? "Ninguna familia tiene resultados: no hay nada que importar"
        : esExcel() ? "Ninguna hoja es de pruebas ni de requisitos: no hay nada que importar"
          : "Ninguna familia es de pruebas ni de requisitos: no hay nada que importar", "error");
      return;
    }

  } else if (IMP.paso === 2 && esResultados()) {
    if (!Object.values(IMP.mapeo.campos.resultado).includes("estado")) { aviso("Elige qué etiqueta tiene el resultado (va a «Resultado»)", "error"); return; }
    IMP.revision = await conEspera("Leyendo los resultados…", () => api.importar_resultados_revisar(IMP.archivo, IMP.mapeo), "Con documentos grandes puede tardar unos minutos; no cierres la ventana.");
    IMP.ejecucion = IMP.ejecucion || { nombre: IMP.analisis.nombre_propuesto, entorno_pruebas: "", entorno: "", objeto: "", responsable: leerLocal("ejecutor") || "" };
    IMP.enValidacion = Boolean(S.validacion);
  } else if (IMP.paso === 2) {
    if (esExcel()) {
      const sinId = tiposElegidos().filter((t) => !Object.values(IMP.mapeo.campos[t]).some((v) => v === "id" || v === "titulo"));
      if (sinId.length) { aviso(`Elige qué columna es el ID (o el título) de ${sinId.map((t) => (t === "prueba" ? "las pruebas" : "los requisitos")).join(" y de ")}: cada fila con ID o título empieza uno nuevo`, "error"); return; }
    }
    IMP.revision = await conEspera("Preparando la vista previa…", () => api.importar_revisar(IMP.archivo, IMP.mapeo, IMP.modo), "Se lee todo el documento con el mapeo elegido. Con documentos grandes puede tardar unos minutos; no cierres la ventana.");
    IMP.ids = {};
    IMP.acciones = {};
    for (const [tipo, datos] of Object.entries(IMP.revision.tipos)) {
      IMP.ids[tipo] = Object.fromEntries([...datos.ids, ...datos.existentes].filter((p) => p.propuesta).map((p) => [String(p.orden), p.propuesta]));
      // Los que cambian se actualizan; los que están igual, no se tocan.
      IMP.acciones[tipo] = Object.fromEntries(datos.existentes.map((c) => [String(c.orden), c.cambios.length ? "actualizar" : "omitir"]));
    }
  }
  IMP.paso += 1;
  pintarAsistente();
}

function tiposElegidos() {
  const tipos = new Set(IMP.analisis.familias.map((f) => IMP.mapeo.tipos[f.firma]));
  return ["prueba", "requisito", "resultado"].filter((t) => tipos.has(t));
}

/* ---- 1. documento ---- */
function pasoDocumento() {
  const radio = (nombre, valor, texto, actual, alCambiar, deshabilitado = false) => h("label", { class: "opcion-radio" + (deshabilitado ? " deshabilitada" : "") },
    h("input", { type: "radio", name: nombre, value: valor, checked: actual === valor, disabled: deshabilitado, onchange: () => alCambiar(valor) }),
    h("span", {}, texto));
  const abierto = S.carpeta && !S.soloLectura ? S.carpeta : null;
  if (!abierto && IMP.modo === "anadir") IMP.modo = "nuevo";
  const soloResultados = S.modo === "ejecucion";
  const elegirTipo = (v) => { IMP.preferido = v || null; pintarAsistente(); };
  const nombre = h("input", { type: "text", id: "imp-nombre", value: IMP.nombre, placeholder: "Nombre de la carpeta del proyecto",
    disabled: IMP.modo !== "nuevo", oninput: (e) => { IMP.nombre = e.target.value; } });
  return h("div", { class: "asistente-documento" },
    h("p", { class: "muted", text: "De un Word, el editor busca las tablas, las agrupa por sus etiquetas («Descripción:», «Pasos:»…) y te deja decidir a qué campo va cada una. De un Excel, cada hoja es un grupo y cada fila, una prueba o un requisito; eliges a qué campo va cada columna. No cambia nada hasta el último paso." }),
    h("div", { class: "campo" },
      h("label", { text: "Documento de Word o Excel" }),
      h("div", { class: "fila-archivo" },
        h("button", { type: "button", class: "btn", onclick: async () => {
          try {
            const r = await api.importar_elegir_documento();
            if (r.cancelado) return;
            if (r.archivo !== IMP.archivo) {
              IMP.archivo = r.archivo;
              IMP.nombre = r.archivo.split(/[\\/]/).pop().replace(/\.(docx|xlsx|xlsm)$/i, "").replace(/\s+/g, "_");
              IMP.analisis = null;
            }
            pintarAsistente();
          } catch (e) { fallo(e); }
        } }, icon("import"), IMP.archivo ? "Cambiar…" : "Elegir documento…"),
        h("span", { class: "ruta-archivo", text: IMP.archivo || "Ningún documento elegido", title: IMP.archivo || "" })),
      soloResultados ? null : h("p", { class: "ayuda" }, "¿Vais a escribir las pruebas en Excel? ",
        h("button", { type: "button", class: "enlace", text: "Descarga una plantilla", onclick: () => descargarPlantillaExcel(IMP.preferido === "requisito" ? "requisito" : "prueba") }),
        " con una columna por campo: se importa sin tener que elegir nada.")),
    h("fieldset", { class: "grupo-radio" },
      h("legend", { text: "¿Qué contiene?" }),
      radio("imp-tipo", "prueba", "Pruebas", IMP.preferido, elegirTipo, soloResultados),
      radio("imp-tipo", "requisito", "Requisitos", IMP.preferido, elegirTipo, soloResultados),
      radio("imp-tipo", "", "Lo decide el editor (pruebas y requisitos en el mismo documento)", IMP.preferido || "", elegirTipo, soloResultados),
      radio("imp-tipo", "resultado", "Resultados de una ejecución (las pruebas ya están en el proyecto)", IMP.preferido, elegirTipo, !S.carpeta),
      h("p", { class: "ayuda", text: soloResultados
        ? "En el modo Validación solo se importan resultados; para importar pruebas o requisitos, cambia al modo Pruebas o Requisitos."
        : "Solo sirve para proponer; en el siguiente paso eliges qué es cada grupo de tablas." })),
    esResultados() ? h("p", { class: "ayuda", text: "Los resultados se enlazan con las pruebas del proyecto por el ID de la cabecera de cada tabla. Se crea una ejecución nueva con esas pruebas"
      + (S.validacion ? `, que puedes añadir a la validación «${S.validacion.datos.nombre}».` : ".") + " Su nombre y su entorno de pruebas se eligen en el último paso." }) :
    h("fieldset", { class: "grupo-radio" },
      h("legend", { text: "¿Dónde se importa?" }),
      radio("imp-modo", "nuevo", "En un proyecto nuevo", IMP.modo, (v) => { IMP.modo = v; nombre.disabled = false; }),
      h("div", { class: "campo sangrado" }, nombre),
      radio("imp-modo", "anadir", abierto ? `Añadirlo al proyecto abierto (${abierto})` : "Añadirlo al proyecto abierto (no hay ninguno)", IMP.modo,
        (v) => { IMP.modo = v; nombre.disabled = true; }, !abierto),
      h("p", { class: "ayuda", text: "Al añadir, lo de cada capítulo va al capítulo del proyecto con el mismo nombre, en su sección (si no existe, se crea al final del índice). Lo que ya existe con el mismo ID se puede actualizar o dejar como está: así se puede importar poco a poco." })));
}

async function descargarPlantillaExcel(tipo) {
  try {
    const r = await api.importar_plantilla_excel(tipo);
    if (r.cancelado) return;
    aviso(`Plantilla guardada: ${r.archivo}`, "ok");
  } catch (e) { fallo(e); }
}

/* ---- 2. familias de tablas ---- */
function pasoTablas() {
  const a = IMP.analisis;
  const tarjetas = a.familias.map((f) => {
    const sel = h("select", { "aria-label": `Qué es la familia ${f.numero}`, onchange: (e) => { IMP.mapeo.tipos[f.firma] = e.target.value; } },
      a.tipos.map((t) => h("option", { value: t.valor, text: t.texto, selected: IMP.mapeo.tipos[f.firma] === t.valor })));
    const etiquetas = f.etiquetas.filter((e) => e.inicio);
    const visibles = etiquetas.slice(0, 14);
    if (f.hoja !== undefined) {               // Excel: una hoja
      return h("li", { class: "familia" },
        h("div", { class: "familia-cab" },
          h("strong", { text: `Hoja «${f.hoja}»` }),
          h("span", { class: "muted", text: plural(f.tablas, "fila", "filas") }),
          h("span", { class: "hueco" }),
          sel),
        f.tablas ? h("p", { class: "familia-ejemplos", text: "Por ejemplo: " + f.ejemplos.join(" · ") }) : null,
        etiquetas.length
          ? h("div", { class: "fichas-etiquetas" }, visibles.map((e) => h("span", { class: "ficha", text: e.etiqueta, title: `Con valor en ${plural(e.tablas, "fila", "filas")}` })),
            etiquetas.length > visibles.length ? h("span", { class: "muted", text: `y ${etiquetas.length - visibles.length} más` }) : null)
          : h("p", { class: "muted", text: "No se encuentra la fila de cabecera (la primera con dos celdas o más)." }),
        f.imagenes ? h("p", { class: "ayuda", text: `${plural(f.imagenes, "imagen", "imágenes")} en la hoja: no se importan; añádelas después en el editor.` }) : null);
    }
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
    h("p", { class: "muted", text: esExcel()
      ? `${plural(a.familias.length, "hoja", "hojas")} con ${plural(a.tablas, "fila", "filas")}. Elige qué hay en cada una; las de notas o datos, «No importar».`
      : `${plural(a.tablas, "tabla", "tablas")} en ${plural(a.familias.length, "familia", "familias")}. Una familia son las tablas con las mismas etiquetas (o casi). Elige qué es cada una: las «tablas informativas» se conservan tal cual, en el texto de su sección.` }),
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
    // Primero las que se importan (en resultados, casi todas las etiquetas son de la prueba y no interesan).
    const importa = (e) => (tipo === "resultado" && ["ignorar", "anterior"].includes(IMP.mapeo.campos[tipo][e.clave]) ? 0 : 1);
    const filas = [...etiquetas.values()].sort((x, y) => (importa(y) - importa(x)) || (y.inicio - x.inicio) || (y.tablas - x.tablas));
    const valores = tipo === "resultado" ? bloqueValores(etiquetas) : null;
    return h("section", { class: "bloque-mapeo" },
      h("h3", { text: { prueba: "Pruebas", requisito: "Requisitos", resultado: "Resultados" }[tipo] }),
      h("p", { class: "ayuda", text: tipo === "resultado"
        ? "La primera celda de la cabecera es el ID de la prueba: así se enlaza cada resultado. Las etiquetas de la propia prueba (descripción, pasos…) no se importan."
        : esExcel()
          ? "Cada fila con ID o título es una nueva; una fila sin ellos continúa la de arriba (por ejemplo, un paso por fila). «Capítulo» y «Sección» ordenan las filas (sin «Capítulo», el capítulo es el nombre de la hoja; «A > B» es la subsección B de A). En las columnas de lista, cada línea de la celda es un elemento."
          : "Cabecera de la tabla: la primera celda es el ID y la segunda, el título." }),
      h("table", { class: "tabla-mapeo" },
        h("thead", {}, h("tr", {}, h("th", { text: esExcel() ? "Columna del Excel" : "Etiqueta en el Word" }), h("th", { text: esExcel() ? "Filas" : "Tablas" }), h("th", { text: "Va a" }))),
        h("tbody", {}, filas.map((e) => {
          const sel = h("select", { "aria-label": `Campo para «${e.etiqueta}»`, onchange: (ev) => {
            IMP.mapeo.campos[tipo][e.clave] = ev.target.value;
            marcar();
            if (valores) valores.repintar();
          } },
            a.opciones[tipo].map((o) => h("option", { value: o.valor, text: o.texto, selected: IMP.mapeo.campos[tipo][e.clave] === o.valor })));
          const fila = h("tr", {},
            h("td", {}, h("span", { text: e.etiqueta }), e.inicio ? null : h("span", { class: "muted peq", text: " · en mitad de una celda" })),
            h("td", { class: "num", text: String(e.tablas) }),
            h("td", {}, sel));
          function marcar() { fila.classList.toggle("ignorada", sel.value === "ignorar"); }
          marcar();
          return fila;
        }))),
      valores);
  });
  return h("div", {},
    h("p", { class: "muted", text: esExcel()
      ? "A qué campo va cada columna. «Campo adicional» la conserva con su nombre; «No importar» la deja fuera."
      : "A qué campo va cada etiqueta. «Campo adicional» la conserva con su nombre; «Parte del campo anterior» deja ese párrafo dentro del campo de antes (útil para una «Nota:» en mitad de un texto)." }),
    bloques);
}

/** Resultados: qué estado es cada valor escrito en el Word en las etiquetas que van a «Resultado». */
function bloqueValores(etiquetas) {
  const caja = h("div", { class: "valores-resultado" });
  caja.repintar = () => {
    const valores = new Map();
    for (const e of etiquetas.values()) {
      if (IMP.mapeo.campos.resultado[e.clave] !== "estado") continue;
      for (const v of e.valores || []) {
        const previo = valores.get(v.clave);
        if (previo) previo.tablas += v.tablas; else valores.set(v.clave, { ...v });
      }
    }
    if (!valores.size) {
      caja.replaceChildren(h("p", { class: "aviso-panel", text: "Ninguna etiqueta va a «Resultado»: elige cuál tiene el resultado de la prueba." }));
      return;
    }
    caja.replaceChildren(
      h("h3", { text: "Qué resultado es cada valor" }),
      h("p", { class: "ayuda", text: "Los valores escritos en el Word en las etiquetas que van a «Resultado». Un texto que no es ningún resultado (por ejemplo, una descripción de lo observado) queda pendiente y se guarda en las observaciones." }),
      h("table", { class: "tabla-mapeo" },
        h("thead", {}, h("tr", {}, h("th", { text: "Valor en el Word" }), h("th", { text: "Tablas" }), h("th", { text: "Resultado" }))),
        h("tbody", {}, [...valores.values()].sort((x, y) => y.tablas - x.tablas).map((v) => h("tr", {},
          h("td", { class: v.valor ? "" : "muted", text: v.valor || "(vacío)" }),
          h("td", { class: "num", text: String(v.tablas) }),
          h("td", {}, h("select", { "aria-label": `Resultado para «${v.valor || "vacío"}»`, onchange: (e) => {
            if (e.target.value) IMP.mapeo.valores[v.clave] = e.target.value; else delete IMP.mapeo.valores[v.clave];
          } },
          h("option", { value: "", text: "(no es un resultado)", selected: !IMP.mapeo.valores[v.clave] }),
          IMP.analisis.estados.map((o) => h("option", { value: o.valor, text: o.texto, selected: IMP.mapeo.valores[v.clave] === o.valor })))))))));
  };
  caja.repintar();
  return caja;
}

function bloqueAvisos(avisos) {
  return avisos.length ? h("section", { class: "bloque-mapeo" },
    h("h3", { text: "Avisos" }),
    avisos.map((g) => h("details", { class: "aviso-grupo g-" + g.gravedad },
      h("summary", {}, h("strong", { text: String(g.total) }), ` ${g.titulo}`),
      h("ul", {}, g.ejemplos.map((e) => h("li", {}, e.donde ? h("span", { class: "muted", text: e.donde + ": " }) : null, e.mensaje)),
        g.total > g.ejemplos.length ? h("li", { class: "muted", text: `y ${g.total - g.ejemplos.length} más` }) : null)))) : null;
}

/* ---- 4. revisión ---- */
function pasoRevisar() {
  if (esResultados()) return pasoRevisarResultados();
  const r = IMP.revision;
  const tipos = Object.entries(r.tipos);
  if (!tipos.length) return h("p", { class: "aviso-panel", text: "Con este mapeo no hay ninguna prueba ni ningún requisito que importar. Vuelve atrás y revisa qué es cada familia." });
  const destino = IMP.modo === "nuevo" ? `en el proyecto nuevo «${IMP.nombre || IMP.analisis.nombre_propuesto}»` : "en el proyecto abierto";
  const resumen = h("p", { class: "resumen-importar" });
  const pintarResumen = () => {
    const partes = tipos.map(([tipo, d]) => {
      const acciones = Object.values(IMP.acciones[tipo] || {});
      const cuenta = (a) => acciones.filter((x) => x === a).length;
      const nuevos = d.total - cuenta("actualizar") - cuenta("omitir");
      const a = tipo === "prueba" ? "a" : "o";
      return [nuevos ? plural(nuevos, `${tipo} nuev${a}`, `${TIPO_PLURAL[tipo]} nuev${a}s`) : "",
        cuenta("actualizar") ? plural(cuenta("actualizar"), `actualizad${a}`, `actualizad${a}s`) : "",
        cuenta("omitir") ? `${cuenta("omitir")} sin tocar` : ""].filter(Boolean).join(", ");
    });
    resumen.replaceChildren(h("strong", { text: partes.join(" · ") }), ` ${destino}.`);
  };
  pintarResumen();
  return h("div", { class: "revision-importar" },
    resumen,
    tipos.map(([tipo, d]) => h("section", { class: "bloque-mapeo" },
      h("h3", { text: tipo === "prueba" ? "Pruebas" : "Requisitos" }),
      h("p", { class: "muted", text: d.capitulos.map((c) => `${c.nombre} (${c.elementos}${c.existente ? ", se añade al capítulo que ya existe" : IMP.modo === "anadir" ? ", capítulo nuevo" : ""})`).join(" · ") }),
      tablaExistentes(tipo, d.existentes, pintarResumen),
      tablaIds(tipo, d.ids),
      ejemplosImportar(tipo, d.ejemplos))),
    bloqueAvisos(r.avisos));
}

/** Resultados: cifras, avisos, un ejemplo y los datos de la ejecución que se va a crear. */
function pasoRevisarResultados() {
  const r = IMP.revision;
  const e = IMP.ejecucion;
  if (!r.pruebas) return h("p", { class: "aviso-panel", text: "Ninguna tabla con resultados corresponde a una prueba del proyecto. Revisa los avisos, o vuelve atrás y revisa el mapeo." });
  const campo = (id, etiqueta, clave, ayuda = "") => h("div", { class: "campo" },
    h("label", { for: id, text: etiqueta }),
    h("input", { id, type: "text", autocomplete: "off", value: e[clave] || "", placeholder: ayuda, oninput: (ev) => { e[clave] = ev.target.value; } }));
  const cifras = ["ok", "no_ok", "bloqueada", "no_aplica"].filter((s) => r.por_estado[s]).map((s) => `${r.por_estado[s]} ${ESTADO_TXT[s]}`);
  return h("div", { class: "revision-importar" },
    h("p", { class: "resumen-importar" },
      h("strong", { text: `${plural(r.pruebas, "prueba", "pruebas")} del proyecto con resultado en el Word` }),
      cifras.length ? `: ${cifras.join(", ")}.` : "."),
    r.por_estado.pendiente ? h("p", { class: "ayuda", text: `${plural(r.por_estado.pendiente, "queda sin resultado", "quedan sin resultado")}: estarán pendientes en la ejecución.` }) : null,
    h("section", { class: "bloque-mapeo" },
      h("h3", { text: "La ejecución" }),
      h("div", { class: "rejilla" },
        Object.assign(campo("imp-ej-nombre", "Nombre *", "nombre", "Regresión v2.3 en Torre"), { className: "campo completo" }),
        selectorEntorno("imp-ej-entorno", e.entorno_pruebas, (_a, nuevo) => { e.entorno_pruebas = nuevo; }),
        campo("imp-ej-objeto", "Qué se prueba", "objeto", "Firmware 2.3.0"),
        campo("imp-ej-banco", "Banco / instalación", "entorno"),
        campo("imp-ej-responsable", "Responsable", "responsable")),
      S.validacion ? h("label", { class: "opcion-radio" },
        h("input", { type: "checkbox", checked: IMP.enValidacion, onchange: (ev) => { IMP.enValidacion = ev.target.checked; pintarAsistente(); } }),
        h("span", { text: `Añadirla a la validación «${S.validacion.datos.nombre}» (se crea dentro de su carpeta)` })) : null,
      h("p", { class: "ayuda", text: "Queda abierta: puedes revisar los resultados, completar las pendientes y cerrarla después." })),
    ejemplosImportar("resultado", r.ejemplos),
    bloqueAvisos(r.avisos));
}

async function ejecutarImportacionResultados() {
  const e = IMP.ejecucion;
  if (!e.nombre.trim()) { aviso("La ejecución necesita un nombre", "error"); return; }
  if (!e.entorno_pruebas) { aviso("Indica en qué entorno de pruebas se ejecutó", "error"); return; }
  let carpeta = null;
  if (!(IMP.enValidacion && S.validacion)) {
    aviso("Elige dónde guardar la ejecución (se creará una subcarpeta)…");
    const elegida = await api.importar_elegir_carpeta(e.nombre, true);
    if (elegida.cancelado) return;
    carpeta = elegida.carpeta;
  }
  const datos = { entorno_pruebas: e.entorno_pruebas, entorno: e.entorno, objeto: e.objeto, responsable: e.responsable };
  const r = await conEspera("Creando la ejecución con los resultados…",
    () => api.importar_resultados_ejecutar(IMP.archivo, IMP.mapeo, e.nombre, datos, Boolean(IMP.enValidacion && S.validacion), carpeta));
  IMP.dlg.close();
  if (e.responsable) guardarLocal("ejecutor", e.responsable);
  if (S.modo !== "ejecucion") {
    S.modo = "ejecucion";
    guardarLocal("modo", "ejecucion");
    aplicarResumen(await api.coleccion("pruebas"));
  }
  await usarEjecucion(r.ejecucion);
  if (S.validacion) await refrescarValidacion();
  aviso(`Ejecución creada: ${plural(r.pruebas, "prueba", "pruebas")}, ${r.con_resultado} con resultado`, "ok");
}

const ACCIONES_EXISTENTES = [
  { valor: "actualizar", texto: "Actualizar el del proyecto" },
  { valor: "nuevo", texto: "Importar como nuevo (otro ID)" },
  { valor: "omitir", texto: "No importar" },
];

/** Los que ya existen en el proyecto: qué cambia y qué hacer con cada uno. */
function tablaExistentes(tipo, existentes, alCambiar) {
  if (!existentes.length) return null;
  const acciones = IMP.acciones[tipo];
  const filas = existentes.map((c) => {
    const id = h("input", { type: "text", class: "mono", value: IMP.ids[tipo][String(c.orden)] || "", "aria-label": `ID nuevo para ${c.id}`,
      oninput: (e) => { IMP.ids[tipo][String(c.orden)] = e.target.value.trim(); } });
    const sel = h("select", { "aria-label": `Qué hacer con ${c.id}`, onchange: (e) => poner(e.target.value) },
      ACCIONES_EXISTENTES.map((a) => h("option", { value: a.valor, text: a.texto, selected: acciones[String(c.orden)] === a.valor })));
    function poner(valor) {
      acciones[String(c.orden)] = valor;
      sel.value = valor;
      id.disabled = valor !== "nuevo";
      alCambiar();
    }
    id.disabled = acciones[String(c.orden)] !== "nuevo";
    const fila = h("tr", {},
      h("td", { class: "mono", text: c.id }),
      h("td", {}, h("span", { text: c.titulo }), h("br"), h("span", { class: "muted peq", text: `en ${c.capitulo}` })),
      h("td", { class: c.cambios.length ? "" : "muted", text: c.cambios.length ? c.cambios.join(", ") : "Sin cambios" }),
      h("td", {}, sel),
      h("td", {}, id));
    fila.poner = poner;
    return fila;
  });
  const todos = h("select", { "aria-label": "Qué hacer con todos", onchange: (e) => {
    if (!e.target.value) return;
    filas.forEach((f) => f.poner(e.target.value));
    e.target.value = "";
  } }, h("option", { value: "", text: "Para todos…" }), ACCIONES_EXISTENTES.map((a) => h("option", { value: a.valor, text: a.texto })));
  return h("div", { class: "existentes" },
    h("div", { class: "existentes-cab" },
      h("strong", { text: `${plural(existentes.length, "ya existe", "ya existen")} en el proyecto` }), todos),
    h("p", { class: "ayuda", text: (esExcel()
      ? "Actualizar cambia los campos que tienen columna en el Excel (los demás se conservan, y sus campos adicionales se añaden a los que ya tenía) y conserva su sitio en el árbol. "
      : "Actualizar cambia sus campos por los del Word y conserva su sitio en el árbol. ")
      + (tipo === "requisito" ? "Si un requisito actualizado tiene pruebas, quedará marcado para revisarlas. " : "")
      + "Por defecto se actualizan los que cambian y no se tocan los que están igual." }),
    h("table", { class: "tabla-mapeo" },
      h("thead", {}, h("tr", {}, h("th", { text: "ID" }), h("th", { text: "Título" }), h("th", { text: "Qué cambia" }), h("th", { text: "Qué hacer" }), h("th", { text: "ID nuevo" }))),
      h("tbody", {}, filas)));
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
  const r = await conEspera("Importando…", () => api.importar_ejecutar(IMP.archivo, IMP.mapeo, IMP.modo, IMP.ids, IMP.nombre, carpeta, IMP.acciones),
    "Se lee el documento, se copian las imágenes y se escriben los YAML. Con documentos grandes puede tardar unos minutos; no cierres la ventana.");
  if (r.cancelado) return;
  IMP.dlg.close();
  const res = r.resultado;
  const hechos = ["prueba", "requisito"].map((t) => [
    res.totales[t] ? plural(res.totales[t], `${t} importad${t === "prueba" ? "a" : "o"}`, `${TIPO_PLURAL[t]} importad${t === "prueba" ? "a" : "o"}s`) : "",
    res.actualizados[t] ? plural(res.actualizados[t], `${t} actualizad${t === "prueba" ? "a" : "o"}`, `${TIPO_PLURAL[t]} actualizad${t === "prueba" ? "a" : "o"}s`) : ""].filter(Boolean).join(", ")).filter(Boolean);
  aviso(`${hechos.join(" · ")}${res.avisos ? ` (${plural(res.avisos, "aviso", "avisos")})` : ""}`, "ok");
  const soloRequisitos = !res.totales.prueba && !res.actualizados.prueba && (res.totales.requisito || res.actualizados.requisito);
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
