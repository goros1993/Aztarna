"use strict";
/* Formularios de pruebas y secciones, editores de lista, imágenes y vista YAML. */

const CAMPOS_TEXTO = ["nombre", "id", "titulo", "descripcion", "componente", "plataforma",
  "automatizable", "criticidad", "entorno", "referencia", "fecha", "version"];
const LISTAS = ["contexto", "situacion_inicial", "pasos", "situacion_final"];
const AUTOMATIZABLE = ["", "si", "no", "corto", "medio", "largo", "hecho"];

/** Formulario abierto: {modo: "editar"|"nueva", tipo: "prueba"|"seccion", indice, valores, cambios, nivel, vista}. */
let F = null;
const formularioActual = () => F;

const principal = () => $("#principal");
function mostrar(nodo) { principal().replaceChildren(nodo); principal().scrollTop = 0; }

/* ---- pantallas sin formulario ---- */
function mostrarSinCarpeta() {
  F = null;
  mostrar(h("div", { class: "centro" },
    h("h2", { text: "Abre una carpeta de YAML" }),
    h("p", { text: "Elige la carpeta que contiene indice.yaml y los capítulos de pruebas." }),
    h("div", { class: "fila-botones" },
      h("button", { class: "btn primary", type: "button", onclick: elegirCarpeta, text: "Abrir carpeta" }))));
}

function mostrarVacio() {
  F = null;
  if (S.modo === "ejecucion") { mostrarPanelCampana(); return; }
  mostrar(h("div", { class: "centro" },
    h("h2", { text: "Elige qué editar" }),
    h("p", { text: "Selecciona una prueba o una sección en el panel izquierdo, o crea una nueva." }),
    h("div", { class: "fila-botones" },
      h("button", { class: "btn primary", type: "button", onclick: () => nuevaPrueba(), text: "Nueva prueba" }),
      h("button", { class: "btn", type: "button", onclick: () => nuevaSeccion(), text: "Nueva sección" }))));
}

/* ---- conversión entre datos YAML y filas editables ---- */
const aLista = (x) => (Array.isArray(x) ? x : x === null || x === undefined || x === "" ? [] : [x]);

function filaDesde(item) {
  if (item && typeof item === "object" && !Array.isArray(item)) {
    const { texto, imagenes, imagen, nivel, ...extra } = item;
    return {
      texto: texto === null || texto === undefined ? "" : String(texto),
      imagenes: [...aLista(imagenes).map(String), ...(imagen ? [String(imagen)] : [])],
      nivel: Math.min(Math.max(Number(nivel) || 0, 0), 4),
      forma: "map", extra,
    };
  }
  return { texto: item === null || item === undefined ? "" : String(item), imagenes: [], nivel: 0, forma: "str", extra: {} };
}

function filasAPlano(filas) {
  return filas.map((f) => {
    const mapa = f.forma === "map" || f.imagenes.length || f.nivel || Object.keys(f.extra).length;
    if (!mapa) return f.texto;
    const o = { texto: f.texto };
    if (f.nivel) o.nivel = f.nivel;
    if (f.imagenes.length) o.imagenes = [...f.imagenes];
    return Object.assign(o, f.extra);
  });
}

function extrasDesde(obj) {
  if (!obj || typeof obj !== "object" || Array.isArray(obj)) return [];
  return Object.entries(obj).map(([clave, v]) => {
    if (v === null || v === undefined) return { clave, valor: "", tipo: "texto", orig: v };
    if (typeof v === "object") {
      if (Array.isArray(v) && v.every((x) => x === null || typeof x !== "object")) {
        return { clave, valor: v.join("\n"), tipo: "lista", orig: v };
      }
      return { clave, valor: JSON.stringify(v, null, 2), tipo: "complejo", orig: v };
    }
    return { clave, valor: String(v), tipo: "texto", orig: v };
  });
}

function extrasAPlano(filas) {
  const salida = {};
  for (const f of filas) {
    const clave = f.clave.trim();
    if (!clave) continue;
    if (f.tipo === "complejo") salida[clave] = f.orig;
    else if (f.tipo === "lista") {
      const lineas = f.valor.split("\n").map((l) => l.trim()).filter(Boolean);
      const igual = Array.isArray(f.orig) && lineas.length === f.orig.length && lineas.every((l, i) => l === String(f.orig[i]));
      salida[clave] = igual ? f.orig : lineas;
    } else {
      salida[clave] = f.orig !== undefined && String(f.orig ?? "") === f.valor ? f.orig : f.valor;
    }
  }
  return salida;
}

function valoresDePrueba(el = {}) {
  const v = {};
  for (const k of CAMPOS_TEXTO) v[k] = el[k] === null || el[k] === undefined ? "" : String(el[k]);
  for (const k of LISTAS) v[k] = aLista(el[k]).map(filaDesde);
  v.campos_adicionales = extrasDesde(el.campos_adicionales);
  v.imagenes = aLista(el.imagenes).map(String);
  v.etiquetas = aLista(el.etiquetas).map(String);
  return v;
}

