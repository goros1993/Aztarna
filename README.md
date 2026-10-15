# Validación: Word y YAML

Herramientas para importar la información de un documento Word a YAML, editar
las pruebas en un editor local y generar un DOCX de lectura a partir de los YAML.

| Archivo | Para qué sirve |
|---|---|
| `convertir.py` | Importación inicial: DOCX → YAML (un archivo por capítulo). |
| `inventario.py` | Agrupa las tablas del DOCX por estructura antes de importar. |
| `editor_web.py` | Editor de pruebas (ventana local con pywebview). |
| `editor_api.py`, `web/` | API en Python e interfaz HTML del editor. |
| `editor_core.py` | Lectura, edición y guardado de los YAML, sin interfaz. |
| `yaml_a_docx.py` | Genera el DOCX a partir de los YAML. |
| `esquema.py` | Campos de las pruebas, sus nombres y sus opciones (único sitio donde se definen). |
| `auditar.py` | Comprueba que la importación no pierde texto (informe HTML y resumen sin contenido). |
| `plantillas/tabla_prueba.docx` | Plantilla de la tabla de cada prueba (vacía, solo etiquetas). |
| `plantillas/auditoria.html` | Plantilla del informe de `auditar.py`. |
| `ejecucion_core.py`, `ejecucion_api.py` | Campañas de ejecución: qué pruebas se pasan y sus resultados. |
| `informe_docx.py` | Informe de una campaña (DOCX y, si se puede, PDF). |
| `robot_core.py`, `importar_robot.py` | Robot Framework: cobertura, ejecución e importación de resultados. |
| `ajustes.py` | Ajustes de este PC (última carpeta, configuración de Robot). |
| `construir_exe.bat` | Genera el `.exe` del editor para Windows. |
| `ejemplos/yaml/` | Capítulos ficticios para probar todo. |
| `ejemplos/ejecuciones/` | Una campaña de ejemplo a medio ejecutar. |
| `ejemplos/robot/` | Suite de Robot de ejemplo y sus resultados. |
| `tests/` | Pruebas automatizadas (`python -m unittest`). |

El manual para quien usa el editor (sin detalles técnicos) está en
[MANUAL.md](MANUAL.md). El trabajo pendiente y las propuestas están en
[PENDIENTE.md](PENDIENTE.md).

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

## Importación inicial: DOCX a YAML

Guarda el documento Word original fuera del repositorio y ejecuta:

```bash
python convertir.py "/ruta/privada/al/documento-original.docx" -o importacion
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
`python inventario.py documento.docx` usa la misma clasificación y resume
cuántas tablas hay de cada clase y variante, sin generar los YAML.

Los avisos indican capítulo, número de tabla en el Word e ID. Además de los
campos que faltan o las etiquetas desconocidas, se avisa de IDs vacíos,
repetidos (con la tabla donde apareció antes) o con espacios.

## Revisar y validar la importación

Antes de adoptar los YAML como datos oficiales, comprueba que no se pierde
nada con `auditar.py`:

```bash
python auditar.py "/ruta/privada/documento.docx" importacion/yaml -o importacion/auditoria.html
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
familias de tablas (las de `inventario.py`) y cada tabla con el original al
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

Trabaja primero en `importacion/`. Cuando se acepte como versión inicial,
cópiala o muévela a una ubicación de datos mantenida por el equipo. Las
carpetas de importación/exportación están ignoradas por Git; los YAML que se
quieran versionar deben guardarse en una carpeta de datos aprobada y excluir
los documentos o contenidos confidenciales.

## Editor de pruebas

