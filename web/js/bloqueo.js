"use strict";
/* Bloqueo de capítulos: si otra persona está editando el capítulo abierto,
   aviso y solo lectura; al empezar a editar, se toma el bloqueo (ver
   app/bloqueos.py). El backend no guarda nunca en un capítulo bloqueado por
   otra persona: esto es para avisar antes de perder el trabajo. */

let BLOQUEO = { capitulo: null, otro: null, mio: false };

const editaCapitulos = () => S.modo !== "ejecucion" && !S.soloLectura && S.capitulos.length > 0;
const capituloBloqueado = () => Boolean(editaCapitulos() && BLOQUEO.otro && BLOQUEO.capitulo === S.capitulo);

async function comprobarBloqueo(reabrir = false) {
  const antes = capituloBloqueado();
  if (!editaCapitulos()) BLOQUEO = { capitulo: null, otro: null, mio: false };
  else {
    const capitulo = S.capitulo;
    try { BLOQUEO = { capitulo, ...(await api.bloqueo(capitulo)) }; } catch (_e) { return; }
  }
  pintarBloqueo();
  // Si lo acaban de dejar, se vuelve a pintar el formulario para poder editarlo.
  if (reabrir && antes && !capituloBloqueado() && !S.dirty) await reabrirSeleccion();
}

/** Al empezar a editar: toma el bloqueo del capítulo. Si lo tiene otra persona, avisa y pasa a solo lectura. */
async function tomarBloqueo() {
  if (!editaCapitulos() || (BLOQUEO.mio && BLOQUEO.capitulo === S.capitulo)) return;
  const capitulo = S.capitulo;
  try { BLOQUEO = { capitulo, ...(await api.bloquear(capitulo)) }; } catch (_e) { return; }
  pintarBloqueo();
  if (BLOQUEO.otro) aviso(`${BLOQUEO.otro.texto}: tus cambios no se podrán guardar`, "error");
}

/** Al cambiar de capítulo o de colección: suelta los bloqueos de esta sesión y mira el nuevo capítulo. */
async function cambioDeCapitulo() {
  try { await api.soltar_bloqueos(); } catch (_e) { /* sin bloqueos */ }
  BLOQUEO = { capitulo: null, otro: null, mio: false };
  await comprobarBloqueo();
}

async function forzarBloqueo() {
  const otro = BLOQUEO.otro;
  if (!otro || !(await confirmar("Forzar el bloqueo",
    `${otro.texto}. Si sigue editando, no podrá guardar sus cambios y tendrá que repetirlos. `
    + "Fuérzalo solo si sabes que no lo está usando (por ejemplo, se dejó el editor abierto).", "Forzar", true))) return;
  const capitulo = S.capitulo;
  try { BLOQUEO = { capitulo, ...(await api.bloquear(capitulo, true)) }; } catch (e) { fallo(e); return; }
  pintarBloqueo();
  if (!S.dirty) await reabrirSeleccion();
  aviso("Ahora puedes editar este capítulo", "ok");
}

function pintarBloqueo() {
  const caja = $("#aviso-bloqueo");
  const bloqueado = capituloBloqueado();
  document.body.classList.toggle("capitulo-bloqueado", bloqueado);
  caja.hidden = !bloqueado;
  for (const id of ["btn-nueva-prueba", "btn-nueva-seccion"]) $("#" + id).disabled = bloqueado || !S.capitulos.length;
  if (!bloqueado) { caja.replaceChildren(); return; }
  caja.replaceChildren(
    h("div", { class: "aviso-bloqueo-texto" }, icon("candado"),
      h("span", {}, h("strong", { text: BLOQUEO.otro.texto }), ". Puedes consultarlo, pero no cambiarlo hasta que lo deje.")),
    h("div", { class: "aviso-bloqueo-botones" },
      h("button", { class: "btn peq", type: "button", text: "Comprobar de nuevo", onclick: () => comprobarBloqueo(true).then(() => {
        if (!capituloBloqueado()) aviso("Ya está libre: puedes editarlo", "ok");
      }) }),
      h("button", { class: "btn ghost peq", type: "button", text: "Forzar…", onclick: forzarBloqueo })));
  desactivarFormulario(principal());
}

/** Formulario en solo lectura (se puede leer, copiar y cambiar de vista, pero no editar ni guardar). */
function desactivarFormulario(raiz) {
  if (!capituloBloqueado() || !raiz) return;
  raiz.querySelectorAll("input, textarea, select, button").forEach((el) => {
    if (!el.closest(".vista-conmutador, .libre-en-bloqueo")) el.disabled = true;
  });
  raiz.querySelectorAll("[contenteditable]").forEach((el) => el.setAttribute("contenteditable", "false"));
  raiz.querySelectorAll(".cm-content").forEach((el) => el.setAttribute("contenteditable", "false"));
}

function iniciarBloqueos() {
  // Cada medio minuto: por si lo dejan (o alguien fuerza el mío).
  setInterval(() => { if (!document.querySelector("dialog[open]")) comprobarBloqueo(true); }, 30000);
}