function serializar(clave) {
  const v = F.valores[clave];
  if (LISTAS.includes(clave)) return filasAPlano(v);
  if (clave === "campos_adicionales") return extrasAPlano(v);
  if (clave === "imagenes" || clave === "etiquetas") return [...v];
  return v;
}

function recogerCambios() {
  const claves = F.modo === "nueva" && F.tipo === "prueba"
    ? [...CAMPOS_TEXTO, ...LISTAS, "campos_adicionales", "imagenes", "etiquetas"]
    : [...F.cambios];
  return Object.fromEntries(claves.map((k) => [k, serializar(k)]));
}

function tocar(clave) {
  if (F) F.cambios.add(clave);
  setDirty(true);
}

/* ---- cabecera con la placa del ID ---- */
function textoPlaca() {
  if (F.tipo === "seccion") return "Sección";
  return F.valores.id || (F.modo === "nueva" ? "Nueva prueba" : "Sin ID");
}

function nombreCabecera() {
  if (F.tipo === "seccion") return F.valores.nombre || (F.modo === "nueva" ? "Nueva sección" : "(sin nombre)");
  return F.valores.titulo || F.valores.nombre || (F.modo === "nueva" ? "Prueba sin título" : "(sin título)");
}

function rutaDe(indice) {
  const nombres = [];
  const capitulo = S.capitulos[S.capitulo];
  if (capitulo) nombres.push(capitulo.nombre);
  const cadena = [];
  let actual = S.nodos.find((n) => n.indice === indice);
  while (actual && actual.padre !== null && actual.padre !== undefined) {
    actual = S.nodos.find((n) => n.indice === actual.padre);
    if (actual) cadena.unshift(actual.titulo);
  }
  return [...nombres, ...cadena].join("  ›  ");
}

function actualizarCabecera() {
  const placa = $("#placa-texto"); if (placa) placa.textContent = textoPlaca();
  const nombre = $("#cab-nombre"); if (nombre) nombre.textContent = nombreCabecera();
  const nivel = $("#placa-nivel"); if (nivel) nivel.textContent = String(F.nivel);
}

function botonIcono(nombre, etiqueta, fn, extra = "") {
  return h("button", { class: "btn icono " + extra, type: "button", title: etiqueta, "aria-label": etiqueta, onclick: fn }, icon(nombre));
}

function cabecera() {
  const esPrueba = F.tipo === "prueba";
  const editando = F.modo === "editar";
  const bloqueTitulo = h("div", { class: "titulo" },
    h("span", { class: "nombre", id: "cab-nombre", text: nombreCabecera() }),
    h("span", { class: "ruta", text: editando ? rutaDe(F.indice) : "Todavía sin guardar" }));
  const placa = h("div", { class: "placa" + (esPrueba ? "" : " seccion") },
    h("span", { class: "texto-placa", id: "placa-texto", text: textoPlaca() }),
    h("span", { class: "nivel", id: "placa-nivel", title: "Nivel de encabezado", text: String(F.nivel) }));
  const sinGuardar = h("span", { class: "sin-guardar", id: "cab-sin-guardar", hidden: !S.dirty, text: "Sin guardar" });
  const botones = [];
  if (editando) {
    botones.push(h("div", { class: "seg", role: "group", "aria-label": "Vista" },
      h("button", { type: "button", "aria-pressed": String(F.vista !== "yaml"), onclick: () => cambiarVista("form"), text: "Formulario" }),
      h("button", { type: "button", "aria-pressed": String(F.vista === "yaml"), onclick: () => cambiarVista("yaml"), text: "YAML" })));
    if (esPrueba && F.vista !== "yaml") {
      botones.push(h("button", { class: "btn ghost", type: "button", onclick: duplicarActual, title: "Crear una prueba nueva con estos datos" }, icon("copy"), "Duplicar"));
    }
    botones.push(h("button", { class: "btn ghost peligro", type: "button", onclick: borrarActual }, icon("trash"), "Borrar"));
    if (F.vista === "yaml") {
      botones.push(h("button", { class: "btn ghost", type: "button", onclick: () => cambiarVista("form", true), text: "Descartar" }));
      botones.push(h("button", { class: "btn primary", type: "button", onclick: guardarActual, text: "Aplicar YAML" }));
    } else {
      botones.push(h("button", { class: "btn primary", type: "button", onclick: guardarActual, title: "Ctrl+S", text: "Guardar" }));
    }
  } else {
    botones.push(h("button", { class: "btn ghost", type: "button", onclick: cancelarNueva, text: "Cancelar" }));
    botones.push(h("button", { class: "btn primary", type: "button", onclick: guardarActual, title: "Ctrl+S", text: esPrueba ? "Crear prueba" : "Crear sección" }));
  }
  return h("div", { class: "acciones" }, placa, bloqueTitulo, sinGuardar, botones);
}

