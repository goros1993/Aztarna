// Capturas del manual: recorre la interfaz real (con la API de Python detrás) en Chromium.
// Uso: node capturar.js <fase> <puerto> <carpeta de salida>   (mejor con capturar.sh)
// Variables: PLAYWRIGHT (módulo de Playwright), CHROMIUM (ejecutable), DESTINO (carpeta de los datos).
const fs = require("fs");
const { chromium } = require(process.env.PLAYWRIGHT || "playwright");
const [fase, puerto, salida] = process.argv.slice(2);
const DATOS = process.env.DESTINO || "/home/ana/validacion";

(async () => {
  const navegador = await chromium.launch(process.env.CHROMIUM ? { executablePath: process.env.CHROMIUM } : {});
  const p = await navegador.newPage({ viewport: { width: 1360, height: 880 } });
  const errores = [];
  p.on("pageerror", (e) => errores.push("pageerror: " + e.message));
  await p.addInitScript(() => {
    window.__falsos = {};
    const real = (n, a) => fetch("/api/" + n, { method: "POST", body: JSON.stringify(a) }).then((r) => r.json());
    window.pywebview = { api: new Proxy({}, { get: (_t, n) => (...a) => (n in window.__falsos
      ? Promise.resolve({ ok: true, datos: typeof window.__falsos[n] === "function" ? window.__falsos[n](...a) : window.__falsos[n] })
      : real(n, a)) }) };
    setTimeout(() => window.dispatchEvent(new Event("pywebviewready")), 0);
  });
  const espera = (ms = 500) => p.waitForTimeout(ms);
  const foto = async (nombre, opciones = {}) => {
    await espera(opciones.espera || 700);
    await p.mouse.move(1355, 875);
    await p.addStyleTag({ content: "#avisos{display:none!important} *{caret-color:transparent}" });
    await p.screenshot({ path: `${salida}/${nombre}.png`, ...opciones.pw });
    console.log("foto", nombre);
  };
  const api = (n, ...a) => p.evaluate(([n, a]) => window.pywebview.api[n](...a), [n, a]);
  const js = (codigo, arg) => p.evaluate(codigo, arg);
  const fila = async (texto) => { await p.evaluate(() => { if (typeof setDirty === "function") setDirty(false); document.activeElement && document.activeElement.blur(); }); await p.evaluate(() => setDirty(false)); await p.click(`#arbol .fila:has-text("${texto}")`); await espera(600); };
  const capitulo = async (i) => { await p.selectOption("#sel-capitulo", String(i)); await espera(); };
  const boton = (texto, ambito = "") => p.click(`${ambito} button:has-text("${texto}")`.trim());
  const cerrarDialogo = async () => { await p.evaluate(() => document.querySelectorAll("dialog[open]").forEach((d) => d.close(""))); await espera(400); };

  await p.goto(`http://127.0.0.1:${puerto}/index.html`);
  await p.waitForSelector("#arbol .fila, .centro");
  await espera(800);
  await api("robot_guardar_config", { suites: `${DATOS}/robot`, comando: "robot" });
  await js(() => { guardarLocal("ejecutor", "Ana Pérez"); });
  await js(async () => { await cargarCobertura(); await cargarNavegacion(); });

  const fases = {
    async edicion() {
      await fila("DEMO-LLAM-001");
      await foto("01_ventana_edicion");
      await p.click("#btn-menu");
      await foto("35_menu");
      await js(async () => { const d = (await window.pywebview.api.acerca_de()).datos;
        window.__falsos.acerca_de = { ...d, ajustes: "C:\\Users\\ana\\AppData\\Roaming\\Aztarna\\ajustes.json", python: "3.12.10", sistema: "Windows 11" }; });
      await p.click('[role="menu"] >> text=Acerca de');
      await foto("36_acerca");
      await cerrarDialogo();
      await p.click("#btn-menu");
      await p.click('[role="menu"] >> text=Ajustes');
      await foto("50_ajustes");
      await cerrarDialogo();
      // Barra de formato: «Comprobar» en negrita y «la planta seleccionada» resaltado.
      await js(() => { const c = $("#f-descripcion"); c.focus(); });
      await p.keyboard.press("Home");
      await p.keyboard.down("Shift");
      for (let i = 0; i < 9; i++) await p.keyboard.press("ArrowRight");
      await p.keyboard.up("Shift");
      await p.click('.formato:visible button.n');
      await p.keyboard.press("End");
      await p.keyboard.down("Shift");
      for (let i = 0; i < 23; i++) await p.keyboard.press("ArrowLeft");
      await p.keyboard.up("Shift");
      await p.click('.formato:visible button.r-amarillo');
      await p.keyboard.press("End");
      await foto("02_formato");
      await js(() => { setDirty(false); });
      await fila("DEMO-LLAM-002");
      await fila("DEMO-LLAM-001");
      await js(() => { [...document.querySelectorAll(".bloque h3")].find((x) => x.textContent === "Ensayo").scrollIntoView(); document.querySelector(".principal").scrollTop -= 50; });
      await foto("03_listas");
      await boton("YAML", ".acciones");
      await foto("05_vista_yaml");
      await boton("Formulario", ".acciones");
      await fila("DEMO-LLAM-002");
      await p.click("#btn-nueva-prueba");
      await espera();
      await p.fill("#f-id", "DEMO-LLAM-004");
      await p.fill("#f-titulo", "La llamada de piso se cancela al pulsar dos veces");
      await p.focus("#f-id");
      await foto("04_nueva_prueba");
      await js(() => { setDirty(false); });
      await boton("Cancelar", ".acciones");
      await fila("DEMO-LLAM-002");
      await p.click("#btn-problemas");
      await p.click("#alcance-todos");
      await foto("06_validacion");
      await p.click("#btn-problemas");
      await p.click("#btn-menu");
      await p.click('[role="menu"] >> text=Exportar DOCX');
      await foto("07_exportar");
      await cerrarDialogo();
      await js(() => document.querySelector("#f-etiquetas, .campo-etiquetas input, [data-campo='etiquetas'] input") && 0);
      const tags = p.locator(".campo:has(label:text-is('Tags')) input");
      await tags.scrollIntoViewIfNeeded();
      await js(() => { document.querySelector(".principal").scrollTop += 120; });
      await tags.click();
      await p.keyboard.type("s");
      await foto("27_tags");
      await p.keyboard.press("Escape");
      await js(() => { setDirty(false); });
      await fila("DEMO-LLAM-001");
      await fila("DEMO-LLAM-003");
      const reqs = p.locator(".campo:has(label:text-is('Requisitos')) input");
      await reqs.scrollIntoViewIfNeeded();
      await js(() => { document.querySelector(".principal").scrollTop += 120; });
      await reqs.click();
      await p.keyboard.type("puer");
      await foto("31_prueba_requisitos");
      await p.keyboard.press("Escape");
      await js(() => { setDirty(false); });
      await fila("DEMO-LLAM-001");
      await fila("DEMO-NIV-001");
      await js(() => { const pr = document.querySelector(".principal"); pr.scrollTop = pr.scrollHeight; });
      await foto("19_cobertura_edicion");
      // Varios elegidos y «Campos…».
      await fila("DEMO-LLAM-001");
      for (const t of ["DEMO-LLAM-002", "DEMO-LLAM-003", "DEMO-NIV-001", "Llamadas simultáneas", "Nivelación"]) {
        await p.click(`#arbol .fila:has-text("${t}")`, { modifiers: ["Control"] });
      }
      await boton("Campos", "#barra-niveles");
      await p.selectOption("dialog[open] select", { label: "Tags" }).catch(() => {});
      await foto("51_campos_varios");
      await cerrarDialogo();
      await p.click("#barra-niveles .btn.icono, #barra-niveles button[aria-label]").catch(() => {});
      await p.keyboard.press("Escape");
      // Buscar en todo.
      await js(() => { S.seleccion = null; mostrarVacio(); renderArbol(); });
      await p.keyboard.press("Control+Shift+F");
      await espera();
      await p.fill("#global-buscar", "banco");
      await espera(800);
      await js(() => { const d = document.querySelector("dialog[open] details"); if (d) d.open = true; });
      await foto("52_buscar_todo");
      await cerrarDialogo();
      // Robot: configuración.
      await fila("DEMO-LLAM-002");
      await p.click("#btn-robot");
      await foto("20_config_robot");
      await cerrarDialogo();
      // Keywords: un paso nuevo en DEMO-CAN-002.
      await capitulo(1);
      await fila("DEMO-CAN-002");
      const ensayo = p.locator(".bloque:has(h3:text-is('Ensayo'))");
      await ensayo.locator("button:has-text('Añadir')").click();
      await espera();
      await p.keyboard.type("alarma");
      await espera(800);
      await js(() => { const b = [...document.querySelectorAll(".bloque h3")].find((x) => x.textContent === "Ensayo"); b.scrollIntoView(); document.querySelector(".principal").scrollTop -= 40; });
      await foto("23_keywords_sugerencias");
      await p.keyboard.press("Enter");
      await espera();
      await p.keyboard.press("End");
      await p.keyboard.type("E-210");
      await p.click(".bloque h3:text-is('Ensayo')");
      await foto("24_keywords_pasos");
      await js(() => { setDirty(false); });
      // Tablas en el contexto de una sección.
      await capitulo(2);
      await fila("Puertas");
      await foto("25_tabla_contexto");
      await p.click(".tabla-lectura, .elemento table");
      await espera();
      await p.click("td:has-text('150 N')");
      await p.keyboard.press("End");
      await foto("26_tabla_edicion");
      await js(() => { setDirty(false); });
      // Capítulo que edita otra persona.
      await capitulo(0);
      const ahora = Date.now() / 1000;
      fs.writeFileSync(`${DATOS}/yaml/pruebas/.01_ejemplo_basico.yaml.lock`, JSON.stringify({ sesion: "otra", persona: "Ana Pérez", equipo: "PC-23", desde: "2026-11-12T10:05", renovado: ahora }));
      await js(async () => { await comprobarBloqueo(true); });
      await fila("DEMO-LLAM-001");
      await foto("46_capitulo_bloqueado", { pw: { clip: { x: 0, y: 0, width: 1360, height: 480 } } });
      fs.unlinkSync(`${DATOS}/yaml/pruebas/.01_ejemplo_basico.yaml.lock`);
    },

    async requisitos() {
      await p.click("#modo-requisitos");
      await espera(1000);
      await foto("28_requisitos_panel");
      await fila("REQ-PUER-002");
      await foto("29_requisito_cambiado");
      await p.fill("#f-id", "REQ-PUER-020");
      await boton("Guardar", ".acciones");
      await foto("30_requisito_id");
      await cerrarDialogo();
      await js(() => { setDirty(false); S.seleccion = null; mostrarVacio(); renderArbol(); });
      const importar = async (archivo, anadir) => {
        await js((ruta) => { window.__falsos.importar_elegir_documento = { archivo: ruta }; }, `${DATOS}/${archivo}`);
        await p.click("#btn-menu");
        await p.click('[role="menu"] >> text=Importar desde Word');
        await espera();
        await boton("Elegir documento", "dialog[open]");
        await p.check("dialog[open] input[name='imp-tipo'][value='requisito']").catch(() => {});
        if (anadir) await p.click("dialog[open] label:has-text('Añadirlo al proyecto abierto')");
      };
      const siguiente = async () => { await boton("Siguiente", "dialog[open]"); await espera(1500); };
      // Un Word nuevo, a un proyecto nuevo.
      await importar("requisitos_botonera.docx", false);
      await foto("37_importar_documento");
      await siguiente();
      await foto("38_importar_tablas");
      await siguiente();
      await foto("39_importar_campos");
      await siguiente();
      await foto("40_importar_revisar");
      await cerrarDialogo();
      // Los requisitos del proyecto, uno cambiado.
      await importar("requisitos_revisados.docx", true);
      for (let i = 0; i < 3; i++) await siguiente();
      await foto("41_importar_existentes");
      await cerrarDialogo();
      // El Word nuevo, añadido al proyecto abierto.
      await importar("requisitos_botonera.docx", true);
      for (let i = 0; i < 3; i++) await siguiente();
      await boton("Importar", "dialog[open] .dlg-pie");
      await espera(2500);
      const ci = await js(() => S.capitulos.findIndex((c) => c.nombre.includes("botonera")));
      await capitulo(ci);
      await fila("BOT-001");
      await js(() => { const b = [...document.querySelectorAll(".bloque h3")].find((x) => x.textContent.startsWith("Tablas e imágenes")); b.scrollIntoView(); document.querySelector(".principal").scrollTop -= 120; });
      await foto("42_requisito_detalle");
      // Varios elegidos para cambiarles el nivel.
      await capitulo(0);
      await fila("REQ-LLAM-002");
      await p.click("#arbol .fila:has-text('REQ-LLAM-003')", { modifiers: ["Control"] });
      await p.click("#arbol .fila:has-text('REQ-LLAM-004')", { modifiers: ["Control"] });
      await foto("43_arbol_niveles", { pw: { clip: { x: 0, y: 48, width: 345, height: 540 } } });
    },

    async ejecucion() {
      await p.click("#modo-ejecucion");
      await espera(1000);
      await foto("08_ejecucion_inicio");
      const abrirEj = async (nombre) => { await js((c) => abrirEjecucion(c), `${DATOS}/ejecuciones/${nombre}`); await espera(1200); };
      await abrirEj("regresion_v2.3");
      await foto("10_resumen_ejecucion");
      await boton("Generar informe", ".acciones");
      await foto("14_informe_dialogo");
      await cerrarDialogo();
      await js((r) => { importarRobot(r); }, `${DATOS}/robot/resultados/output.xml`);
      await foto("18_importar_robot", { espera: 1500 });
      await cerrarDialogo();
      await boton("Ejecutar Robot", ".acciones");
      await foto("21_ejecutar_robot", { espera: 1200 });
      await cerrarDialogo();
      await js(() => {
        window.__falsos.ejecucion_robot_progreso = { en_marcha: true, codigo: null, cancelada: false, segundos: 3, total: 6,
          terminados: [{ estado: "PASS", nombre: "Llamada de cabina lleva a la planta pedida" }, { estado: "PASS", nombre: "Llamada de piso queda registrada" }],
          actual: { nombre: "Nivelación sin carga" }, output: null, consola: [] };
        seguirRobot(6);
      });
      await foto("22_progreso_robot", { espera: 1800 });
      await js(() => { window.__falsos.ejecucion_robot_progreso = null; });
      await cerrarDialogo();
      await p.click("#btn-ejecucion");
      await boton("Nueva ejecución", "dialog[open] .dlg-pie");
      await espera(800);
      await p.fill("#c-nombre", "Regresión v2.4 en torre");
      await p.selectOption("#c-entorno-pruebas", "Torre");
      await p.click("dialog[open] .ficha-filtro:text-is('regresion')").catch(() => {});
      await foto("09_nueva_ejecucion", { espera: 1200 });
      await cerrarDialogo();
      await abrirEj("2026-11-10_Torre_Luis_repeticion");
      await boton("Cerrar ejecución", ".acciones");
      await foto("13_cerrar_ejecucion");
      await cerrarDialogo();
      await abrirEj("2026-11-05_Torre_Luis");
      await foto("15_ejecucion_cerrada");
    },

    async validacion() {
      await p.click("#modo-ejecucion");
      await espera(800);
      await js((c) => abrirValidacion(c), `${DATOS}/validaciones/validacion_v2.3`);
      await espera(1500);
      await foto("32_validacion_panel");
      await js(() => irAPestanaValidacion("pruebas"));
      await boton("Desplegar todo");
      await foto("33_validacion_matriz");
      await js(() => irAPestanaValidacion("requisitos"));
      await foto("47_validacion_requisitos");
      await js(() => irAPestanaValidacion("comparacion"));
      await foto("48_validacion_comparacion");
      await boton("Generar informe", ".acciones");
      await foto("53_informe_validacion");
      await cerrarDialogo();
      await js(() => irAPestanaValidacion("resumen"));
      await js(() => irAPruebaValidacion(S.validacion.pruebas.find((x) => x.id === "DEMO-NIV-001")));
      await foto("34_validacion_prueba");
      // Cambiar de ejecución desde la ruta.
      await p.click("#btn-ejecucion");
      await foto("57_ruta_ejecuciones");
      await cerrarDialogo();
      // Triaje: DEMO-PUER-002, NO OK en la regresión y OK en la repetición.
      await api("validacion_triar", "DEMO-PUER-002", "Torre", null);
      await js(async () => { await refrescarValidacion(); await cargarNavegacion(); });
      await js(() => irAPruebaValidacion(S.validacion.pruebas.find((x) => x.id === "DEMO-PUER-002")));
      await espera(800);
      await p.fill(".triaje textarea", "El NO OK de la regresión era BUG-141; corregido en rc3, la repetición en torre da OK.");
      await js(() => { const t = document.querySelector(".triaje"); t.scrollIntoView({ block: "center" }); });
      await foto("58_triaje");
      // Pasar una prueba dentro de la validación.
      const carpeta = await js(() => S.validacion.ejecuciones.find((e) => e.nombre === "Regresión v2.3 (ejemplo)").carpeta);
      await js(([c, id]) => abrirEjecucionDeValidacion(c, id), [carpeta, "DEMO-LLAM-003"]);
      await espera(1200);
      await p.click(".estado-btn.e-no_ok");
      await p.fill("#r-observaciones", "La cabina atiende primero P1 (bajada) aunque va subiendo. Se repite 3 de 3 veces.");
      await foto("11_pasar_prueba");
      await js(() => { setDirty(false); });
      await js(() => irAPruebaEjecucion("DEMO-LLAM-001"));
      await espera(800);
      await js(() => { const d = document.querySelector("details.historial"); d.open = true; const panel = d.closest(".panel-resultado"); panel.scrollTop = panel.scrollHeight; });
      await foto("12_historial");
      // Editar la prueba desde Validar, con la pastilla para volver.
      await js(() => irAPruebaEjecucion("DEMO-LLAM-003"));
      await espera(800);
      await boton("Editar esta prueba", ".acciones");
      await espera(1200);
      await foto("59_editar_desde_validar");
    },

    async grande() {
      await p.click("#modo-ejecucion");
      await espera(800);
      await js((c) => abrirValidacion(c), `${DATOS}/grande/validaciones/v3.0`);
      await espera(4000);
      await js(() => irAPestanaValidacion("pruebas"));
      await foto("49_validacion_grande", { espera: 1500 });
    },

    async resultados() {
      await p.click("#modo-ejecucion");
      await espera(800);
      const v = await api("validacion_crear", "Validación v2.4", "Controlador DEMO-A1, firmware 2.4.0", { etiquetas: ["regresion"] }, `${DATOS}/validaciones/validacion_v2.4`);
      await js((r) => usarValidacion(r), v.datos);
      await espera(1000);
      await js((ruta) => { window.__falsos.importar_elegir_documento = { archivo: ruta }; }, `${DATOS}/resultados_torre.docx`);
      await p.click("#btn-menu");
      await p.click('[role="menu"] >> text=Importar desde Word');
      await espera();
      await boton("Elegir documento", "dialog[open]");
      await p.check("dialog[open] input[name='imp-tipo'][value='resultado']").catch(() => {});
      await boton("Siguiente", "dialog[open]"); await espera(1500);
      await boton("Siguiente", "dialog[open]"); await espera(1500);
      await js(() => { const t = [...document.querySelectorAll("dialog[open] h3, dialog[open] h4, dialog[open] strong")].find((x) => x.textContent.startsWith("Qué resultado")); if (t) t.scrollIntoView(); const c = document.querySelector("dialog[open] .dlg-cuerpo"); if (c) c.scrollTop -= 100; });
      await foto("44_resultados_valores");
      await boton("Siguiente", "dialog[open]"); await espera(1500);
      await p.fill("dialog[open] input[id*='nombre'], dialog[open] .campo:has(label:text-is('Nombre *')) input", "Regresión v2.4 en Torre").catch(() => {});
      await p.selectOption("dialog[open] select", "Torre").catch(() => {});
      await p.fill("dialog[open] .campo:has(label:text-is('Responsable')) input", "Luis Gómez").catch(() => {});
      await foto("45_resultados_revisar");
    },

    async excel() {
      await fila("DEMO-LLAM-001");
      await js(() => { S.seleccion = null; mostrarVacio(); renderArbol(); });
      const importar = async (archivo) => {
        await js((ruta) => { window.__falsos.importar_elegir_documento = { archivo: ruta }; }, `${DATOS}/${archivo}`);
        await p.click("#btn-menu");
        await p.click('[role="menu"] >> text=Importar desde Word');
        await espera();
        await boton("Elegir documento", "dialog[open]");
        await p.check("dialog[open] input[name='imp-tipo'][value='prueba']").catch(() => {});
        await p.click("dialog[open] label:has-text('Añadirlo al proyecto abierto')");
        await boton("Siguiente", "dialog[open]"); await espera(1500);
      };
      await importar("pruebas_llamadas.xlsx");
      await foto("54_excel_hojas");
      await boton("Siguiente", "dialog[open]"); await espera(1500);
      await foto("55_excel_columnas");
      await p.selectOption("dialog[open] tr:has-text('Notas') select", { label: "No importar" });
      await boton("Siguiente", "dialog[open]"); await espera(1500);
      await boton("Importar", "dialog[open] .dlg-pie");
      await espera(2500);
      await js(() => { S.seleccion = null; mostrarVacio(); renderArbol(); });
      await importar("pruebas_llamadas_luis.xlsx");
      await boton("Siguiente", "dialog[open]"); await espera(1500);
      await foto("56_excel_mapeo_proyecto");
    },
  };
  await fases[fase]();
  console.log(errores.length ? errores.join("\n") : "SIN ERRORES");
  await navegador.close();
})().catch((e) => { console.error(e); process.exit(1); });
