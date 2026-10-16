# Trabajo pendiente

Estado del proyecto, siguientes pasos y propuestas. El uso de las
herramientas está en el [README](README.md) y en el [manual](MANUAL.md).

## Hecho

- **Importación del Word de pruebas** (`migracion/`): inventario de tablas por
  estructura, conversión con avisos (`avisos.txt` / `avisos.csv`),
  clasificación de tablas (prueba, dudosa, no prueba), auditoría sin pérdidas
  (`auditar`) y corrección de IDs repetidos (`ids`).
- **Esquema común de las pruebas** con la plantilla
  `plantillas/tabla_prueba.docx`, definido solo en `esquema.py`; el formato
  antiguo se convierte con `esquema.migrar_prueba`. Obligatorios: ID y título.
- **Editor**: formulario, formato en línea, listas, imágenes, tablas que no
  son pruebas (en el contexto, editables al hacer clic), vista YAML,
  validación, arrastre en el árbol, plegar/desplegar todo, tags y keywords de
  Robot propuestos al escribir, botón Descartar y exportación a Word con la
  plantilla.
- **Ejecuciones** (antes «campañas»): selección por tags, automatizable, entorno,
  maniobra, capítulo o Robot; resultados con historial y evidencias; huellas
  para detectar pruebas cambiadas; resincronizar; resumen con capítulos
  pulsables; cerrar (pruebas congeladas) e informe DOCX/PDF.
- **Robot Framework**: enlace por la etiqueta `id:<ID>`, cobertura en el
  editor, importar `output.xml` (RF 6 y 7), lanzar Robot desde la ejecución
  con avance en vivo. Detalles en [docs/robot.md](docs/robot.md).
- **Requisitos y trazabilidad**: esquema con `plantillas/tabla_requisito.docx`,
  proyecto con `pruebas/` y `requisitos/`, cobertura por requisito, sección y
  capítulo, referencias a requisitos que no existen, requisitos cambiados con
  pruebas por revisar (`revisiones.yaml`), modo Requisitos en el editor,
  matriz CSV, Word de requisitos y `herramientas.py trazabilidad`.
- **Validación de una versión**: ejecuciones con su entorno de pruebas
  (Automático, Maqueta, Torre), validación que las une y consolida por prueba
  y entorno, panel con la tabla prueba × entorno e informe DOCX/PDF. Detalle y
  puntos por comprobar en «Propuestas».