/* ---- campos de texto ---- */
function campoTexto(clave, etiqueta, { ancho = false, completo = false, mono = false } = {}) {
  const id = "f-" + clave;
  const input = h("input", {
    id, type: "text", class: mono ? "mono" : "", value: F.valores[clave], autocomplete: "off",
    spellcheck: mono ? "false" : "true",
    oninput: (e) => {
      F.valores[clave] = e.target.value;
      tocar(clave);
      quitarErrorCampo(clave);
      if (clave === "id" || clave === "titulo" || clave === "nombre") actualizarCabecera();
    },
  });
  return h("div", { class: "campo" + (ancho ? " ancho" : "") + (completo ? " completo" : "") },
    h("label", { for: id, text: etiqueta }), input);
}

/** Etiquetas como fichas: Enter o coma añade, Retroceso en vacío quita la última. */
function campoEtiquetas() {
  const etiquetas = F.valores.etiquetas;
  const fichas = h("div", { class: "fichas" });
  const sugerencias = h("datalist", { id: "sugerencias-etiquetas" });
  const entrada = h("input", {
    id: "f-etiquetas", type: "text", autocomplete: "off", list: "sugerencias-etiquetas",
    placeholder: "Añadir etiqueta…", "aria-label": "Añadir etiqueta",
    onkeydown: (e) => {
      if ((e.key === "Enter" || e.key === ",") && entrada.value.trim()) { e.preventDefault(); añadir(entrada.value); }
      else if (e.key === "Enter") e.preventDefault();
      else if (e.key === "Backspace" && !entrada.value && etiquetas.length) { etiquetas.pop(); tocar("etiquetas"); pintar(); }
    },
    oninput: () => { if (entrada.value.includes(",")) añadir(entrada.value); },
    onchange: () => { if (entrada.value.trim()) añadir(entrada.value); },   // al elegir una sugerencia
  });
  function añadir(texto) {
    for (const parte of texto.split(",").map((t) => t.trim()).filter(Boolean)) {
      if (!etiquetas.includes(parte)) etiquetas.push(parte);
    }
    entrada.value = "";
    tocar("etiquetas");
    pintar();
  }
  function pintar() {
    fichas.replaceChildren(...etiquetas.map((t, i) => h("span", { class: "ficha" }, t,
      h("button", {
        type: "button", class: "quitar", title: `Quitar «${t}»`, "aria-label": `Quitar etiqueta ${t}`,
        onclick: () => { etiquetas.splice(i, 1); tocar("etiquetas"); pintar(); entrada.focus(); },
      }, "×"))), entrada);
  }
  pintar();
  api.etiquetas().then((lista) => {
    sugerencias.replaceChildren(...lista.map((t) => h("option", { value: t })));
  }, () => {});
  return h("div", { class: "campo completo" },
    h("label", { for: "f-etiquetas", text: "Etiquetas" }), fichas, sugerencias,
    h("span", { class: "ayuda", text: "Sirven para elegir qué pruebas entran en una campaña de ejecución." }));
}

function campoSelect(clave, etiqueta, opciones) {
  const id = "f-" + clave;
  const lista = opciones.includes(F.valores[clave]) ? opciones : [...opciones, F.valores[clave]];
  const select = h("select", {
    id, onchange: (e) => { F.valores[clave] = e.target.value; tocar(clave); },
  }, lista.map((o) => h("option", { value: o, selected: o === F.valores[clave], text: o || "(sin indicar)" })));
  return h("div", { class: "campo" }, h("label", { for: id, text: etiqueta }), select);
}

function campoArea(clave, etiqueta) {
  const id = "f-" + clave;
  const editor = editorFormato({
    id, etiqueta, valor: F.valores[clave],
    alCambiar: (texto) => { F.valores[clave] = texto; tocar(clave); },
  });
  return h("div", { class: "campo completo" },
    h("label", { for: id, text: etiqueta, onclick: () => $("#" + id).controlFormato.alFinal() }), editor);
}

function mostrarErrorCampo(clave, mensaje) {
  const el = $("#f-" + clave);
  if (!el) return;
  quitarErrorCampo(clave);
  el.classList.add("invalido");
  el.setAttribute("aria-invalid", "true");
  el.parentElement.appendChild(h("div", { class: "error-campo", id: "e-" + clave, role: "alert", text: mensaje }));
  el.focus();
  el.scrollIntoView({ block: "center" });
}

function quitarErrorCampo(clave) {
  const el = $("#f-" + clave);
  if (el) { el.classList.remove("invalido"); el.removeAttribute("aria-invalid"); }
  const msg = $("#e-" + clave);
  if (msg) msg.remove();
}

/* ---- miniaturas e imágenes ---- */
/** Miniatura de una imagen; `fuente(ruta, ancho)` la obtiene (por defecto, de la carpeta de YAML). */
function miniatura(ruta, alQuitar, fuente = datosImagen) {
  const nombre = ruta.split("/").pop();
  const img = h("img", { alt: nombre });
  const marco = h("div", { class: "marco" }, img);
  const fig = h("figure", { class: "miniatura" }, marco,
    h("figcaption", { text: nombre, title: ruta }),
    alQuitar ? h("button", {
      class: "btn icono quitar", type: "button", title: "Quitar imagen", "aria-label": "Quitar " + nombre,
      onclick: (e) => { e.stopPropagation(); alQuitar(); },
    }, icon("x")) : null);
  fuente(ruta, 240).then((d) => {
    img.src = d.uri;
    img.title = `${d.ancho} × ${d.alto} px`;
    img.addEventListener("click", () => visorImagen(ruta, nombre, fuente));
  }, (e) => {
    const perdida = /No se encuentra/.test(e.message);
    fig.classList.add("falla");
    if (perdida) fig.classList.add("perdida");
    marco.title = e.message;
    marco.replaceChildren(h("span", { text: perdida ? "No se encuentra el archivo" : "Sin vista previa" }));
  });
  return fig;
}

