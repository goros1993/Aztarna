"use strict";
/* Tablas que no son pruebas (historial de cambios, parámetros…). Suelen ir
   dentro del contexto de una sección o de una prueba; las de antes del primer
   título son del capítulo y salen en el árbol. Se muestran como una tabla de
   lectura y, al hacer clic, se editan como una cuadrícula: cada celda es un
   texto con formato, puede ocupar varias columnas («columnas») y llevar
   imágenes. */

/** {filas: [[{texto, imagenes, columnas}]], resto}; las filas cortas se completan
    alargando su última celda, igual que al generar el Word. `resto` guarda las
    demás claves de la tabla (por ejemplo, el motivo de la importación). */
function valoresDeTabla(el = {}) {
  const { filas: crudas, ...resto } = el || {};
  const filas = aLista(crudas).filter(Array.isArray).map((fila) => fila.map((celda) => (
    celda && typeof celda === "object"
      ? { texto: String(celda.texto ?? ""), imagenes: aLista(celda.imagenes).map(String), columnas: Math.max(Number(celda.columnas) || 1, 1) }
      : { texto: celda === null || celda === undefined ? "" : String(celda), imagenes: [], columnas: 1 })));
  if (!filas.length) filas.push([celdaVacia(), celdaVacia()]);
  for (const fila of filas) if (!fila.length) fila.push(celdaVacia());
  const ancho = anchoTabla(filas);
  for (const fila of filas) {
    const falta = ancho - fila.reduce((a, c) => a + c.columnas, 0);
    if (falta > 0) fila[fila.length - 1].columnas += falta;
  }
  return { filas, resto };
}

const celdaVacia = () => ({ texto: "", imagenes: [], columnas: 1 });
const anchoTabla = (filas) => Math.max(1, ...filas.map((f) => f.reduce((a, c) => a + c.columnas, 0)));
const tablaNueva = () => valoresDeTabla({ filas: [["", ""], ["", ""]] });

function tablaAPlano(filas) {
  return filas.map((fila) => fila.map((c) => (c.imagenes.length || c.columnas > 1
    ? { texto: c.texto, ...(c.imagenes.length ? { imagenes: [...c.imagenes] } : {}), ...(c.columnas > 1 ? { columnas: c.columnas } : {}) }
    : c.texto)));
}

function tituloDeTabla(filas) {
  for (const fila of filas) {
    for (const c of fila) {
      const t = marcasACaracteres(c.texto).map((x) => x.c).join("").replace(/\s+/g, " ").trim();
      if (t) return t.slice(0, 80);
    }
  }
  return "";
}

/* ---- operaciones sobre la cuadrícula ---- */
/** Columna de la rejilla donde empieza la celda k de una fila. */
const inicioCelda = (fila, k) => fila.slice(0, k).reduce((a, c) => a + c.columnas, 0);

/** Celda de la fila que cubre la columna `col` de la rejilla: {k, inicio} o null. */
function celdaEnColumna(fila, col) {
  let inicio = 0;
  for (let k = 0; k < fila.length; k++) {
    if (col < inicio + fila[k].columnas) return { k, inicio };
    inicio += fila[k].columnas;
  }
  return null;
}

const OPERACIONES_TABLA = {
  filaEncima(filas, r) { filas.splice(r, 0, Array.from({ length: anchoTabla(filas) }, celdaVacia)); return [r, 0]; },
  filaDebajo(filas, r) { filas.splice(r + 1, 0, Array.from({ length: anchoTabla(filas) }, celdaVacia)); return [r + 1, 0]; },
  columna(filas, col) {
    for (const fila of filas) {
      const c = celdaEnColumna(fila, col);
      if (!c) fila.push(celdaVacia());                         // al final
      else if (c.inicio === col) fila.splice(c.k, 0, celdaVacia());
      else fila[c.k].columnas += 1;                            // cae dentro de una celda unida: se ensancha
    }
  },
  borrarColumna(filas, col) {
    for (const fila of filas) {
      const c = celdaEnColumna(fila, col);
      if (!c) continue;
      if (fila[c.k].columnas > 1) fila[c.k].columnas -= 1;
      else fila.splice(c.k, 1);
    }
  },
  unirDerecha(fila, k) {
    const [a, b] = [fila[k], fila[k + 1]];
    a.texto = [a.texto, b.texto].filter((t) => t.trim()).join("\n");
    a.imagenes.push(...b.imagenes);
    a.columnas += b.columnas;
    fila.splice(k + 1, 1);
  },
  separar(fila, k) {
    fila[k].columnas -= 1;
    fila.splice(k + 1, 0, celdaVacia());
  },
};

