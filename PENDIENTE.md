# Trabajo pendiente

Planificación y propuestas. El uso de las herramientas está en el
[README](README.md).

## Campañas de ejecución

Objetivo: apuntar los resultados de las pruebas sin tocar los YAML de pruebas,
ver el avance y generar un entregable al terminar.

Cada campaña es una carpeta que cada usuario elige en su PC, con
`campaña.yaml` (datos, criterio de selección y lista congelada de pruebas con
la huella de su contenido), `resultados.yaml` (un resultado por prueba, con
observaciones, incidencia, evidencias e historial de intentos) y `evidencias/`.

Estados: **Pendiente** (aún sin ejecutar), **OK**, **NO OK** (se ejecutó y el
producto falla), **Bloqueada** (no se pudo ejecutar por algo ajeno al
producto: banco caído, falta hardware, depende de otra prueba que falló) y
**No aplica**. El porcentaje de OK se calcula sobre las pruebas que aplican.

Hecho:

- Fase 1: núcleo (`ejecucion_core.py`): selección por etiquetas, criticidad,
  automatizable, plataforma, entorno, componente, capítulo e IDs; creación con
  lista congelada; resultados con historial; huella para detectar pruebas
  cambiadas después de ejecutarse; resincronizar; cerrar; resumen y avisos.
- Fase 2: campo `etiquetas` en el editor (fichas con sugerencias) y en los
  ejemplos.
- Fase 3: modo «Ejecución» en el editor (`ejecucion_api.py`,
  `web/js/ejecucion.js`): crear o abrir campaña con vista previa de la
  selección, recientes, árbol con el estado de cada prueba y filtro por
  estado, ficha en solo lectura con panel de resultado (estado con teclas,
  observaciones, incidencia, ejecutor, evidencias, historial) y «Guardar y
  siguiente» (Ctrl+Intro). Campaña de ejemplo en `ejemplos/ejecuciones/`.
- Fase 4 (primera versión): panel de resumen con avance, totales, porcentaje
  de OK sobre las que aplican, desglose por capítulo y criticidad, avisos y
  resincronizar.

Siguiente:

- Fase 5: cerrar campaña y generar el entregable: DOCX/PDF con el mismo
  aspecto que `yaml_a_docx.py`, con un resumen al principio (datos de la
  campaña, totales, criterio de selección) y el resultado de cada prueba.

Para más adelante:

- **Varias personas en la misma campaña.** Ahora cada campaña vive en el PC de
  quien la ejecuta. Si varias personas reparten una campaña, habrá que fusionar
  sus resultados. Opciones a valorar: un archivo de resultados por persona (o
  por prueba) que se combinan al abrir la campaña; una función «Importar
  resultados de otra copia» que una registros y avise de conflictos (la misma
  prueba con resultados distintos, resuelta por fecha o eligiendo a mano); o
  una carpeta compartida con bloqueo. Las huellas y el historial de intentos
  ya guardan lo necesario para detectar esos conflictos.
- Comparar campañas («nuevos fallos respecto a la versión anterior»).
- Importar resultados de pruebas automáticas (por ejemplo, JUnit XML) para las
  pruebas con `automatizable: si`.

## Siguientes pasos de importación

Cuando haya demasiadas tablas o estructuras distintas, conviene seguir esta
secuencia antes de declarar como oficiales los YAML:

1. Ejecutar `python inventario.py "<docx>"` y guardar su salida para agrupar
   tablas por estructura.
2. Ejecutar la importación inicial con `python convertir.py "<docx>" -o importacion`
   y revisar `importacion/avisos.txt` agrupando los avisos por tipo e ID.
3. Identificar, en una muestra de 2 o 3 tablas de cada formato, cuáles son:
   - pruebas estándar,
   - variantes de prueba,
   - tablas informativas,
   - casos dudosos que requieren revisión manual.
4. Preservar las tablas no prueba sin forzarlas al esquema de pruebas,
   manteniendo su contenido original en YAML y un motivo de clasificación.
5. Añadir una validación automática de los YAML: sintaxis, IDs, campos
   obligatorios, niveles, imágenes referenciadas, secciones y conteos.
6. Auditar que todas las tablas y el contexto del DOCX original tengan una
   representación equivalente en YAML.

Una vez importadas y validadas todas las tablas, los YAML serán la única fuente
de verdad. A partir de ese momento no se debe volver a importar el DOCX
original; las correcciones y ampliaciones se harán editando los YAML y
regenerando el DOCX cuando sea necesario.

## Tareas abiertas

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

## Clasificación de tablas no prueba (propuesta)

La validación inicial del DOCX debe separar tablas de prueba de tablas
informativas antes de convertirlas al esquema estándar. Una estrategia
práctica y auditable es:

1. Extraer las etiquetas normalizadas de cada tabla con el mismo criterio que
   `convertir.py` (`norm`, `CAMPOS` y `SECCIONES`).
2. Calcular una puntuación para cada tabla:
   - proporción de etiquetas reconocidas;
   - presencia de una fila inicial con identificador y título;
   - presencia de al menos una sección reconocida (`Situación inicial`, `Pasos`
     o `Situación final`);
   - número de campos requeridos presentes.
3. Clasificar la tabla:
   - **prueba estándar**: el parser puede extraer ID, identificador de título
     y una o más secciones;
   - **variante de prueba**: gran parte de las etiquetas coincide, pero faltan
     campos o aparecen etiquetas desconocidas; se importa con avisos;
   - **tabla informativa**: no tiene identificador de prueba ni secciones
     reconocidas, o sus etiquetas no coinciden con `CAMPOS`/`SECCIONES`;
   - **revisar manualmente**: casos intermedios, con coincidencia parcial o
     etiquetas ambiguas.
4. Conservar las tablas no prueba sin forzarlas al esquema de pruebas, por
   ejemplo como una entrada separada en el YAML:

   ```yaml
   - tabla_informativa:
       tipo: texto_libre
       titulo: Notas de instalación
       filas:
         - ["Columna", "Valor"]
         - ["Observación", "Texto original preservado"]
       motivo_clasificacion: "Sin ID de prueba ni secciones reconocidas"
   ```

5. Mantener siempre un aviso por tabla clasificada como informativa o dudosa, y
   comparar conteos con el documento original antes de aceptar la importación.