async function pegarImagenes(e, destino, alCambiar) {
  const archivos = [...((e.clipboardData && e.clipboardData.files) || [])].filter((f) => f.type.startsWith("image/"));
  if (!archivos.length) return;
  e.preventDefault();
  await añadirArchivos(archivos, destino, alCambiar);
}

async function añadirArchivos(archivos, destino, alCambiar) {
  try {
    const rutas = await importarArchivos(archivos);
    if (rutas.length) { destino.push(...rutas); alCambiar(); aviso(plural(rutas.length, "imagen añadida", "imágenes añadidas"), "ok"); }
  } catch (err) { fallo(err); }
}

async function elegirImagenes(destino, alCambiar) {
  try {
    const { rutas } = await api.elegir_imagenes();
    if (rutas.length) { destino.push(...rutas); alCambiar(); }
  } catch (err) { fallo(err); }
}

/** Hace que un elemento acepte archivos de imagen soltados encima. */
function aceptarArchivos(el, destino, alCambiar) {
  el.addEventListener("dragover", (e) => { if (tieneArchivos(e)) { e.preventDefault(); el.classList.add("suelta-archivo"); } });
  el.addEventListener("dragleave", () => el.classList.remove("suelta-archivo"));
  el.addEventListener("drop", (e) => {
    if (!tieneArchivos(e)) return;
    e.preventDefault();
    el.classList.remove("suelta-archivo");
    añadirArchivos([...e.dataTransfer.files], destino, alCambiar);
  });
}

/* ---- editor de listas (contexto, situaciones, pasos) ---- */
let filaArrastrada = null;

function editorLista(clave, titulo, { numerada = false, ayuda = "" } = {}) {
  const filas = F.valores[clave];
  const lista = h("ol", { class: "lista" + (numerada ? " numerada" : "") });
  const nuevaFila = (nivel = 0) => ({ texto: "", imagenes: [], nivel, forma: "str", extra: {} });

  function pintar(enfocar = null) {
    lista.replaceChildren();
    if (!filas.length) lista.appendChild(h("li", { class: "vacio", text: "Sin elementos." }));
    filas.forEach((fila, i) => lista.appendChild(crearFila(fila, i)));
    const areas = lista.querySelectorAll(".editable");
    if (enfocar !== null && areas[enfocar]) areas[enfocar].controlFormato.alFinal();   // sin esperar al siguiente fotograma
  }
  const insertar = (pos) => { filas.splice(pos, 0, nuevaFila(pos > 0 ? filas[pos - 1].nivel : 0)); tocar(clave); pintar(pos); };
  const quitar = (i) => { filas.splice(i, 1); tocar(clave); pintar(filas.length ? Math.min(i, filas.length - 1) : null); };
  const mover = (i, d) => {
    const j = i + d;
    if (j < 0 || j >= filas.length) return;
    [filas[i], filas[j]] = [filas[j], filas[i]];
    tocar(clave); pintar(j);
  };
  const sangria = (i, d) => { filas[i].nivel = Math.min(Math.max(filas[i].nivel + d, 0), 4); tocar(clave); pintar(i); };

  function crearFila(fila, i) {
    const editor = editorFormato({
      valor: fila.texto, etiqueta: `${titulo}, elemento ${i + 1}`,
      alCambiar: (texto) => { fila.texto = texto; tocar(clave); },
      onkeydown: (e) => {
        if (e.isComposing) return;
        if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); insertar(i + 1); }
        else if (e.key === "Backspace" && !fila.texto && !fila.imagenes.length && filas.length) { e.preventDefault(); quitar(i); }
        else if (e.altKey && e.key === "ArrowUp") { e.preventDefault(); mover(i, -1); }
        else if (e.altKey && e.key === "ArrowDown") { e.preventDefault(); mover(i, 1); }
      },
      onpaste: (e) => pegarImagenes(e, fila.imagenes, () => { tocar(clave); pintar(i); }),
    });
    const miniaturas = fila.imagenes.length
      ? h("div", { class: "imagenes" }, fila.imagenes.map((ruta, k) => miniatura(ruta, () => { fila.imagenes.splice(k, 1); tocar(clave); pintar(i); })))
      : null;
    const asa = h("span", { class: "asa", title: "Arrastra para reordenar" }, h("span", { class: "n" }), icon("grip"));
    const li = h("li", { class: "elemento", style: { "--nivel": String(fila.nivel) } },
      asa,
      h("div", { class: "contenido" }, editor, miniaturas),
      h("div", { class: "herramientas" },
        botonIcono("image", "Añadir imagen", () => elegirImagenes(fila.imagenes, () => { tocar(clave); pintar(i); })),
        botonIcono("outdent", "Quitar sangría", () => sangria(i, -1)),
        botonIcono("indent", "Añadir sangría", () => sangria(i, 1)),
        botonIcono("up", "Subir (Alt+↑)", () => mover(i, -1)),
        botonIcono("down", "Bajar (Alt+↓)", () => mover(i, 1)),
        botonIcono("trash", "Quitar elemento", () => quitar(i), "peligro")));
    aceptarArchivos(li, fila.imagenes, () => { tocar(clave); pintar(i); });
    asa.addEventListener("pointerdown", () => { li.draggable = true; });
    li.addEventListener("dragstart", (e) => {
      if (!li.draggable) return;
      filaArrastrada = { clave, i };
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", fila.texto);
    });
    li.addEventListener("dragend", () => { li.draggable = false; filaArrastrada = null; lista.querySelectorAll(".drop-antes,.drop-despues").forEach((x) => x.classList.remove("drop-antes", "drop-despues")); });
    li.addEventListener("dragover", (e) => {
      if (!filaArrastrada || filaArrastrada.clave !== clave) return;
      e.preventDefault();
      const caja = li.getBoundingClientRect();
      const antes = e.clientY < caja.top + caja.height / 2;
      li.classList.toggle("drop-antes", antes);
      li.classList.toggle("drop-despues", !antes);
    });
    li.addEventListener("dragleave", () => li.classList.remove("drop-antes", "drop-despues"));
    li.addEventListener("drop", (e) => {
      if (!filaArrastrada || filaArrastrada.clave !== clave) return;
      e.preventDefault();
      const caja = li.getBoundingClientRect();
      let destino = e.clientY < caja.top + caja.height / 2 ? i : i + 1;
      const origen = filaArrastrada.i;
      filaArrastrada = null;
      if (destino === origen || destino === origen + 1) { pintar(); return; }
      const [movida] = filas.splice(origen, 1);
      if (destino > origen) destino -= 1;
      filas.splice(destino, 0, movida);
      tocar(clave); pintar(destino);
    });
    return li;
  }

  const bloque = h("section", { class: "bloque", "aria-label": titulo },
    h("div", { class: "bloque-cab" },
      h("h3", { text: titulo }),
      ayuda ? h("p", { class: "ayuda", text: ayuda }) : null,
      h("button", { class: "btn ghost peq", type: "button", onclick: () => insertar(filas.length) }, icon("plus"), "Añadir")),
    lista);
  pintar();
  return bloque;
}

