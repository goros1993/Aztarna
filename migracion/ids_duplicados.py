#!/usr/bin/env python3
"""Ayuda a corregir IDs de prueba repetidos, vacíos o con espacios.

Uso:
    python herramientas.py ids ruta/a/yaml                      # escribe ids.csv con una propuesta
    python herramientas.py ids ruta/a/yaml -o otra.csv
    python herramientas.py ids ruta/a/yaml --aplicar ids.csv    # aplica los ID nuevos del CSV

1. Sin `--aplicar` escribe un CSV (se abre con Excel) con una fila por cada
   prueba afectada: dónde está, su título, cuánto se parece a la otra prueba
   con el mismo ID y un ID nuevo propuesto (el siguiente número libre de la
   misma serie: LLAM_003 -> LLAM_014). La primera aparición de cada ID lo
   conserva.
2. Revisa el CSV: cambia `id_nuevo` donde quieras otro, déjalo igual que
   `id_actual` para no tocar esa prueba y rellena los que no tienen propuesta
   (IDs sin número, como «CASO DE PRUEBA»).
3. Con `--aplicar` cambia esos IDs en los YAML (conserva los comentarios) y
   comprueba antes que los nuevos no se repiten.

Si ya hay ejecuciones con resultados de estas pruebas, cambiar el ID hace que
allí aparezcan como «ya no existe» (las ejecuciones reconocen las pruebas por su ID).
"""
from __future__ import annotations

import argparse
import csv
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from app.editor_core import read_chapters, save_chapter

COLUMNAS = ["id_actual", "id_nuevo", "motivo", "parecido", "archivo", "indice", "capitulo", "seccion", "titulo"]
_ID_VALIDO = re.compile(r"^[A-Za-z][A-Za-z0-9]*(?:[_\-.][A-Za-z0-9]+)+$")
_PALABRAS = re.compile(r"\w+")


def _texto(valor: Any) -> str:
    if isinstance(valor, dict):
        return " ".join(_texto(v) for k, v in valor.items() if k not in ("imagenes", "imagen", "nivel"))
    if isinstance(valor, list):
        return " ".join(_texto(v) for v in valor)
    return "" if valor is None else str(valor)


def parecido(a: dict[str, Any], b: dict[str, Any]) -> tuple[str, int]:
    """Cuánto se parecen dos pruebas sin contar ID, encabezado ni nivel: (texto, %)."""
    def palabras(p):
        return set(_PALABRAS.findall(_texto({k: v for k, v in p.items() if k not in ("id", "nombre", "nivel")}).lower()))
    pa, pb = palabras(a), palabras(b)
    if not pa and not pb:
        return "idéntica", 100
    pct = round(100 * len(pa & pb) / len(pa | pb))
    if pct == 100:
        return "idéntica", pct
    return ("muy parecida" if pct >= 80 else "distinta"), pct


def pruebas_de(carpeta: Path) -> list[dict[str, Any]]:
    """Todas las pruebas, en el orden del documento, con su capítulo y sección."""
    resultado = []
    for capitulo in read_chapters(carpeta):
        pila: list[tuple[int, str]] = []
        for indice, e in enumerate(capitulo["data"]["contenido"]):
            if not isinstance(e, dict):
                continue
            if isinstance(e.get("seccion"), str):
                nivel = int(e.get("nivel") or 2)
                pila = [s for s in pila if s[0] < nivel] + [(nivel, e["seccion"])]
            elif isinstance(e.get("prueba"), dict):
                p = e["prueba"]
                nivel = int(p.get("nivel") or 3)
                resultado.append({
                    "prueba": p, "archivo": capitulo["path"].name, "indice": indice,
                    "capitulo": str(capitulo["data"].get("capitulo") or ""),
                    "seccion": " › ".join(s[1] for s in pila if s[0] < nivel),
                })
    return resultado


