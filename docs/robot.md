# Robot Framework y las pruebas YAML

Cómo enlazar los tests automáticos de Robot Framework con las pruebas del
editor para que sus resultados entren en las campañas de ejecución.

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

| Robot | Campaña |
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

2. En el editor, modo **Ejecución**, abre la campaña y pulsa **Importar
   Robot…** en el resumen. Elige el `output.xml`. Antes de cambiar nada verás
   qué resultado tendrá cada prueba y los avisos:
   - pruebas que ya tenían un resultado manual (el manual no se pierde: queda
     en el historial),
   - tests de Robot sin etiqueta `id:`,
   - IDs que no existen en las pruebas (erratas o pruebas borradas),
   - IDs que existen pero no están en esta campaña,
   - pruebas de la campaña sin test de Robot (se quedan como están, para
     pasarlas a mano).
3. Pulsa **Importar**. Se copian `output.xml`, `log.html`, `report.html` y
   las capturas enlazadas en el log a `evidencias/robot/<fecha>/` dentro de la
   campaña, y cada prueba queda con su resultado, el ejecutor «Robot
   Framework», la captura y el `log.html` como evidencias.

También desde la línea de comandos (útil en un PC sin el editor abierto o,
más adelante, en integración continua):

```bash
python importar_robot.py ruta/a/la/campaña resultados/output.xml --simular   # solo mira
python importar_robot.py ruta/a/la/campaña resultados/output.xml             # importa
```

Volver a importar el mismo `output.xml` no duplica nada. Si se repiten los
tests fallidos (`robot --rerunfailed resultados/output.xml …`) y se importa
el nuevo resultado, el anterior queda en el historial de cada prueba.

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
prueba, un test sin `id:` y un ID que no existe). Sus resultados ya generados
están en `ejemplos/robot/resultados/output.xml`; se pueden importar en la
campaña de ejemplo `ejemplos/ejecuciones/regresion_v2.3`.