/* ---- campos adicionales ---- */
function editorExtras() {
  const filas = F.valores.campos_adicionales;
  const lista = h("div", { class: "extras" });
  function pintar(enfocar = null) {
    lista.replaceChildren();
    if (!filas.length) lista.appendChild(h("p", { class: "vacio", text: "Sin campos adicionales." }));
    filas.forEach((f, i) => lista.appendChild(crear(f, i)));
    if (enfocar !== null) { const el = lista.querySelectorAll("input")[enfocar]; if (el) el.focus(); }
    requestAnimationFrame(() => lista.querySelectorAll("textarea").forEach(autosize));
  }
  function crear(f, i) {
    const valor = f.tipo === "complejo"
      ? h("pre", { class: "complejo", title: "Estructura compleja: edítala en la vista YAML", text: f.valor })
      : h("textarea", {
        rows: 1, value: f.valor, "aria-label": `Valor de ${f.clave || "campo " + (i + 1)}`,
        placeholder: f.tipo === "lista" ? "Un elemento por línea" : "",
        oninput: (e) => { f.valor = e.target.value; autosize(e.target); tocar("campos_adicionales"); },
      });
    return h("div", { class: "extra" },
      h("input", {
        type: "text", class: "clave", value: f.clave, placeholder: "Nombre del campo", "aria-label": `Nombre del campo ${i + 1}`,
        oninput: (e) => { f.clave = e.target.value; tocar("campos_adicionales"); },
      }),
      valor,
      botonIcono("trash", "Quitar campo", () => { filas.splice(i, 1); tocar("campos_adicionales"); pintar(); }, "peligro"));
  }
  const bloque = h("section", { class: "bloque", "aria-label": "Campos adicionales" },
    h("div", { class: "bloque-cab" },
      h("h3", { text: "Campos adicionales" }),
      h("p", { class: "ayuda", text: "Información propia de esta prueba, como el resultado esperado." }),
      h("button", {
        class: "btn ghost peq", type: "button",
        onclick: () => { filas.push({ clave: "", valor: "", tipo: "texto", orig: undefined }); tocar("campos_adicionales"); pintar(filas.length - 1); },
      }, icon("plus"), "Añadir")),
    lista);
  pintar();
  return bloque;
}

