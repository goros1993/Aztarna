# Cambios

Qué trae cada versión. La versión está en `app/__init__.py` (`__version__`) y
cada versión publicada lleva su etiqueta de Git (`v0.8.0`…).

## 1.1.0

Importar poco a poco, también desde Excel:

- **Importar desde Excel** (⋯ → *Importar desde Word o Excel…*): una fila por
  prueba o requisito y una columna por campo. Cada hoja es un grupo; las
  columnas *Capítulo* y *Sección* ordenan las filas (sin ellas, el capítulo es
  la hoja; «A > B» es una subsección); una fila sin ID ni título continúa la de
  arriba (un paso por fila); en las listas, una línea por elemento. **Plantilla
  de Excel** con una columna por campo y las opciones del proyecto en
  desplegables, desde el primer paso del asistente.
- **Importar poco a poco**: al añadir al proyecto abierto, cada capítulo va al
  que ya existe con el mismo nombre y cada prueba a su sección, sin repetir
  capítulos, textos ni secciones vacías. (Antes, cada importación añadía sus
  capítulos al final del índice.)
- Al **actualizar desde un Excel** solo cambian los campos que tienen columna;
  los demás se conservan y los campos adicionales se combinan.
- **Mapeo del proyecto** (`importacion.yaml`, junto a `aztarna.yaml`): lo
  elegido al importar se guarda en el proyecto, para que todo el equipo
  importe igual sin volver a elegir los campos. Se puede editar a mano.

Proyecto, validaciones y ejecuciones:

- **Cada ejecución y validación sabe de qué proyecto es.** El identificador del
  proyecto sale de Git (igual en todos los clones) o se guarda en su
  `aztarna.yaml`; las de antes se reconocen por sus pruebas y se les apunta al
  abrirlas.
- Al entrar en **Validación** solo se reabre la última validación o ejecución
  **del proyecto abierto**. Portada con el proyecto, su **carpeta de
  validaciones** (donde se crean y se buscan), sus validaciones y ejecuciones,
  y las de otros proyectos aparte.
- **Abrir una de otro proyecto avisa antes** (al abrirla cambian las pruebas).
  Al cambiar de carpeta de pruebas se deja la de otro proyecto que estuviera
  abierta. Los menús de recientes marcan las de otros proyectos.
- El **nombre del proyecto** se ve en la barra superior, también en
  Validación; se cambia desde la portada (`proyecto: nombre:` en
  `aztarna.yaml`).

Necesita `openpyxl` (en `requirements.txt`). Sin cambios en el formato de los
datos (sigue el 1).

**Al actualizar:** la 1.0.0 no abre un proyecto cuyo `aztarna.yaml` tenga
`proyecto:` (el nombre o la carpeta de validaciones): que todo el equipo pase
a la 1.1.0 antes de ponerlos.

## 1.0.0

Primera versión con el nombre definitivo, **Aztarna** («huella, rastro» en
euskera):

- Ventana, barra superior, «Acerca de», pies de los informes y `--version`.
- El ejecutable es `Aztarna.exe` (`construir_exe.bat`).
- Los ajustes de cada PC van en `%APPDATA%\Aztarna\ajustes.json` (variable de
  entorno `AZTARNA_AJUSTES`).
- El repositorio pasa a llamarse `Aztarna` en GitHub.
- Las opciones de **Maniobra** y **Entorno de pruebas** son de cada proyecto:
  se leen de su `aztarna.yaml` (con equivalencias para importar desde Word).
  Sin ese archivo, Maniobra no tiene opciones y Entorno usa Automático,
  Maqueta y Torre. Al cerrar una ejecución se guarda una copia con sus pruebas
  congeladas. Los ejemplos usan Simplex y Dúplex.
- En el código, «campaña» pasa a llamarse «ejecución» en todas partes
  (variables, funciones y la API de la interfaz).
- **Ejecuciones de otra persona** con las pruebas en otra ruta (cada uno con
  su copia del repositorio): se abren con tu carpeta de pruebas si tiene todas
  sus pruebas; si no, se pide la carpeta una vez y la recuerda tu PC, sin
  cambiar la ejecución para los demás.
- **Versión de las pruebas en Git**: si las pruebas están en un repositorio,
  cada ejecución apunta el commit y la etiqueta al crearla y al cerrarla (en
  su resumen y en su informe). Al crearla avisa si tu copia tiene cambios sin
  commit, y la validación avisa si sus ejecuciones se hicieron con versiones
  distintas. El manual explica cómo se organiza el equipo (apartado 1).
- README más corto; el uso del editor está en el manual.

**Al actualizar:** si tus pruebas usan Maniobra, crea un `aztarna.yaml` en
la carpeta del proyecto con sus opciones (ver el manual, apartado 9); sin
él, el editor marca esos valores como «no es una opción».

Sin cambios en el formato de los datos (sigue el 1).

## 0.12.0

Validación de una versión:

- **Pestañas** Resumen, Pruebas, Requisitos y Comparación. Las tablas van
  **por capítulos** que se despliegan, con buscador y plegar/desplegar todo,
  para trabajar con cientos o miles de pruebas; el resumen tiene una tabla por
  capítulo.
- **Requisitos en la validación**: verificado, fallido, bloqueado, pendiente
  o sin pruebas según el resultado de sus pruebas, y **ejecución de impacto**
  con las pruebas de los requisitos que han cambiado.
- **Comparar con la versión anterior** (y una ejecución con otra): nuevos
  fallos, arregladas, siguen fallando y demás cambios, y la **evolución** por
  versión. También `herramientas.py comparar`.
