"use strict";
/* Robot Framework: configuración, cobertura (qué pruebas tienen test de Robot),
   keywords propuestas al escribir los pasos y ejecución desde el editor. Los
   tests de Robot se enlazan con las pruebas mediante la etiqueta id:<ID> (ver
   docs/robot.md). */

/* ---- cobertura ---- */
async function cargarCobertura() {
  try { S.cobertura = await api.robot_cobertura(); } catch (_e) { S.cobertura = null; }
  try { prepararKeywords(await api.robot_keywords()); } catch (_e) { prepararKeywords(null); }
  const resumen = $("#robot-resumen");
  if (resumen) {
    resumen.textContent = S.cobertura ? `Robot · ${S.cobertura.cubiertas.length}` : "Robot";
    $("#btn-robot").title = S.cobertura
      ? `${plural(S.cobertura.cubiertas.length, "prueba tiene", "pruebas tienen")} test de Robot. Pulsa para ver la cobertura o cambiar la configuración.`
      : "Configurar Robot Framework (dónde están los tests y cómo ejecutarlos)";
  }
}

const tieneRobot = (id) => Boolean(S.cobertura && id && S.cobertura.por_id[id]);
const testsRobotDe = (id) => (S.cobertura && S.cobertura.por_id[id]) || [];

function listaTestsRobot(id) {
  return h("ul", { class: "tests-robot" }, testsRobotDe(id).map((t) => h("li", {},
    h("span", { class: "nombre-robot", text: t.nombre }),
    h("span", { class: "muted", text: ` ${t.archivo}:${t.linea}` }))));
}

/** Bloque de solo lectura en el formulario de la prueba. */
function bloqueAutomatizacion(id) {
  if (!S.cobertura) return null;
  const tests = testsRobotDe(id);
  return h("section", { class: "bloque", "aria-label": "Automatización" },
    h("div", { class: "bloque-cab" }, h("h3", { text: "Automatización (Robot Framework)" }),
      h("p", { class: "ayuda", text: "Tests de Robot con la etiqueta id: de esta prueba." })),
    tests.length ? listaTestsRobot(id)
      : h("p", { class: "vacio", text: id ? `Ningún test de Robot lleva la etiqueta id:${id}.` : "Pon un ID a la prueba para enlazarla con Robot." }));
}

/* ---- keywords: se proponen al escribir situaciones y pasos ---- */
const sinAcentos = (t) => t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
/** Como compara Robot los nombres de keyword: sin mayúsculas, espacios ni guiones bajos. */
const normalizarKeyword = (t) => sinAcentos(t).replace(/[\s_]+/g, "");
const ARG_INCRUSTADO = /\$\{([^}:]+)(?::[^}]*)?\}/g;
const PREFIJO_BDD = /^(given|when|then|and|but|dado|cuando|entonces|y|pero)\s+/i;

function prepararKeywords(datos) {
  S.keywords = datos && datos.keywords.length ? datos : null;
  if (!S.keywords) return;
  for (const kw of S.keywords.keywords) {
    kw.norm = normalizarKeyword(kw.nombre);
    kw.buscar = sinAcentos(kw.nombre);
    if (kw.nombre.includes("${")) {
      let patron = "", inicio = 0;
      for (const m of kw.nombre.matchAll(ARG_INCRUSTADO)) {
        patron += sinAcentos(kw.nombre.slice(inicio, m.index)).replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/\s+/g, "\\s+") + "(.+?)";
        inicio = m.index + m[0].length;
      }
      patron += sinAcentos(kw.nombre.slice(inicio)).replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/\s+/g, "\\s+");
      kw.patron = new RegExp("^" + patron + "$");
    }
  }
}

const hayKeywords = () => Boolean(S.keywords);

/** Texto plano del paso y su primera celda (lo que sería la keyword en Robot). */
function celdaKeyword(texto) {
  const plano = marcasACaracteres(texto).map((c) => c.c).join("");
  return plano.split(/ {2,}|\t|\n/)[0].trim().replace(/\.$/, "").replace(PREFIJO_BDD, "");
}