/* ---- imágenes de la prueba ---- */
function galeria() {
  const imagenes = F.valores.imagenes;
  const contenedor = h("div", { class: "imagenes" });
  const zona = h("div", { class: "galeria", tabIndex: 0, "aria-label": "Imágenes de la prueba. Pega una captura con Ctrl+V o suelta archivos aquí." }, contenedor);
  const cambiado = () => { tocar("imagenes"); pintar(); };
  function pintar() {
    contenedor.replaceChildren();
    if (!imagenes.length) contenedor.appendChild(h("p", { class: "vacio", text: "Sin imágenes. Pega una captura con Ctrl+V o suelta archivos aquí." }));
    imagenes.forEach((ruta, i) => contenedor.appendChild(miniatura(ruta, () => { imagenes.splice(i, 1); cambiado(); })));
  }
  zona.addEventListener("paste", (e) => pegarImagenes(e, imagenes, cambiado));
  aceptarArchivos(zona, imagenes, cambiado);
  pintar();
  return h("section", { class: "bloque", "aria-label": "Imágenes de la prueba" },
    h("div", { class: "bloque-cab" },
      h("h3", { text: "Imágenes de la prueba" }),
      h("p", { class: "ayuda", text: "Se añaden al final de la tabla en el documento." }),
      h("button", { class: "btn ghost peq", type: "button", onclick: () => elegirImagenes(imagenes, cambiado) }, icon("image"), "Añadir")),
    zona);
}

/* ---- ubicación al crear ---- */
async function selectorUbicacion(esSeccion, porDefecto) {
  const secciones = await api.ubicaciones(S.capitulo);
  F.secciones = secciones;
  const seleccion = S.seleccion;
  const opciones = [];
  if (seleccion && seleccion.tipo === "prueba") {
    const nodo = S.nodos.find((n) => n.indice === seleccion.indice);
    if (nodo) opciones.push({ tipo: "despues", indice: nodo.indice, texto: `Justo después de «${nodo.id || nodo.titulo || "la prueba seleccionada"}»` });
  }
  for (const s of secciones) {
    opciones.push({ tipo: "seccion", indice: s.indice, texto: `${"    ".repeat(Math.max(0, s.nivel - 2))}Dentro de «${s.titulo}», al final` });
  }
  opciones.push({ tipo: "final", texto: "Al final del capítulo" });
  let elegida = 0;
  if (porDefecto) elegida = Math.max(0, opciones.findIndex((o) => o.tipo === porDefecto.tipo && o.indice === porDefecto.indice));
  else if (seleccion && seleccion.tipo === "seccion") elegida = Math.max(0, opciones.findIndex((o) => o.tipo === "seccion" && o.indice === seleccion.indice));
  else if (!(seleccion && seleccion.tipo === "prueba")) elegida = opciones.length - 1;

  const aplicar = (o) => {
    F.ubicacion = o.tipo === "final" ? { tipo: "final" } : { tipo: o.tipo, indice: o.indice };
    F.nivel = nivelDeUbicacion(F.ubicacion, esSeccion);
    actualizarCabecera();
  };
  const select = h("select", {
    id: "f-ubicacion",
    onchange: (e) => { aplicar(opciones[Number(e.target.value)]); setDirty(true); },
  }, opciones.map((o, i) => h("option", { value: String(i), selected: i === elegida, text: o.texto })));
  aplicar(opciones[elegida]);
  return h("section", { class: "bloque" },
    h("div", { class: "rejilla" },
      h("div", { class: "campo completo" }, h("label", { for: "f-ubicacion", text: esSeccion ? "Dónde crear la sección" : "Dónde crear la prueba" }), select)));
}

function nivelDeUbicacion(u, esSeccion) {
  if (u.tipo === "final") return esSeccion ? 2 : 3;
  if (u.tipo === "seccion") {
    const s = F.secciones.find((x) => x.indice === u.indice);
    return Math.min((s ? s.nivel : 2) + 1, 6);
  }
  const nodo = S.nodos.find((n) => n.indice === u.indice);
  return nodo ? nodo.nivel : 3;
}

/* ---- pantallas de formulario ---- */
function cuerpoPrueba(ubicacion) {
  const v = F.valores;
  const cont = h("div", { class: "formulario" }, cabecera(), ubicacion);
  cont.appendChild(h("section", { class: "bloque", "aria-label": "Datos de la prueba" },
    h("div", { class: "bloque-cab" }, h("h3", { text: "Datos de la prueba" })),
    h("div", { class: "rejilla" },
      campoTexto("id", "ID", { mono: true }),
      campoTexto("nombre", "Encabezado en el documento", { ancho: true }),
      campoTexto("titulo", "Título", { completo: true }),
      campoTexto("componente", "Componente"),
      campoTexto("plataforma", "Plataforma"),
      campoTexto("entorno", "Entorno de pruebas"),
      campoTexto("criticidad", "Criticidad"),
      campoSelect("automatizable", "Automatizable", AUTOMATIZABLE),
      campoTexto("referencia", "Referencia"),
      campoTexto("fecha", "Fecha"),
      campoTexto("version", "Versión"),
      campoEtiquetas(),
      campoArea("descripcion", "Descripción"))));
  cont.append(
    editorLista("contexto", "Contexto", { ayuda: "Texto que aparece antes de la tabla de la prueba." }),
    editorLista("situacion_inicial", "Situación inicial"),
    editorLista("pasos", "Pasos", { numerada: true, ayuda: "Pulsa Enter para añadir otro paso; Mayús+Enter inserta un salto de línea." }),
    editorLista("situacion_final", "Situación final"),
    editorExtras(),
    galeria(),
    bloqueAutomatizacion(F.idOriginal || F.valores.id));
  return cont;
}

