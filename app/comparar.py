#!/usr/bin/env python3
"""Comparar dos validaciones (o dos ejecuciones): qué ha empeorado y qué se ha arreglado.

Para cada prueba se mira su resultado antes y ahora (el de la versión en una
validación; el de la prueba en una ejecución) y se clasifica:

- nuevo_fallo: ahora es NO OK y antes no lo era;
- arreglada: antes era NO OK y ahora está bien (validada, OK o No aplica);
- sigue_fallando: NO OK antes y ahora;
- otros_cambios: cualquier otro cambio (p. ej., bloqueada → validada);
- nueva: no estaba en la anterior;
- ya_no_esta: estaba en la anterior y ya no;
- sin_cambios.

Uso:
    python herramientas.py comparar carpeta_anterior carpeta_actual   # validaciones o ejecuciones
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

CATEGORIAS = ("nuevo_fallo", "arreglada", "sigue_fallando", "otros_cambios", "nueva", "ya_no_esta", "sin_cambios")
VISIBLES = {
    "nuevo_fallo": "Nuevos fallos", "arreglada": "Arregladas", "sigue_fallando": "Siguen fallando",
    "otros_cambios": "Otros cambios", "nueva": "Nuevas", "ya_no_esta": "Ya no están", "sin_cambios": "Sin cambios",
}
BIEN = {"validada", "ok", "no_aplica"}


def categoria(antes: str | None, ahora: str | None) -> str:
    if antes is None:
        return "nueva"
    if ahora is None:
        return "ya_no_esta"
    if ahora == "no_ok":
        return "sigue_fallando" if antes == "no_ok" else "nuevo_fallo"
    if antes == "no_ok" and ahora in BIEN:
        return "arreglada"
    return "sin_cambios" if antes == ahora else "otros_cambios"


def comparar(antes: dict[str, dict[str, Any]], ahora: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """`antes` y `ahora`: {id: {"estado", "titulo"}}. Filas en el orden de `ahora` (y las que ya no están, al final)."""
    filas = []
    for ident in [*ahora, *(i for i in antes if i not in ahora)]:
        a, b = antes.get(ident), ahora.get(ident)
        filas.append({"id": ident, "titulo": (b or a or {}).get("titulo", ""),
                      "antes": a["estado"] if a else None, "ahora": b["estado"] if b else None,
                      "categoria": categoria(a["estado"] if a else None, b["estado"] if b else None)})
    return {"filas": filas, "cuentas": {c: sum(1 for f in filas if f["categoria"] == c) for c in CATEGORIAS}}


# --- de dónde salen los estados ------------------------------------------------------
def estados_validacion(consolidado: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {p["id"]: {"estado": p["estado"], "titulo": p["titulo"]} for p in consolidado["pruebas"]}


def estados_ejecucion(ejecucion: dict[str, Any]) -> dict[str, dict[str, Any]]:
    from app import ejecucion_core as ej
    from app.editor_core import tests_in_chapter
    titulos = {}
    try:
        for capitulo in ej.capitulos_de(ejecucion):
            for _i, prueba in tests_in_chapter(capitulo):
                titulos[str(prueba.get("id") or "").strip()] = str(prueba.get("titulo") or "")
    except (OSError, ValueError):
        pass                                        # sin sus pruebas: se compara sin títulos
    return {i: {"estado": ej.estado_de(ejecucion, i), "titulo": titulos.get(i, "")} for i in ej.ids_de(ejecucion)}


def describir(carpeta: str | Path) -> dict[str, Any]:
    """Nombre, tipo y estados de una validación o de una ejecución."""
    from app import ejecucion_core as ej
    from app import validacion_core as vc
    carpeta = Path(carpeta)
    if vc.es_validacion(carpeta):
        validacion = vc.cargar(carpeta)
        datos = validacion["datos"]
        return {"tipo": "validacion", "carpeta": str(carpeta), "nombre": str(datos.get("nombre") or carpeta.name),
                "version": str(datos.get("version") or ""),
                "estados": estados_validacion(vc.consolidar(validacion, con_comparacion=False, con_requisitos=False))}
    if ej.es_ejecucion(carpeta):
        ejecucion = ej.cargar(carpeta)
        datos = ejecucion["datos"]
        return {"tipo": "ejecucion", "carpeta": str(carpeta), "nombre": str(datos.get("nombre") or carpeta.name),
                "version": str(datos.get("objeto") or ""), "estados": estados_ejecucion(ejecucion)}
    raise ValueError(f"{carpeta} no es una validación ni una ejecución.")


def comparar_carpetas(anterior: str | Path, actual: str | Path) -> dict[str, Any]:
    a, b = describir(anterior), describir(actual)
    if a["tipo"] != b["tipo"]:
        raise ValueError("Compara una validación con otra validación, o una ejecución con otra ejecución.")
    return {"anterior": {k: v for k, v in a.items() if k != "estados"},
            "actual": {k: v for k, v in b.items() if k != "estados"},
            **comparar(a["estados"], b["estados"])}


def main(argv=None, prog=None) -> None:
    ap = argparse.ArgumentParser(prog=prog, description="Compara dos validaciones o dos ejecuciones")
    ap.add_argument("anterior", help="carpeta de la validación (o ejecución) anterior")
    ap.add_argument("actual", help="carpeta de la validación (o ejecución) actual")
    ap.add_argument("--todas", action="store_true", help="lista también las pruebas sin cambios")
    args = ap.parse_args(argv)
    try:
        r = comparar_carpetas(args.anterior, args.actual)
    except ValueError as error:
        raise SystemExit(str(error))
    print(f"{r['anterior']['nombre']} → {r['actual']['nombre']}")
    print("  " + " · ".join(f"{VISIBLES[c]}: {n}" for c, n in r["cuentas"].items() if n))
    for c in CATEGORIAS:
        if c == "sin_cambios" and not args.todas:
            continue
        filas = [f for f in r["filas"] if f["categoria"] == c]
        if filas:
            print(f"\n{VISIBLES[c]} ({len(filas)}):")
            for f in filas:
                print(f"  {f['id']:<18} {str(f['antes'] or '—'):>10} → {str(f['ahora'] or '—'):<10} {f['titulo'][:60]}")


if __name__ == "__main__":
    main()
