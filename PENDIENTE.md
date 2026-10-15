# Trabajo pendiente

Estado del proyecto, siguientes pasos y propuestas. El uso de las
herramientas está en el [README](README.md) y en el [manual](MANUAL.md).

## Hecho

- **Importación del Word de pruebas** (`migracion/`): inventario de tablas por
  estructura, conversión con avisos (`avisos.txt` / `avisos.csv`),
  clasificación de tablas (prueba, dudosa, no prueba), auditoría sin pérdidas
  (`auditar`) y corrección de IDs repetidos (`ids`).
- **Esquema común de las pruebas** con la plantilla
  `plantillas/tabla_prueba.docx`, definido solo en `esquema.py`; el formato
  antiguo se convierte con `esquema.migrar_prueba`. Obligatorios: ID y título.
- **Editor**: formulario, formato en línea, listas, imágenes, tablas que no
  son pruebas (en el contexto, editables al hacer clic), vista YAML,
  validación, arrastre en el árbol, plegar/desplegar todo, tags y keywords de
  Robot propuestos al escribir, botón Descartar y exportación a Word con la
  plantilla.
- **Campañas de ejecución**: selección por tags, automatizable, entorno,
  maniobra, capítulo o Robot; resultados con historial y evidencias; huellas
  para detectar pruebas cambiadas; resincronizar; resumen con capítulos
  pulsables; cerrar (pruebas congeladas) e informe DOCX/PDF.
- **Robot Framework**: enlace por la etiqueta `id:<ID>`, cobertura en el
  editor, importar `output.xml` (RF 6 y 7), lanzar Robot desde la campaña
  con avance en vivo. Detalles en [docs/robot.md](docs/robot.md).
- **Requisitos y trazabilidad**: esquema con `plantillas/tabla_requisito.docx`,
  proyecto con `pruebas/` y `requisitos/`, cobertura por requisito, sección y
  capítulo, referencias a requisitos que no existen, requisitos cambiados con
  pruebas por revisar (`revisiones.yaml`), modo Requisitos en el editor,
  matriz CSV, Word de requisitos y `herramientas.py trazabilidad`.

## Siguientes pasos

| # | Tarea | Tamaño | Necesita |
|---|---|---|---|
| 1 | Importar el Word real de requisitos: adaptar `inventario`, `convertir` y `auditar` a la tabla de requisitos | medio | el inventario del Word |
| 2 | Renombrar la herramienta a **Aztarna** (ventana, ejecutable, documentación y repositorio) y probar el `.exe` en Windows tras la reorganización en `app/` | pequeño | un PC con Windows |
| 3 | Requisitos en las campañas: estado verificado / fallido por requisito según sus pruebas, sección en el informe y «campaña de impacto» con las pruebas de los requisitos cambiados | medio | — |
| 4 | `convertir --anadir-a`: añadir a una carpeta de YAML existente los capítulos que se importan más tarde, sin pisar archivos ni imágenes | pequeño-medio | esos capítulos |
| 5 | Validación de una versión: consolidar varias campañas en una vista e informe únicos (ver abajo) | grande | reglas de consolidación |
| 6 | Comparar campañas: nuevos fallos y arreglos respecto a la versión anterior | pequeño | — |
| 7 | Robot: avisar si se cierra el editor con Robot en marcha; contar en la cobertura qué pasos ya son keywords | pequeño | — |
| 8 | Requisitos: líneas base y comparación entre revisiones (nuevos, eliminados, modificados con diff, posibles renombrados) | medio | — |
| 9 | Tablas informativas: las celdas unidas en vertical se importan repetidas en cada fila, y el editor no puede unirlas en vertical | pequeño | — |
| 10 | Manual: rehacer las capturas 13, 15 y 22, que muestran la barra superior antigua | pequeño | una campaña cerrada y Robot |

### Decisiones abiertas

- ¿Basta una prueba para dar un requisito por cubierto, o hace falta una
  marca manual de «cobertura completa» para los que necesitan varias?
- ¿Coinciden los IDs del campo `requisitos` de las pruebas con los del Word
  de requisitos? (se verá al importarlo).
- Qué campos adicionales de las pruebas pasan a formar parte del esquema.
- Qué datos se versionan en Git y cuáles van a un repositorio privado.

## Propuestas

### Validación de una versión (varias campañas)

Una misma versión se valida con campañas distintas: Robot, manuales en el
banco HIL, en un entorno real, en PCs sin red o repartidas entre varias
personas. Para dar la versión por válida hace falta una vista única:

- agrupar las campañas de la misma versión (`objeto` de la campaña) y dar,
  por prueba, el resultado de cada campaña y uno consolidado;
- reglas a decidir: OK en una y NO OK en otra (¿el último, el peor o un
  conflicto?), pruebas sin ejecutar en ninguna, pruebas que solo valen en un
  entorno concreto;
- avisar si las campañas ejecutaron versiones distintas de una prueba (las
  huellas ya lo permiten);
- informe final que cite cada campaña (quién, dónde, cuándo).

Para varias personas en una misma campaña sirve lo mismo, o una función
«Importar resultados de otra copia» que una registros y avise de conflictos.

### Pasos ejecutables (aplazada)

Que cada paso del YAML sea una keyword de Robot y que un generador cree los
`.robot` a partir de los YAML, para no mantener dos descripciones del mismo
test. Aplazada: reescribir cientos de pruebas en un lenguaje controlado es
demasiado trabajo por ahora. Mientras tanto, el enlace es la etiqueta `id:`,
el editor propone las keywords al escribir y marca los pasos que ya lo son.

### Descartada: pruebas en dos sitios

Se valoró una «referencia a prueba» para las pruebas que aparecen en dos
apartados. No hace falta: son pruebas distintas, con su propio ID, y el
ensayo de una cita a la otra.