```bash
python editor_web.py                 # última carpeta usada, o ejemplos/yaml
python editor_web.py ruta/a/yaml     # otra carpeta
python editor_web.py --depurar       # con herramientas de desarrollo
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
  texto y formato. Se guarda con las marcas que entiende `yaml_a_docx.py`
  (`**negrita**`, `[[rojo|…]]`, `[[res:amarillo|…]]`…).
- Reordenar y mover pruebas y secciones arrastrando en el árbol; los niveles se
  ajustan solos.
- Vista YAML con resaltado y errores señalados en la línea exacta.
- Panel de validación (IDs duplicados o vacíos, pruebas sin título, imágenes
  que faltan, valores que no son opciones del esquema, campos que ya no
  existen, saltos de nivel) y botón **Exportar DOCX**.
- Recuerda la última carpeta abierta.
- Al borrar una prueba solo se elimina esa prueba. Al borrar una sección
  desaparece su encabezado, pero su contexto se conserva como texto y sus
  pruebas y subsecciones se mantienen, subidas un nivel.
- Si se cierra la ventana con cambios sin guardar, pregunta si guardar, salir
  sin guardar o seguir editando.

El editor está pensado para un usuario de confianza en el mismo equipo. Haz
copias de seguridad de los YAML antes de ediciones masivas.

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
`dist\EditorPruebas.exe` (un solo archivo, sin consola). PyInstaller no compila
de forma cruzada, así que hay que hacerlo en Windows. Los ejemplos no se
incluyen en el .exe: en el primer arranque pide una carpeta y después la
recuerda.

## Ejecución de pruebas (campañas)

El editor tiene dos modos, que se eligen arriba a la izquierda: **Edición**
(cambiar las pruebas) y **Ejecución** (apuntar sus resultados). En ejecución
los YAML de pruebas solo se leen: los resultados se guardan en la carpeta de
una *campaña*, que cada uno guarda donde quiera en su PC.

```text
2026-11-03_Regresión_v2.3/
├── campaña.yaml      # datos, criterio de selección y lista de pruebas
├── resultados.yaml   # un resultado por prueba, con su historial
└── evidencias/       # capturas y archivos adjuntos
```

**Crear una campaña.** Botón de la campaña → *Nueva campaña*: nombre, qué se
prueba (versión), entorno, responsable y qué pruebas entran, marcando
tags, automatizable, entorno de pruebas, maniobra o capítulos (dentro de un
grupo basta con una opción; entre grupos, todas). La
vista previa muestra las pruebas que entrarán. Después se elige la carpeta
donde guardarla y se crea una subcarpeta con la fecha y el nombre. La lista de
pruebas queda fijada; *Resincronizar* añade las que se etiqueten más tarde.

**Apuntar resultados.** El árbol muestra solo las pruebas de la campaña, con
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

**Cerrar e informe.** *Cerrar campaña* exige que no quede nada pendiente,
guarda dentro de la campaña una copia de sus pruebas tal como están
(`pruebas_congeladas/`, con secciones e imágenes) y bloquea los resultados.
Desde entonces la campaña se revisa y se informa con esa copia, aunque los YAML
de pruebas sigan cambiando; el editor la muestra en solo lectura. *Generar
informe* crea un DOCX con el mismo aspecto que `yaml_a_docx.py`: un resumen al
principio (datos de la campaña, criterio, totales, desglose por capítulo,
fallos y bloqueos, avisos) y cada prueba con su resultado, observaciones,
incidencia, evidencias e intentos anteriores. Con la campaña abierta sale
marcado como BORRADOR. El PDF se genera con LibreOffice o, en Windows, con
Microsoft Word, si están instalados. También desde la línea de comandos:

```bash
python informe_docx.py ruta/a/la/campaña -o informe.docx --pdf
```

**Cómo se une una campaña con las pruebas.** La campaña no copia las pruebas
mientras está abierta: guarda dónde están (ruta relativa a la campaña y ruta
absoluta, y prueba las dos al abrirla) y, de cada prueba, su **ID** y una
*huella* de su contenido. Si no encuentra la carpeta de pruebas, pregunta
dónde está y lo recuerda. Por eso **los ID deben ser únicos y estables**: el
editor no deja guardar un ID repetido, la validación marca los duplicados, no
se puede crear una campaña con IDs repetidos y, al cambiar el ID de una prueba
existente, el editor pide confirmación (para las campañas, un ID nuevo es otra
prueba). Cambiar el texto, los pasos o la ubicación de una prueba no rompe
nada; si ya se había ejecutado, la campaña avisa de que cambió.

**Pruebas automáticas (Robot Framework).** Cada test de Robot lleva la
etiqueta `id:<ID de la prueba>`. *Importar Robot…* (en el resumen de la
campaña) o `python importar_robot.py <campaña> <output.xml>` apuntan sus
resultados (PASS → OK, FAIL → NO OK, SKIP → No aplica) con el log y las
capturas como evidencias. Con la carpeta de tests de Robot configurada (botón
*Robot*), el editor marca qué pruebas tienen test automático, avisa de las
`automatizable: hecho` sin test, permite filtrar campañas por automatización
y lanza Robot desde la campaña (*Ejecutar Robot…*) con el avance en vivo.
Al escribir situaciones y pasos propone las keywords de Robot (de los
`.robot`, `.resource` y librerías de Python) y marca los pasos que ya son una
keyword. Detalles en [docs/robot.md](docs/robot.md).

Para probarlo: modo Ejecución → *Abrir campaña…* →
`ejemplos/ejecuciones/regresion_v2.3`. Al abrir una campaña se abre también
su carpeta de pruebas.

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
`plantillas/tabla_prueba.docx`. Se definen en un solo sitio, `esquema.py`, que
usan el importador, el editor (formulario y validación), el DOCX y las
campañas:

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

**Cambiar un campo para todas las pruebas.** Se cambia en `esquema.py` (y, si
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
  campaña de ejecución.
- Usa un ID único salvo que la repetición sea deliberada y esté documentada.
- Mantén `parametrizacion`, `situacion_inicial` y `pasos` como listas, y
  `maniobra`, `entorno`, `requisitos` y `etiquetas` como listas de textos.
- Para añadir una imagen, guarda el archivo en la carpeta de imágenes del
  capítulo y añade su ruta relativa al elemento de lista o contexto pertinente.
- Añade el capítulo al `indice.yaml` si creas un archivo de capítulo nuevo.

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
documento original y están registrados en `ejemplos/yaml/indice.yaml`. Describen
un controlador de ascensor inventado («DEMO-A1») probado en un banco HIL:

- `01_ejemplo_basico.yaml` (llamadas y nivelación): texto de capítulo,
  secciones en dos niveles, subpuntos con `nivel` en las listas y una imagen en
  un paso.
- `02_ejemplo_adicionales.yaml` (bus CAN y diagnóstico): campos adicionales de
  texto, de varias líneas y de lista, contexto de prueba y todas las marcas de
  formato en línea (negrita, cursiva, colores, color hexadecimal y resaltados).
- `03_ejemplo_secciones_imagenes.yaml` (puertas y serie de seguridad):
  secciones anidadas hasta el nivel 6 e imágenes PNG, JPG y EMF en el contexto
  de sección y de prueba, en la situación inicial, los pasos y la situación
  final, y como imágenes de la prueba.
- `04_ejemplo_edicion_variantes.yaml` (mantenimiento y variantes): una prueba
  completa y otra casi vacía, todos los valores de `automatizable`, la clave
  antigua `imagen` y una sección vacía para practicar el arrastre en el árbol.

Los ejemplos validan sin errores ni avisos y llevan comentarios YAML que el
editor conserva al guardar. Las imágenes son sintéticas y están en
`ejemplos/yaml/imagenes/`. Puedes modificar los ejemplos para practicar; guarda
una copia si quieres conservar los originales.

## Generar un DOCX desde los YAML

Con el índice y los capítulos dentro de la misma carpeta:

```bash
python yaml_a_docx.py importacion/yaml -o exportacion/pruebas.docx
```

Para generar desde un único capítulo:

```bash
python yaml_a_docx.py importacion/yaml/02_funciones_basicas.yaml \
  -o exportacion/funciones_basicas.docx
```

Si los títulos deben empezar con otro número de capítulo:

```bash
python yaml_a_docx.py importacion/yaml -o exportacion/pruebas.docx \
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
campañas de ejecución (selección, resultados, historial, evidencias, resumen)
y que los ejemplos validan sin errores.

## Publicación del repositorio

Antes de publicar o actualizar el repositorio remoto, revisa `git status` y el
contenido preparado para asegurarte de que solo subes código y documentación no
confidenciales:

```bash
git status
git add .gitignore README.md MANUAL.md PENDIENTE.md docs/ requirements.txt construir_exe.bat \
  convertir.py inventario.py yaml_a_docx.py \
  editor_core.py editor_api.py editor_web.py web/ \
  ejecucion_core.py ejecucion_api.py informe_docx.py robot_core.py importar_robot.py ajustes.py \
  tests/ ejemplos/
git status
git commit -m "Descripción del cambio"
git push
```

No añadas el DOCX original, los resultados generados, imágenes privadas o
YAML confidenciales. Los archivos generados aparecen ignorados en
`.gitignore`; además, `inventario.txt` y las carpetas `salida/`, `importacion/`,
`exportacion/`, `build/` y `dist/` son de uso local.
