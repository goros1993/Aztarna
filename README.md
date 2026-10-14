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
| `ejecucion_core.py` | Campañas de ejecución: selección de pruebas y resultados (en desarrollo). |
| `construir_exe.bat` | Genera el `.exe` del editor para Windows. |
| `ejemplos/yaml/` | Capítulos ficticios para probar todo. |
| `test_*.py` | Pruebas automatizadas. |

El trabajo pendiente y las propuestas están en [PENDIENTE.md](PENDIENTE.md).

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
├── avisos.txt
└── yaml/
    ├── indice.yaml
    ├── 01_nombre_del_capitulo.yaml
    └── imagenes/
```

Se genera un archivo YAML por capítulo. Las imágenes incrustadas se guardan en
`yaml/imagenes/` y se referencian desde los YAML usando rutas relativas. El
importador conserva texto contextual asociado a títulos y pruebas, y reconoce
el formato estándar y algunas variantes de formularios.

> **Limitación conocida:** el importador aún no clasifica de forma fiable las
> tablas que no son pruebas. Algunas tablas informativas pueden producir
> avisos o acabar interpretadas como pruebas. No consideres la importación
> completa hasta revisar esos casos y confirmar que no falta información.

## Revisar y validar la importación

Antes de adoptar los YAML como datos oficiales:

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

- Un único formulario para pruebas y secciones, con las listas (situación
  inicial, pasos, situación final, contexto) como filas editables: añadir,
  quitar, reordenar (Alt+↑/↓) y sangrar. Los pasos van numerados.
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
- Panel de validación (IDs duplicados, imágenes que faltan, pruebas sin título
  o sin pasos, saltos de nivel) y botón **Exportar DOCX**.
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
están en `test_editor_api.py`.

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

## Edición de pruebas en YAML

Los capítulos tienen una secuencia ordenada en `contenido`. Sus elementos
actuales pueden ser secciones, pruebas o texto contextual:

```yaml
capitulo: Funciones básicas
contenido:
  - seccion: Llamadas
    nivel: 2
    contexto:
      - "Texto explicativo aplicable al grupo."
  - prueba:
      nombre: Llamada de cabina
      nivel: 3
      id: LLAMADA_CAB_001
      titulo: Se valida el funcionamiento de las llamadas de cabina
      descripcion: Verificar que la llamada se atiende correctamente.
      componente: CPU_A
      plataforma: HIL
      situacion_inicial:
        - Ascensor en reposo.
      pasos:
        - Realizar una llamada de cabina.
      situacion_final:
        - La llamada se atiende.
      automatizable: si
      criticidad: ""
      entorno: HIL
      referencia: ""
      fecha: ""
      version: ""
      etiquetas: [regresion, smoke]
      contexto:
        - "Contexto que se aplica únicamente a esta prueba."
      campos_adicionales:
        Resultado esperado: La llamada se atiende.
```

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
- Mantén `situacion_inicial`, `pasos` y `situacion_final` como listas.
- Conserva los campos adicionales con su significado; no mezcles el resultado
  esperado con la situación final salvo que el modelo del equipo lo defina así.
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

Ejecuta las pruebas con las dependencias instaladas:

```bash
python -m unittest discover -v
```

Cubren la conversión Word/YAML, la extracción y exportación de imágenes, las
funciones del núcleo (navegación jerárquica, inserción, movimiento y borrado),
la API del editor (edición, validación, imágenes, exportación y cierre) y que
los capítulos de ejemplo validan sin errores.

## Publicación del repositorio

Antes de publicar o actualizar el repositorio remoto, revisa `git status` y el
contenido preparado para asegurarte de que solo subes código y documentación no
confidenciales:

```bash
git status
git add .gitignore README.md PENDIENTE.md requirements.txt construir_exe.bat \
  convertir.py inventario.py yaml_a_docx.py \
  editor_core.py editor_api.py editor_web.py web/ \
  test_conversion.py test_editor_core.py test_editor_api.py ejemplos/
git status
git commit -m "Descripción del cambio"
git push
```

No añadas el DOCX original, los resultados generados, imágenes privadas o
YAML confidenciales. Los archivos generados aparecen ignorados en
`.gitignore`; además, `inventario.txt` y las carpetas `salida/`, `importacion/`,
`exportacion/`, `build/` y `dist/` son de uso local.