def _siguiente(id_base: str, usados: set[str]) -> str:
    """Siguiente ID libre de la serie: LLAM_003 -> LLAM_004…; sin número, «ID_2», «ID_3»…"""
    m = re.match(r"^(.*?)(\d+)$", id_base)
    if m:
        prefijo, numero = m.group(1), m.group(2)
        serie = [int(re.match(rf"^{re.escape(prefijo)}(\d+)$", u).group(1))
                 for u in usados if re.match(rf"^{re.escape(prefijo)}(\d+)$", u)]
        n = max(serie + [int(numero)]) + 1
        while f"{prefijo}{n:0{len(numero)}d}" in usados:
            n += 1
        return f"{prefijo}{n:0{len(numero)}d}"
    n = 2
    while f"{id_base}_{n}" in usados:
        n += 1
    return f"{id_base}_{n}"


def proponer(carpeta: Path) -> list[dict[str, Any]]:
    """Filas del CSV: pruebas con ID repetido, vacío o con espacios, y un ID nuevo propuesto."""
    pruebas = pruebas_de(carpeta)
    usados = {str(p["prueba"].get("id") or "").strip() for p in pruebas}
    por_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for p in pruebas:
        por_id[str(p["prueba"].get("id") or "").strip()].append(p)
    filas = []

    def fila(p: dict[str, Any], nuevo: str, motivo: str, parecida: str = "") -> dict[str, Any]:
        return {"id_actual": str(p["prueba"].get("id") or "").strip(), "id_nuevo": nuevo, "motivo": motivo,
                "parecido": parecida, "archivo": p["archivo"], "indice": p["indice"], "capitulo": p["capitulo"],
                "seccion": p["seccion"], "titulo": str(p["prueba"].get("titulo") or "")}

    for test_id, lista in por_id.items():
        limpio = re.sub(r"\s+", "", test_id)
        valido = bool(_ID_VALIDO.match(test_id))
        if not test_id:
            filas.extend(fila(p, "", "sin ID") for p in lista)
            continue
        if len(lista) == 1 and valido:
            continue
        for n, p in enumerate(lista):
            if n == 0:
                if valido:
                    filas.append(fila(p, test_id, f"ID repetido ({len(lista)} veces): conserva el ID"))
                    continue
                # ID con espacios o con forma extraña: se propone sin espacios si no choca con otro.
                if limpio != test_id and _ID_VALIDO.match(limpio) and limpio not in usados:
                    usados.add(limpio)
                    filas.append(fila(p, limpio, "ID con espacios" + (f" y repetido ({len(lista)} veces)" if len(lista) > 1 else "")))
                    continue
                filas.append(fila(p, "", "ID que no parece un ID: elige uno"
                                  + (f" (repetido {len(lista)} veces)" if len(lista) > 1 else "")))
                continue
            texto, pct = parecido(lista[0]["prueba"], p["prueba"])
            base = limpio if _ID_VALIDO.match(limpio) else ""
            nuevo = _siguiente(base, usados) if base else ""
            if nuevo:
                usados.add(nuevo)
            filas.append(fila(p, nuevo, f"ID repetido ({len(lista)} veces)" + ("" if nuevo else ": elige uno"),
                              f"{texto} ({pct} %) a la primera"))
    orden = {(p["archivo"], p["indice"]): i for i, p in enumerate(pruebas)}
    filas.sort(key=lambda f: orden[(f["archivo"], f["indice"])])
    return filas


