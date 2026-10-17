# Aztarna

**Aztarna** (en euskera, «huella, rastro») sigue el rastro de cada requisito
hasta sus pruebas y sus resultados.

Herramientas para importar la información de un documento Word a YAML, editar
las pruebas y los requisitos en un editor local, ver qué requisitos cubre cada
prueba (trazabilidad) y generar un DOCX de lectura a partir de los YAML.

```text
editor_web.py      Aztarna, el editor (python editor_web.py)
herramientas.py    las utilidades de línea de órdenes (python herramientas.py <orden>)
app/               lógica del editor, de la trazabilidad y de las ejecuciones
migracion/         importación del Word original (hasta que los YAML son la fuente oficial)
web/               interfaz del editor (HTML, CSS y JavaScript)
plantillas/        plantillas de la tabla de cada prueba y de cada requisito, y del informe de auditoría
recursos/          icono de la aplicación (y el script que lo genera)
ejemplos/          pruebas, requisitos, ejecuciones, una validación y una suite de Robot ficticios
tests/             pruebas automatizadas (python -m unittest)
docs/              capturas del manual y documentación de Robot Framework
```

| Módulo | Para qué sirve |
|---|---|
| `app/esquema.py` | Campos de las pruebas y de los requisitos, sus nombres y sus opciones (único sitio donde se definen). |
| `app/trazabilidad.py` | Cobertura de los requisitos, referencias que no existen, requisitos cambiados y matriz. |
| `app/editor_core.py` | Lectura, edición y guardado de los YAML, sin interfaz. |
| `app/editor_api.py` | API del editor que usa la interfaz de `web/`. |
| `app/ejecucion_core.py`, `app/ejecucion_api.py` | Ejecuciones: qué pruebas se pasan, en qué entorno y con qué resultado. |
| `app/validacion_core.py`, `app/validacion_api.py` | Validación de una versión: une ejecuciones y consolida por prueba y entorno. |
| `app/robot_core.py` | Robot Framework: cobertura, ejecución e importación de resultados. |
| `app/yaml_a_docx.py` | Genera el DOCX a partir de los YAML (de pruebas o de requisitos). |
| `app/informe_docx.py` | Informe de una ejecución (DOCX y, si se puede, PDF). |
| `app/informe_validacion.py` | Informe de la validación de una versión (DOCX y, si se puede, PDF). |
| `app/importacion.py`, `app/importacion_api.py` | Importar pruebas o requisitos de un Word con un mapeo de etiquetas (asistente del editor y `herramientas.py importar`). |
| `app/importacion_resultados.py` | Importar los resultados de una ejecución desde un Word con filas de resultado. |
| `app/ajustes.py` | Ajustes de este PC (última carpeta, configuración de Robot, preferencias de la interfaz). |
| `app/manual.py` | Convierte `MANUAL.md` en HTML para abrirlo dentro del editor. |
| `app/__init__.py` | Nombre y versión de la herramienta (único sitio donde se definen). |
| `migracion/convertir.py` | Importación inicial: DOCX → YAML (un archivo por capítulo). |
| `migracion/inventario.py` | Agrupa las tablas del DOCX por estructura antes de importar. |
| `migracion/auditar.py` | Comprueba que la importación no pierde texto (informe HTML y resumen sin contenido). |
| `migracion/ids_duplicados.py` | Propone y aplica IDs nuevos para pruebas con ID repetido, vacío o con espacios. |
| `construir_exe.bat` | Genera el `.exe` del editor para Windows (con el icono de `recursos/`). |
| `recursos/generar_icono.py` | Genera el icono de la aplicación (`recursos/icono.png` e `icono.ico`, `web/img/icono.png`). |

Las utilidades se ejecutan todas con `herramientas.py`:

| Orden | Hace |
|---|---|
| `python herramientas.py importar documento.docx --tipo requisito -o proyecto` | Word → proyecto (pruebas o requisitos), con el mapeo propuesto |
| `python herramientas.py convertir documento.docx -o importacion` | Word de pruebas → YAML, con avisos (importación inicial) |
| `python herramientas.py inventario documento.docx` | Agrupa las tablas del Word por estructura |
| `python herramientas.py auditar documento.docx importacion/yaml` | Comprueba que la importación no pierde texto |
| `python herramientas.py ids importacion/yaml` | Propone (y con `--aplicar`, aplica) IDs nuevos para los repetidos |
| `python herramientas.py word ruta/a/yaml -o pruebas.docx` | Genera el Word a partir de los YAML |
| `python herramientas.py informe ruta/a/ejecución --pdf` | Informe de una ejecución |
| `python herramientas.py robot ruta/a/ejecución output.xml` | Importa resultados de Robot Framework |
| `python herramientas.py trazabilidad ruta/al/proyecto` | Cobertura de los requisitos y matriz CSV |
| `python herramientas.py validacion ruta/a/la/validación --pdf` | Informe de la validación de una versión |

`python herramientas.py` sin nada lista las órdenes y `python herramientas.py
<orden> --help` explica las opciones de cada una.

El manual para quien usa el editor (sin detalles técnicos) está en
[MANUAL.md](MANUAL.md) y se abre también desde el editor (**⋯ → Manual de
usuario**). El trabajo pendiente y las propuestas están en
[PENDIENTE.md](PENDIENTE.md); las novedades de cada versión, en
[CHANGELOG.md](CHANGELOG.md).

La versión se define solo en `app/__init__.py` (`__version__`). Aparece en
la barra inferior del editor, en `python herramientas.py --version` y
`python editor_web.py --version`, en el pie de los informes y en las
propiedades de los Word generados (no en su texto). Al publicar una versión,
súbela allí y añade su entrada en `CHANGELOG.md`.

## Fuente de verdad y flujo de trabajo