- **Informe** con resumen por capítulos y detalle por capítulo (opcional:
  *Incluir el detalle*, `--solo-resumen`), comparación y requisitos.
- **Resultados en Excel (CSV)** de una ejecución o una validación; también
  `herramientas.py resultados`.
- Más rápida: lo leído se guarda y solo se vuelve a leer lo que cambia; la
  validación anterior se consolida una sola vez.

Uso diario:

- **Pasar una prueba**: ficha compacta (se ven de una ensayos de 20-30 pasos),
  los cuatro resultados en una fila y más sitio para las observaciones.
- **Tamaño (zoom)**: Ctrl + rueda, Ctrl + / − / 0 y *⋯ → Tamaño*; se recuerda.
- **Ajustes** (*⋯ → Ajustes…*): tu nombre, la carpeta donde se publica el
  programa (aviso de **versión nueva** al abrir) y la dirección de las
  **incidencias** (se abren con un clic).
- **Cambiar un campo en varias pruebas** a la vez (*Campos…* con varios
  elegidos en el árbol).
- **Buscar y reemplazar en todos los capítulos** (Ctrl+Mayús+F), sin límite de
  elementos.
- **Ruleta** en todo lo que tarda, que se puede ocultar si pasa de 8 s.
- Los archivos de bloqueo no se suben a Git (se añaden al `.gitignore`).
- La guía de Robot Framework pasa al manual (apartado 10), para que vaya
  dentro del programa.
- Ejemplo grande en `ejemplos/grande`: 1000 pruebas, 500 requisitos y dos
  validaciones.

## 0.11.0

- **Versión del formato de los datos**, para poder migrarlos algún día:
  `formato.yaml` en las carpetas de pruebas y de requisitos y la clave
  `formato` en ejecuciones y validaciones (formato 1). Lo anterior cuenta como
  formato 1 y se marca al guardar.
- **Protección para copias antiguas del programa**: si los datos están en un
  formato más nuevo que el que entiende, se pueden consultar (en solo lectura,
  con un aviso), pero no se guardan.

## 0.10.0

- **Varias personas en la misma carpeta** (issue #7): cada capítulo lo edita
  una persona a la vez. Al primer cambio se reserva a su nombre; los demás lo
  ven en solo lectura con un aviso de quién lo edita y desde cuándo, y no se
  puede guardar en él. La reserva caduca si el editor se cierra mal, se suelta
  al cambiar de capítulo o tras 15 minutos sin cambios, y se puede forzar.

## 0.9.0

Importación desde Word en el editor (issues #1, #2 y #3):

- **⋯ → Importar desde Word…**: asistente en cuatro pasos (documento, tablas,
  campos, revisar) para pruebas, requisitos o los dos a la vez. Agrupa las
  tablas por sus etiquetas, propone a qué campo va cada una («Origen» →
  Fuente, «Pasos» → Ensayo…) y recuerda el mapeo elegido. También
  `herramientas.py importar`.
- Revisión antes de importar: IDs repetidos, vacíos o que ya existen (con un ID
  nuevo propuesto), ejemplo de cómo queda, avisos y texto del Word que no llega
  a ningún campo.
- **Actualizar desde un Word**: al importar en el proyecto abierto, los que ya
  existen se comparan y se elige actualizarlos, importarlos como nuevos u
  omitirlos. Un requisito actualizado con pruebas queda por revisar.
- **Resultados de una ejecución** desde un Word con filas de resultado: qué
  estado es cada valor («Correcto» → OK, «N/A» → No aplica…) y ejecución nueva
  con esas pruebas, también dentro de la validación abierta.
- Niveles bien calculados: un título con varias tablas es una sección; los
  títulos se reconocen también por su nivel de esquema o el estilo en que se
  basan.
- Requisitos: tablas e imágenes de la descripción (`detalle`) y campos
  adicionales, en el editor y en el Word exportado.
- Árbol: elegir varios elementos (Ctrl+clic, Mayús+clic) y subirlos o bajarlos
  de nivel (también Alt+← / Alt+→).
- La espera de las tareas largas se ve también dentro de los diálogos, con el
  tiempo que lleva.
- Validación: aviso cuando la ejecución abierta no forma parte de la validación
  abierta, con un botón para añadirla.

## 0.8.0

Primera versión numerada. Incluye:

- **Importación del Word de pruebas** (`herramientas.py convertir`, `inventario`,
  `auditar` e `ids`), con la tabla común de `plantillas/tabla_prueba.docx`.
- **Editor de pruebas**: formulario, formato, listas, imágenes, tablas, vista
  YAML, validación, tags y keywords de Robot propuestos, exportación a Word.
- **Requisitos y trazabilidad**: modo Requisitos, cobertura por requisito y
  sección, requisitos cambiados con pruebas por revisar, matriz CSV y Word de
  requisitos.
- **Ejecuciones** con su entorno de pruebas (Automático, Maqueta, Torre),
  resultados con historial y evidencias, cierre con pruebas congeladas e
  informe DOCX/PDF.
- **Validación de una versión**: une ejecuciones de varias personas y entornos y
  da el resultado por prueba y entorno, con informe DOCX/PDF.
- **Robot Framework**: cobertura, importación de `output.xml` y ejecución desde
  el editor.
- Las preferencias del editor (recientes, último modo, ejecutor…) se guardan
  en los ajustes del PC; los diálogos de carpeta empiezan en la última usada.
- En modo Validación, el árbol marca las pruebas cambiadas después de
  ejecutarse.
- Versión visible en el editor, en la línea de órdenes (`--version`) y en los
  documentos generados.