def escribir_csv(filas: list[dict[str, Any]], ruta: Path) -> None:
    with open(ruta, "w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUMNAS, delimiter=";")
        escritor.writeheader()
        escritor.writerows(filas)


def leer_csv(ruta: Path) -> list[dict[str, str]]:
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        muestra = f.read(4096)
        f.seek(0)
        delimitador = ";" if muestra.count(";") >= muestra.count(",") else ","   # Excel puede guardarlo con comas
        return list(csv.DictReader(f, delimiter=delimitador))


def aplicar(carpeta: Path, filas: list[dict[str, str]], guardar: bool = True) -> dict[str, Any]:
    """Cambia los IDs del CSV. Comprueba antes que la prueba sigue ahí y que no quedan IDs repetidos."""
    capitulos = {c["path"].name: c for c in read_chapters(carpeta)}
    cambios = []
    errores = []
    for n, f in enumerate(filas, start=2):                    # la fila 1 del CSV es la cabecera
        actual, nuevo = (f.get("id_actual") or "").strip(), (f.get("id_nuevo") or "").strip()
        if not nuevo or nuevo == actual:
            continue
        capitulo = capitulos.get(f.get("archivo") or "")
        try:
            indice = int(f.get("indice") or -1)
            prueba = capitulo["data"]["contenido"][indice]["prueba"] if capitulo else None
        except (ValueError, IndexError, KeyError, TypeError):
            prueba = None
        if prueba is None or str(prueba.get("id") or "").strip() != actual:
            errores.append(f"Fila {n}: la prueba «{actual}» ya no está en {f.get('archivo')} (posición {f.get('indice')}). "
                           "Vuelve a generar el CSV.")
            continue
        if re.search(r"\s", nuevo):
            errores.append(f"Fila {n}: el ID nuevo «{nuevo}» tiene espacios.")
            continue
        cambios.append((capitulo, prueba, actual, nuevo))
    # IDs que quedarían después de los cambios
    finales = Counter()
    cambiadas = {id(p) for _c, p, _a, _n in cambios}
    for c in capitulos.values():
        for e in c["data"]["contenido"]:
            if isinstance(e, dict) and isinstance(e.get("prueba"), dict) and id(e["prueba"]) not in cambiadas:
                finales[str(e["prueba"].get("id") or "").strip()] += 1
    for _c, _p, _a, nuevo in cambios:
        finales[nuevo] += 1
    choques = sorted(i for _c, _p, _a, i in cambios if finales[i] > 1)
    if choques:
        errores.append(f"Estos IDs nuevos quedarían repetidos: {', '.join(dict.fromkeys(choques))}.")
    if errores:
        return {"aplicados": 0, "errores": errores, "repetidos_restantes": []}
    tocados = set()
    for capitulo, prueba, _actual, nuevo in cambios:
        prueba["id"] = nuevo
        tocados.add(capitulo["path"].name)
    if guardar:
        for nombre in tocados:
            save_chapter(capitulos[nombre])
    restantes = sorted(i for i, n in finales.items() if n > 1 and i)
    return {"aplicados": len(cambios), "errores": [], "archivos": sorted(tocados), "repetidos_restantes": restantes}


def main(argv=None, prog=None) -> None:
    ap = argparse.ArgumentParser(prog=prog, description="Propone y aplica IDs nuevos para pruebas con ID repetido, vacío o con espacios")
    ap.add_argument("carpeta", help="carpeta con indice.yaml y los capítulos")
    ap.add_argument("-o", "--salida", default="ids.csv", help="CSV con la propuesta (por defecto: ids.csv)")
    ap.add_argument("--aplicar", metavar="CSV", help="aplica los id_nuevo de este CSV")
    args = ap.parse_args(argv)
    carpeta = Path(args.carpeta)
    try:
        if args.aplicar:
            r = aplicar(carpeta, leer_csv(Path(args.aplicar)))
            if r["errores"]:
                print("No se ha cambiado nada:")
                for e in r["errores"]:
                    print(f"  {e}")
                raise SystemExit(1)
            print(f"{r['aplicados']} IDs cambiados en {len(r['archivos'])} archivos.")
            if r["repetidos_restantes"]:
                print(f"Siguen repetidos ({len(r['repetidos_restantes'])}): {', '.join(r['repetidos_restantes'][:20])}"
                      f"{' …' if len(r['repetidos_restantes']) > 20 else ''}")
            return
        filas = proponer(carpeta)
    except (ValueError, OSError) as error:
        raise SystemExit(f"Error: {error}")
    escribir_csv(filas, Path(args.salida))
    motivos = Counter(f["motivo"].split(" (")[0].split(":")[0] for f in filas if f["id_nuevo"] != f["id_actual"])
    sin_propuesta = sum(1 for f in filas if not f["id_nuevo"])
    print(f"{len(filas)} pruebas en {args.salida}:")
    for motivo, n in motivos.most_common():
        print(f"  {n:5d}  {motivo}")
    if sin_propuesta:
        print(f"  {sin_propuesta} sin propuesta: rellena «id_nuevo» en el CSV.")
    print(f"Revísalo y aplícalo con: python herramientas.py ids {args.carpeta} --aplicar {args.salida}")


if __name__ == "__main__":
    main()