El DOCX original se usa para una **importación inicial**. Después de revisar y
corregir la importación, los YAML son la fuente de verdad: las pruebas se
mantienen en YAML y el DOCX se vuelve a generar cuando se necesita una copia
legible o compartible. No se debe volver a importar el DOCX original después
de empezar a editar los YAML, porque eso puede sobrescribir los cambios o
generar una base desactualizada.

Mantén el DOCX original fuera del repositorio. Este proyecto ignora los
archivos `*.docx`, los entornos virtuales y las carpetas de resultados para
evitar subir documentos de trabajo o datos derivados accidentalmente.

## Requisitos e instalación

Se necesita Python 3.10 o posterior y pip.

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Windows (PowerShell):

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

En Linux, pywebview usa WebKitGTK a través de PyGObject (en Ubuntu, los paquetes
`python3-gi` y `gir1.2-webkit2-4.1`; si el entorno virtual no los ve, créalo con
`--system-site-packages`). En Windows usa WebView2, que viene con Windows 11 y
con Windows 10 actualizado.

## Importar desde Word (asistente)

En el editor, **⋯ → Importar desde Word…** importa pruebas, requisitos o los
resultados de una ejecución. Pasos:

1. **Documento**: qué contiene y dónde se importa (proyecto nuevo o añadido al
   abierto).
2. **Tablas**: las tablas se agrupan en familias por sus etiquetas
   (`importacion.analizar`) y se elige qué es cada familia: pruebas,
   requisitos, tabla informativa o nada.
3. **Campos**: a qué campo del esquema va cada etiqueta («Origen» → `fuente`,
   «Pasos» → `pasos`…), campo adicional, «parte del campo anterior» o nada. Se
   proponen por sinónimos y parecido; lo elegido se recuerda en los ajustes del
   PC.
4. **Revisar**: cifras, ejemplo, IDs repetidos o vacíos con un ID nuevo
   propuesto, avisos (también el texto del Word que no llega a ningún campo)
   y, al añadir al proyecto, los IDs que ya existen con sus diferencias para
   **actualizarlos** en su sitio, importarlos como nuevos u omitirlos.

Se espera la forma de las plantillas: primera fila «ID | Título» y celdas
«Etiqueta: valor». Un título con varias tablas es una sección; los títulos se
reconocen por su estilo (o el estilo en que se basan) o su nivel de esquema.
Las tablas dentro de una celda se conservan (en un requisito, en `detalle`).

**Resultados**: con un Word de pruebas con filas de resultado, se elige qué
etiqueta es el resultado, las observaciones, la incidencia, el ejecutor y la
fecha, y qué estado es cada valor escrito («Correcto» → OK, «N/A» → No
aplica…). Se crea una ejecución nueva, abierta, con las pruebas del Word que
están en el proyecto (también dentro de la validación abierta).

Lo mismo para pruebas o requisitos desde la línea de órdenes:

```bash
python herramientas.py importar documento.docx --tipo requisito                      # análisis y mapeo propuesto
python herramientas.py importar documento.docx --guardar-mapeo mapeo.json            # para revisarlo y editarlo
python herramientas.py importar documento.docx --mapeo mapeo.json -o proyecto --renombrar
```

## Importación inicial por línea de órdenes: DOCX a YAML

Es la importación del Word de pruebas con la que empezó el proyecto; se
conserva junto a `inventario`, `auditar` e `ids`. Para importar ahora, el
asistente anterior hace lo mismo (y también requisitos).

Guarda el documento Word original fuera del repositorio y ejecuta:

```bash
python herramientas.py convertir "/ruta/privada/al/documento-original.docx" -o importacion
```

En Windows, sustituye la ruta por la ruta local correspondiente. La
importación crea:

```text
importacion/
├── avisos.txt      # agrupados por tipo, con un resumen al principio
├── avisos.csv      # uno por línea (gravedad, tipo, capítulo, nº de tabla, ID), para filtrar en Excel
└── yaml/
    ├── indice.yaml
    ├── 01_nombre_del_capitulo.yaml
    └── imagenes/
```

Se genera un archivo YAML por capítulo. Las imágenes incrustadas se guardan en
`yaml/imagenes/` y se referencian desde los YAML usando rutas relativas. El
importador conserva texto contextual asociado a títulos y pruebas, y reconoce
el formato estándar y algunas variantes de formularios.

Antes de leer cada tabla, el importador decide si es una prueba:

| Clase | Criterio | Qué se hace |
|---|---|---|
| Prueba | Tiene Situación inicial / Ensayo / Situación final (o sus equivalentes) o al menos 3 campos de prueba | Pasa al esquema común (`prueba:`) |
| Dudosa | 1 o 2 campos de prueba, o la cabecera parece un ID sin campos | Se conserva como tabla y se avisa para revisarla |
| No prueba | Ningún campo de prueba (historial de cambios, parámetros…) | Se conserva tal cual (`tabla:`), sin avisos de prueba |

Las tablas que no son pruebas van donde iría un párrafo en ese punto: en el
`contexto` de la sección o de la prueba siguiente, entre su texto, o en el
capítulo si están antes del primer título. El DOCX generado las vuelve a
pintar en su sitio: el documento queda completo.
`python herramientas.py inventario documento.docx` usa la misma clasificación y resume
cuántas tablas hay de cada clase y variante, sin generar los YAML.

Los avisos indican capítulo, número de tabla en el Word e ID. Además de los
campos que faltan o las etiquetas desconocidas, se avisa de IDs vacíos,
repetidos (con la tabla donde apareció antes) o con espacios.

## Revisar y validar la importación

Antes de adoptar los YAML como datos oficiales, comprueba que no se pierde
nada con la auditoría:

