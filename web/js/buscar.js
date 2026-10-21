"use strict";
/* Buscar (y reemplazar) en todos los capítulos del proyecto, no solo en el abierto. */

async function buscarEnTodo() {
  if (S.modo === "ejecucion") { aviso("En el modo Validar, busca en el árbol del capítulo; para buscar en todo, cambia a Editar pruebas o Editar requisitos", "info"); return; }
  if (!S.capitulos.length) return;
  if (!(await guardia())) return;
  setDirty(false);
  let datos = { resultados: [], total: 0 };
  const entrada = h("input", { type: "search", id: "global-buscar", autocomplete: "off", value: $("#buscar").value || "",
    placeholder: enRequisitos() ? "Texto a buscar en todos los requisitos" : "Texto a buscar en todas las pruebas" });
  const reemplazo = h("input", { type: "text", id: "global-reemplazo", autocomplete: "off", placeholder: "Texto nuevo" });
  const lista = h("div", { class: "resultados-globales" });
  const resumen = h("p", { class: "muted" });
  const botonReemplazar = h("button", { type: "button", class: "btn", disabled: true, onclick: () => reemplazar().catch(fallo) });
  const zonaReemplazo = h("details", { class: "zona-reemplazo" },
    h("summary", { text: "Reemplazar" }),
    h("div", { class: "fila-archivo" }, reemplazo, botonReemplazar),
    h("p", { class: "ayuda", text: "Cambia el texto en todos los resultados (sin distinguir mayúsculas), salvo en los ID. Los capítulos que está editando otra persona se saltan." }));

  const dlg = h("dialog", { class: "ancho buscar-global", "aria-label": "Buscar en todo el proyecto" });
  dlg.addEventListener("close", () => dlg.remove());

  async function buscar() {
    const texto = entrada.value.trim();
    if (texto.length < 2) { datos = { resultados: [], total: 0 }; pintar(); return; }
    try { datos = await api.buscar_global(texto); } catch (e) { fallo(e); return; }
    pintar();
  }
  function pintar() {
    const texto = entrada.value.trim();
    resumen.textContent = texto.length < 2 ? "Escribe al menos dos letras."
      : datos.total ? `${plural(datos.total, "resultado", "resultados")}${datos.total > datos.resultados.length ? ` (se muestran ${datos.resultados.length})` : ""}` : "Nada coincide.";
    botonReemplazar.textContent = datos.total ? `Reemplazar en ${plural(datos.total, "elemento", "elementos")}…` : "Reemplazar…";
    botonReemplazar.disabled = !datos.total || S.soloLectura;
    let capitulo = null;
    lista.replaceChildren(...datos.resultados.flatMap((r) => {
      const fila = h("button", { type: "button", class: "resultado-global", onclick: () => ir(r) },
        h("span", { class: "rg-quien" }, r.id ? h("span", { class: "tid", text: r.id }) : h("span", { class: "muted", text: r.tipo === "seccion" ? "Sección" : "Tabla" }),
          " ", h("span", { text: r.titulo })),
        h("span", { class: "rg-donde" }, h("span", { class: "muted", text: `${r.campo}: ` }), r.antes, h("mark", { text: r.coincide }), r.despues,
          r.veces > 1 ? h("span", { class: "muted", text: `  (${r.veces} veces)` }) : null));
      const cab = r.capitulo !== capitulo ? [h("div", { class: "rg-capitulo", text: r.nombre_capitulo })] : [];
      capitulo = r.capitulo;
      return [...cab, fila];
    }));
  }
  async function ir(r) {
    dlg.close();
    if (r.capitulo !== S.capitulo) { $("#sel-capitulo").value = String(r.capitulo); await cambiarCapitulo(String(r.capitulo)); }
    await seleccionar(r.tipo === "requisito" || r.tipo === "prueba" ? r.tipo : r.tipo, r.indice);
    renderArbol();
    enfocarSeleccion();
  }
  async function reemplazar() {
    const de = entrada.value.trim();
    const a = reemplazo.value;
    if (!(await confirmar("Reemplazar en todo el proyecto",
      `Se cambiará «${de}» por «${a}» en ${plural(datos.total, "elemento", "elementos")} (no en los ID) y se guardará. Con Git puedes deshacerlo; sin Git, no.`, "Reemplazar"))) return;
    const r = await api.reemplazar_global(de, a, datos.elementos || datos.resultados.map((x) => ({ capitulo: x.capitulo, indice: x.indice })));
    aviso(`Cambiado en ${plural(r.cambiados, "elemento", "elementos")} (${plural(r.veces, "vez", "veces")})`, "ok");
    if (r.saltados.length) aviso(`No se ha cambiado: ${r.saltados.join("; ")}`, "error");
    await refrescarTodo(S.seleccion ? { seleccionar: S.seleccion } : {});
    entrada.value = a.trim().length >= 2 ? a : de;
    await buscar();
  }

  entrada.addEventListener("input", debounce(buscar, 250));
  entrada.addEventListener("keydown", (e) => { if (e.key === "Enter" && datos.resultados.length) ir(datos.resultados[0]); });
  append(dlg, [
    h("div", { class: "dlg-cab", text: enRequisitos() ? "Buscar en todos los requisitos" : "Buscar en todas las pruebas" }),
    h("div", { class: "dlg-cuerpo" }, entrada, resumen, lista, zonaReemplazo),
    h("div", { class: "dlg-pie" }, h("button", { type: "button", class: "btn primary", text: "Cerrar", onclick: () => dlg.close() })),
  ]);
  document.body.appendChild(dlg);
  dlg.showModal();
  entrada.focus();
  entrada.select();
  buscar();
}
