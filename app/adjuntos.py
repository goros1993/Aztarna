"""Adjuntos: archivos (Excel, Word…) que van con una prueba o con una sección, en `adjuntos/`.

La clave `adjuntos` aparece en dos sitios:

- en la prueba (o la sección, o un texto o una tabla sueltos del capítulo), la
  lista de sus adjuntos:

      adjuntos:
      - archivo: adjuntos/DEMO-LLAM-001_1.xlsx
        vista_previa: adjuntos/DEMO-LLAM-001_1.emf   # opcional: cómo se ve en el documento
        icono: true                                   # opcional: se ve como icono

- en un párrafo de una lista (un paso, el contexto…), dónde va cada uno en el
  documento: `adjuntos: [adjuntos/DEMO-LLAM-001_1.xlsx]`.

Al importar un Word, cada objeto incrustado (un Excel dentro del documento) se
guarda así: el archivo y su dibujo en `adjuntos/` (el dibujo no es una imagen
de la prueba) y, en el párrafo donde estaba, la referencia. Al exportar vuelve
a ser el objeto incrustado, como estaba: si era un icono, un doble clic lo
abre en Excel. Los que no tienen sitio van al final de la tabla de la prueba
(o tras el contexto de la sección), como icono si no tienen vista previa.

En la lista también vale escribir solo la ruta (`- adjuntos/hoja.xlsx`).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

CARPETA = "adjuntos"

# Lo que se sabe incrustar en Word: extensión -> (ProgID, tipo de contenido). Los de Office 2007
# y posteriores van como paquete (el archivo tal cual); los antiguos, como objeto OLE (.bin).
PAQUETES = {
    ".xlsx": ("Excel.Sheet.12", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    ".xlsm": ("Excel.SheetMacroEnabled.12", "application/vnd.ms-excel.sheet.macroEnabled.12"),
    ".docx": ("Word.Document.12", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ".docm": ("Word.DocumentMacroEnabled.12", "application/vnd.ms-word.document.macroEnabled.12"),
    ".pptx": ("PowerPoint.Show.12", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
}
OLE_ANTIGUOS = {".xls": "Excel.Sheet.8", ".doc": "Word.Document.8", ".ppt": "PowerPoint.Show.8"}
# ProgID de un objeto OLE (.bin) -> extensión con la que se guarda (el .bin se abre tal cual).
EXTENSION_OLE = {"Excel.Sheet.8": ".xls", "Excel.Chart.8": ".xls", "Word.Document.8": ".doc", "PowerPoint.Show.8": ".ppt"}
# Nombre legible del tipo de objeto, para los avisos.
NOMBRE_TIPO = {"Excel": "Excel", "Word": "Word", "PowerPoint": "PowerPoint", "Package": "archivo empaquetado",
               "AcroExch": "PDF", "Visio": "Visio"}


def lista(valor: Any) -> list[dict[str, Any]]:
    """Los adjuntos como [{archivo, vista_previa?, icono?}] (acepta la forma corta, solo la ruta)."""
    resultado = []
    for a in valor if isinstance(valor, list) else []:
        if isinstance(a, str) and a.strip():
            resultado.append({"archivo": a.strip()})
        elif isinstance(a, dict) and str(a.get("archivo") or "").strip():
            limpio: dict[str, Any] = {"archivo": str(a["archivo"]).strip()}
            if str(a.get("vista_previa") or "").strip():
                limpio["vista_previa"] = str(a["vista_previa"]).strip()
            if a.get("icono") is True:
                limpio["icono"] = True
            resultado.append(limpio)
    return resultado


def referencias(item: Any) -> list[str]:
    """Los adjuntos que van en un párrafo (su clave `adjuntos`: rutas)."""
    return [a["archivo"] for a in lista(item.get("adjuntos"))] if isinstance(item, dict) else []


def rutas_imagen(valor: Any) -> list[str]:
    """Rutas de imagen (claves `imagenes` e `imagen`) en cualquier nivel, en el orden del documento.
    (Los dibujos de los adjuntos no son imágenes: van en su clave `adjuntos`.)"""
    rutas: list[str] = []
    if isinstance(valor, dict):
        for clave, hijo in valor.items():
            if clave in ("imagenes", "imagen"):
                rutas.extend(r.strip() for r in (hijo if isinstance(hijo, list) else [hijo]) if isinstance(r, str) and r.strip())
            elif clave != "adjuntos":
                rutas.extend(rutas_imagen(hijo))
    elif isinstance(valor, list):
        for hijo in valor:
            rutas.extend(rutas_imagen(hijo))
    return rutas


def archivos(valor: Any) -> set[str]:
    """Archivos de los adjuntos (con sus vistas previas) de un contenido, en cualquier nivel."""
    encontrados: set[str] = set()
    if isinstance(valor, dict):
        for clave, hijo in valor.items():
            if clave == "adjuntos":
                encontrados |= {r for a in lista(hijo) for r in (a["archivo"], a.get("vista_previa")) if r}
            else:
                encontrados |= archivos(hijo)
    elif isinstance(valor, list):
        for hijo in valor:
            encontrados |= archivos(hijo)
    return encontrados


def es_ole_antiguo(datos: bytes) -> bool:
    """Si un .xls/.doc/.ppt lleva la marca de objeto incrustado (sale de un Word): solo esos se
    reincrustan; un archivo antiguo suelto, sin ella, Word no lo sabría abrir como objeto."""
    return datos[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" and "\x01Ole".encode("utf-16-le") in datos


def incrustable(ruta: Path) -> bool:
    extension = ruta.suffix.lower()
    if extension in PAQUETES:
        return True
    return extension in OLE_ANTIGUOS and ruta.is_file() and es_ole_antiguo(ruta.read_bytes())


def nombre_tipo(prog_id: str) -> str:
    return NOMBRE_TIPO.get(prog_id.split(".")[0], prog_id or "desconocido")


# --- objetos incrustados en un Word (importar) --------------------------------------
def objetos(elemento, parte) -> list[dict[str, Any]]:
    """Objetos OLE dentro de un elemento del Word (una tabla, un párrafo).

    Cada uno: {prog_id, extension, datos, vista (la parte de su dibujo) o None,
    icono (si se ve como icono), vinculado (ruta del archivo externo, si no está
    incrustado)}. `extension` y `datos` son None si no se sabe extraer (p. ej.
    un PDF empaquetado).
    """
    from docx.oxml.ns import qn
    resultado = []
    for obj in elemento.xpath(".//w:object"):
        ole = next(iter(obj.xpath("./*[local-name()='OLEObject']")), None)
        if ole is None:
            continue
        prog_id = ole.get("ProgID") or ""
        vista = None
        for imagen in obj.xpath(".//*[local-name()='imagedata']"):
            rel = parte.rels.get(imagen.get(qn("r:id")))
            if rel is not None and not rel.is_external:
                vista = rel.target_part
                break
        item = {"prog_id": prog_id, "extension": None, "datos": None, "vista": vista,
                "icono": ole.get("DrawAspect") == "Icon", "vinculado": None}
        rel = parte.rels.get(ole.get(qn("r:id")))
        if rel is None:
            pass
        elif rel.is_external or ole.get("Type") == "Link":
            item["vinculado"] = rel.target_ref
        else:
            incrustado = rel.target_part
            extension = Path(str(incrustado.partname)).suffix.lower()
            if extension in PAQUETES:
                item["extension"] = extension
            elif extension == ".bin" and prog_id in EXTENSION_OLE:
                item["extension"] = EXTENSION_OLE[prog_id]
            if item["extension"]:
                item["datos"] = incrustado.blob
        resultado.append(item)
    return resultado