```bash
python herramientas.py auditar "/ruta/privada/documento.docx" importacion/yaml -o importacion/auditoria.html
```

Compara las palabras del Word con las de los YAML, tabla a tabla y párrafo a
párrafo (sin mirar el formato ni el orden de los campos), y clasifica cada
tabla:

- ✖ **pérdida**: faltan palabras que ninguna regla quita, hay tablas dentro
  de celdas (su texto no se importa) o faltan imágenes. Hay que revisarlas.
- ⚠ **solo eliminaciones**: falta solo texto de campos que el esquema elimina
  (componente, resultado esperado, resultados…) o valores que no son una
  opción (HIL, Triplex…).
- ✔ **completa**. Las conversiones (A → Automático, S → Simplex, la
  situación final que pasa al ensayo) no cuentan como faltas.

`auditoria.html` muestra los recuentos (pruebas, tablas, imágenes, IDs), las
familias de tablas (las del inventario) y cada tabla con el original al
lado de la nueva y las palabras que faltan marcadas; marca como **muestra** la
primera, la central y la última de cada familia para revisar a ojo que cada
texto ha ido a su campo. Lleva el texto del documento: no lo compartas.
`auditoria.txt` solo tiene recuentos y estructura (familia, fila, columna y
etiqueta de las celdas con pérdidas), sin contenido.

Además:

1. Revisa `importacion/avisos.txt`, agrupando los avisos por tipo e ID; no es
   necesario asumir que cada aviso significa pérdida de datos.
2. Comprueba el número de pruebas y capítulos frente al documento original.
3. Revisa ejemplos de cada formato de tabla, incluidos formularios alternativos,
   tablas con imágenes, texto contextual y tablas que no sean pruebas.
4. Verifica que los IDs, el orden de títulos y los valores de campos sean
   correctos. Investiga los IDs duplicados: pueden ser errores o repeticiones
   intencionadas.
5. Abre las imágenes referenciadas y confirma que las rutas existen. Los EMF
   se conservan como imágenes vectoriales y el exportador puede incrustarlos en
   el DOCX.
6. Corrige los YAML importados y repite la revisión hasta que los datos sean
   aceptables.

### Corregir IDs repetidos

Las ejecuciones reconocen cada prueba por su ID, así que conviene corregir los
repetidos antes de empezar a apuntar resultados:

```bash
python herramientas.py ids importacion/yaml -o ids.csv          # propuesta
python herramientas.py ids importacion/yaml --aplicar ids.csv   # aplica lo revisado
```

`ids.csv` (se abre con Excel) tiene una fila por prueba con ID repetido, vacío
o con espacios: dónde está, su título, cuánto se parece a la primera con ese
ID («idéntica» puede ser una copia que sobra) y un `id_nuevo` propuesto. La
primera aparición conserva el ID; las demás reciben el siguiente número libre
de su serie (`LLAM_009` → `LLAM_010`), los IDs con espacios se proponen sin
ellos y los que no tienen número (`CASO DE PRUEBA`) quedan en blanco para
elegirlos. Revisa el CSV y aplícalo: solo cambia los IDs (conserva los
comentarios) y, si algún ID nuevo quedara repetido o alguna prueba ya no
está donde dice el CSV, no cambia nada y lo explica.

Trabaja primero en `importacion/`. Cuando se acepte como versión inicial,
cópiala o muévela a una ubicación de datos mantenida por el equipo. Las
carpetas de importación/exportación están ignoradas por Git; los YAML que se
quieran versionar deben guardarse en una carpeta de datos aprobada y excluir
los documentos o contenidos confidenciales.

## El editor

```bash
python editor_web.py                 # última carpeta usada, o ejemplos/yaml
python editor_web.py ruta/a/yaml     # otra carpeta
python editor_web.py --depurar       # con herramientas de desarrollo
python editor_web.py --version       # versión de la herramienta
```

Abre una ventana local: no inicia ningún servidor ni abre el navegador. El
editor modifica directamente los YAML de la carpeta (no hay base de datos
aparte) y conserva sus comentarios y su formato.

- Un único formulario para pruebas y secciones, con los campos de la tabla
  común (ver «Esquema de las pruebas») y las listas (contexto,
  parametrización, situación inicial, ensayo) como filas editables: añadir,
  quitar, reordenar (Alt+↑/↓) y sangrar. El ensayo va numerado.
- Imágenes por elemento con miniatura: botón de añadir, pegar con Ctrl+V o
  soltar archivos. Se copian a `imagenes/`. Los EMF no tienen vista previa fuera
  de Windows, pero se conservan.
- Formato en línea (negrita, cursiva, colores, resaltado) que se ve mientras se
  escribe, sin marcas a la vista. Los botones alternan: volver a pulsar
  resaltado sobre un texto resaltado lo quita; sin selección, el formato se
  aplica a lo siguiente que se escriba. Ctrl+Z / Ctrl+Y deshacen y rehacen
  texto y formato. Se guarda con las marcas que entiende `app/yaml_a_docx.py`
  (`**negrita**`, `[[rojo|…]]`, `[[res:amarillo|…]]`…).
- Reordenar y mover pruebas y secciones arrastrando en el árbol; los niveles se
  ajustan solos. Varios elementos elegidos (Ctrl+clic, Mayús+clic) se suben o
  bajan de nivel a la vez (Alt+← / Alt+→), las secciones con su contenido.
- Vista YAML con resaltado y errores señalados en la línea exacta.
- Panel de validación (IDs duplicados o vacíos, pruebas sin título, imágenes
  que faltan, valores que no son opciones del esquema, campos que ya no
  existen, saltos de nivel).
- Menú **⋯** en la barra superior: Importar desde Word, Exportar DOCX,
  Tamaño, Ajustes, manual de usuario (en una ventana aparte, generado desde
  `MANUAL.md` con la librería `markdown`, sin internet) y *Acerca de* (versión
  y ruta de los ajustes).