/** Keyword con la que coincide un paso (o null). */
function keywordDePaso(texto) {
  if (!S.keywords) return null;
  const celda = celdaKeyword(texto);
  if (!celda) return null;
  const norm = normalizarKeyword(celda);
  const plano = sinAcentos(celda);
  return S.keywords.keywords.find((kw) => kw.norm === norm || norm.endsWith("." + kw.norm)) ||
    S.keywords.keywords.find((kw) => kw.patron && kw.patron.test(plano)) || null;
}

/** Keywords que encajan con lo escrito, las más probables primero. */
function buscarKeywords(consulta, maximo = 8) {
  const palabras = sinAcentos(consulta).split(/\s+/).filter(Boolean);
  if (!palabras.length) return [];
  const inicio = sinAcentos(consulta).trim();
  const candidatas = [];
  for (const kw of S.keywords.keywords) {
    const acierto = palabras.filter((p) => kw.buscar.includes(p)).length;
    // Con argumentos incrustados lo escrito puede llevar ya los valores (P2, 1 s…).
    const basta = kw.patron ? acierto >= Math.max(1, Math.ceil(palabras.length * 0.6)) : acierto === palabras.length;
    if (basta) candidatas.push({ kw, nota: (acierto === palabras.length ? 2 : 0) + (kw.buscar.startsWith(inicio) ? 1 : 0) });
  }
  candidatas.sort((a, b) => b.nota - a.nota || b.kw.usos - a.kw.usos || a.kw.nombre.localeCompare(b.kw.nombre));
  return candidatas.slice(0, maximo).map((c) => c.kw);
}

/** Texto que se escribe al elegir una keyword y qué queda seleccionado para rellenar. */
function textoDeKeyword(kw) {
  const obligatorios = kw.argumentos.filter((a) => a.obligatorio);
  const texto = kw.nombre + obligatorios.map((a) => `    ${a.nombre}=`).join("");
  const incrustado = kw.nombre.search(/\$\{/);
  if (incrustado >= 0) return { texto, a: incrustado, b: kw.nombre.indexOf("}", incrustado) + 1 };
  if (obligatorios.length) { const a = kw.nombre.length + 4 + obligatorios[0].nombre.length + 1; return { texto, a, b: a }; }
  return { texto, a: texto.length, b: texto.length };
}

const firmaKeyword = (kw) => kw.argumentos.map((a) => a.nombre + (a.defecto != null ? "=" + a.defecto : "")).join(", ");

function nombreKeywordResaltado(nombre) {
  const partes = [];
  let inicio = 0;
  for (const m of nombre.matchAll(ARG_INCRUSTADO)) {
    partes.push(nombre.slice(inicio, m.index), h("span", { class: "arg", text: m[0] }));
    inicio = m.index + m[0].length;
  }
  partes.push(nombre.slice(inicio));
  return h("span", { class: "kw-nombre" }, partes);
}

/**
 * Lista de keywords bajo el editor de un paso. Devuelve {actualizar(texto),
 * tecla(e)}: `tecla` devuelve true si la tecla era para la lista (↑ ↓ Intro
 * Tab Esc) y así el editor no la usa.
 */
function sugerenciasKeywords(area, contenedor, textoInicial) {
  const lista = h("div", { class: "sugerencias-kw", role: "listbox", hidden: true });
  const marca = h("span", { class: "paso-kw", hidden: true }, icon("robot"));
  area.parentElement.after(lista);
  contenedor.append(marca);
  let opciones = [], activa = 0, cerradaCon = null;

  function pintarMarca(texto) {
    const kw = keywordDePaso(texto);
    marca.hidden = !kw;
    if (kw) marca.title = `Keyword de Robot: ${kw.nombre} (${kw.archivo}:${kw.linea})`;
    area.classList.toggle("con-keyword", Boolean(kw));
  }
  function cerrar() { lista.hidden = true; opciones = []; }
  function pintar() {
    lista.replaceChildren(...opciones.map((kw, i) => h("div", {
      class: "kw" + (i === activa ? " activa" : ""), role: "option", "aria-selected": String(i === activa),
      onmousedown: (e) => e.preventDefault(),
      onclick: () => elegir(kw),
    },
      h("div", { class: "kw-linea" }, nombreKeywordResaltado(kw.nombre),
        kw.argumentos.length ? h("span", { class: "kw-args", text: firmaKeyword(kw) }) : null),
      kw.doc ? h("div", { class: "kw-doc", text: kw.doc }) : null,
      h("div", { class: "kw-origen", text: `${kw.archivo}:${kw.linea}${kw.usos ? " · usada " + plural(kw.usos, "vez", "veces") : ""}` }))));
    lista.hidden = !opciones.length;
    const activo = lista.children[activa];
    if (activo) activo.scrollIntoView({ block: "nearest" });
  }
  function elegir(kw) {
    const { texto, a, b } = textoDeKeyword(kw);
    cerrar();
    cerradaCon = texto;
    area.controlFormato.reemplazar(texto, a, b);
  }
  function actualizar(texto) {
    pintarMarca(texto);
    const plano = marcasACaracteres(texto).map((c) => c.c).join("");
    const consulta = celdaKeyword(texto);
    // Sin lista si el paso ya es una keyword, tiene varias líneas o se acaba de elegir.
    if (document.activeElement !== area || plano.includes("\n") || consulta.length < 2 || keywordDePaso(texto) || texto === cerradaCon) { cerrar(); return; }
    opciones = buscarKeywords(consulta);
    activa = 0;
    pintar();
  }
  function tecla(e) {
    if (lista.hidden) return false;
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      activa = (activa + (e.key === "ArrowDown" ? 1 : opciones.length - 1)) % opciones.length;
      pintar();
    } else if ((e.key === "Enter" && !e.shiftKey) || e.key === "Tab") {
      elegir(opciones[activa]);
    } else if (e.key === "Escape") {
      cerradaCon = area.controlFormato.valor;
      cerrar();
    } else return false;
    e.preventDefault();
    e.stopPropagation();
    return true;
  }
  area.addEventListener("blur", () => setTimeout(cerrar, 120));
  pintarMarca(textoInicial);
  return { actualizar, tecla };
}

