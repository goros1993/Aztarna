# Robot Framework y las pruebas YAML

Cómo enlazar los tests automáticos de Robot Framework con las pruebas del
editor para que sus resultados entren en las ejecuciones.

## La convención: la etiqueta `id:`

Cada test de Robot lleva la etiqueta `id:` seguida del **ID de la prueba
YAML** que automatiza:

```robotframework
*** Test Cases ***
Llamada de cabina lleva a la planta pedida
    [Tags]    id:DEMO-LLAM-001    regresion
    ${planta}=    Simular Viaje    origen=0    destino=2
    Should Be Equal As Integers    ${planta}    2
```

- **Es el único enlace.** El nombre del test de Robot, su suite o su archivo
  pueden cambiar sin romper nada; el ID no (igual que en el editor).
- **Un test puede cubrir varias pruebas:** pon varias etiquetas
  (`[Tags]  id:DEMO-PUER-001  id:DEMO-PUER-002`).
- **Varios tests pueden cubrir la misma prueba** (variantes, datos
  distintos): todos llevan la misma etiqueta `id:`.
- Las demás etiquetas (`regresion`, `smoke`…) se pueden seguir usando como
  siempre; el importador solo mira las que empiezan por `id:`.
- Las mayúsculas del prefijo dan igual (`ID:` también vale); el ID se copia
  tal cual, así que debe coincidir exactamente con el de la prueba YAML.

Para etiquetar muchos tests de una suite a la vez puede usarse `Test Tags`
en *Settings* (`Force Tags` en versiones antiguas de Robot), pero lo normal
es una etiqueta por test.

## Cómo se convierte cada resultado

| Robot | Ejecución |
|---|---|
| PASS | OK |
| FAIL | NO OK (el mensaje de error va a *Observaciones*) |
| SKIP | No aplica (el motivo va a *Observaciones*) |
| NOT RUN | No se importa (la prueba sigue como estaba) |

Si varios tests de Robot cubren la misma prueba: si **alguno falla**, NO OK;
si no, si **alguno pasa**, OK; si **todos se saltan**, No aplica. Las
observaciones indican qué tests se ejecutaron y por qué falló cada uno.

## Importar los resultados

1. Ejecuta Robot como siempre; deja un `output.xml` (por defecto, junto a
   `log.html` y `report.html`):

   ```bash
   robot --outputdir resultados pruebas_robot/
   ```

2. En el editor, modo **Validación**, abre la ejecución y pulsa **Importar
   Robot…** en el resumen. Elige el `output.xml`. Antes de cambiar nada verás
   qué resultado tendrá cada prueba y los avisos:
   - pruebas que ya tenían un resultado manual (el manual no se pierde: queda
     en el historial),
   - tests de Robot sin etiqueta `id:`,
   - IDs que no existen en las pruebas (erratas o pruebas borradas),
   - IDs que existen pero no están en esta ejecución,
   - pruebas de la ejecución sin resultado en ese archivo (se quedan como
     están, para pasarlas a mano o en otra ejecución).
3. Pulsa **Importar**. Se copian `output.xml`, `log.html`, `report.html` y
   las capturas enlazadas en el log a `evidencias/robot/<fecha>/` dentro de la
   ejecución, y cada prueba queda con su resultado, el ejecutor «Robot
   Framework», la captura y el `log.html` como evidencias.

También desde la línea de comandos (útil en un PC sin el editor abierto o,
más adelante, en integración continua):

```bash
python herramientas.py robot ruta/a/la/ejecución resultados/output.xml --simular   # solo mira
python herramientas.py robot ruta/a/la/ejecución resultados/output.xml             # importa
```

Volver a importar el mismo `output.xml` no duplica nada. Si se repiten los
tests fallidos (`robot --rerunfailed resultados/output.xml …`) y se importa
el nuevo resultado, el anterior queda en el historial de cada prueba.

## Configurar Robot en el editor

Botón **Robot** de la barra superior. La configuración es de cada PC y de
cada carpeta de pruebas:

- **Carpeta con los tests de Robot:** la carpeta de las suites (o un archivo
  `.robot`).
- **Comando para ejecutar Robot:** el que usarías en la consola, por ejemplo
  `robot`, `python -m robot` o la ruta completa
  (`C:\venv\Scripts\robot.exe`). *Comprobar* ejecuta `--version`.
- **Argumentos adicionales:** los que necesite el banco, por ejemplo
  `--variable BANCO:2 --pythonpath lib`.

Robot se ejecuta en la carpeta de los tests, con el Python donde esté
instalado; el editor no necesita tenerlo instalado.

## Cobertura: qué pruebas tienen test de Robot

Con la carpeta configurada, el editor lee las etiquetas `id:` de los `.robot`
(sin ejecutarlos; tiene en cuenta `Test Tags`/`Force Tags` del archivo y de
`__init__.robot`) y:

- marca con un robot en el árbol las pruebas que tienen test automático, y
  en cada prueba lista sus tests de Robot (archivo y línea);
- avisa en la validación de las pruebas con `automatizable: hecho` sin test
  de Robot;
- en la configuración muestra los tests sin `id:` y los `id:` que no existen;
- al crear una ejecución permite filtrar por **Automatización: con / sin test
  de Robot**.

## Escribir los pasos con las keywords

Para que las pruebas nuevas se escriban igual que los tests de Robot, el
editor propone las keywords existentes al escribir *Situación inicial*,
*Pasos* y *Situación final*, y marca con un robot los pasos que ya son una
keyword.

De dónde salen (sin ejecutar nada, leyendo los archivos):

- la sección *Keywords* de los `.robot` y `.resource` de la carpeta de tests
  (con `[Arguments]` y la primera línea de `[Documentation]`);
- las librerías de Python: las funciones decoradas con `@keyword` y, si algún
  `.robot` o `.resource` importa el archivo con `Library`, sus funciones
  públicas (o los métodos de la clase que se llama como el archivo). Se
  respetan `ROBOT_AUTO_KEYWORDS = False`, `@library` y `@not_keyword`;
- **Otras carpetas con keywords** (en la configuración de Robot): librerías o
  `.resource` que no están dentro de la carpeta de tests. Varias, separadas
  por `;`.

Las más usadas en los tests aparecen primero. Al elegir una, el paso se
escribe con la sintaxis de Robot:

| Keyword | Paso escrito |
|---|---|
| `Registrar una llamada de piso en ${planta}` (argumento incrustado) | `Registrar una llamada de piso en ${planta}` con `${planta}` seleccionado para escribir el valor |
| `Comprobar la alarma` con `[Arguments]  ${codigo}  ${timeout}=5 s` | `Comprobar la alarma    codigo=` (solo los obligatorios, con nombre) |

Un paso se considera keyword si su primera celda (hasta dos espacios
seguidos) coincide con el nombre como lo compara Robot (sin mayúsculas,
espacios ni guiones bajos), ignorando un punto final y los prefijos
*Given/When/Then/And/But*; las keywords con argumentos incrustados se
reconocen con cualquier valor (`Esperar al menos 1 s.` es `Esperar al
menos ${tiempo}`).

Las keywords con **argumentos incrustados** son las que mejor sirven a la
vez de paso manual y de paso de Robot: se leen como una frase
(`Llevar la cabina a P2 y esperar a que cierre puertas`). Ver
`ejemplos/robot/banco.resource` y `ejemplos/robot/banco_hil.py`. Es el
primer paso de la propuesta de pasos ejecutables (ver
[PENDIENTE.md](../PENDIENTE.md)).

## Ejecutar Robot desde una ejecución

**Ejecutar Robot…** (en el resumen de la ejecución) lanza Robot solo con los
tests de las pruebas elegidas: las pendientes o todas las de la ejecución que
tienen test de Robot. El editor:

1. crea `evidencias/robot/<fecha>/` dentro de la ejecución y lanza Robot con
   `--include id:<id>` por cada prueba (en un archivo de argumentos), las
   suites y los argumentos configurados;
2. muestra el avance test a test (con un *listener* que escribe en
   `progreso.jsonl`) y permite cancelar;
3. al terminar abre la vista previa de la importación; los resultados ya
   están en la ejecución (`output.xml`, `log.html`, `report.html`, la salida de
   la consola en `consola.txt`), así que no se copian otra vez.

Si Robot termina sin `output.xml` (comando mal configurado, argumentos
inválidos…), se muestra la salida de la consola.

## Capturas

Las capturas que Robot enlaza en el log (por ejemplo, las de SeleniumLibrary o
un `Log  <img src="captura.png">  HTML`) se adjuntan a la prueba si están en
la carpeta de resultados. Las rutas absolutas o URLs no se copian.

## Compatibilidad

El `output.xml` se lee directamente, sin necesidad de tener Robot Framework
instalado en el PC del editor. Se admiten los formatos de Robot Framework 6
y 7 (y anteriores desde la 4).

## Ejemplo

`ejemplos/robot/regresion_demo.robot` es una suite ficticia que muestra todos
los casos (OK, NO OK, SKIP, un test para dos pruebas, dos tests para la misma
prueba, un test sin `id:` y un ID que no existe). `banco.resource` y
`banco_hil.py` son keywords de ejemplo (Robot y Python) que coinciden con
pasos de las pruebas de ejemplo. Sus resultados ya generados están en `ejemplos/robot/resultados/output.xml`; se pueden importar en la
ejecución de ejemplo `ejemplos/ejecuciones/regresion_v2.3`.