- **Tamaño (zoom)**: Ctrl + rueda, Ctrl + / − / 0 o *⋯ → Tamaño*, con el zoom
  nativo de WebView2 o WebKitGTK (`app/zoom.py`); se recuerda.
- **Ajustes** del PC: nombre (ejecutor y bloqueos), carpeta donde se publica
  el programa (al abrir avisa si allí hay un `version.txt` más nuevo,
  `app/actualizaciones.py`) y dirección de las incidencias con `{id}` (las
  incidencias se abren con un clic).
- **Varios a la vez**: con varios elegidos en el árbol, *Campos…* cambia tags,
  requisitos, maniobra, entorno, automatizable, versión o fecha en todos.
- **Buscar en todo** (Ctrl+Mayús+F): busca en todos los capítulos y reemplaza
  en todos los resultados, salvo en los ID.
- Lo que tarda muestra una ruleta (que se puede ocultar pasados 8 s).
- Recuerda la última carpeta abierta, el modo, la última validación y
  ejecución, el ejecutor, el ancho del panel y la última carpeta de los
  diálogos. Se guarda en los ajustes del PC (sección `interfaz`), no en el
  `localStorage` del navegador, que pywebview borra al cerrar.
- En el modo Validación, un triángulo en el árbol marca las pruebas editadas
  después de ejecutarse; el filtro *Cambiadas tras ejecutarse* las deja solas.
- Al borrar una prueba solo se elimina esa prueba. Al borrar una sección
  desaparece su encabezado, pero su contexto se conserva como texto y sus
  pruebas y subsecciones se mantienen, subidas un nivel.
- Si se cierra la ventana con cambios sin guardar, pregunta si guardar, salir
  sin guardar o seguir editando.

Varias personas pueden abrir la misma carpeta (por ejemplo, en una unidad de
red): cada capítulo lo edita una a la vez. Al primer cambio, el editor crea
junto al capítulo `.<archivo>.yaml.lock` con la persona, el PC y la hora; los
demás lo ven en solo lectura con un aviso, y el backend no guarda nunca en un
capítulo reservado por otro. La reserva se renueva cada minuto, caduca a los 5
sin renovar, se suelta al cambiar de capítulo, al cerrar o tras 15 minutos sin
cambios, y se puede forzar (`app/bloqueos.py`). Con Git, cada uno con su copia,
no se usa. Haz copias de seguridad de los YAML antes de ediciones masivas.

`web/vendor/yaml-editor.js` es un bundle precompilado de CodeMirror 6 (licencia
MIT) para la vista YAML; no hace falta Node para usar el editor. Toda la
comunicación con Python pasa por `window.pywebview.api`; las pruebas de la API
están en `tests/test_editor_api.py`.

En Linux, al cerrar el editor Ubuntu puede registrar un fallo de
`WebKitWebProcess` («corrupted double-linked list»). Es un error de la propia
WebKitGTK al apagarse, cuando el editor ya ha terminado: no se pierde nada.

### Generar el .exe de Windows

En un Windows con Python 3.10 o posterior, ejecuta `construir_exe.bat`. Crea un
entorno limpio, instala `requirements.txt` y PyInstaller, y deja
`dist\Aztarna.exe` (un solo archivo, sin consola), con el manual y sus
capturas dentro. PyInstaller no compila
de forma cruzada, así que hay que hacerlo en Windows. Los ejemplos no se
incluyen en el .exe: en el primer arranque pide una carpeta y después la
recuerda.

Cada persona usa su copia del `.exe`; los ajustes de cada una están en su PC
(`%APPDATA%\Aztarna\ajustes.json`) y los datos, en la carpeta que
abre. Al publicar una versión, reparte el `.exe` nuevo: las copias antiguas no
guardan en datos de un formato más nuevo (ver «Versión del formato de los
datos»), y el bloqueo de capítulos solo lo respetan las versiones que lo
tienen (0.10.0 o posterior).

## Requisitos y trazabilidad

Un proyecto tiene dos carpetas con el mismo formato (índice, capítulos y
secciones):

```text
proyecto/
├── pruebas/       indice.yaml, capítulos e imagenes/
└── requisitos/    indice.yaml, capítulos y revisiones.yaml
```

El editor, `trazabilidad` y `word` aceptan la carpeta del proyecto o la de
pruebas; las ejecuciones guardan la ruta de `pruebas/`. Una carpeta de pruebas
suelta (con `indice.yaml` dentro, como la que crea `convertir`) también vale:
sus requisitos van entonces en su subcarpeta `requisitos/`.

Cada requisito es un elemento `requisito:` con la tabla de
`plantillas/tabla_requisito.docx`:

```yaml
- requisito:
    nombre: ''
    nivel: 3
    id: REQ-LLAM-001
    titulo: Atención de llamadas de cabina
    descripcion: Una llamada registrada desde la botonera de cabina se atenderá…
    fuente: Cliente
    referencia: PT-DEMO-A1 v2, apartado 4.1
    tipo: Obligatorio                 # Informativo / Obligatorio / Opcional
    criterio_validacion: [Test]       # Inspección / Análisis / Test (varios)
    fase: Fase 1
    fecha: '2026-01-05'
    version: '1.0'
```

Opcionales: `detalle` (tablas, imágenes y párrafos que siguen a la descripción
dentro de su celda; salen ahí en el Word exportado y cuentan para la huella)
y `campos_adicionales` (como en las pruebas).

El enlace se guarda en un solo sitio: el campo `requisitos` de cada prueba
(lista de IDs). A partir de ahí `app/trazabilidad.py` calcula:

