#!/usr/bin/env python3
"""Utilidades de línea de órdenes del proyecto.

Uso:
    python herramientas.py <orden> [opciones]
    python herramientas.py <orden> --help        # opciones de cada orden

Importación del Word:
    importar    pruebas o requisitos con un mapeo de etiquetas (lo mismo que ⋯ → Importar… en el editor)
    convertir   Word de pruebas -> YAML (un archivo por capítulo), con avisos
    inventario  agrupa las tablas del Word por estructura antes de importar
    auditar     comprueba que la importación no pierde texto (informe HTML)
    ids         propone y aplica IDs nuevos para pruebas con ID repetido

Documentos y ejecuciones (carpeta app/):
    word        genera el Word a partir de los YAML (de pruebas o de requisitos)
    informe     informe DOCX (y PDF) de una ejecución
    resultados  resultados de una ejecución o de una validación en CSV para Excel
    validacion  informe DOCX (y PDF) de la validación de una versión
    comparar    compara dos validaciones (o dos ejecuciones): nuevos fallos y arreglos
    robot       importa en una ejecución los resultados de Robot Framework (output.xml)

Requisitos (carpeta app/):
    trazabilidad  matriz requisitos -> pruebas: cobertura y referencias que no existen

El editor se abre con: python editor_web.py
"""
from __future__ import annotations

import importlib
import sys

from app import firma

ORDENES = {
    "importar": ("app.importacion", "Importa pruebas o requisitos de un Word con un mapeo de etiquetas"),
    "convertir": ("migracion.convertir", "Word de pruebas -> YAML (un archivo por capítulo), con avisos"),
    "inventario": ("migracion.inventario", "Agrupa las tablas del Word por estructura"),
    "auditar": ("migracion.auditar", "Comprueba que la importación no pierde texto"),
    "ids": ("migracion.ids_duplicados", "Propone y aplica IDs nuevos para pruebas con ID repetido"),
    "word": ("app.yaml_a_docx", "Genera el Word a partir de los YAML"),
    "informe": ("app.informe_docx", "Informe DOCX (y PDF) de una ejecución"),
    "resultados": ("app.exportar_resultados", "Resultados de una ejecución o de una validación en CSV para Excel"),
    "validacion": ("app.informe_validacion", "Informe DOCX (y PDF) de la validación de una versión"),
    "comparar": ("app.comparar", "Compara dos validaciones (o dos ejecuciones): nuevos fallos y arreglos"),
    "robot": ("app.importar_robot", "Importa resultados de Robot Framework en una ejecución"),
    "trazabilidad": ("app.trazabilidad", "Matriz requisitos -> pruebas: cobertura y referencias que no existen"),
}


def ayuda() -> str:
    ancho = max(len(o) for o in ORDENES)
    lineas = [firma(), "", "Uso: python herramientas.py <orden> [opciones]", "", "Órdenes:"]
    lineas += [f"  {orden:<{ancho}}  {texto}" for orden, (_m, texto) in ORDENES.items()]
    lineas += ["", "Cada orden tiene su ayuda: python herramientas.py <orden> --help",
               "Versión: python herramientas.py --version",
               "El editor se abre con: python editor_web.py"]
    return "\n".join(lineas)


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "ayuda"):
        print(ayuda())
        return
    if argv[0] in ("-V", "--version", "version"):
        print(firma())
        return
    orden, resto = argv[0], argv[1:]
    if orden not in ORDENES:
        raise SystemExit(f"Orden desconocida: «{orden}».\n\n{ayuda()}")
    modulo = importlib.import_module(ORDENES[orden][0])
    modulo.main(resto, prog=f"herramientas.py {orden}")


if __name__ == "__main__":
    main()