function cuerpoSeccion(ubicacion) {
  const cont = h("div", { class: "formulario" }, cabecera(), ubicacion);
  cont.appendChild(h("section", { class: "bloque", "aria-label": "Datos de la sección" },
    h("div", { class: "rejilla" }, campoTexto("nombre", "Nombre de la sección", { completo: true }))));
  if (F.modo === "editar") {
    cont.appendChild(editorLista("contexto", "Contexto", { ayuda: "Texto compartido por todas las pruebas de la sección." }));
  }
  return cont;
}

function mostrarElemento(datos) {
  const el = datos.elemento;
  if (datos.tipo === "prueba") {
    F = { modo: "editar", tipo: "prueba", indice: datos.indice, valores: valoresDePrueba(el), cambios: new Set(), nivel: el.nivel, vista: "form", idOriginal: String(el.id || "") };
    mostrar(cuerpoPrueba(null));
  } else {
    F = {
      modo: "editar", tipo: "seccion", indice: datos.indice, nivel: el.nivel, vista: "form", cambios: new Set(),
      valores: { nombre: String(el.seccion || ""), contexto: aLista(el.contexto).map(filaDesde) },
    };
    mostrar(cuerpoSeccion(null));
  }
  setDirty(false);
}

async function mostrarNuevaPrueba(inicial = null, porDefecto = null) {
  F = { modo: "nueva", tipo: "prueba", indice: null, valores: inicial || valoresDePrueba({}), cambios: new Set(), nivel: 3, vista: "form" };
  if (!inicial && !F.valores.pasos.length) F.valores.pasos.push(filaDesde(""));
  const ubicacion = await selectorUbicacion(false, porDefecto);
  mostrar(cuerpoPrueba(ubicacion));
  setDirty(Boolean(inicial));
  const campo = $("#f-id"); if (campo) campo.focus();
}

async function mostrarNuevaSeccion() {
  F = { modo: "nueva", tipo: "seccion", indice: null, valores: { nombre: "", contexto: [] }, cambios: new Set(), nivel: 2, vista: "form" };
  const ubicacion = await selectorUbicacion(true, null);
  mostrar(cuerpoSeccion(ubicacion));
  setDirty(false);
  const campo = $("#f-nombre"); if (campo) campo.focus();
}

/* ---- guardar, crear, borrar ---- */
function marcarErrorEnCampo(error) {
  const msg = error && error.message ? error.message : "";
  if (F && F.tipo === "prueba" && /\bID\b/.test(msg)) mostrarErrorCampo("id", msg);
  else if (F && F.tipo === "seccion" && /nombre/i.test(msg)) mostrarErrorCampo("nombre", msg);
}

async function guardarActual() {
  if (S.modo === "ejecucion") return guardarResultado();
  if (!F) return true;
  const { tipo, indice, modo, vista } = F;
  try {
    if (vista === "yaml") {
      await api.aplicar_yaml(S.capitulo, indice, F.editor.getValue());
      setDirty(false);
      await refrescarTodo({ seleccionar: { tipo, indice } });
      aviso("YAML aplicado", "ok");
      return true;
    }
    if (modo === "nueva") return await crearActual();
    if (!F.cambios.size) { aviso("No hay cambios que guardar"); return true; }
    const cambios = recogerCambios();
    if (tipo === "prueba" && F.idOriginal && "id" in cambios && String(cambios.id).trim() !== F.idOriginal) {
      const r = await dialogo({
        titulo: "¿Cambiar el ID de la prueba?",
        cuerpo: h("div", {},
          h("p", { text: `El ID pasará de «${F.idOriginal}» a «${String(cambios.id).trim()}».` }),
          h("p", { text: "Las campañas de ejecución reconocen cada prueba por su ID. Si esta prueba ya tiene resultados en alguna campaña, allí aparecerá como «ya no existe» y el ID nuevo contará como una prueba distinta. Cambia el ID solo si es un error o si de verdad es otra prueba." })),
        botones: [{ texto: "Cancelar", valor: "no", tipo: "ghost" }, { texto: "Cambiar el ID", valor: "si", tipo: "peligro" }],
      });
      if (r !== "si") return false;
    }
    if (tipo === "prueba") await api.guardar_prueba(S.capitulo, indice, cambios);
    else await api.guardar_seccion(S.capitulo, indice, cambios);
    setDirty(false);
    await refrescarTodo({ seleccionar: { tipo, indice } });
    aviso(tipo === "prueba" ? "Prueba guardada" : "Sección guardada", "ok");
    return true;
  } catch (error) {
    marcarErrorEnCampo(error);
    fallo(error);
    return false;
  }
}

