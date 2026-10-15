"use strict";
/* Árbol de secciones, pruebas y tablas: selección, plegado, teclado y arrastre. */

function profundidades(nodos) {
  const prof = new Map();
  for (const n of nodos) {
    prof.set(n.indice, n.padre === null || n.padre === undefined ? 0 : (prof.get(n.padre) ?? 0) + 1);
  }
  return prof;
}

const claveColapso = (n) => `${S.capitulo}:${n.titulo}`;

/** Marca por elemento ("indice") con la peor gravedad del capítulo abierto. */
function marcasProblemas() {
  const marcas = new Map();
  for (const p of S.problemas) {
    if (p.capitulo !== S.capitulo || p.indice === null) continue;
    if (marcas.get(p.indice) !== "error") marcas.set(p.indice, p.severidad);
  }
  return marcas;
}

/** Cantidad de pruebas bajo cada sección. */
function contarPruebas(nodos) {
  const cuenta = new Map();
  const padres = new Map(nodos.map((n) => [n.indice, n.padre]));
  for (const n of nodos) {
    if (n.tipo !== "prueba") continue;
    let p = n.padre;
    while (p !== null && p !== undefined) {
      cuenta.set(p, (cuenta.get(p) || 0) + 1);
      p = padres.get(p);
    }
  }
  return cuenta;
}

function renderArbol() {
  const ul = $("#arbol");
  ul.replaceChildren();
  if (!S.nodos.length) {
    const texto = S.modo === "ejecucion"
      ? (S.campana ? "Ninguna prueba de la campaña en este capítulo con este filtro." : "Abre o crea una campaña.")
      : S.consulta ? "Nada coincide con la búsqueda." : "Este capítulo no tiene pruebas todavía.";
    ul.appendChild(h("li", { class: "arbol-vacio", text: texto }));
    return;
  }
  const prof = profundidades(S.nodos);
  const conHijos = new Set(S.nodos.map((n) => n.padre).filter((p) => p !== null && p !== undefined));
  const cuenta = contarPruebas(S.nodos);
  const marcas = marcasProblemas();
  const buscando = Boolean(S.consulta);
  const cerradas = new Set();
  const ocultas = new Set();

  for (const n of S.nodos) {
    if (n.padre !== null && n.padre !== undefined && (cerradas.has(n.padre) || ocultas.has(n.padre))) {
      ocultas.add(n.indice);
      continue;
    }
    const cerrada = n.tipo === "seccion" && !buscando && S.colapsadas.has(claveColapso(n));
    if (cerrada) cerradas.add(n.indice);
    ul.appendChild(filaArbol(n, prof.get(n.indice), cerrada, conHijos.has(n.indice), cuenta.get(n.indice) || 0, marcas.get(n.indice)));
  }
}

function filaArbol(n, profundidad, cerrada, tieneHijos, cuenta, marca) {
  const seleccionada = S.seleccion && S.seleccion.indice === n.indice;
  const li = h("li", {
    class: `fila ${n.tipo}${seleccionada ? " sel" : ""}`,
    role: "treeitem",
    "aria-level": String(profundidad + 1),
    "aria-selected": String(Boolean(seleccionada)),
    tabIndex: seleccionada ? 0 : -1,
    draggable: S.modo !== "ejecucion",   // en ejecución no se reordena
    dataset: { tipo: n.tipo, indice: String(n.indice) },
    style: { "--prof": String(profundidad) },
    onclick: () => seleccionar(n.tipo, n.indice),
  });
  if (n.tipo === "seccion") {
    li.setAttribute("aria-expanded", String(!cerrada));
    li.appendChild(tieneHijos && !S.consulta
      ? h("button", {
        class: "conmutador", type: "button", tabIndex: -1,
        "aria-label": cerrada ? "Desplegar sección" : "Plegar sección",
        "aria-expanded": String(!cerrada),
        onclick: (e) => { e.stopPropagation(); alternarSeccion(n); },
      }, icon("chevron"))
      : h("span", { class: "hueco" }));
    append(li, [
      h("span", { class: "tit", text: n.titulo || "(sin nombre)" }),
      cuenta ? h("span", { class: "cuenta", text: String(cuenta), title: plural(cuenta, "prueba", "pruebas") }) : null,
    ]);
  } else if (n.tipo === "tabla") {
    li.title = `Tabla de ${n.filas} × ${n.columnas}`;
    append(li, [
      h("span", { class: "hueco" }),
      h("span", { class: "icono-tabla" }, icon("table")),
      h("span", { class: "tit", text: n.titulo || "(tabla vacía)" }),
    ]);
  } else {
    append(li, [
      h("span", { class: "hueco" }),
      S.modo === "ejecucion" ? marcaEstado(n.id) : null,
      h("span", { class: "tid", text: n.id || "(sin ID)" }),
      h("span", { class: "tit", text: n.titulo || "(sin título)" }),
      tieneRobot(n.id) ? h("span", { class: "marca-robot", title: "Tiene test de Robot Framework" }, icon("robot")) : null,
    ]);
  }
  if (marca) {
    li.appendChild(h("span", {
      class: "marca-problema " + marca,
      title: marca === "error" ? "Tiene errores de validación" : "Tiene avisos de validación",
    }));
  }
  return li;
}

