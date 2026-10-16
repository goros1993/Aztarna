"use strict";
/* Menú «…» de la barra superior: lo que no se usa a diario (importar, exportar,
   manual, acerca de) y la versión de la barra inferior. */

const REPOSITORIO = "https://github.com/goros1993/Validacion";

/** Opciones del menú según el modo y lo que haya abierto. */
function opcionesMenu() {
  const conCapitulos = S.capitulos.length > 0;
  return [
    {
      texto: "Importar…", icono: "import", desactivada: true,
      ayuda: "Próximamente: importar pruebas o requisitos desde un Word (issue #2). Hoy, con «python herramientas.py convertir».",
    },
    S.modo === "ejecucion" ? null : {
      texto: enRequisitos() ? "Exportar DOCX de requisitos…" : "Exportar DOCX…", icono: "export", accion: exportarDocx,
      desactivada: !conCapitulos, ayuda: "Generar el documento de Word con todos los capítulos",
    },
    "-",
    { texto: "Manual de usuario", icono: "libro", accion: abrirManual, ayuda: "Abrir el manual en una ventana aparte" },
    { texto: "Acerca de…", icono: "info", accion: acercaDe },
  ].filter(Boolean);
}

let menuAbierto = null;

function cerrarMenu() {
  if (!menuAbierto) return;
  menuAbierto.remove();
  menuAbierto = null;
  $("#btn-menu").setAttribute("aria-expanded", "false");
}

function abrirMenu() {
  if (menuAbierto) { cerrarMenu(); return; }
  const boton = $("#btn-menu");
  const items = opcionesMenu().map((o) => o === "-"
    ? h("div", { class: "menu-separador", role: "separator" })
    : h("button", {
      type: "button", class: "menu-opcion", role: "menuitem", disabled: Boolean(o.desactivada), title: o.ayuda || null,
      onclick: async () => { cerrarMenu(); try { await o.accion(); } catch (e) { fallo(e); } },
    }, icon(o.icono), o.texto));
  menuAbierto = h("div", { class: "menu-flotante", role: "menu", "aria-label": "Más opciones" }, items);
  document.body.appendChild(menuAbierto);
  const caja = boton.getBoundingClientRect();
  menuAbierto.style.top = `${caja.bottom + 4}px`;
  menuAbierto.style.right = `${Math.max(8, window.innerWidth - caja.right)}px`;
  boton.setAttribute("aria-expanded", "true");
  const primera = menuAbierto.querySelector(".menu-opcion:not([disabled])");
  if (primera) primera.focus();
}

async function abrirManual() {
  await api.abrir_manual();
}

async function acercaDe() {
  const d = await api.acerca_de();
  const fila = (etiqueta, valor) => [h("dt", { text: etiqueta }), h("dd", { text: valor })];
  await dialogo({
    titulo: `${d.nombre} ${d.version}`,
    cuerpo: h("div", { class: "acerca-de" },
      h("div", { class: "acerca-cab" }, h("img", { src: "img/icono.png", alt: "", width: "56", height: "56" }),
        h("p", { text: "Pruebas, requisitos, trazabilidad, ejecuciones y validación de versiones, con los datos en YAML." })),
      h("dl", { class: "datos-campana" },
        fila("Versión", d.version), fila("Ajustes de este PC", d.ajustes), fila("Python", d.python), fila("Sistema", d.sistema)),
      h("p", {}, h("button", { class: "enlace", type: "button", text: "Novedades y código en GitHub", onclick: () => api.abrir_enlace(REPOSITORIO).catch(fallo) }))),
    botones: [{ texto: "Manual de usuario", valor: "manual", tipo: "" }, { texto: "Cerrar", valor: "", tipo: "primary" }],
  }).then((r) => (r === "manual" ? abrirManual() : null));
}

function iniciarMenu() {
  $("#btn-menu").addEventListener("click", (e) => { e.stopPropagation(); abrirMenu(); });
  document.addEventListener("click", (e) => { if (menuAbierto && !menuAbierto.contains(e.target)) cerrarMenu(); });
  document.addEventListener("keydown", (e) => {
    if (!menuAbierto) return;
    if (e.key === "Escape") { e.preventDefault(); cerrarMenu(); $("#btn-menu").focus(); return; }
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault();
    const opciones = [...menuAbierto.querySelectorAll(".menu-opcion:not([disabled])")];
    const i = opciones.indexOf(document.activeElement);
    const siguiente = opciones[(i + (e.key === "ArrowDown" ? 1 : opciones.length - 1)) % opciones.length];
    if (siguiente) siguiente.focus();
  });
  window.addEventListener("resize", cerrarMenu);
  // Versión en la barra inferior (abre «Acerca de»).
  const version = $("#btn-version");
  api.acerca_de().then((d) => { version.textContent = `v${d.version}`; }, () => { version.hidden = true; });
  version.addEventListener("click", acercaDe);
}
