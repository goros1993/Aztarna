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

- Fase 5: cerrar campaña (congela sus pruebas con secciones e imágenes en
  `pruebas_congeladas/` y la deja en solo lectura) e informe DOCX/PDF
  (`informe_docx.py`) con resumen al principio y el resultado de cada prueba.
  La campaña guarda la ruta a las pruebas relativa y absoluta y, si no las
  encuentra, pregunta dónde están. Cambiar el ID de una prueba pide
  confirmación.

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

## Pruebas automáticas con Robot Framework

Parte de las pruebas se automatizan con un framework en Python + Robot
Framework. Hoy no hay ninguna referencia entre los tests de Robot y los YAML,
y Robot se lanza a mano en el PC del tester (o en otro PC, de momento sin
red). La versión de Robot no está fijada: hay que admitir RF 6 y RF 7.

**Convención (propuesta):** cada test de Robot lleva la etiqueta
`id:<ID de la prueba YAML>` (`[Tags]  id:DEMO-LLAM-001`). Es el único enlace,
igual que el ID en las campañas: el nombre del test de Robot puede cambiar
libremente. Un test de Robot puede llevar varios `id:` (cubre varias pruebas)
y varios tests de Robot pueden cubrir la misma prueba (variantes): si todos
pasan, OK; si alguno falla, NO OK. Detalles en
[docs/robot.md](docs/robot.md).

**Equivalencia de resultados:** PASS → OK, FAIL → NO OK (con el mensaje de
error en observaciones), SKIP → No aplica (con el motivo).

Plan:

1. *Hecho (primera versión):* importar el `output.xml` de Robot en una
   campaña, desde el editor (con vista previa antes de aplicar) y por línea de
   comandos (`importar_robot.py`). Se copian `output.xml`, `log.html` y
   `report.html` a las evidencias de la campaña y se avisa de los tests sin
   `id:` y de los `id:` que no existen. Lee el XML directamente, sin instalar
   Robot en el editor, y admite los formatos de RF 6 y RF 7.
2. *Hecho:* cobertura. Se leen las etiquetas `id:` de los `.robot` (sin
   ejecutarlos) para marcar en el editor qué pruebas tienen test automático,
   avisar de `automatizable: hecho` sin test y de IDs inexistentes, y filtrar
   «con / sin test de Robot» al crear una campaña. La configuración (carpeta
   de suites, comando y argumentos) es de cada PC (`ajustes.py`).
3. *Hecho:* lanzar Robot desde la campaña solo con las pruebas elegidas
   (`--include id:…` en un archivo de argumentos), con avance en vivo mediante
   un *listener*, cancelación y vista previa de la importación al terminar.
   Pendiente: si se cierra el editor con Robot en marcha, Robot sigue y sus
   resultados se pueden importar después con *Importar Robot…*; valorar
   avisar o esperar.
4. Cuando haya red o integración continua: importar sin intervención (la
   línea de comandos ya lo permite).

### Propuesta aplazada: un solo test (pasos ejecutables)

Hoy hay tests en YAML (para pasar a mano) y tests de Robot que los
automatizan; son parecidos pero no iguales, y pueden divergir. Propuesta para
no duplicarlos: que **cada paso del YAML sea el nombre de una keyword de
Robot** (Robot admite nombres de keyword con argumentos incrustados, como
`Pulsar el botón ${planta} de la botonera de cabina`) y que un generador cree
los `.robot` a partir de los YAML (situación inicial → *Given*, pasos →
*When*, situación final → *Then*), sin editarlos a mano. Las keywords las
mantiene el equipo de automatización y contienen el detalle técnico
(timeouts, tolerancias, direcciones del banco).

- Ventajas: una sola descripción; el tester y Robot hacen los mismos pasos;
  `robot --dryrun` lista los pasos sin keyword (el trabajo pendiente de
  automatización); el editor podría proponer las keywords existentes al
  escribir un paso.
- Excepciones: pasos solo manuales (marcados en el YAML) y tests de Robot
  escritos a mano para casos complejos, enlazados con `id:` y con una
  etiqueta `huella:` para avisar si el YAML cambió desde que se automatizó.
- Transición: inventario de equivalencias, vocabulario común de pasos
  (partiendo de las keywords existentes), generador con *dry-run* y retirada
  de los tests duplicados.
- **Aplazada:** hoy son unas 400 pruebas y 80 keywords; reescribir los pasos
  en un lenguaje controlado es demasiado trabajo por ahora. Mientras tanto,
  el enlace es la etiqueta `id:` y la cobertura avisa de lo que falta.
- *Hecho (primer paso, sin reescribir nada):* el editor propone las keywords
  de Robot (`.robot`, `.resource` y librerías de Python) al escribir
  situaciones y pasos, y marca los pasos que ya son una keyword. Así las
  pruebas nuevas nacen con el vocabulario de Robot. Siguientes pasos
  posibles: contar en la cobertura cuántos pasos de cada prueba son keywords
  (las candidatas a generarse solas), y avisar de pasos casi iguales a una
  keyword.

## Varias formas de ejecutar y validación de una versión de SW

Una misma versión de software se valida con pruebas que se ejecutan de
formas distintas: automáticas con Robot, manuales en el banco HIL, manuales
en un entorno real (instalación física), y en PCs distintos, a veces sin red.
Hoy cada una de esas ejecuciones es una campaña independiente.

Para dar por válida una versión hará falta **consolidar varias campañas** (o
varios `resultados.yaml`) en una vista y un informe únicos:

- Una «validación de versión» que agrupe campañas de la misma versión
  (`objeto` de la campaña) y dé una tabla por prueba con el resultado de cada
  campaña y un resultado consolidado.
- Reglas de consolidación a decidir: qué pasa si la misma prueba sale OK en
  una campaña y NO OK en otra (¿prevalece el último resultado, el peor, o se
  marca como conflicto?); pruebas que no se han ejecutado en ninguna; pruebas
  que solo pueden darse por válidas en un entorno concreto (por ejemplo, un
  campo `entorno_requerido` o etiquetas como `entorno-real`).
- Comprobar que todas las campañas usan las mismas pruebas (las huellas ya lo
  permiten) o avisar de qué versión de cada prueba se ejecutó en cada sitio.
- Informe final de versión que cite cada campaña (quién, dónde, cuándo) y
  enlace sus informes.
- Lo mismo sirve para juntar resultados de varias personas sobre una misma
  campaña (ver «Varias personas en la misma campaña»).

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

## Clasificación de tablas no prueba

*Hecho:* `convertir.py` clasifica cada tabla (prueba, dudosa o no prueba) con
las reglas de abajo; las que no son pruebas se conservan como `tabla:` en su
sitio y `yaml_a_docx.py` las vuelve a pintar. `inventario.py` usa la misma
clasificación. Los avisos van agrupados por tipo (`avisos.txt`) y uno por
línea con capítulo, nº de tabla e ID (`avisos.csv`). Pendiente: mostrar las
tablas en el editor (ahora solo se conservan) y revisar con el documento real
las dudosas y los umbrales.

Propuesta original:

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
