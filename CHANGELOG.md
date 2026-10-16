# Cambios

Qué trae cada versión. La versión está en `app/__init__.py` (`__version__`) y
cada versión publicada lleva su etiqueta de Git (`v0.8.0`…).

## 0.8.0

Primera versión numerada. Incluye:

- **Importación del Word de pruebas** (`herramientas.py convertir`, `inventario`,
  `auditar` e `ids`), con la tabla común de `plantillas/tabla_prueba.docx`.
- **Editor de pruebas**: formulario, formato, listas, imágenes, tablas, vista
  YAML, validación, tags y keywords de Robot propuestos, exportación a Word.
- **Requisitos y trazabilidad**: modo Requisitos, cobertura por requisito y
  sección, requisitos cambiados con pruebas por revisar, matriz CSV y Word de
  requisitos.
- **Ejecuciones** con su entorno de pruebas (Automático, Maqueta, Torre),
  resultados con historial y evidencias, cierre con pruebas congeladas e
  informe DOCX/PDF.
- **Validación de una versión**: une ejecuciones de varias personas y entornos y
  da el resultado por prueba y entorno, con informe DOCX/PDF.
- **Robot Framework**: cobertura, importación de `output.xml` y ejecución desde
  el editor.
- Las preferencias del editor (recientes, último modo, ejecutor…) se guardan
  en los ajustes del PC; los diálogos de carpeta empiezan en la última usada.
- En modo Validación, el árbol marca las pruebas cambiadas después de
  ejecutarse.
- Versión visible en el editor, en la línea de órdenes (`--version`) y en los
  documentos generados.