- **Cobertura** de cada requisito: *cubierto* (alguna prueba lo cita), *sin
  cobertura* (se valida con «Test», o no tiene criterio, y ninguna lo cita) o
  *no aplica* (informativo, o solo inspección o análisis). Resumen por capítulo
  y por sección.
- **Referencias que no existen** (pruebas que citan un ID que no está en el
  catálogo) y **pruebas sin requisito**.
- **Requisitos cambiados:** la huella de título, descripción (con su `detalle`) y contexto. Si el
  editor guarda un cambio en un requisito con pruebas, lo apunta en
  `requisitos/revisiones.yaml` con el texto revisado por última vez, hasta que
  se marcan sus pruebas como revisadas. Fecha, versión, tipo y criterio no
  cuentan como cambio.

En el editor, el modo **Requisitos** tiene el árbol con la cobertura de cada
requisito y sección, un panel de cobertura (con exportación de la matriz a
CSV), la ficha de cada requisito con las pruebas que lo cubren y el aviso de
cambio, y el cambio de ID propagado a las pruebas. En el modo Pruebas, el campo
Requisitos propone los IDs del catálogo y marca los que no existen o han
cambiado.

```bash
python herramientas.py trazabilidad ejemplos/yaml                    # resumen
python herramientas.py trazabilidad ejemplos/yaml -o matriz.csv      # y matriz para Excel
python herramientas.py word ejemplos/yaml/requisitos -o requisitos.docx
```

## Ejecuciones y validación de una versión

El editor tiene tres modos, que se eligen arriba a la izquierda: **Pruebas**
(cambiar las pruebas), **Requisitos** (cambiar los requisitos, ver la sección
anterior) y **Validación** (pasar las pruebas y unir los resultados de una
versión). En este modo los YAML de pruebas solo se leen. Hay dos niveles:

- **Ejecución**: una persona pasa un conjunto de pruebas sobre una versión y
  en un **entorno de pruebas** (Automático, Maqueta o Torre). Cada una es una
  carpeta que se guarda donde se quiera.
- **Validación**: une las ejecuciones de una versión (normalmente de varias
  personas y entornos) y da el resultado de cada prueba en cada entorno. Ver
  «Validación de una versión» más abajo.

```text
2026-11-03_Regresión_v2.3/
├── ejecucion.yaml    # datos (entorno de pruebas incluido), criterio y lista de pruebas
├── resultados.yaml   # un resultado por prueba, con su historial
└── evidencias/       # capturas y archivos adjuntos
```

**Crear una ejecución.** Botón de la ejecución → *Nueva ejecución*: nombre,
entorno de pruebas (obligatorio), qué se prueba (versión), banco o instalación,
responsable y qué pruebas entran, marcando
tags, automatizable, entorno de pruebas, maniobra o capítulos (dentro de un
grupo basta con una opción; entre grupos, todas). La
vista previa muestra las pruebas que entrarán. Después se elige la carpeta
donde guardarla y se crea una subcarpeta con la fecha y el nombre. La lista de
pruebas queda fijada; *Resincronizar* añade las que se etiqueten más tarde.

**Apuntar resultados.** El árbol muestra solo las pruebas de la ejecución, con
un punto de color por estado, y se puede filtrar por estado. Al abrir una
prueba se ve en solo lectura y, a la derecha, su resultado:

| Estado | Significado | Tecla |
|---|---|---|
| OK | Se ejecutó y el resultado es el esperado. | 1 |
| NO OK | Se ejecutó y el producto no se comporta como se espera. | 2 |
| Bloqueada | No se pudo ejecutar por algo ajeno al producto (banco, hardware, otra prueba que falló). | 3 |
| No aplica | No aplica a esta versión o configuración. | 4 |
| Pendiente | Aún sin ejecutar. | 0 |

Cada resultado admite observaciones, incidencia, ejecutor y evidencias (pegar
una captura con Ctrl+V, soltar archivos o *Añadir*; también logs u otros
archivos). **Ctrl+Intro** guarda y salta a la siguiente pendiente. Si se
apunta otro resultado, el anterior queda en el historial («NO OK con BUG-123 y
OK tras corregirlo»). Si una prueba se edita después de ejecutarse, se avisa.

**Resumen.** El botón *Resumen* (o no tener ninguna prueba seleccionada)
muestra el avance, los totales por estado, el porcentaje de OK sobre las
pruebas que aplican, el desglose por capítulo y avisos como
NO OK sin observaciones o pruebas que ya no existen.

**Cerrar e informe.** *Cerrar ejecución* exige que no quede nada pendiente,
guarda dentro de la ejecución una copia de sus pruebas tal como están
(`pruebas_congeladas/`, con secciones e imágenes) y bloquea los resultados.
Desde entonces la ejecución se revisa y se informa con esa copia, aunque los YAML
de pruebas sigan cambiando; el editor la muestra en solo lectura. *Generar
informe* crea un DOCX con el mismo aspecto que el Word de las pruebas: un resumen al
principio (datos de la ejecución, criterio, totales, desglose por capítulo,
fallos y bloqueos, avisos) y cada prueba con su resultado, observaciones,
incidencia, evidencias e intentos anteriores. Con la ejecución abierta sale
marcado como BORRADOR. El PDF se genera con LibreOffice o, en Windows, con
Microsoft Word, si están instalados. También desde la línea de comandos:

```bash
python herramientas.py informe ruta/a/la/ejecución -o informe.docx --pdf
```