- **Icono** de la aplicación (`recursos/`).
- **Uso diario** (versión 0.8.0, issues #4, #5, #6 y #8): versión de la
  herramienta en el editor, `--version`, informes y propiedades de los Word
  (`CHANGELOG.md`); menú «⋯» con Exportar, manual dentro de la aplicación y
  Acerca de; triángulo en el árbol y filtro para pruebas cambiadas después de
  ejecutarse; preferencias y última carpeta de los diálogos guardadas en los
  ajustes del PC.
- **Importación desde Word en el editor** (versión 0.9.0, issues #1, #2 y #3):
  asistente con familias de tablas, mapeo de etiquetas, revisión de IDs y de
  texto no importado; pruebas, requisitos (con tablas en la descripción) y
  resultados de una ejecución; actualizar los que ya existen; niveles bien
  calculados y cambio de nivel de varios elementos desde el árbol.

## Siguientes pasos

Cada tarea grande o independiente tiene su issue en GitHub
(<https://github.com/goros1993/Validacion/issues>); el detalle, las dudas y la
discusión van allí. Aquí queda el resumen.

| Issue | Tarea | Tamaño |
|---|---|---|
| [#7](https://github.com/goros1993/Validacion/issues/7) | Evitar que dos personas editen a la vez las mismas pruebas (necesita decidir cómo se comparte la carpeta) | medio |

#7, cuando esté decidido cómo se comparten las carpetas.

Sin issue todavía:

| Tarea | Tamaño | Necesita |
|---|---|---|
| Probar en el `.exe` de Windows el manual dentro de la aplicación (extensiones de `markdown` empaquetadas) y el asistente de importación (selector de `.docx`, espera) | pequeño | un PC con Windows |
| Importar: compartir el mapeo con el equipo (guardar y cargar un perfil desde el asistente; hoy se recuerda en cada PC y la línea de órdenes ya lo lee y escribe) | pequeño | cuando haga falta |
| Importar: otras formas de tabla (etiqueta en una celda y valor en la siguiente; una tabla con una fila por elemento; el ID fuera de la primera celda) | medio | un Word que las use |
| Importar: mover una tabla suelta a otra familia (hoy el tipo se elige por familia) | pequeño | — |
| Importar resultados desde la línea de órdenes (hoy, solo en el editor) | pequeño | — |
| Decidir si se retiran `convertir`, `inventario` y `auditar` (la importación por familias hace lo mismo; se conservan por ahora) | — | usarla con los Word reales |
| Renombrar la herramienta a **Aztarna** (ver abajo) y probar el `.exe` en Windows | pequeño | un PC con Windows |
| Requisitos en la validación: verificado / fallido por requisito según sus pruebas, sección en el informe y ejecución «de impacto» con las pruebas de los requisitos cambiados | medio | — |
| Comparar validaciones o ejecuciones: nuevos fallos y arreglos respecto a la versión anterior | pequeño | — |
| Robot: avisar si se cierra el editor con Robot en marcha; contar en la cobertura qué pasos ya son keywords | pequeño | — |
| Requisitos: líneas base y comparación entre revisiones (nuevos, eliminados, modificados con diff, posibles renombrados) | medio | — |
| Tablas informativas: las celdas unidas en vertical se importan repetidas en cada fila, y el editor no puede unirlas en vertical | pequeño | — |
| Manual: rehacer la captura 22 (Robot en marcha) | pequeño | ejecutar Robot |
| Validación de una versión: integrada en `main`; quedan los puntos «por comprobar» de más abajo al usarla con datos reales | — | usarla |

### Cambio de nombre a Aztarna

Sitios con el nombre actual, para cambiarlos todos a la vez:

- **Nombre en el código**: `NOMBRE` en `app/__init__.py` (lo usan la versión,
  «Acerca de», el manual, los pies de los informes y `--version`) y el
  archivo temporal del manual (`pruebas_yaml_manual.html` en `app/manual.py`).

- **Título de la ventana**: «Editor de pruebas YAML» en `editor_web.py` (también
  su docstring y la descripción de `--help`).
- **Interfaz**: `<title>Editor de pruebas</title>` y la marca «Pruebas YAML» de la
  barra superior en `web/index.html`.
- **Ejecutable**: `EditorPruebas` en `construir_exe.bat` (→ `Aztarna.exe`) y sus
  menciones en README y MANUAL.
- **Carpeta de ajustes**: `EditorPruebasYaml` en `app/ajustes.py` y la
  variable de entorno `EDITOR_PRUEBAS_AJUSTES`. Mientras nadie use la
  herramienta no hace falta migrar nada.
- **Documentación**: títulos de README («Validación: Word y YAML») y MANUAL
  («Editor de pruebas»), la nota de nombre futuro del README y las capturas.
- **Repositorio** en GitHub (Settings → Rename); el remoto local sigue
  funcionando por la redirección.
- El icono (`recursos/generar_icono.py`: rastro de huellas que acaba en una
  marca de validación) ya está pensado para el nombre nuevo.

### Decisiones abiertas

- ¿Basta una prueba para dar un requisito por cubierto, o hace falta una
  marca manual de «cobertura completa» para los que necesitan varias?
- ¿Coinciden los IDs del campo `requisitos` de las pruebas con los del Word
  de requisitos? (se verá al importarlo).
- Qué campos adicionales de las pruebas pasan a formar parte del esquema.
- Qué datos se versionan en Git y cuáles van a un repositorio privado.

## Propuestas

### Validación de una versión (primera versión)

Hecho (integrado en `main`):

- «Campaña» pasa a llamarse **ejecución** (`ejecucion.yaml`; las carpetas con
  `campaña.yaml` se siguen leyendo) y el modo del editor, **Validación**.
- Cada ejecución indica su **entorno de pruebas** (Automático, Maqueta o
  Torre); el texto libre queda como «Banco / instalación».
- Una **validación** (`validacion.yaml`) tiene nombre, versión, su criterio de
  qué pruebas hay que pasar y la lista de ejecuciones (rutas relativas y
  absolutas; no las copia).
- Reglas: resultado por prueba y entorno; en un mismo entorno vale el más
  reciente; un entorno que la prueba no pide se muestra pero no cuenta (un
  NO OK ahí se avisa); una prueba sin entorno vale en cualquiera (con aviso);
  validada = OK (o No aplica) en todos sus entornos.
- Editor: panel de la validación (resultado, ejecuciones, por entorno, tabla
  prueba × entorno, avisos), ficha de la prueba con su historial por entorno,
  «Añadir ejecuciones…» (una o todas las de una carpeta), nueva ejecución
  dentro de la validación y vuelta desde una ejecución.
- Informe DOCX/PDF de la validación (`herramientas.py validacion`), borrador
  mientras quede alguna ejecución abierta.
- Ejemplo: cuatro ejecuciones de varias personas en `ejemplos/ejecuciones/`
  unidas en `ejemplos/validaciones/validacion_v2.3`.

Operativa prevista: cada persona hace una o dos ejecuciones en su PC; después
alguien une tres o cuatro de varias personas en una validación.

Por comprobar al usarla con datos reales:

- **Dónde viven las ejecuciones.** La validación apunta a ellas, no las copia:
  si llegan de otros PCs (USB, correo, carpeta compartida) hay que dejarlas en
  un sitio estable. Valorar una opción para **copiarlas a la carpeta de la
  validación** al añadirlas, para que el entregable quede completo y se pueda
  archivar.
- Ejecuciones de otro PC con la carpeta de pruebas en otra ruta: la
  validación usa sus propias pruebas para consolidar, pero abrir esa ejecución
  en el editor pide reubicar sus pruebas.
- Si las reglas de consolidación encajan en la práctica (sobre todo «vale el
  más reciente» y los entornos que no cuentan).
- Si hace falta que varias personas trabajen sobre la **misma** ejecución
  (repartirse sus pruebas) o basta con una ejecución por persona.
- Requisitos en la validación: un requisito verificado cuando todas sus
  pruebas están validadas (aplazado).
- En el código siguen las variables y funciones `campaña` / `campana_*`:
  renombrarlas es mecánico pero toca mucho; decidir si se hace.

### Pasos ejecutables (aplazada)

Que cada paso del YAML sea una keyword de Robot y que un generador cree los
`.robot` a partir de los YAML, para no mantener dos descripciones del mismo
test. Aplazada: reescribir cientos de pruebas en un lenguaje controlado es
demasiado trabajo por ahora. Mientras tanto, el enlace es la etiqueta `id:`,
el editor propone las keywords al escribir y marca los pasos que ya lo son.

### Descartada: pruebas en dos sitios

Se valoró una «referencia a prueba» para las pruebas que aparecen en dos
apartados. No hace falta: son pruebas distintas, con su propio ID, y el
ensayo de una cita a la otra.
