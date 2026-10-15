#!/usr/bin/env python3
"""
Agrupa las tablas del Word por los campos que contienen, para ver qué
variantes existen antes de ajustar el parser. Cada tabla se clasifica igual
que en convertir.py: prueba, dudosa (se conservará como tabla; revisar) o
informativa (no es una prueba; se conservará tal cual).

Uso (en la misma carpeta que convertir.py):
    python inventario.py tu_archivo.docx
Escribe inventario.txt y muestra un resumen corto por pantalla.
"""
import sys
from collections import Counter, defaultdict

from docx import Document

from convertir import CAMPOS, SECCIONES, celdas_unicas, clasificar_tabla, etiquetas_tabla

# Campos del esquema (los alias, como «Condiciones iniciales», cuentan como su campo).
ESTANDAR = set(CAMPOS.values()) | set(SECCIONES.values())
CLASES = {"prueba": "PRUEBA", "dudosa": "DUDOSA", "informativa": "NO PRUEBA"}


def etiquetas(tabla):
    """Devuelve (id, {etiqueta_normalizada: texto_original}, nº de filas, clase, motivo)."""
    filas = [celdas_unicas(r) for r in tabla.rows]
    ident = " ".join(filas[0][0].text.split())[:60] if filas and filas[0] else "?"
    clase, motivo = clasificar_tabla(tabla)
    return ident, etiquetas_tabla(tabla), len(filas), clase, motivo


def main(ruta):
    doc = Document(ruta)
    familias = defaultdict(list)
    motivos = {}
    desconocidas = Counter()
    clases = Counter()
    problemas = []
    for i, t in enumerate(doc.tables):
        try:
            ident, etq, nfilas, clase, motivo = etiquetas(t)
        except Exception as e:  # tabla con estructura inesperada
            problemas.append(f"tabla {i + 1}: {type(e).__name__}: {e}")
            continue
        clases[clase] += 1
        if clase == "prueba":
            presentes = {CAMPOS.get(n) or SECCIONES.get(n) for n in etq} - {None}
            sobran = sorted(crudo for n, crudo in etq.items() if n not in CAMPOS and n not in SECCIONES)
            desconocidas.update(sobran)
            clave = (clase, tuple(sorted(ESTANDAR - presentes)), tuple(sobran), nfilas)
        else:
            # Las que no son pruebas se agrupan por motivo, no por campos que les faltan.
            clave = (clase, (), (), nfilas)
            motivos.setdefault(clave, motivo)
        familias[clave].append(f"{ident or '(vacía)'} [tabla {i + 1}]")

    lineas = [f"Tablas analizadas: {len(doc.tables)}"]
    lineas += [f"  {clases[c]:5d}  {CLASES[c]}" for c in CLASES if clases[c]]
    lineas.append("")
    for (clase, faltan, sobran, nfilas), ids in sorted(familias.items(), key=lambda x: (list(CLASES).index(x[0][0]), -len(x[1]))):
        if clase != "prueba":
            tipo = CLASES[clase]
        else:
            tipo = "ESTÁNDAR" if not faltan and not sobran else "VARIANTE"
        lineas.append(f"{len(ids):5d}  {tipo}  filas={nfilas}")
        if clase != "prueba":
            lineas.append(f"       motivo: {motivos[(clase, faltan, sobran, nfilas)]}")
        if faltan:
            lineas.append(f"       faltan: {', '.join(faltan)}")
        if sobran:
            lineas.append(f"       sobran: {', '.join(sobran)}")
        lineas.append(f"       ejemplos: {', '.join(ids[:3])}")
    lineas += ["", "Etiquetas desconocidas en las pruebas (texto original, nº de tablas):"]
    lineas += [f"  {n:5d}  {e!r}" for e, n in desconocidas.most_common()]
    if problemas:
        lineas += ["", "Tablas que no se pudieron analizar:"] + [f"  {p}" for p in problemas[:30]]
    texto = "\n".join(lineas) + "\n"
    open("inventario.txt", "w", encoding="utf-8").write(texto)
    print("\n".join(lineas[:25]))
    print("\n(completo en inventario.txt)")


if __name__ == "__main__":
    main(sys.argv[1])