**Cómo se une una ejecución con las pruebas.** La ejecución no copia las pruebas
mientras está abierta: guarda dónde están (ruta relativa a la ejecución y ruta
absoluta, y prueba las dos al abrirla) y, de cada prueba, su **ID** y una
*huella* de su contenido. Si no encuentra la carpeta de pruebas, pregunta
dónde está y lo recuerda. Por eso **los ID deben ser únicos y estables**: el
editor no deja guardar un ID repetido, la validación marca los duplicados, no
se puede crear una ejecución con IDs repetidos y, al cambiar el ID de una prueba
existente, el editor pide confirmación (para las ejecuciones, un ID nuevo es otra
prueba). Cambiar el texto, los pasos o la ubicación de una prueba no rompe
nada; si ya se había ejecutado, la ejecución avisa de que cambió.

**Pruebas automáticas (Robot Framework).** Cada test de Robot lleva la
etiqueta `id:<ID de la prueba>`. *Importar Robot…* (en el resumen de la
ejecución) o `python herramientas.py robot <ejecución> <output.xml>` apuntan sus
resultados (PASS → OK, FAIL → NO OK, SKIP → No aplica) con el log y las
capturas como evidencias. Con la carpeta de tests de Robot configurada (botón
*Robot*), el editor marca qué pruebas tienen test automático, avisa de las
`automatizable: hecho` sin test, permite filtrar ejecuciones por automatización
y lanza Robot desde la ejecución (*Ejecutar Robot…*) con el avance en vivo.
Al escribir situaciones y pasos propone las keywords de Robot (de los
`.robot`, `.resource` y librerías de Python) y marca los pasos que ya son una
keyword. Detalles en el [manual, apartado 10](MANUAL.md#10-robot-framework-guía-para-quien-escribe-los-tests).

Para probarlo: modo Validación → *Abrir ejecución…* →
`ejemplos/ejecuciones/regresion_v2.3`. Al abrir una ejecución se abre también
su carpeta de pruebas.

### Validación de una versión

La operativa habitual: cada persona hace una o dos ejecuciones (cada una en su
entorno) y después alguien las une en la validación de la versión.

```text
Validación v2.3/
└── validacion.yaml   # nombre, versión, criterio de qué pruebas hay que pasar
                      # y las rutas de sus ejecuciones (relativas y absolutas)
```

Cada prueba indica en su campo `entorno` dónde hay que pasarla y cada ejecución
en `entorno_pruebas` dónde se hizo. `app/validacion_core.py` consolida:

- por prueba y entorno vale el resultado **más reciente** de las ejecuciones de
  ese entorno; los anteriores quedan como historial;
- una prueba está **validada** con OK (o No aplica) en todos sus entornos;
  **NO OK** si falla en alguno; **bloqueada** si alguno no se pudo ejecutar;
  **pendiente** si falta alguno (planificado en una ejecución o *sin
  planificar*);
- un resultado en un entorno que la prueba no pide se muestra pero no cuenta
  (un NO OK ahí se avisa); una prueba sin entorno vale en cualquiera, con aviso;
- también avisa de pruebas que cambiaron después de ejecutarse, ejecuciones sin
  entorno y ejecuciones que no se encuentran.

En el editor: botón de la validación (barra superior) → nueva o abrir;
*Añadir ejecuciones…* (una, o todas las de una carpeta), *Nueva ejecución*
dentro de la validación y un panel con cuatro pestañas:

- **Resumen**: resultado, tabla por capítulo, ejecuciones, tabla por entorno y
  avisos;
- **Pruebas**: tabla prueba × entorno agrupada por capítulos desplegables, con
  buscador y filtro (pensada para miles de pruebas);
- **Requisitos**: verificado / fallido / bloqueado / pendiente / sin pruebas
  según sus pruebas en la validación, y *ejecución de impacto* con las pruebas
  de los requisitos cambiados;
- **Comparación**: con la validación de la versión anterior (`comparar_con` en
  `validacion.yaml`): nuevos fallos, arregladas, siguen fallando, otros
  cambios, y la evolución por versión siguiendo la cadena.

Cada prueba tiene su ficha con el historial por entorno. El informe DOCX/PDF
lleva el resumen por capítulos y, si se pide, el detalle por capítulo
(borrador mientras quede alguna ejecución abierta):

```bash
python herramientas.py validacion ejemplos/validaciones/validacion_v2.3 -o informe.docx --pdf [--solo-resumen]
python herramientas.py comparar ejemplos/validaciones/validacion_v2.2 ejemplos/validaciones/validacion_v2.3
python herramientas.py resultados ejemplos/validaciones/validacion_v2.3 -o resultados.csv   # CSV para Excel
```

La consolidación lee los YAML con una caché (`app/lectura.py`): solo vuelve a
leer los archivos que han cambiado. Con 1000 pruebas, abrir la validación por
primera vez tarda unos segundos; después, menos de medio segundo.

Las ejecuciones y las validaciones son registros (con evidencias que pesan) y
cada persona hace las suyas: mejor en una carpeta compartida que en el
repositorio Git de las pruebas.

Las carpetas con `campaña.yaml` (el nombre anterior de las ejecuciones) se
siguen leyendo.

## Edición de pruebas en YAML

Los capítulos tienen una secuencia ordenada en `contenido`. Sus elementos
actuales pueden ser secciones, pruebas o texto contextual. Las tablas que no
son pruebas (`tabla:` con sus `filas`; cada celda es un texto o un mapa con
`texto`, `imagenes` y `columnas` si ocupa varias) van dentro del `contexto`
de una sección o de una prueba, o en `contenido` si están antes del primer
título. El editor las muestra como tabla y, al hacer clic, las edita como una
cuadrícula (filas, columnas, celdas unidas, formato e imágenes):

```yaml
capitulo: Funciones básicas
contenido:
  - seccion: Llamadas
    nivel: 2
    contexto:
      - "Texto explicativo aplicable al grupo."
      - tabla:
          filas:
            - ["**Parámetro**", "**Valor**"]
            - [Velocidad nominal, 1 m/s]
  - prueba:
      nombre: Llamada de cabina
      nivel: 3
      id: LLAMADA_CAB_001
      titulo: Se valida el funcionamiento de las llamadas de cabina
      descripcion: Verificar que la llamada se atiende correctamente.
      parametrizacion:
        - "Número de paradas: 4."
      situacion_inicial:
        - Ascensor en reposo.
      pasos:                       # «Ensayo» en la tabla
        - Realizar una llamada de cabina.
        - La llamada se atiende.
      maniobra: [Simplex, Dúplex]
      automatizable: si
      entorno: [Automático, Maqueta]
      requisitos: [REQ-LLAM-001]
      etiquetas: [regresion, smoke]  # «Tags» en la tabla
      fecha: "15/10/2026"
      version: "1.2"
      contexto:
        - "Contexto que se aplica únicamente a esta prueba."
      campos_adicionales:
        Datos de prueba: Bus CAN1 a 250 kbit/s.
```

### Esquema de las pruebas

Todas las pruebas tienen los mismos campos, en el orden de la tabla de
`plantillas/tabla_prueba.docx`. Se definen en un solo sitio, `app/esquema.py`, que
usan el importador, el editor (formulario y validación), el DOCX y las
ejecuciones:

| Campo | En la tabla | Tipo |
|---|---|---|
| `id`, `titulo` | ID \| Título (cabecera verde) | texto, **obligatorios** |
| `descripcion` | Descripción | texto |
| `parametrizacion` | Parametrización | lista con viñetas |
| `situacion_inicial` | Situación inicial | lista con viñetas |
| `pasos` | Ensayo | lista numerada |
| `maniobra` | Maniobra | varias de: Simplex, Dúplex |
| `automatizable` | Automatizable | una de: si, no, corto, medio, largo, hecho |
| `entorno` | Entorno de pruebas | varias de: Automático, Maqueta, Torre |
| `requisitos` | Requisitos | lista de textos (uno por línea) |
| `etiquetas` | Tags | lista de textos (separados por comas) |
| `fecha`, `version` | Fecha \| Versión | texto |

Además, `nombre` y `nivel` (título en el documento), `contexto`,
`campos_adicionales` (filas al final de la tabla) e `imagenes`.

**Cambiar un campo para todas las pruebas.** Se cambia en `app/esquema.py` (y, si
el Word trae datos que convertir, la regla en `esquema.migrar_prueba`) y se
vuelve a importar el Word.

Al importar, el formato anterior se convierte así: *Situación final* pasa al final
del *Ensayo*; *componente*, *plataforma*, *criticidad* y *referencia* se
eliminan; *Maniobra(s)*, *Requisito(s)* y *Tags* de los campos adicionales
pasan a su campo; *Resultado esperado*, *Criterio(s) de aceptación*,
*Criterio validación*, *Observaciones* y los campos de resultado (*Ejecutor
prueba*, *Fecha ejecución*, *Resultado obtenido*, *Decisión*, *Resultado*) se
eliminan; *entorno* (A, M, T y mezclas como «A/M» o «AMT») y *maniobra*
(S, D…) pasan a opciones y lo que no encaja se descarta con un aviso.

Las listas pueden contener texto sencillo o mapas con `texto`, `nivel` e
`imagenes`. En el resto de estructuras, las imágenes se referencian mediante
`imagenes: ["imagenes/imagen_001.png"]`, relativas al directorio del YAML del
capítulo. Mantén juntos esos archivos de imagen y los YAML que los usan.

Consejos para crear una prueba:

- Copia una prueba existente del mismo tipo y actualiza el ID, títulos, campos
  y pasos.
- Usa `etiquetas` para agrupar pruebas (por ejemplo `regresion`, `smoke`,
  `seguridad`); son el criterio principal para elegir qué pruebas entran en una
  ejecución o una validación.
- Usa un ID único salvo que la repetición sea deliberada y esté documentada.
- Mantén `parametrizacion`, `situacion_inicial` y `pasos` como listas, y
  `maniobra`, `entorno`, `requisitos` y `etiquetas` como listas de textos.
- Para añadir una imagen, guarda el archivo en la carpeta de imágenes del
  capítulo y añade su ruta relativa al elemento de lista o contexto pertinente.
- Añade el capítulo al `indice.yaml` si creas un archivo de capítulo nuevo.

### Versión del formato de los datos

Para poder migrar los datos algún día, cada carpeta indica en qué formato
están (`app/formato.py`). No es la versión del programa: es un número que solo
sube cuando cambia la forma de guardar los datos.

- `pruebas/` y `requisitos/` tienen un `formato.yaml` (`formato: 1` y
  `escrito_con: Aztarna …`); no es un capítulo.
- `ejecucion.yaml` y `validacion.yaml` llevan la clave `formato`.
- Lo que no lo indica es del formato 1. Se marca al guardar.

Un programa que encuentra un formato más nuevo que el suyo deja consultar,
pero no guarda (una copia antigua no estropea datos que no entiende). Para
cambiar de formato: sube `FORMATO`, escribe la migración desde el anterior y
anótalo en `CHANGELOG.md`.

### Formato en línea

Los textos admiten estas marcas, que el editor muestra ya aplicadas y el
exportador convierte en formato de Word:

| Marca | Resultado |
|---|---|
| `**texto**` | negrita |
| `*texto*` | cursiva |
| `[[rojo\|texto]]`, `[[azul\|…]]`, `[[verde\|…]]` | color de texto |
| `[[#7030A0\|texto]]` | color hexadecimal |
| `[[res:amarillo\|texto]]`, `[[res:verde\|…]]`, `[[res:cian\|…]]` | resaltado |

## Ejemplos

El repositorio incluye datos ficticios para probar la aplicación antes de
importar el documento real. Estos ejemplos no contienen información del
documento original. `ejemplos/yaml` es un proyecto con `pruebas/` (registradas
en `pruebas/indice.yaml`) y `requisitos/`. Describen un controlador de ascensor
inventado («DEMO-A1») probado en un banco HIL:

- `pruebas/01_ejemplo_basico.yaml` (llamadas y nivelación): texto de capítulo,
  secciones en dos niveles, subpuntos con `nivel` en las listas y una imagen en
  un paso.
- `pruebas/02_ejemplo_adicionales.yaml` (bus CAN y diagnóstico): campos adicionales de
  texto, de varias líneas y de lista, contexto de prueba y todas las marcas de
  formato en línea (negrita, cursiva, colores, color hexadecimal y resaltados).
- `pruebas/03_ejemplo_secciones_imagenes.yaml` (puertas y serie de seguridad):
  secciones anidadas hasta el nivel 6 e imágenes PNG, JPG y EMF en el contexto
  de sección y de prueba, en la situación inicial, los pasos y la situación
  final, y como imágenes de la prueba.
- `pruebas/04_ejemplo_edicion_variantes.yaml` (mantenimiento y variantes): una prueba
  completa y otra casi vacía, todos los valores de `automatizable`, la clave
  antigua `imagen` y una sección vacía para practicar el arrastre en el árbol.
- `requisitos/` (dos capítulos): requisitos citados por esas pruebas, con un
  ejemplo de cada caso: sin cobertura (`REQ-LLAM-004`), informativo
  (`REQ-GEN-001`), validado por inspección (`REQ-SEG-002`) y cambiado con
  pruebas por revisar (`REQ-PUER-002`, en `revisiones.yaml`). La prueba
  `DEMO-LLAM-003` cita `REQ-COLA-001`, que no existe.

Y, en `ejemplos/`, las ejecuciones y la validación de la versión 2.3, como las
harían varias personas:

- `ejecuciones/regresion_v2.3` (Ana, Maqueta, abierta),
  `ejecuciones/2026-11-04_Robot` (resultados de Robot, Automático, cerrada),
  `ejecuciones/2026-11-05_Torre_Luis` (Torre, cerrada, con un NO OK) y
  `ejecuciones/2026-11-10_Torre_Luis_repeticion` (repite en torre la que falló).
- `validaciones/validacion_v2.3`: une las cuatro (4 validadas, 1 NO OK, 1
  bloqueada, 3 pendientes y 1 no aplica) y se compara con
  `validaciones/validacion_v2.2`, la de la versión anterior (con sus
  ejecuciones `ejecuciones/2026-10-1*_v2.2`).
- `grande/`: un proyecto de tamaño real generado por `grande/generar.py` (1000
  pruebas en 20 capítulos, 500 requisitos y las validaciones `v2.9` y `v3.0`),
  para ver el editor y los informes con muchas pruebas.
- `robot/`: una suite de Robot ficticia y sus resultados (`output.xml`).

Los ejemplos validan sin errores; el único aviso es esa referencia a un
requisito que no existe, puesta a propósito. Llevan comentarios YAML que el
editor conserva al guardar. Las imágenes son sintéticas y están en
`ejemplos/yaml/pruebas/imagenes/`. Puedes modificar los ejemplos para practicar; guarda
una copia si quieres conservar los originales.

## Generar un DOCX desde los YAML

Con el índice y los capítulos dentro de la misma carpeta:

```bash
python herramientas.py word importacion/yaml -o exportacion/pruebas.docx
```

Para generar desde un único capítulo:

```bash
python herramientas.py word importacion/yaml/02_funciones_basicas.yaml \
  -o exportacion/funciones_basicas.docx
```

Si los títulos deben empezar con otro número de capítulo:

```bash
python herramientas.py word importacion/yaml -o exportacion/pruebas.docx \
  --primer-capitulo 8
```

El DOCX generado es una salida de los YAML, no una fuente para actualizar los
datos. El exportador informa de IDs duplicados y de imágenes no encontradas;
esos avisos deben revisarse. Las imágenes EMF se incrustan directamente. El
aspecto del documento generado no pretende reproducir exactamente la plantilla
Word original.

## Pruebas automatizadas

Las pruebas están en `tests/`. Ejecútalas desde la raíz del repositorio, con
las dependencias instaladas:

```bash
python -m unittest discover -v
```

Cubren la conversión Word/YAML, la extracción y exportación de imágenes, las
funciones del núcleo (navegación jerárquica, inserción, movimiento y borrado),
la API del editor (edición, validación, imágenes, exportación y cierre), las
ejecuciones (selección, resultados, historial, evidencias, resumen), la
validación de versión (consolidación por entorno, informe), los requisitos y la
trazabilidad, la importación desde Word (familias, mapeo, niveles, ida y vuelta
Word → YAML de los ejemplos sin pérdidas, actualizar los que existen,
resultados) y que los ejemplos validan sin errores.

## Publicación del repositorio

Antes de publicar o actualizar el repositorio remoto, revisa `git status` y el
contenido preparado para asegurarte de que solo subes código y documentación no
confidenciales:

```bash
git status
git add .gitignore README.md MANUAL.md PENDIENTE.md CHANGELOG.md docs/ requirements.txt construir_exe.bat \
  editor_web.py herramientas.py app/ migracion/ web/ plantillas/ tests/ ejemplos/
git status
git commit -m "Descripción del cambio"
git push
```

No añadas el DOCX original, los resultados generados, imágenes privadas o
YAML confidenciales. Los archivos generados aparecen ignorados en
`.gitignore`; además, `inventario.txt` y las carpetas `salida/`, `importacion/`,
`exportacion/`, `build/` y `dist/` son de uso local.
