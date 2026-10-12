#!/usr/bin/env python3
"""
Agrupa las tablas del Word por los campos que contienen, para ver qué
variantes existen antes de ajustar el parser.

Uso (en la misma carpeta que convertir.py):
    python inventario.py tu_archivo.docx
Escribe inventario.txt y muestra un resumen corto por pantalla.
"""
import sys
from collections import Counter, defaultdict

from docx import Document

from convertir import CAMPOS, SECCIONES, celdas_unicas, norm

ESTANDAR = set(CAMPOS) | set(SECCIONES)


def etiquetas(tabla):
    """Devuelve (id, {etiqueta_normalizada: texto_original}, nº de filas)."""
    filas = [celdas_unicas(r) for r in tabla.rows]
    ident = filas[0][0].text.strip() if filas and filas[0] else "?"
    etq = {}
    for fila in filas[1:]:
        for c in fila:
            seccion = False
            for p in c.paragraphs:
                n = norm(p.text).rstrip(":")
                if n in SECCIONES:
                    etq[n] = p.text.strip()
                    seccion = True
            if not seccion and ":" in c.text:
                crudo = c.text.split(":", 1)[0].strip()
                etq[norm(crudo)] = crudo
    return ident, etq, len(filas)


def main(ruta):
    doc = Document(ruta)
    familias = defaultdict(list)
    desconocidas = Counter()
    problemas = []
    for i, t in enumerate(doc.tables):
        try:
            ident, etq, nfilas = etiquetas(t)
        except Exception as e:  # tabla con estructura inesperada
            problemas.append(f"tabla {i}: {type(e).__name__}: {e}")
            continue
        for n, crudo in etq.items():
            if n not in ESTANDAR:
                desconocidas[crudo] += 1
        clave = (tuple(sorted(ESTANDAR - set(etq))),
                 tuple(sorted(set(etq) - ESTANDAR)), nfilas)
        familias[clave].append(ident)

    lineas = [f"Tablas analizadas: {len(doc.tables)}", ""]
    for (faltan, sobran, nfilas), ids in sorted(familias.items(), key=lambda x: -len(x[1])):
        tipo = "ESTÁNDAR" if not faltan and not sobran else "VARIANTE"
        lineas.append(f"{len(ids):5d}  {tipo}  filas={nfilas}")
        if faltan:
            lineas.append(f"       faltan: {', '.join(faltan)}")
        if sobran:
            lineas.append(f"       sobran: {', '.join(sobran)}")
        lineas.append(f"       ejemplos: {', '.join(ids[:3])}")
    lineas += ["", "Etiquetas desconocidas (texto original, nº de tablas):"]
    lineas += [f"  {n:5d}  {e!r}" for e, n in desconocidas.most_common()]
    if problemas:
        lineas += ["", "Tablas que no se pudieron analizar:"] + [f"  {p}" for p in problemas[:30]]
    texto = "\n".join(lineas)
    open("inventario.txt", "w", encoding="utf-8").write(texto)
    print("\n".join(lineas[:25]))
    print("\n(completo en inventario.txt)")


if __name__ == "__main__":
    main(sys.argv[1])
