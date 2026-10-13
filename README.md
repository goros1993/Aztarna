# Validación: Word y YAML

Herramientas para importar la información de un documento Word a YAML y
generar un DOCX de lectura a partir de los YAML.

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

El editor de escritorio usa Tkinter, que no se instala mediante pip. En Ubuntu
instala el módulo del sistema con:

```bash
sudo apt-get install python3-tk
```

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
python -m tkinter
python editor_yaml.py
```

El instalador oficial de Python para Windows normalmente incluye Tkinter
(opción **Tcl/Tk and IDLE**); no se añade con `pip` ni aparece en
`requirements.txt`. `python -m tkinter` debe abrir una ventana de prueba. Si
falla, modifica o repara la instalación de Python y asegúrate de incluir
**Tcl/Tk and IDLE**. Cuando funcione, `python editor_yaml.py` abre el editor de
escritorio sin iniciar un servidor.

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
- Usa un ID único salvo que la repetición sea deliberada y esté documentada.
- Mantén `situacion_inicial`, `pasos` y `situacion_final` como listas.
- Conserva los campos adicionales con su significado; no mezcles el resultado
  esperado con la situación final salvo que el modelo del equipo lo defina así.
- Para añadir una imagen, guarda el archivo en la carpeta de imágenes del
  capítulo y añade su ruta relativa al elemento de lista o contexto pertinente.
- Añade el capítulo al `indice.yaml` si creas un archivo de capítulo nuevo.

## Editor de escritorio local

Para crear, buscar y editar pruebas con formularios, ejecuta desde la carpeta
del proyecto:

```bash
python editor_yaml.py
```

El editor abre una ventana de escritorio; no inicia un servidor ni requiere
Streamlit. Necesita Python con Tkinter instalado (en Ubuntu se proporciona con
`python3-tk`) y las dependencias de `requirements.txt`. La carpeta inicial es
`ejemplos/yaml`; puedes seleccionar otra con **Examinar**, por ejemplo la
carpeta de una importación revisada. El editor modifica directamente el archivo
YAML del capítulo y no mantiene una base de datos paralela. En la lista lateral
puedes filtrar por ID o texto. La pestaña **Crear prueba** permite añadirla al
final del capítulo o bajo una sección existente.
El panel lateral refleja la jerarquía de secciones del YAML; puedes desplegar o
plegar cada rama y seleccionar pruebas desde su sección. Al crear una prueba,
puedes elegir insertarla justo después de la prueba seleccionada, al final del
capítulo o dentro de una sección existente; el nivel de encabezado se calcula
según la ubicación. Para crear una sección sin añadir una prueba, selecciona una
prueba en el navegador, abre la pestaña **Nueva sección**, escribe el nombre y
créala. Se insertará justo después de la prueba seleccionada. Después aparecerá
en la lista de ubicaciones disponibles al crear pruebas.
Al seleccionar una sección se abre su pantalla de edición: permite cambiar el
nombre y el `contexto`, una lista YAML que puede contener texto o mapas con
`texto` e `imagenes`. También permite añadir imágenes al contexto y ver sus
miniaturas. Las vistas previas se actualizan al editar el YAML del contexto y
las rutas relativas se resuelven desde la carpeta seleccionada de YAML; si un
archivo no existe o no se puede mostrar, el editor lo indica.

Las pruebas y secciones se pueden borrar desde sus respectivas pantallas, con
confirmación. Al borrar una prueba solo se elimina esa prueba. Al borrar una
sección desaparece su encabezado, pero su contexto se conserva como texto y las
pruebas y subsecciones descendientes se mantienen, promocionadas un nivel.

El repositorio incluye datos ficticios para probar la aplicación antes de
importar el documento real. Estos ejemplos no contienen información del
documento original y están registrados en `ejemplos/yaml/indice.yaml`:

- `01_ejemplo_basico.yaml`: pruebas sencillas y jerarquía de secciones.
- `02_ejemplo_adicionales.yaml`: contexto de prueba y campos adicionales.
- `03_ejemplo_secciones_imagenes.yaml`: secciones anidadas, imágenes en el
  contexto de sección, de prueba y de pasos, y una prueba con todos los campos.
- `04_ejemplo_edicion_variantes.yaml`: varias pruebas bajo secciones para
  practicar búsqueda, creación, edición y borrado.

Las imágenes ficticias usadas por el tercer capítulo están en
`ejemplos/yaml/imagenes/`. Puedes modificar los ejemplos para practicar; guarda
una copia si quieres conservar los originales.

Las listas de las pruebas se editan como listas YAML en campos separados. En
**Campos adicionales** se puede conservar información específica de una
variante. Las imágenes seleccionadas desde el formulario se copian a
`imagenes/` y se asocian a la prueba o al contexto de la sección. Para asociar
una imagen a un paso concreto, se puede usar un mapa de lista como
`{texto: "Paso", imagenes: ["imagenes/archivo.png"]}`.

El editor está pensado para un usuario de confianza en el mismo equipo. Haz
copias de seguridad de los YAML antes de ediciones masivas.

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

Las pruebas cubren la conversión Word/YAML, la extracción y exportación de
imágenes, y las funciones del editor como navegación jerárquica, edición,
inserción y borrado. También comprueban que los capítulos de ejemplo se cargan
y que sus referencias a imágenes existen.

## Trabajo pendiente

### Sobre el documento original

- Hacer una copia controlada del DOCX y agrupar sus tablas por estructura.
- Identificar las tablas que no son pruebas y decidir cómo representarlas sin
  forzarlas al esquema de pruebas.
- Evaluar la normalización de los formularios repetidos a una plantilla común,
  preservando todos los datos y campos con significado.
- Probar cualquier transformación sobre unas pocas tablas de cada formato
  antes de aplicarla al documento completo.
- Mantener el documento original privado; compartir solo ejemplos
  anonimizados cuando haga falta definir nuevas reglas.

### Para declarar los YAML como datos oficiales

- Añadir un clasificador explícito para tablas de prueba frente a tablas
  informativas y preservar las tablas no reconocidas sin pérdida.
- Añadir una validación de esquema para campos, tipos, imágenes referenciadas,
  orden y unicidad de IDs.
- Auditar la primera importación: comparar conteos, revisar muestras de cada
  variante y resolver todos los casos de posible pérdida o clasificación
  incorrecta.
- Decidir qué campos adicionales pasan a formar parte del esquema común y
  documentar los campos opcionales.
- Elegir qué datos pueden versionarse en Git y cuáles deben permanecer en un
  repositorio privado o almacenamiento aprobado por el equipo.
- Añadir una comprobación de generación completa del DOCX y una inspección
  visual de capítulos, tablas, saltos de página e imágenes.

## Crear el repositorio en GitHub

Este directorio todavía no es un repositorio Git. Después de crear un
repositorio vacío en GitHub, revisa que solo vayan a subirse código y
documentación no confidenciales:

```bash
git init
git add .gitignore README.md requirements.txt convertir.py yaml_a_docx.py test_conversion.py
git status
git commit -m "Add Word and YAML conversion tools"
git branch -M main
git remote add origin https://github.com/OWNER/REPOSITORY.git
git push -u origin main
```

Sustituye `OWNER/REPOSITORY` por los datos del repositorio creado. Antes de
confirmar el commit, revisa `git status` y el contenido staged; no añadas el
DOCX original, los resultados generados, imágenes o YAML confidenciales.