function alternarSeccion(n, forzar) {
  const clave = claveColapso(n);
  const cerrar = forzar === undefined ? !S.colapsadas.has(clave) : forzar;
  if (cerrar) S.colapsadas.add(clave); else S.colapsadas.delete(clave);
  renderArbol();
  enfocarSeleccion();
}

function enfocarSeleccion() {
  const fila = $("#arbol .fila.sel");
  if (fila) fila.scrollIntoView({ block: "nearest" });
}

/* ---- teclado ---- */
function filasVisibles() {
  return [...document.querySelectorAll("#arbol .fila")];
}

function teclasArbol(e) {
  const filas = filasVisibles();
  if (!filas.length) return;
  const actual = filas.findIndex((f) => f.classList.contains("sel"));
  const nodo = (fila) => S.nodos.find((n) => n.indice === Number(fila.dataset.indice));
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault();
    const siguiente = filas[Math.min(Math.max(actual + (e.key === "ArrowDown" ? 1 : -1), 0), filas.length - 1)];
    seleccionar(siguiente.dataset.tipo, Number(siguiente.dataset.indice)).then(() => {
      const f = $(`#arbol .fila[data-indice="${siguiente.dataset.indice}"]`);
      if (f) f.focus();
    });
  } else if ((e.key === "ArrowLeft" || e.key === "ArrowRight") && actual >= 0) {
    const n = nodo(filas[actual]);
    if (n && n.tipo === "seccion") {
      e.preventDefault();
      alternarSeccion(n, e.key === "ArrowLeft");
      const f = $(`#arbol .fila[data-indice="${n.indice}"]`);
      if (f) f.focus();
    }
  }
}

/* ---- arrastre ---- */
let arrastre = null;

function zonaDeSoltar(fila, e) {
  const caja = fila.getBoundingClientRect();
  const razon = (e.clientY - caja.top) / caja.height;
  if (fila.dataset.tipo === "seccion") return razon < 0.28 ? "antes" : razon > 0.72 ? "despues" : "dentro";
  return razon < 0.5 ? "antes" : "despues";
}

function limpiarZonas() {
  document.querySelectorAll("#arbol .fila").forEach((f) => f.classList.remove("drop-antes", "drop-despues", "drop-dentro"));
}

function iniciarArrastreArbol() {
  const ul = $("#arbol");
  ul.addEventListener("keydown", teclasArbol);
  ul.addEventListener("dragstart", (e) => {
    const fila = e.target.closest && e.target.closest(".fila");
    if (!fila) return;
    arrastre = { tipo: fila.dataset.tipo, indice: Number(fila.dataset.indice) };
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", fila.textContent);
    fila.classList.add("arrastrando");
  });
  ul.addEventListener("dragover", (e) => {
    if (!arrastre) return;
    const fila = e.target.closest(".fila");
    if (!fila) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    limpiarZonas();
    if (Number(fila.dataset.indice) !== arrastre.indice) fila.classList.add("drop-" + zonaDeSoltar(fila, e));
  });
  ul.addEventListener("drop", async (e) => {
    if (!arrastre) return;
    e.preventDefault();
    const fila = e.target.closest(".fila");
    const origen = arrastre;
    const zona = fila ? zonaDeSoltar(fila, e) : null;
    arrastre = null;
    limpiarZonas();
    if (!fila || Number(fila.dataset.indice) === origen.indice) return;
    await moverElemento(origen, Number(fila.dataset.indice), zona);
  });
  ul.addEventListener("dragend", () => {
    arrastre = null;
    limpiarZonas();
    document.querySelectorAll("#arbol .arrastrando").forEach((f) => f.classList.remove("arrastrando"));
  });
}

async function moverElemento(origen, destino, zona) {
  if (!(await guardia())) return;
  try {
    const r = await api.mover(S.capitulo, origen.indice, destino, zona);
    await refrescarTodo({ seleccionar: { tipo: origen.tipo, indice: r.indice } });
    aviso({ seccion: "Sección movida", prueba: "Prueba movida", tabla: "Tabla movida" }[origen.tipo], "ok");
  } catch (e) {
    fallo(e);
    await refrescarTodo({});
  }
}
