#!/usr/bin/env python3
"""El mapeo de importación del proyecto (importacion.yaml): cómo se importan sus Word y sus Excel.

Va junto a `aztarna.yaml`, en la carpeta del proyecto (o dentro de una carpeta
de pruebas suelta), y viaja con él en su repositorio: así todo el equipo
importa igual sin tener que volver a elegir los campos. Lo escribe el
asistente al importar y se puede editar a mano:

    excel:
      hojas:                  # qué hay en cada hoja: prueba, requisito o ignorar
        Llamadas: prueba
      columnas:
        prueba:
          ID: id
          Pasos: pasos
          Notas: adicional
    word:
      etiquetas:
        prueba:
          ENSAYO(s) / Proceso(s): pasos
          Criticidad: ignorar

Los nombres van tal cual aparecen en el Excel o en el Word (al comparar no
cuentan mayúsculas, tildes, espacios ni signos); los campos son las claves del
esquema (`app/esquema.py`) o adicional / anterior / ignorar.

Al importar, se propone primero lo de este archivo, después lo recordado en
el PC y, por último, lo que se deduce del nombre.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app import esquema
from app import importacion as imp

ARCHIVO = "importacion.yaml"
CABECERA = ("Cómo se importan los Word y los Excel de este proyecto. Lo escribe el asistente\n"
            "de importación (⋯ → Importar desde Word o Excel…); también se puede editar a mano.\n"
            "Los campos son los de app/esquema.py o adicional / anterior / ignorar.")


def carpeta_proyecto(carpeta_pruebas: str | Path) -> Path:
    """Donde va el archivo: la carpeta del proyecto (la que contiene pruebas/) o la de pruebas suelta."""
    carpeta = Path(carpeta_pruebas)
    return carpeta.parent if carpeta.name == esquema.CARPETA_PRUEBAS else carpeta


def archivo(carpeta_pruebas: str | Path) -> Path:
    return carpeta_proyecto(carpeta_pruebas) / ARCHIVO


def _validos(tipo: str, origen: str) -> set[str]:
    from app import importacion_excel as ix
    especiales = ix.ESPECIALES if origen == "excel" else imp.ESPECIALES
    return set(imp.CLASES[tipo]) | set(especiales) | (set(ix.ESTRUCTURA) if origen == "excel" else set())


def leer(carpeta_pruebas: str | Path | None, origen: str) -> tuple[dict[str, Any], Path | None, list[str]]:
    """(mapeo en la forma del asistente, archivo leído o None, problemas) para «word» o «excel»."""
    if carpeta_pruebas is None:
        return {}, None, []
    ruta = archivo(carpeta_pruebas)
    if not ruta.is_file():
        return {}, None, []
    from ruamel.yaml import YAML
    from ruamel.yaml.error import YAMLError
    try:
        with ruta.open(encoding="utf-8") as f:
            datos = YAML(typ="safe").load(f) or {}
    except (OSError, YAMLError) as error:
        return {}, ruta, [f"No se puede leer {ruta.name}: {error}"]
    if not isinstance(datos, dict):
        return {}, ruta, [f"{ruta.name} no tiene la forma esperada (excel: / word:)."]
    parte = datos.get(origen) or {}
    problemas: list[str] = []
    mapeo: dict[str, Any] = {"tipos": {}, "campos": {t: {} for t in imp.CLASES}}
    if origen == "excel":
        for hoja, tipo in (parte.get("hojas") or {}).items():
            if tipo in ("prueba", "requisito", "ignorar"):
                mapeo["tipos"][f"hoja:{hoja}"] = tipo
            else:
                problemas.append(f"hoja «{hoja}»: «{tipo}» no es prueba, requisito ni ignorar")
    nombres = (parte.get("columnas") if origen == "excel" else parte.get("etiquetas")) or {}
    for tipo, campos in nombres.items():
        if tipo not in imp.CLASES or not isinstance(campos, dict):
            problemas.append(f"«{tipo}» no es prueba ni requisito")
            continue
        validos = _validos(tipo, origen)
        for nombre, campo in campos.items():
            if campo in validos:
                mapeo["campos"][tipo][imp.clave(nombre)] = campo
            else:
                problemas.append(f"{nombre}: «{campo}» no es un campo de {'las pruebas' if tipo == 'prueba' else 'los requisitos'}")
    return mapeo, ruta, problemas


def combinar(*mapeos: dict[str, Any] | None) -> dict[str, Any]:
    """Une varios mapeos; los de detrás mandan (p. ej., el del PC y encima el del proyecto)."""
    resultado: dict[str, Any] = {"tipos": {}, "campos": {t: {} for t in imp.CLASES}}
    for m in mapeos:
        if not isinstance(m, dict):
            continue
        resultado["tipos"].update(m.get("tipos") or {})
        for t in imp.CLASES:
            resultado["campos"][t].update((m.get("campos") or {}).get(t) or {})
    return resultado


def guardar(carpeta_pruebas: str | Path, origen: str, mapeo: dict[str, Any], analisis: dict[str, Any]) -> Path:
    """Añade al importacion.yaml del proyecto lo elegido para este documento (conserva lo demás y sus comentarios).

    De cada tipo que se importa se guardan sus etiquetas (o columnas) con su
    nombre tal como está en el documento; en un Excel, también qué hay en cada hoja.
    """
    from ruamel.yaml.comments import CommentedMap
    from app.editor_core import roundtrip_yaml
    ruta = archivo(carpeta_pruebas)
    yaml = roundtrip_yaml()
    datos = None
    if ruta.is_file():
        with ruta.open(encoding="utf-8") as f:
            datos = yaml.load(f)
    if not isinstance(datos, dict):
        datos = CommentedMap()
        datos.yaml_set_start_comment(CABECERA)
    parte = datos.setdefault(origen, CommentedMap())
    tipos = mapeo.get("tipos") or {}
    usados = {tipos.get(f["firma"], f["tipo"]) for f in analisis.get("familias") or []}
    if origen == "excel":
        hojas = parte.setdefault("hojas", CommentedMap())
        for f in analisis.get("familias") or []:
            hojas[f["hoja"]] = tipos.get(f["firma"], f["tipo"])
    nombres = parte.setdefault("columnas" if origen == "excel" else "etiquetas", CommentedMap())
    for tipo in imp.CLASES:
        if tipo not in usados:
            continue
        de_tipo = nombres.setdefault(tipo, CommentedMap())
        existentes = {imp.clave(k): k for k in de_tipo}
        for f in analisis.get("familias") or []:
            if tipos.get(f["firma"], f["tipo"]) != tipo:
                continue
            for e in f["etiquetas"]:
                campo = ((mapeo.get("campos") or {}).get(tipo) or {}).get(e["clave"])
                if not campo:
                    continue
                nombre = existentes.get(e["clave"], e["etiqueta"])     # se respeta cómo estaba escrito
                de_tipo[nombre] = campo
                existentes[e["clave"]] = nombre
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8") as f:
        yaml.dump(datos, f)
    return ruta
