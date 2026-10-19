# Aztarna

**Aztarna** (en euskera, «huella, rastro») sigue el rastro de cada requisito
hasta sus pruebas y sus resultados.

Las pruebas y los requisitos se guardan en YAML y se editan con un editor
local. Con ellos se ve qué requisitos cubre cada prueba, se pasan las pruebas
(ejecuciones), se unen los resultados de una versión (validación) y se
generan los Word y los informes. Un asistente importa los datos iniciales
desde Word.

El uso del editor se explica en el [manual de usuario](MANUAL.md), que
también se abre desde el editor (**⋯ → Manual de usuario**). Las novedades
están en el [CHANGELOG](CHANGELOG.md) y el trabajo pendiente, en
[PENDIENTE.md](PENDIENTE.md).

## Instalación

Hace falta Python 3.10 o posterior.

```bash
python3 -m venv .venv
source .venv/bin/activate            # Windows: .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

En Linux, pywebview usa WebKitGTK a través de PyGObject (en Ubuntu, los
paquetes `python3-gi` y `gir1.2-webkit2-4.1`; si el entorno virtual no los
ve, créalo con `--system-site-packages`). En Windows usa WebView2, que viene
con Windows 10 y 11.

## Uso

```bash
python editor_web.py                 # el editor (última carpeta usada, o ejemplos/yaml)
python editor_web.py ruta/al/proyecto
python editor_web.py --depurar       # con herramientas de desarrollo
```

El editor es una ventana local: no arranca ningún servidor ni abre el
navegador. Cambia directamente los YAML de la carpeta y conserva sus
comentarios y su formato.

Las demás utilidades se ejecutan con `herramientas.py` (`python
herramientas.py` las lista y `<orden> --help` explica sus opciones):

| Orden | Hace |
|---|---|
| `importar documento.docx -o proyecto` | Word o Excel → proyecto nuevo (pruebas o requisitos), con el mapeo propuesto |
| `convertir documento.docx -o importacion` | Importación inicial del Word de pruebas, con avisos |
| `inventario documento.docx` | Agrupa las tablas del Word por estructura |
| `auditar documento.docx importacion/yaml` | Comprueba que la importación no pierde texto |
| `ids importacion/yaml` | Propone (y con `--aplicar`, aplica) IDs nuevos para los repetidos |
| `word ruta/a/pruebas -o pruebas.docx` | Genera el Word a partir de los YAML |
| `trazabilidad ruta/al/proyecto -o matriz.csv` | Cobertura de los requisitos y matriz |
| `informe ruta/a/la/ejecución --pdf` | Informe de una ejecución |
| `robot ruta/a/la/ejecución output.xml` | Importa resultados de Robot Framework |
| `validacion ruta/a/la/validación --pdf` | Informe de la validación de una versión |
| `comparar anterior actual` | Compara dos validaciones (o dos ejecuciones) |
| `resultados ruta/a/la/validación` | Resultados en CSV para Excel |

## Los datos

```text
proyecto/
├── aztarna.yaml   nombre y carpeta de validaciones del proyecto, y opciones de maniobra y entorno (opcional)
├── importacion.yaml  cómo se importan sus Word y Excel (lo escribe el asistente; opcional)
├── pruebas/       indice.yaml, un YAML por capítulo, imagenes/ y formato.yaml
└── requisitos/    lo mismo, y revisiones.yaml (requisitos cambiados)

2026-11-03_Regresión_v2.3/      una ejecución, en cualquier carpeta
├── ejecucion.yaml              datos, criterio y lista de pruebas (ID y huella)
├── resultados.yaml             un resultado por prueba, con su historial
├── evidencias/
└── pruebas_congeladas/         copia de sus pruebas al cerrarla