/* ---- configuración ---- */
async function configurarRobot() {
  if (!S.capitulos.length) { aviso("Abre primero la carpeta de pruebas", "error"); return; }
  let datos;
  try { datos = await api.robot_config(); } catch (e) { fallo(e); return; }
  const c = datos.config || {};
  const campo = (id, etiqueta, valor, ayuda) => h("div", { class: "campo completo" },
    h("label", { for: id, text: etiqueta }), h("input", { id, type: "text", value: valor || "", placeholder: ayuda || "", autocomplete: "off" }));
  const suites = campo("rb-suites", "Carpeta (o archivo) con los tests de Robot", c.suites, "Por ejemplo C:\\proyectos\\banco\\tests");
  const comando = campo("rb-comando", "Comando para ejecutar Robot", c.comando, datos.comando_defecto);
  const argumentos = campo("rb-args", "Argumentos adicionales (opcional)", c.argumentos, "--variable BANCO:2 --pythonpath lib");
  const keywords = campo("rb-keywords", "Otras carpetas con keywords (opcional)", c.keywords, "Librerías de Python o .resource fuera de la carpeta de tests; separa varias con ;");
  const comprobacion = h("p", { class: "muted", id: "rb-comprobacion" });
  const examinar = h("button", {
    type: "button", class: "btn peq", text: "Examinar…",
    onclick: async () => {
      try { const r = await api.robot_elegir_carpeta(); if (!r.cancelado) suites.querySelector("input").value = r.carpeta; } catch (e) { fallo(e); }
    },
  });
  const comprobar = h("button", {
    type: "button", class: "btn peq", text: "Comprobar",
    onclick: async () => {
      comprobacion.textContent = "Comprobando…";
      comprobacion.className = "muted";
      try {
        const r = await api.robot_comprobar(comando.querySelector("input").value.trim());
        comprobacion.textContent = "✓ " + r.version;
        comprobacion.className = "ok-txt";
      } catch (e) { comprobacion.textContent = e.message; comprobacion.className = "error-campo"; }
    },
  });
  suites.appendChild(h("div", { class: "fila-botones" }, examinar));
  comando.appendChild(h("div", { class: "fila-botones" }, comprobar, comprobacion));
  const cobertura = S.cobertura ? resumenCobertura(S.cobertura, S.keywords) : null;
  const r = await dialogo({
    titulo: "Robot Framework", ancho: true,
    cuerpo: h("div", { class: "config-robot" },
      h("p", { text: "Para saber qué pruebas están automatizadas y poder lanzarlas desde una ejecución. La configuración es de este PC y de esta carpeta de pruebas. Cada test de Robot se enlaza con su prueba con la etiqueta id:<ID> (ver docs/robot.md)." }),
      h("div", { class: "rejilla" }, suites, comando, argumentos, keywords),
      cobertura),
    botones: [{ texto: "Cancelar", valor: "no", tipo: "ghost" }, { texto: "Guardar", valor: "si", tipo: "primary" }],
  });
  if (r !== "si") return;
  try {
    const res = await api.robot_guardar_config({
      suites: suites.querySelector("input").value, comando: comando.querySelector("input").value,
      argumentos: argumentos.querySelector("input").value, keywords: keywords.querySelector("input").value,
    });
    await cargarCobertura();
    renderArbol();
    validarEnSegundoPlano();
    if (F && F.tipo === "prueba") await reabrirSeleccion();
    aviso(res.cobertura ? `Robot: ${plural(res.cobertura.tests_robot, "test", "tests")}, ${plural(res.cobertura.cubiertas.length, "prueba automatizada", "pruebas automatizadas")}` : "Configuración de Robot guardada", "ok");
  } catch (e) { fallo(e); }
}

