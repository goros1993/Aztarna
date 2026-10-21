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
  con avance en vivo. Detalles en el [manual, apartado 10](MANUAL.md#10-robot-framework-guía-para-quien-escribe-los-tests).
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
- **Varias personas en la misma carpeta** (versión 0.10.0, issue #7): bloqueo
  por capítulo con aviso, solo lectura, caducidad y forzar (`app/bloqueos.py`).
- **Versión del formato de los datos** (versión 0.11.0): `formato.yaml` por
  carpeta y `formato` en ejecuciones y validaciones; una copia antigua del
  programa no guarda en datos de un formato más nuevo (`app/formato.py`).
- **Validación para proyectos grandes y uso diario** (versión 0.12.0):
  pestañas y tablas por capítulos, requisitos verificados por la validación y
  ejecución de impacto, comparación con la versión anterior y evolución,
  informe con resumen y detalle por capítulo, CSV de resultados, ficha
  compacta al pasar pruebas, zoom, ajustes (nombre, versión nueva,
  incidencias), cambiar un campo en varias pruebas, buscar y reemplazar en
  todo, ruleta y caché de lectura (`app/lectura.py`).
- **Nombre: Aztarna** (versión 1.0.0): ventana, barra, ejecutable
  (`Aztarna.exe`), carpeta de ajustes, documentación y repositorio.

## Siguientes pasos

Cada tarea grande o independiente tiene su issue en GitHub
(<https://github.com/goros1993/Aztarna/issues>); el detalle, las dudas y la
discusión van allí. Aquí queda el resumen.

Ahora mismo no hay ninguno abierto.

Sin issue todavía:

| Tarea | Tamaño | Necesita |
|---|---|---|
| Bloqueos: probarlos en la unidad de red real con dos PCs; marcar en el selector de capítulos los que edita otra persona | pequeño | dos PCs |
| Probar en el `.exe` de Windows el manual dentro de la aplicación (extensiones de `markdown` empaquetadas) y el asistente de importación (selector de `.docx`, espera) | pequeño | un PC con Windows |
| Importar: compartir el mapeo con el equipo (guardar y cargar un perfil desde el asistente; hoy se recuerda en cada PC y la línea de órdenes ya lo lee y escribe) | pequeño | cuando haga falta |
| Importar: otras formas de tabla (etiqueta en una celda y valor en la siguiente; una tabla con una fila por elemento; el ID fuera de la primera celda) | medio | un Word que las use |
| Importar: mover una tabla suelta a otra familia (hoy el tipo se elige por familia) | pequeño | — |
| Importar resultados desde la línea de órdenes (hoy, solo en el editor) | pequeño | — |
| Decidir si se retiran `convertir`, `inventario` y `auditar` (la importación por familias hace lo mismo; se conservan por ahora) | — | usarla con los Word reales |
| Robot: avisar si se cierra el editor con Robot en marcha; contar en la cobertura qué pasos ya son keywords | pequeño | — |
| Requisitos: líneas base y comparación entre revisiones (nuevos, eliminados, modificados con diff, posibles renombrados) | medio | — |
| Tablas informativas: las celdas unidas en vertical se importan repetidas en cada fila, y el editor no puede unirlas en vertical | pequeño | — |
| Probar con datos reales: el enlace de incidencias con el Jira de la empresa y Robot Framework en el PC de uso | pequeño | el PC de uso |
| Repartir una ejecución entre varias personas (asignar pruebas y filtro «Mis pendientes») | medio | decidir si hace falta |
| Primera apertura de una validación grande en red (unos 4 s en local con 1000 pruebas): leer los YAML más rápido si se nota | pequeño | medirlo en la red |
| Validación de una versión: integrada en `main`; quedan los puntos «por comprobar» de más abajo al usarla con datos reales | — | usarla |

### Decisiones abiertas

- ¿Basta una prueba para dar un requisito por cubierto, o hace falta una
  marca manual de «cobertura completa» para los que necesitan varias?
- ¿Coinciden los IDs del campo `requisitos` de las pruebas con los del Word
  de requisitos? (se verá al importarlo).
- Qué campos adicionales de las pruebas pasan a formar parte del esquema.
- Qué datos se versionan en Git y cuáles van a un repositorio privado.
  Previsto: pruebas, requisitos y `aztarna.yaml` en un repositorio privado
  (cada persona con su clon); ejecuciones y validaciones en una carpeta
  compartida (manual, apartado 1).
- Cómo se reparte el programa: un solo `Aztarna.exe` en red que abren todos
  (siempre la última versión, pero no arranca sin red) o una copia en cada PC
  con el aviso de `version.txt`. Decidir con la práctica.
- Ejecuciones sin red: se crean en una carpeta local y después se copian a la
  carpeta compartida y se añaden a la validación. Ver si basta así o conviene
  algo más cómodo (p. ej., «Mover a la validación…» desde la ejecución).

## Propuestas

### Validación de una versión (primera versión)

Hecho (integrado en `main`):

- «Campaña» pasa a llamarse **ejecución** (`ejecucion.yaml`; las carpetas con
  `campaña.yaml` se siguen leyendo) y el modo del editor, **Validación**. En
  el código, variables, funciones y la API también se llaman `ejecucion`.
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
- Ejecuciones de otro PC con la carpeta de pruebas en otra ruta: se abren con
  la carpeta de pruebas abierta si tiene todas sus pruebas; si no, se pide
  una vez y se recuerda en los ajustes del PC (sin tocar `ejecucion.yaml`).
  Falta probarlo con dos PCs y un repositorio clonado en cada uno.
- Si las reglas de consolidación encajan en la práctica (sobre todo «vale el
  más reciente» y los entornos que no cuentan).
- Si hace falta que varias personas trabajen sobre la **misma** ejecución
  (repartirse sus pruebas) o basta con una ejecución por persona.
- Requisitos en la validación: un requisito verificado cuando todas sus
  pruebas están validadas (aplazado).

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