/* ---- vista de lectura ---- */
function vistaTabla(valores) {
  return h("table", { class: "tabla-vista" }, valores.filas.map((fila) => h("tr", {}, fila.map((celda) => {
    const texto = h("div", { class: "fmt-texto" });
    pintarCaracteres(texto, marcasACaracteres(celda.texto));
    return h("td", { colSpan: celda.columnas }, texto,
      celda.imagenes.length ? h("div", { class: "imagenes" }, celda.imagenes.map((ruta) => miniatura(ruta, null))) : null);
  }))));
}

/**
 * Tabla que se ve en modo lectura y se edita al hacer clic en ella.
 * `alCambiar()` se llama tras cada cambio; los datos se modifican en `valores`.
 */
function componenteTabla(valores, { alCambiar, editando = false }) {
  const raiz = h("div", { class: "componente-tabla" });
  let modo = editando ? "editar" : "ver";

  function pintar(enfocar = null) {
    if (modo === "ver") {
      const vista = h("div", {
        class: "tabla-lectura", role: "button", tabIndex: 0, title: "Haz clic para editar la tabla",
        "aria-label": `Tabla «${tituloDeTabla(valores.filas) || "vacía"}»: pulsa para editarla`,
        onclick: (e) => { if (!e.target.closest(".miniatura img")) editar(); },
        onkeydown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); editar(); } },
      }, vistaTabla(valores), h("span", { class: "pista-editar" }, "Editar tabla"));
      raiz.replaceChildren(vista);
    } else {
      raiz.replaceChildren(editorTabla(valores, {
        alCambiar,
        alTerminar: () => { modo = "ver"; pintar(); raiz.querySelector(".tabla-lectura").focus(); },
        enfocar,
      }));
    }
  }
  function editar() { modo = "editar"; pintar([0, 0]); }
  pintar(editando ? [0, 0] : null);
  return raiz;
}

