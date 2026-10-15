#!/usr/bin/env python3
"""Utilidades de línea de órdenes del proyecto.

Uso:
    python herramientas.py <orden> [opciones]
    python herramientas.py <orden> --help        # opciones de cada orden

Importación del Word (carpeta migracion/; se usa hasta que los YAML son la fuente oficial):
    convertir   Word -> YAML (un archivo por capítulo), con avisos
    inventario  agrupa las tablas del Word por estructura antes de importar
    auditar     comprueba que la importación no pierde texto (informe HTML)
    ids         propone y aplica IDs nuevos para pruebas con ID repetido

Documentos y campañas (carpeta app/):
    word        genera el Word a partir de los YAML (de pruebas o de requisitos)
    informe     informe DOCX (y PDF) de una campaña
    robot       importa en una campaña los resultados de Robot Framework (output.xml)

Requisitos (carpeta app/):
    trazabilidad  matriz requisitos -> pruebas: cobertura y referencias que no existen

El editor se abre con: python editor_web.py
"""
from __future__ import annotations

import importlib
import sys

ORDENES = {
    "convertir": ("migracion.convertir", "Word -> YAML (un archivo por capítulo), con avisos"),
    "inventario": ("migracion.inventario", "Agrupa las tablas del Word por estructura"),
    "auditar": ("migracion.auditar", "Comprueba que la importación no pierde texto"),
    "ids": ("migracion.ids_duplicados", "Propone y aplica IDs nuevos para pruebas con ID repetido"),
    "word": ("app.yaml_a_docx", "Genera el Word a partir de los YAML"),
    "informe": ("app.informe_docx", "Informe DOCX (y PDF) de una campaña"),
    "robot": ("app.importar_robot", "Importa resultados de Robot Framework en una campaña"),
    "trazabilidad": ("app.trazabilidad", "Matriz requisitos -> pruebas: cobertura y referencias que no existen"),
}


def ayuda() -> str:
    ancho = max(len(o) for o in ORDENES)
    lineas = ["Uso: python herramientas.py <orden> [opciones]", "", "Órdenes:"]
    lineas += [f"  {orden:<{ancho}}  {texto}" for orden, (_m, texto) in ORDENES.items()]
    lineas += ["", "Cada orden tiene su ayuda: python herramientas.py <orden> --help",
               "El editor se abre con: python editor_web.py"]
    return "\n".join(lineas)


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "ayuda"):
        print(ayuda())
        return
    orden, resto = argv[0], argv[1:]
    if orden not in ORDENES:
        raise SystemExit(f"Orden desconocida: «{orden}».\n\n{ayuda()}")
    modulo = importlib.import_module(ORDENES[orden][0])
    modulo.main(resto, prog=f"herramientas.py {orden}")


if __name__ == "__main__":
    main()