async function crearActual() {
  if (F.tipo === "prueba") {
    if (!F.valores.id.trim()) { mostrarErrorCampo("id", "El ID es obligatorio."); return false; }
    const r = await api.crear_prueba(S.capitulo, F.ubicacion, recogerCambios());
    setDirty(false);
    await refrescarTodo({ seleccionar: { tipo: "prueba", indice: r.indice } });
    aviso("Prueba creada", "ok");
  } else {
    if (!F.valores.nombre.trim()) { mostrarErrorCampo("nombre", "El nombre de la sección es obligatorio."); return false; }
    const r = await api.crear_seccion(S.capitulo, F.ubicacion, F.valores.nombre);
    setDirty(false);
    await refrescarTodo({ seleccionar: { tipo: "seccion", indice: r.indice } });
    aviso("Sección creada", "ok");
  }
  return true;
}

async function cancelarNueva() {
  if (!(await guardia())) return;
  setDirty(false);
  await reabrirSeleccion();
}

function duplicarActual() {
  if (!F || F.tipo !== "prueba" || F.modo !== "editar") return;
  const copia = JSON.parse(JSON.stringify(F.valores));
  copia.id = "";
  mostrarNuevaPrueba(copia, { tipo: "despues", indice: F.indice });
}

async function borrarActual() {
  if (!F || F.modo !== "editar") return;
  const { tipo, indice } = F;
  let titulo, cuerpo, boton;
  if (tipo === "prueba") {
    titulo = "Borrar prueba";
    cuerpo = `Vas a borrar «${F.valores.id || "sin ID"}: ${F.valores.titulo || F.valores.nombre || "sin título"}». Esta acción no se puede deshacer.`;
    boton = "Borrar prueba";
  } else {
    const hijas = descendientes(indice);
    titulo = "Borrar sección";
    cuerpo = `Vas a borrar el encabezado de «${F.valores.nombre}». ` + (hijas.length
      ? `Sus ${plural(hijas.length, "elemento", "elementos")} se conservan y suben un nivel; el contexto de la sección se conserva como texto.`
      : "La sección no contiene pruebas; su contexto se conserva como texto.");
    boton = "Borrar sección";
  }
  if (!(await confirmar(titulo, cuerpo, boton, true))) return;
  try {
    if (tipo === "prueba") await api.borrar_prueba(S.capitulo, indice);
    else await api.borrar_seccion(S.capitulo, indice);
    setDirty(false);
    S.seleccion = null;
    await refrescarTodo({});
    aviso(tipo === "prueba" ? "Prueba borrada" : "Sección borrada", "ok");
  } catch (error) { fallo(error); }
}

function descendientes(indice) {
  const dentro = new Set([indice]);
  const salida = [];
  for (const n of S.nodos) {
    if (n.padre !== null && n.padre !== undefined && dentro.has(n.padre)) { dentro.add(n.indice); salida.push(n); }
  }
  return salida;
}

/* ---- vista YAML ---- */
function crearEditorYaml(contenedor, texto, alCambiar) {
  if (window.YamlEditor) return window.YamlEditor.create(contenedor, texto, { onChange: alCambiar });
  const area = h("textarea", { value: texto, spellcheck: "false", "aria-label": "YAML", oninput: () => alCambiar(area.value) });
  contenedor.appendChild(area);
  return { getValue: () => area.value, setValue: (t) => { area.value = t; }, setError() {}, clearError() {}, focus: () => area.focus(), destroy() {} };
}

async function cambiarVista(vista, descartar = false) {
  if (!F || F.modo !== "editar") return;
  if (vista === F.vista) return;
  const { tipo, indice } = F;
  if (vista === "form") {
    if (S.dirty && !descartar && !(await guardia())) return;
    setDirty(false);
    await abrir(tipo, indice);
    return;
  }
  if (S.dirty) { aviso("Guarda o descarta los cambios antes de abrir la vista YAML.", "error"); return; }
  try {
    const { texto } = await api.obtener_yaml(S.capitulo, indice);
    F.vista = "yaml";
    const estado = h("div", { class: "estado-yaml ok", role: "status", text: "YAML válido" });
    const contenedor = h("div", { class: "editor-yaml" });
    const validar = debounce(async (t) => {
      try {
        const r = await api.validar_yaml(t);
        if (!F || F.vista !== "yaml" || !F.editor) return;   // ya se salió de la vista YAML
        if (r.valido) { F.editor.clearError(); estado.className = "estado-yaml ok"; estado.textContent = "YAML válido"; }
        else { F.editor.setError(r.linea, r.columna, r.mensaje); estado.className = "estado-yaml mal"; estado.textContent = `Línea ${r.linea}, columna ${r.columna}: ${r.mensaje}`; }
      } catch (e) { fallo(e); }
    }, 300);
    F.editor = crearEditorYaml(contenedor, texto, (t) => { setDirty(t !== texto); validar(t); });
    mostrar(h("div", { class: "formulario" }, cabecera(),
      h("div", { class: "vista-yaml" }, contenedor, estado)));
    F.editor.focus();
  } catch (e) { fallo(e); }
}