Validación v2.3/
└── validacion.yaml             versión, criterio y rutas de sus ejecuciones
```

- Los **YAML son la fuente de verdad**. El Word original solo se usa para la
  importación inicial; después, el Word se genera desde los YAML.
- Cada capítulo tiene una lista ordenada `contenido` con secciones, pruebas
  (`prueba:`), requisitos (`requisito:`) y texto o tablas de contexto.
- Una prueba cita sus requisitos en su campo `requisitos`. Es el único enlace:
  la cobertura y la matriz se calculan a partir de él (`app/trazabilidad.py`).
- Las ejecuciones reconocen cada prueba por su **ID**, así que debe ser único
  y estable. La *huella* del contenido avisa de las pruebas que cambian
  después de ejecutarse.
- Lo previsto es tener `proyecto/` en un repositorio de Git (cada persona con
  su clon) y las ejecuciones y validaciones en una carpeta compartida. Si las
  pruebas están en Git, cada ejecución guarda el commit y la etiqueta al
  crearla y al cerrarla (`git` y `git_cierre`, `app/git_pruebas.py`). La
  validación avisa si sus ejecuciones usan versiones distintas.
- Cada ejecución y validación guarda **de qué proyecto es** (`proyecto:` con
  `id` y `nombre`, `app/proyecto.py`). El identificador sale de Git (el primer
  commit del repositorio y la subcarpeta del proyecto, igual en todos los
  clones) o, sin Git, se genera y se escribe en `aztarna.yaml`. En el modo
  Validación solo se ofrece lo del proyecto abierto; abrir lo de otro pide
  confirmación. `aztarna.yaml` puede indicar el `nombre` del proyecto y su
  carpeta de `validaciones` (donde se crean y se buscan).
- Cada carpeta indica la versión del formato de sus datos (`formato.yaml`, o la
  clave `formato` en `ejecucion.yaml` y `validacion.yaml`; `app/formato.py`).
  Una copia antigua del programa abre unos datos más nuevos, pero no los guarda.
- Las carpetas con `campaña.yaml` (el nombre anterior de las ejecuciones) se
  siguen leyendo.

### Esquema de las pruebas

Los campos, sus nombres y sus opciones se definen solo en `app/esquema.py`.
Lo usan el importador, el editor, el Word y las ejecuciones. La tabla de cada
prueba sigue `plantillas/tabla_prueba.docx`:

| Campo | En la tabla | Tipo |
|---|---|---|
| `id`, `titulo` | ID \| Título | texto, obligatorios |
| `descripcion` | Descripción | texto |
| `parametrizacion`, `situacion_inicial` | Parametrización, Situación inicial | listas |
| `pasos` | Ensayo | lista numerada |
| `maniobra`, `entorno` | Maniobra, Entorno de pruebas | varias opciones (las del proyecto) |
| `automatizable` | Automatizable | si, no, corto, medio, largo o hecho |
| `requisitos`, `etiquetas` | Requisitos, Tags | listas de textos |
| `fecha`, `version` | Fecha \| Versión | texto |

Además: `nombre` y `nivel` (título en el documento), `contexto`,
`campos_adicionales` e `imagenes`. Los requisitos siguen
`plantillas/tabla_requisito.docx` (`fuente`, `referencia`, `tipo`,
`criterio_validacion`, `fase`, `detalle`…). Los textos admiten formato en
línea: `**negrita**`, `*cursiva*`, `[[rojo|texto]]`, `[[#7030A0|texto]]` y
`[[res:amarillo|texto]]`.

### Opciones del proyecto (`aztarna.yaml`)

Las opciones de maniobra y de entorno dependen de cada organización, así que
no están en el código. Las da el `aztarna.yaml` del proyecto:

```yaml
opciones:
  maniobra: [Simplex, Dúplex]
  entorno: [Automático, Maqueta, Torre]
equivalencias:                 # otras formas de escribirlas en el Word
  maniobra: {S: Simplex, D: Dúplex}
```

Sin el archivo, maniobra no tiene opciones y entorno usa Automático, Maqueta
y Torre (con A, M y T como equivalencias). Al comparar no cuentan las
mayúsculas, las tildes ni los espacios. El editor lo lee al abrir la carpeta.
Un proyecto nuevo importado desde el editor copia el del proyecto abierto, y
al cerrar una ejecución se guarda una copia con sus pruebas congeladas. En
línea de órdenes, `convertir`, `auditar` e `importar` admiten
`--configuracion aztarna.yaml`.

## Importar desde Word o Excel

El asistente del editor (**⋯ → Importar desde Word o Excel…**) o la orden
`importar` cubren lo habitual: proponen qué es cada familia de tablas (o cada
hoja del Excel) y a qué campo va cada etiqueta (o columna). Lo elegido se
guarda en el `importacion.yaml` del proyecto (`app/mapeo_importacion.py`), para
que todo el equipo importe igual, y en los ajustes del PC.

- **Excel** (`app/importacion_excel.py`): una fila por elemento y una columna
  por campo, con columnas de capítulo y sección; una fila sin ID ni título
  continúa la de arriba. La plantilla se descarga desde el asistente. Al
  actualizar desde un Excel solo cambian los campos que tienen columna.
- **Poco a poco**: al añadir al proyecto abierto, cada capítulo importado va al
  que ya existe con el mismo nombre, en su sección (`importacion.unir_capitulo`).

La importación con la que empezó el proyecto se conserva como `convertir` +
`auditar` + `ids`:

```bash
python herramientas.py convertir "/ruta/privada/original.docx" -o importacion --configuracion aztarna.yaml
python herramientas.py auditar "/ruta/privada/original.docx" importacion/yaml -o importacion/auditoria.html
python herramientas.py ids importacion/yaml -o ids.csv          # revisar y después --aplicar ids.csv
```

`auditar` compara las palabras del Word con las de los YAML, tabla a tabla,
y separa las pérdidas reales de lo que el esquema elimina o convierte a
propósito. `auditoria.html` lleva el texto del documento: no lo compartas
(`auditoria.txt` solo tiene recuentos).

## Ejemplos

`ejemplos/` tiene datos ficticios de un controlador de ascensor inventado
(«DEMO-A1»):

- `yaml/`: un proyecto con pruebas, requisitos y su `aztarna.yaml`. Valida sin
  errores; el único aviso es una referencia a un requisito que no existe,
  puesta a propósito.
- `ejecuciones/` y `validaciones/`: las ejecuciones y la validación de las
  versiones 2.2 y 2.3, como las harían varias personas.
- `grande/`: un proyecto de tamaño real (1000 pruebas y 500 requisitos)
  generado por `grande/generar.py`.
- `robot/`: una suite de Robot Framework y sus resultados.

## Desarrollo

```text
editor_web.py      el editor
herramientas.py    las órdenes de línea de órdenes
app/               lógica (esquema, editor, trazabilidad, ejecuciones, validación, informes, importación)
web/               interfaz del editor (HTML, CSS y JavaScript, sin compilar)
migracion/         importación inicial del Word original
plantillas/        tablas de prueba y de requisito, e informe de auditoría
tests/             python -m pytest
docs/manual/       capturas del manual
```

- La versión se define solo en `app/__init__.py`. Al publicar una versión,
  súbela allí, añade su entrada en `CHANGELOG.md` y sube la etiqueta
  (`git tag v1.1.0` y `git push origin v1.1.0`). GitHub Actions construye el
  .exe en Windows, pasa los tests allí y publica la Release con `Aztarna.exe`,
  `version.txt` y la entrada del CHANGELOG (`.github/workflows/exe.yml`; falla
  sin publicar si la etiqueta no coincide con la versión o falta la entrada).
  Los tests pasan además en cada push a `main` y en cada PR (`ci.yml`).
- `web/vendor/yaml-editor.js` es CodeMirror 6 precompilado (licencia MIT): no
  hace falta Node. La interfaz habla con Python a través de
  `window.pywebview.api`.
- **.exe de Windows**: `construir_exe.bat`, en Windows, deja
  `dist\Aztarna.exe` con el manual dentro. Cada persona guarda sus ajustes en
  `%APPDATA%\Aztarna\ajustes.json`.
- Varias personas pueden abrir la misma carpeta en una unidad de red: cada
  capítulo lo edita una a la vez (`.<archivo>.yaml.lock`, `app/bloqueos.py`).
- En Linux, Ubuntu puede registrar un fallo de `WebKitWebProcess` al cerrar
  el editor. Es de WebKitGTK al apagarse y no se pierde nada.

**Datos confidenciales.** No subas al repositorio el Word original, los
informes, las ejecuciones reales ni el `aztarna.yaml` de tu organización.
`.gitignore` excluye los `*.docx` (salvo las plantillas) y las carpetas
`salida/`, `importacion/`, `exportacion/`, `build/` y `dist/`. Revisa
`git status` antes de cada commit.