/* ---- editor de la cuadrícula ---- */
function editorTabla(valores, { alCambiar, alTerminar, enfocar = null }) {
  const filas = valores.filas;
  const cuadricula = h("table", { class: "tabla-editable" });
  const barra = h("div", { class: "barra-tabla", role: "toolbar", "aria-label": "Editar la tabla" });
  const dims = h("span", { class: "muted dims-tabla" });
  let foco = null;                       // [fila, celda] con el cursor

  const vigente = () => (foco && filas[foco[0]] && filas[foco[0]][foco[1]] ? foco : null);
  const cambiado = (enfocarEn) => { alCambiar(); pintar(enfocarEn); };

  function pintar(enfocarEn = null) {
    cuadricula.replaceChildren(...filas.map((fila, r) => h("tr", {}, fila.map((celda, k) => crearCelda(celda, r, k)))));
    dims.textContent = `${plural(filas.length, "fila", "filas")} × ${plural(anchoTabla(filas), "columna", "columnas")}`;
    if (enfocarEn) {
      const [r, k] = enfocarEn;
      const area = cuadricula.rows[r] && cuadricula.rows[r].cells[k] && cuadricula.rows[r].cells[k].querySelector(".editable");
      if (area) area.controlFormato.alFinal();
    }
    actualizarBarra();
  }

  function crearCelda(celda, r, k) {
    const repintar = () => cambiado([r, k]);
    const editor = editorFormato({
      valor: celda.texto, etiqueta: `Fila ${r + 1}, celda ${k + 1}`,
      alCambiar: (texto) => { celda.texto = texto; alCambiar(); },
      onpaste: (e) => pegarImagenes(e, celda.imagenes, repintar),
      onkeydown: (e) => { if (e.key === "Escape") { e.preventDefault(); alTerminar(); } },
    });
    editor.querySelector(".editable").addEventListener("focus", () => { foco = [r, k]; actualizarBarra(); });
    const td = h("td", { colSpan: celda.columnas },
      editor,
      celda.imagenes.length ? h("div", { class: "imagenes" }, celda.imagenes.map((ruta, i) => miniatura(ruta, () => { celda.imagenes.splice(i, 1); repintar(); }))) : null);
    aceptarArchivos(td, celda.imagenes, repintar);
    return td;
  }

  function boton(icono, texto, titulo, accion, activo, clase = "") {
    return h("button", {
      type: "button", class: ("btn peq " + clase).trim(), title: titulo, disabled: !activo,
      onmousedown: (e) => e.preventDefault(),          // no quita el foco de la celda
      onclick: accion,
    }, icono ? icon(icono) : null, texto);
  }

  function actualizarBarra() {
    const f = vigente();
    const [r, k] = f || [0, 0];
    const fila = filas[r] || [];
    const celda = fila[k];
    const ini = celda ? inicioCelda(fila, k) : 0;
    const ancho = anchoTabla(filas);
    barra.replaceChildren(
      boton("plus", "Fila encima", "Insertar una fila encima", () => cambiado(OPERACIONES_TABLA.filaEncima(filas, r)), f),
      boton("plus", "Fila debajo", "Insertar una fila debajo", () => cambiado(OPERACIONES_TABLA.filaDebajo(filas, r)), f),
      boton("plus", "Columna izquierda", "Insertar una columna a la izquierda", () => { OPERACIONES_TABLA.columna(filas, ini); cambiado([r, k + 1]); }, f),
      boton("plus", "Columna derecha", "Insertar una columna a la derecha", () => { OPERACIONES_TABLA.columna(filas, ini + celda.columnas); cambiado([r, k]); }, f),
      h("span", { class: "sep" }),
      boton(null, "Unir con la derecha", "Unir esta celda con la de su derecha", () => { OPERACIONES_TABLA.unirDerecha(fila, k); cambiado([r, k]); }, f && k < fila.length - 1),
      boton(null, "Separar", "Separar la última columna de esta celda unida", () => { OPERACIONES_TABLA.separar(fila, k); cambiado([r, k]); }, f && celda.columnas > 1),
      boton("image", "Imagen", "Añadir una imagen a esta celda", () => elegirImagenes(celda.imagenes, () => cambiado([r, k])), f),
      h("span", { class: "sep" }),
      boton("trash", "Borrar fila", "Borrar la fila de esta celda", () => {
        filas.splice(r, 1);
        foco = null;
        cambiado([Math.min(r, filas.length - 1), 0]);
      }, f && filas.length > 1),
      boton("trash", "Borrar columna", "Borrar la columna de esta celda", () => {
        OPERACIONES_TABLA.borrarColumna(filas, ini);
        for (let i = filas.length - 1; i >= 0; i--) if (!filas[i].length) filas.splice(i, 1);
        foco = null;
        cambiado([Math.min(r, filas.length - 1), 0]);
      }, f && ancho > 1),
      dims,
      boton("check", "Hecho", "Dejar de editar la tabla (Esc)", alTerminar, true, "primary"));
    cuadricula.querySelectorAll("td.foco").forEach((td) => td.classList.remove("foco"));
    if (f && cuadricula.rows[r]) cuadricula.rows[r].cells[k].classList.add("foco");
  }

  pintar(enfocar);
  return h("div", { class: "editor-tabla" }, barra, h("div", { class: "envoltura-tabla" }, cuadricula),
    h("p", { class: "ayuda", text: "Tab pasa a la celda siguiente. Las celdas admiten formato e imágenes (pegar o soltar). Esc o «Hecho» para terminar." }));
}

/* ---- tablas del capítulo (en el árbol) ---- */
function mostrarTabla(datos) {
  F = { modo: "editar", tipo: "tabla", indice: datos.indice, valores: valoresDeTabla(datos.elemento), cambios: new Set(), nivel: null, vista: "form" };
  const motivo = F.valores.resto.motivo;
  mostrar(h("div", { class: "formulario" }, cabecera(),
    h("section", { class: "bloque", "aria-label": "Tabla" },
      h("div", { class: "bloque-cab" }, h("h3", { text: "Tabla del capítulo" }),
        h("p", { class: "ayuda", text: "Va antes del primer título del capítulo. Haz clic en ella para editarla." })),
      componenteTabla(F.valores, { alCambiar: () => { tocar("filas"); actualizarCabecera(); } })),
    motivo ? h("p", { class: "muted nota-tabla", text: `Importada del Word como tabla que no es una prueba (${motivo}).` }) : null));
  setDirty(false);
}