function resumenCobertura(c, kws) {
  const lista = (titulo, elementos, clase = "") => elementos.length ? h("div", { class: "aviso-robot " + clase },
    h("strong", { text: `${titulo} (${elementos.length})` }), h("span", { text: elementos.join(", ") })) : null;
  return h("div", { class: "cobertura-robot" },
    h("h3", { text: "Cobertura" }),
    h("p", { text: `${plural(c.tests_robot, "test de Robot", "tests de Robot")} · ${plural(c.cubiertas.length, "prueba automatizada", "pruebas automatizadas")}` +
      (kws ? ` · ${plural(kws.keywords.length, "keyword", "keywords")} para los pasos.` : ".") }),
    lista("Automatizable «hecho» sin test de Robot", c.hecho_sin_robot, "atencion"),
    lista("IDs de Robot que no existen en las pruebas", c.inexistentes, "atencion"),
    lista("Tests de Robot sin etiqueta id:", c.sin_id.map((t) => `${t.nombre} (${t.archivo}:${t.linea})`)),
    lista("No se pudieron leer", [...c.errores, ...(kws ? kws.errores : [])], "atencion"));
}

/* ---- ejecutar Robot desde una ejecución ---- */
async function ejecutarRobot() {
  if (!S.campana || S.campana.cerrada) return;
  if (!(await guardia())) return;
  setDirty(false);
  await cargarCobertura();
  if (!S.cobertura) {
    aviso("Configura antes Robot Framework (botón Robot de la barra superior)", "error");
    await configurarRobot();
    return;
  }
  const pruebas = S.campana.resumen.pruebas.filter((p) => tieneRobot(p.id));
  if (!pruebas.length) {
    await dialogo({ titulo: "Ejecutar Robot", cuerpo: "Ninguna prueba de esta ejecución tiene test de Robot (etiqueta id:<ID>).", botones: [{ texto: "Entendido", valor: "", tipo: "primary" }] });
    return;
  }
  const pendientes = pruebas.filter((p) => p.estado === "pendiente");
  const elegir = (valor, texto, n) => h("label", { class: "casilla opcion" },
    h("input", { type: "radio", name: "rb-alcance", value: valor, checked: valor === (pendientes.length ? "pendientes" : "todas"), disabled: !n }), ` ${texto} (${n})`);
  const cuerpo = h("div", { class: "lanzar-robot" },
    h("p", { text: "Se lanzará Robot solo con los tests de estas pruebas. Al terminar verás qué resultados se apuntarían antes de guardarlos." }),
    elegir("pendientes", "Solo las pendientes", pendientes.length),
    elegir("todas", "Todas las de la ejecución con test de Robot (las ya ejecutadas pasan al historial)", pruebas.length),
    h("ul", { class: "tests-elegidos" }, pruebas.map((p) => h("li", {},
      h("span", { class: "punto-estado e-" + p.estado }), " ", h("span", { class: "tid", text: p.id }), " ", p.titulo))));
  const r = await dialogo({
    titulo: "Ejecutar Robot Framework", cuerpo, ancho: true,
    botones: [{ texto: "Cancelar", valor: "no", tipo: "ghost" }, { texto: "Ejecutar", valor: "si", tipo: "primary" }],
  });
  if (r !== "si") return;
  const alcance = cuerpo.querySelector("input[name=rb-alcance]:checked").value;
  const ids = (alcance === "pendientes" ? pendientes : pruebas).map((p) => p.id);
  try {
    await api.campana_robot_lanzar(ids);
  } catch (e) { fallo(e); return; }
  await seguirRobot(ids.length);
}

