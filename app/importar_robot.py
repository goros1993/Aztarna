#!/usr/bin/env python3
"""Importa en una ejecución los resultados de Robot Framework (output.xml).

Uso:
    python herramientas.py robot ruta/a/la/ejecución ruta/a/output.xml            # importa
    python herramientas.py robot ruta/a/la/ejecución ruta/a/output.xml --simular  # solo muestra qué haría

Cada test de Robot debe llevar la etiqueta id:<ID de la prueba YAML>.
PASS -> OK, FAIL -> NO OK, SKIP -> No aplica. Ver el apartado 10 de MANUAL.md.
"""
from __future__ import annotations

import argparse

from app import ejecucion_core as ej
from app import robot_core

VISIBLE = {"ok": "OK", "no_ok": "NO OK", "no_aplica": "No aplica"}


def main(argv=None, prog=None) -> None:
    ap = argparse.ArgumentParser(prog=prog, description="Importa resultados de Robot Framework en una ejecución")
    ap.add_argument("ejecucion", help="carpeta de la ejecución (con ejecucion.yaml)")
    ap.add_argument("output", help="output.xml generado por Robot Framework")
    ap.add_argument("--simular", action="store_true", help="no cambia nada; solo muestra qué se importaría")
    ap.add_argument("--ejecutor", default=robot_core.EJECUTOR, help="nombre del ejecutor (por defecto: Robot Framework)")
    args = ap.parse_args(argv)
    try:
        ejecucion = ej.cargar(args.ejecucion)
        capitulos = ej.capitulos_de(ejecucion)
        if args.simular:
            datos = robot_core.plan(ejecucion, robot_core.leer_output(args.output), capitulos)
        else:
            datos = robot_core.importar(ejecucion, args.output, capitulos, ejecutor=args.ejecutor)
    except (ValueError, OSError) as error:
        raise SystemExit(f"Error: {error}")

    print(f"{datos['tests_robot']} tests en {args.output} ({datos['generador']})")
    for r in datos["resultados"]:
        cambio = f"   (antes: {ej.ESTADOS_VISIBLES.get(r['anterior'], r['anterior'])})" if r["anterior"] else ""
        print(f"  {VISIBLE[r['estado']]:9} {r['id']}{cambio}")
    t = datos["totales"]
    print(f"{'Se importarían' if args.simular else 'Importados'}: {t['ok']} OK, {t['no_ok']} NO OK, {t['no_aplica']} no aplica.")
    avisos = [
        ("Sustituyen un resultado manual (queda en el historial)", datos["sustituyen_manual"]),
        ("Tests de Robot sin etiqueta id:", datos["sin_id"]),
        ("IDs que no existen en las pruebas", datos["inexistentes"]),
        ("IDs que no están en esta ejecución", datos["fuera_de_ejecucion"]),
        ("Pruebas de la ejecución sin resultado en este archivo", datos["sin_robot"]),
    ]
    for titulo, lista in avisos:
        if lista:
            print(f"{titulo} ({len(lista)}): {', '.join(lista)}")
    if not args.simular and datos.get("carpeta_evidencias"):
        print(f"Log y capturas copiados a {datos['carpeta_evidencias']}")


if __name__ == "__main__":
    main()
