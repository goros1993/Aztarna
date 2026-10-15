#!/usr/bin/env python3
"""Trazabilidad entre requisitos y pruebas.

El enlace se guarda en un solo sitio: el campo `requisitos` de cada prueba
(lista de IDs). A partir de ahí se calcula todo lo demás:

- cobertura de cada requisito: qué pruebas lo cubren y su estado
  (cubierto, sin cobertura o no aplica: informativo o verificado sin pruebas);
- referencias huérfanas: pruebas que citan un requisito que no existe;
- pruebas sin requisito;
- resumen por capítulo y por sección;
- requisitos «modificados»: su texto ha cambiado desde la última vez que se
  revisaron sus pruebas (ver `revisiones.yaml`).

Los requisitos están en la carpeta `requisitos/`, junto a la de pruebas
(editor_core.requirements_dir), con el mismo formato de capítulos.

Uso (matriz de trazabilidad):
    python herramientas.py trazabilidad ejemplos/yaml
    python herramientas.py trazabilidad ejemplos/yaml -o matriz.csv
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from app import esquema
from app.editor_core import items_in_chapter, normalize_level, read_chapters, requirements_dir, roundtrip_yaml, tests_dir

ESTADOS = ("cubierto", "sin_cobertura", "no_aplica")
ESTADO_TEXTO = {"cubierto": "Cubierto", "sin_cobertura": "Sin cobertura", "no_aplica": "No aplica"}
ARCHIVO_REVISIONES = "revisiones.yaml"
CABECERA_REVISIONES = (
    "# Requisitos cambiados cuyas pruebas faltan por revisar (lo escribe el editor).\n"
    "# Guarda el texto que tenían cuando se revisaron sus pruebas por última vez;\n"
    "# al marcar «Pruebas revisadas» se quita su entrada.\n"
)
CAMPOS_HUELLA = ("titulo", "descripcion", "contexto")


def carpeta_requisitos(carpeta_pruebas: str | Path) -> Path:
    return requirements_dir(carpeta_pruebas)


def leer_requisitos(carpeta_pruebas: str | Path) -> list[dict[str, Any]]:
    """Capítulos de requisitos; lista vacía si la carpeta no existe."""
    carpeta = carpeta_requisitos(carpeta_pruebas)
    if not carpeta.is_dir() or not any(carpeta.glob("*.yaml")):
        return []
    return read_chapters(carpeta)


def _plano(valor: Any) -> Any:
    if isinstance(valor, dict):
        return {str(k): _plano(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_plano(v) for v in valor]
    return valor if valor is None or isinstance(valor, (bool, int, float)) else str(valor)


def huella(requisito: Any) -> str:
    """Huella del contenido del requisito (título, descripción y contexto).

    Cambiar la fecha, la versión, el tipo o el encabezado no la cambia.
    """
    datos = {c: _plano(requisito.get(c)) for c in CAMPOS_HUELLA if requisito.get(c) not in (None, "", [])}
    texto = json.dumps(datos, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]


def lista(valor: Any) -> list[str]:
    valores = valor if isinstance(valor, list) else ([valor] if valor not in (None, "") else [])
    return [str(v).strip() for v in valores if str(v).strip()]


# ----------------------------------------------------------------------
# Revisiones pendientes (requisitos cambiados)
# ----------------------------------------------------------------------
def leer_revisiones(carpeta_req: Path) -> dict[str, Any]:
    ruta = Path(carpeta_req) / ARCHIVO_REVISIONES
    if not ruta.is_file():
        return {}
    with ruta.open(encoding="utf-8") as fuente:
        datos = roundtrip_yaml().load(fuente) or {}
    return {str(k): _plano(v) for k, v in datos.items()} if isinstance(datos, dict) else {}


def guardar_revisiones(carpeta_req: Path, revisiones: dict[str, Any]) -> None:
    ruta = Path(carpeta_req) / ARCHIVO_REVISIONES
    if not revisiones:
        if ruta.exists():
            ruta.unlink()
        return
    texto = CABECERA_REVISIONES + _a_texto(dict(sorted(revisiones.items())))
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=ruta.parent, prefix=".revisiones.",
                                     suffix=".tmp", delete=False) as temporal:
        temporal.write(texto)
    os.replace(temporal.name, ruta)


def _a_texto(valor: Any) -> str:
    from io import StringIO

    salida = StringIO()
    roundtrip_yaml().dump(valor, salida)
    return salida.getvalue()


def anotar_cambio(revisiones: dict[str, Any], anterior: Any, actual: Any) -> bool:
    """Apunta (o quita) un requisito cambiado. Devuelve True si `revisiones` cambia.

    Se guarda el texto revisado por última vez: si ya había una entrada se
    conserva (los cambios se acumulan hasta la revisión), y si el texto vuelve
    a ser el revisado la entrada se quita sola. Si el ID cambia, la entrada
    pasa al ID nuevo.
    """
    id_anterior = str(anterior.get("id") or "").strip()
    id_actual = str(actual.get("id") or "").strip()
    cambiado = False
    entrada = revisiones.pop(id_anterior, None) if id_anterior != id_actual else revisiones.get(id_actual)
    if id_anterior != id_actual and entrada is not None:
        cambiado = True
    if entrada is None:
        if huella(anterior) == huella(actual):
            return cambiado
        entrada = {"huella": huella(anterior), **{c: _plano(anterior.get(c)) for c in CAMPOS_HUELLA if anterior.get(c) not in (None, "", [])}}
    if entrada.get("huella") == huella(actual):
        revisiones.pop(id_actual, None)
        return True
    if revisiones.get(id_actual) != entrada:
        revisiones[id_actual] = entrada
        cambiado = True
    return cambiado


# ----------------------------------------------------------------------
# Cálculo
# ----------------------------------------------------------------------
def _recorrer(capitulos: list[dict[str, Any]], clave: str):
    """(índice de capítulo, índice en el contenido, elemento, ruta de secciones) de cada prueba o requisito."""
    for ci, capitulo in enumerate(capitulos):
        pila: list[tuple[int, str]] = []
        for indice, elemento in enumerate(capitulo["data"]["contenido"]):
            if not isinstance(elemento, dict):
                continue
            if isinstance(elemento.get("seccion"), str):
                nivel = normalize_level(elemento.get("nivel"), 2)
                while pila and pila[-1][0] >= nivel:
                    pila.pop()
                pila.append((nivel, elemento["seccion"]))
            elif isinstance(elemento.get(clave), dict):
                item = elemento[clave]
                nivel = normalize_level(item.get("nivel"), 3)
                while pila and pila[-1][0] >= nivel:
                    pila.pop()
                yield ci, indice, item, [nombre for _n, nombre in pila]


def calcular(pruebas: list[dict[str, Any]], requisitos: list[dict[str, Any]],
             revisiones: dict[str, Any] | None = None) -> dict[str, Any]:
    """Cobertura de cada requisito, referencias huérfanas y resúmenes."""
    revisiones = revisiones or {}
    reqs: dict[str, dict[str, Any]] = {}
    orden: list[str] = []
    for ci, indice, req, ruta in _recorrer(requisitos, "requisito"):
        rid = str(req.get("id") or "").strip()
        if not rid or rid in reqs:
            continue                       # sin ID o repetido: lo avisa la validación
        reqs[rid] = {
            "id": rid, "titulo": str(req.get("titulo") or ""), "capitulo": ci, "indice": indice,
            "archivo": requisitos[ci]["path"].name,
            "nombre_capitulo": str(requisitos[ci]["data"].get("capitulo") or requisitos[ci]["path"].stem),
            "seccion": ruta, "tipo": str(req.get("tipo") or ""),
            "criterio": lista(req.get("criterio_validacion")),
            "necesita": esquema.necesita_pruebas(req), "pruebas": [],
            "modificado": rid in revisiones and revisiones[rid].get("huella") != huella(req),
        }
        orden.append(rid)

    huerfanas, sin_requisito = [], []
    for ci, indice, prueba, _ruta in _recorrer(pruebas, "prueba"):
        pid = str(prueba.get("id") or "").strip()
        refs = lista(prueba.get("requisitos"))
        datos = {"id": pid, "titulo": str(prueba.get("titulo") or ""), "capitulo": ci, "indice": indice,
                 "archivo": pruebas[ci]["path"].name}
        if not refs:
            sin_requisito.append(datos)
        for ref in refs:
            if ref in reqs:
                if not any(p["id"] == pid and p["capitulo"] == ci and p["indice"] == indice for p in reqs[ref]["pruebas"]):
                    reqs[ref]["pruebas"].append(datos)
            else:
                huerfanas.append({**datos, "requisito": ref})

    for r in reqs.values():
        r["estado"] = "no_aplica" if not r["necesita"] else "cubierto" if r["pruebas"] else "sin_cobertura"
        r["modificado"] = bool(r["modificado"] and r["pruebas"])   # sin pruebas no hay nada que revisar

    lista_reqs = [reqs[i] for i in orden]
    return {
        "requisitos": lista_reqs,
        "huerfanas": huerfanas,
        "sin_requisito": sin_requisito,
        "total": _cuentas(lista_reqs),
        "capitulos": [
            {"capitulo": ci, "nombre": str(c["data"].get("capitulo") or c["path"].stem), "archivo": c["path"].name,
             **_cuentas([r for r in lista_reqs if r["capitulo"] == ci])}
            for ci, c in enumerate(requisitos)
        ],
    }


def _cuentas(reqs: list[dict[str, Any]]) -> dict[str, int]:
    cuentas = {"requisitos": len(reqs), "modificados": sum(1 for r in reqs if r["modificado"])}
    for estado in ESTADOS:
        cuentas[estado] = sum(1 for r in reqs if r["estado"] == estado)
    return cuentas


def porcentaje(cuentas: dict[str, int]) -> int | None:
    """Porcentaje de requisitos con pruebas entre los que las necesitan (None si ninguno las necesita)."""
    necesitan = cuentas["cubierto"] + cuentas["sin_cobertura"]
    return round(100 * cuentas["cubierto"] / necesitan) if necesitan else None


# ----------------------------------------------------------------------
# Matriz y resumen en texto
# ----------------------------------------------------------------------
COLUMNAS_MATRIZ = ("requisito", "titulo", "capitulo", "seccion", "tipo", "criterio_validacion",
                   "estado", "modificado", "pruebas")


def escribir_matriz(datos: dict[str, Any], salida: str | Path) -> None:
    """CSV (separado por «;», para Excel) con una fila por requisito y otra por referencia huérfana."""
    with open(salida, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(COLUMNAS_MATRIZ)
        for r in datos["requisitos"]:
            w.writerow([r["id"], r["titulo"], r["nombre_capitulo"], " › ".join(r["seccion"]), r["tipo"],
                        ", ".join(r["criterio"]), ESTADO_TEXTO[r["estado"]], "sí" if r["modificado"] else "",
                        ", ".join(p["id"] for p in r["pruebas"])])
        for h in datos["huerfanas"]:
            w.writerow([h["requisito"], "", "", "", "", "", "No existe", "", h["id"]])


def _plural(n: int, uno: str, varios: str) -> str:
    return f"{n} {uno if n == 1 else varios}"


def resumen_texto(datos: dict[str, Any]) -> str:
    t = datos["total"]
    pct = porcentaje(t)
    lineas = [
        f"{t['requisitos']} requisitos: {t['cubierto']} cubiertos, {t['sin_cobertura']} sin cobertura, "
        f"{t['no_aplica']} no aplica" + (f" ({pct} % cubiertos)" if pct is not None else ""),
    ]
    if t["modificados"]:
        lineas.append(_plural(t["modificados"], "requisito cambiado", "requisitos cambiados") + " con pruebas por revisar")
    lineas.append(_plural(len(datos["huerfanas"]), "referencia", "referencias") + " a requisitos que no existen")
    lineas.append(_plural(len(datos["sin_requisito"]), "prueba", "pruebas") + " sin requisito")
    lineas.append("")
    for c in datos["capitulos"]:
        pct = porcentaje(c)
        lineas.append(f"  {c['nombre']}: {c['cubierto']}/{c['cubierto'] + c['sin_cobertura']} cubiertos"
                      + (f" ({pct} %)" if pct is not None else "") + (f", {c['no_aplica']} no aplica" if c["no_aplica"] else ""))
    sin = [r for r in datos["requisitos"] if r["estado"] == "sin_cobertura"]
    if sin:
        lineas += ["", "Sin cobertura:"] + [f"  {r['id']}  {r['titulo']}" for r in sin]
    if datos["huerfanas"]:
        lineas += ["", "Referencias a requisitos que no existen:"]
        lineas += [f"  {h['id']} -> {h['requisito']}" for h in datos["huerfanas"]]
    return "\n".join(lineas)


def main(argv=None, prog=None):
    ap = argparse.ArgumentParser(prog=prog, description="Matriz de trazabilidad requisitos -> pruebas")
    ap.add_argument("carpeta", help="carpeta del proyecto (con pruebas/ y requisitos/) o la de pruebas")
    ap.add_argument("-o", "--salida", help="escribe la matriz en este CSV")
    args = ap.parse_args(argv)
    carpeta = tests_dir(args.carpeta)
    requisitos = leer_requisitos(carpeta)
    if not requisitos:
        raise SystemExit(f"No hay requisitos en {carpeta_requisitos(carpeta)}.")
    datos = calcular(read_chapters(carpeta), requisitos, leer_revisiones(carpeta_requisitos(carpeta)))
    print(resumen_texto(datos))
    if args.salida:
        escribir_matriz(datos, args.salida)
        print(f"\nMatriz -> {args.salida}")


if __name__ == "__main__":
    main()