/** Diálogo con el avance; al terminar ofrece importar los resultados. */
async function seguirRobot(numeroPruebas) {
  const barra = h("div", { class: "barra-progreso" });
  const estado = h("p", { class: "estado-robot", text: "Arrancando Robot…" });
  const lista = h("ol", { class: "avance-robot" });
  const consola = h("pre", { class: "consola-robot", hidden: true });
  const cuerpo = h("div", {}, estado, barra, lista, consola);
  let ultimo = null;
  const promesa = dialogo({
    titulo: `Robot Framework · ${plural(numeroPruebas, "prueba", "pruebas")}`, cuerpo, ancho: true,
    botones: [{ texto: "Cancelar la ejecución", valor: "cancelar", tipo: "peligro" }],
  });
  const cerrarDialogo = (valor) => { const dlg = cuerpo.closest("dialog"); if (dlg && dlg.open) dlg.close(valor); };
  const temporizador = setInterval(async () => {
    try {
      const p = await api.campana_robot_progreso();
      if (!p) return;
      ultimo = p;
      const hechos = p.terminados.length;
      const total = p.total || Math.max(hechos, 1);
      barra.replaceChildren(...["PASS", "FAIL", "SKIP"].map((e) => {
        const n = p.terminados.filter((t) => t.estado === e).length;
        return n ? h("span", { class: "e-" + { PASS: "ok", FAIL: "no_ok", SKIP: "no_aplica" }[e], style: { flexGrow: String(n) } }) : null;
      }).filter(Boolean), h("span", { class: "e-pendiente", style: { flexGrow: String(Math.max(total - hechos, 0)) } }));
      estado.textContent = p.en_marcha
        ? `${hechos} de ${p.total ?? "?"} tests · ${p.actual ? "ejecutando «" + p.actual.nombre + "»" : "preparando"} · ${p.segundos} s`
        : p.cancelada ? "Ejecución cancelada." : `Terminado: ${hechos} tests en ${p.segundos} s.`;
      lista.replaceChildren(...p.terminados.slice(-8).map((t) => h("li", {},
        h("span", { class: "chip-estado e-" + ({ PASS: "ok", FAIL: "no_ok", SKIP: "no_aplica" }[t.estado] || "pendiente"), text: t.estado }), " ", t.nombre,
        t.mensaje ? h("span", { class: "muted", text: " · " + t.mensaje }) : null)));
      if (!p.en_marcha) {
        clearInterval(temporizador);
        if (!p.output) {
          consola.hidden = false;
          consola.textContent = p.consola.join("\n") || "(sin salida)";
          estado.textContent = `Robot terminó sin resultados (código ${p.codigo}). Revisa el comando y los argumentos en la configuración de Robot.`;
        } else {
          setTimeout(() => cerrarDialogo("fin"), 600);
        }
      }
    } catch (e) { clearInterval(temporizador); fallo(e); }
  }, 700);
  const r = await promesa;
  if (r === "cancelar" && ultimo && ultimo.en_marcha) {
    await api.campana_robot_cancelar().catch(fallo);
    aviso("Ejecución de Robot cancelada");
  }
  clearInterval(temporizador);
  if (r === "fin" && ultimo && ultimo.output) await importarRobot(ultimo.output);
}

function iniciarRobot() {
  $("#btn-robot").addEventListener("click", configurarRobot);
}
