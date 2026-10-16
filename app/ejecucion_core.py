#!/usr/bin/env python3
"""Ejecuciones de pruebas: qué pruebas se pasan, sobre qué y con qué resultado.

Los YAML de pruebas no se tocan. Cada ejecución (antes «campaña»; en el código
siguen llamándose así muchas variables) es una carpeta elegida por el usuario con:

    ejecucion.yaml    datos de la ejecución, criterio de selección y lista
                      congelada de pruebas (ID + huella de su contenido);
                      las carpetas antiguas lo tienen como campaña.yaml
    resultados.yaml   un registro por prueba ejecutada, con su historial
    evidencias/       capturas y archivos adjuntos a los resultados

Este módulo no depende de ninguna interfaz gráfica.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from ruamel.yaml.scalarstring import LiteralScalarString

from app import esquema
from app.editor_core import read_chapters, roundtrip_yaml, section_end_index, tests_dir, tests_in_chapter

ARCHIVO_EJECUCION = "ejecucion.yaml"
ARCHIVO_CAMPAÑA = "campaña.yaml"        # nombre antiguo: se sigue leyendo y guardando en esas carpetas
ARCHIVO_RESULTADOS = "resultados.yaml"
CARPETA_EVIDENCIAS = "evidencias"
# Al cerrar, copia de las pruebas de la ejecución tal como estaban (mismo formato que la carpeta de pruebas).
CARPETA_CONGELADA = "pruebas_congeladas"

ESTADOS = ("pendiente", "ok", "no_ok", "bloqueada", "no_aplica")
ESTADOS_VISIBLES = {
    "pendiente": "Pendiente",
    "ok": "OK",
    "no_ok": "NO OK",
    "bloqueada": "Bloqueada",
    "no_aplica": "No aplica",
}
# Campos de la prueba por los que se puede filtrar (además de etiquetas, capítulos e IDs).
# Entorno y maniobra son listas: basta con que la prueba tenga uno de los valores pedidos.
CAMPOS_FILTRO = ("automatizable", "entorno", "maniobra")


def to_plain_simple(valor: Any) -> Any:
    """Listas y textos de ruamel como tipos simples, para comparar."""
    if isinstance(valor, list):
        return [to_plain_simple(v) for v in valor]
    return str(valor) if valor is not None else None


def ahora() -> str:
    return datetime.now().isoformat(timespec="minutes")


# ----------------------------------------------------------------------
# Huella de una prueba
# ----------------------------------------------------------------------
def huella(prueba: dict[str, Any]) -> str:
    """Resumen del contenido de una prueba para saber si cambió después de ejecutarla.

    No cuenta el `nivel`, que cambia al mover la prueba de sitio sin cambiar
    lo que hay que probar.
    """
    contenido = {k: v for k, v in prueba.items() if k != "nivel"}
    texto = json.dumps(contenido, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:12]


# ----------------------------------------------------------------------
# Selección de pruebas
# ----------------------------------------------------------------------
def etiquetas_de(prueba: dict[str, Any]) -> list[str]:
    valor = prueba.get("etiquetas") or []
    if isinstance(valor, str):
        valor = [valor]
    return [str(e).strip() for e in valor if str(e).strip()]


def _lista(valor: Any) -> list[str]:
    if valor in (None, ""):
        return []
    if isinstance(valor, str):
        valor = [valor]
    return [str(v).strip() for v in valor if str(v).strip()]


def cumple_filtro(prueba: dict[str, Any], archivo: str, filtro: dict[str, Any],
                  ids_robot: set[str] | None = None) -> bool:
    """True si la prueba entra en la selección.

    - `etiquetas`: basta con que tenga una de ellas.
    - `automatizable`, `entorno`, `maniobra` (CAMPOS_FILTRO): algún valor de la
      prueba debe estar en la lista.
    - `capitulos`: nombres de archivo de capítulo.
    - `robot`: ["con"] o ["sin"] test de Robot (necesita `ids_robot`).
    - `incluir_ids` entra siempre; `excluir_ids` no entra nunca.
    Un criterio vacío no filtra.
    """
    test_id = str(prueba.get("id") or "").strip()
    if test_id in _lista(filtro.get("excluir_ids")):
        return False
    if test_id in _lista(filtro.get("incluir_ids")):
        return True
    etiquetas = _lista(filtro.get("etiquetas"))
    if etiquetas and not set(etiquetas) & set(etiquetas_de(prueba)):
        return False
    capitulos = _lista(filtro.get("capitulos"))
    if capitulos and archivo not in capitulos:
        return False
    for campo in CAMPOS_FILTRO:
        valores = _lista(filtro.get(campo))
        if valores and not set(valores) & set(_lista(prueba.get(campo))):
            return False
    robot = _lista(filtro.get("robot"))
    if robot and ids_robot is not None and len(robot) == 1:
        tiene = test_id in ids_robot
        if (robot[0] == "con") != tiene:
            return False
    return True


def seleccionar(capitulos: list[dict[str, Any]], filtro: dict[str, Any],
                ids_robot: set[str] | None = None) -> list[dict[str, Any]]:
    """Pruebas que cumplen el filtro, en el orden del documento."""
    seleccion = []
    for capitulo in capitulos:
        archivo = capitulo["path"].name
        for indice, prueba in tests_in_chapter(capitulo):
            if cumple_filtro(prueba, archivo, filtro, ids_robot):
                seleccion.append({
                    "id": str(prueba.get("id") or "").strip(),
                    "archivo": archivo, "indice": indice, "prueba": prueba,
                })
    return seleccion


def opciones_filtro(capitulos: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Valores existentes de cada criterio, para proponerlos en la interfaz."""
    opciones: dict[str, set[str]] = {campo: set() for campo in ("etiquetas", *CAMPOS_FILTRO)}
    for capitulo in capitulos:
        for _indice, prueba in tests_in_chapter(capitulo):
            opciones["etiquetas"].update(etiquetas_de(prueba))
            for campo in CAMPOS_FILTRO:
                opciones[campo].update(_lista(prueba.get(campo)))
    resultado = {campo: sorted(valores) for campo, valores in opciones.items()}
    resultado["capitulos"] = [c["path"].name for c in capitulos]
    return resultado


def indice_por_id(capitulos: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """ID -> {archivo, indice, prueba}. Con IDs repetidos se queda el primero."""
    indice: dict[str, dict[str, Any]] = {}
    for capitulo in capitulos:
        for posicion, prueba in tests_in_chapter(capitulo):
            test_id = str(prueba.get("id") or "").strip()
            if test_id and test_id not in indice:
                indice[test_id] = {"archivo": capitulo["path"].name, "indice": posicion, "prueba": prueba}
    return indice


# ----------------------------------------------------------------------
# Lectura y escritura
# ----------------------------------------------------------------------
def _escribir_yaml(ruta: Path, datos: Any) -> None:
    """Escritura atómica: un fallo a mitad no deja el archivo roto."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fd, temporal = tempfile.mkstemp(dir=ruta.parent, prefix=ruta.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            roundtrip_yaml().dump(datos, f)
        os.replace(temporal, ruta)
    except BaseException:
        Path(temporal).unlink(missing_ok=True)
        raise


def _leer_yaml(ruta: Path) -> Any:
    with open(ruta, encoding="utf-8") as f:
        return roundtrip_yaml().load(f)


def archivo_datos(carpeta: str | Path) -> Path:
    """ejecucion.yaml, o campaña.yaml si la carpeta es de antes del cambio de nombre."""
    carpeta = Path(carpeta)
    antiguo = carpeta / ARCHIVO_CAMPAÑA
    if antiguo.is_file() and not (carpeta / ARCHIVO_EJECUCION).is_file():
        return antiguo
    return carpeta / ARCHIVO_EJECUCION


def es_campaña(carpeta: str | Path) -> bool:
    return archivo_datos(carpeta).is_file()


def _tiene_pruebas(ruta: Path) -> bool:
    return ruta.is_dir() and ((ruta / "indice.yaml").is_file() or any(ruta.glob("*.yaml")))


def rutas_pruebas(carpeta_campaña: Path, pruebas: Path) -> dict[str, str]:
    """Cómo guardar dónde están las pruebas: relativa a la ejecución (si se puede) y absoluta.

    La relativa sigue valiendo si se mueven juntas (o se copian a otro PC); la
    absoluta, si solo se mueve la ejecución.
    """
    pruebas = Path(pruebas).resolve()
    datos = {}
    try:
        datos["pruebas_yaml"] = Path(os.path.relpath(pruebas, Path(carpeta_campaña).resolve())).as_posix()
    except ValueError:            # en Windows, otra unidad: no hay ruta relativa
        pass
    datos["pruebas_yaml_absoluta"] = str(pruebas)
    return datos


def carpeta_pruebas(campaña: dict[str, Any]) -> Path | None:
    """Carpeta de los YAML de pruebas, o None si no se encuentra en ninguna de las rutas guardadas."""
    for clave in ("pruebas_yaml", "pruebas_yaml_absoluta"):
        valor = campaña["datos"].get(clave)
        if not valor:
            continue
        ruta = Path(str(valor)).expanduser()
        ruta = ruta if ruta.is_absolute() else (campaña["carpeta"] / ruta).resolve()
        if _tiene_pruebas(ruta):
            return ruta
    return None


def carpeta_congelada(campaña: dict[str, Any]) -> Path | None:
    ruta = campaña["carpeta"] / CARPETA_CONGELADA
    return ruta if _tiene_pruebas(ruta) else None


def reubicar_pruebas(campaña: dict[str, Any], nueva: str | Path) -> Path:
    """Indica dónde están ahora las pruebas de la ejecución (si se movieron)."""
    nueva = tests_dir(Path(nueva).expanduser().resolve())
    if not _tiene_pruebas(nueva):
        raise ValueError("Esa carpeta no contiene YAML de pruebas.")
    if not set(indice_por_id(read_chapters(nueva))) & set(ids_de(campaña)):
        raise ValueError("Esa carpeta no contiene ninguna prueba de esta ejecución.")
    campaña["datos"].pop("pruebas_yaml", None)
    campaña["datos"].update(rutas_pruebas(campaña["carpeta"], nueva))
    guardar(campaña)
    return nueva


def cargar(carpeta: str | Path) -> dict[str, Any]:
    carpeta = Path(carpeta)
    if not es_campaña(carpeta):
        raise ValueError(f"La carpeta no contiene una ejecución ({ARCHIVO_EJECUCION}).")
    archivo = archivo_datos(carpeta)
    datos = _leer_yaml(archivo) or {}
    if not isinstance(datos, dict) or not isinstance(datos.get("pruebas"), list):
        raise ValueError(f"{archivo.name} no tiene el formato esperado (falta 'pruebas').")
    ruta_resultados = carpeta / ARCHIVO_RESULTADOS
    resultados = _leer_yaml(ruta_resultados) if ruta_resultados.is_file() else None
    return {"carpeta": carpeta, "datos": datos, "resultados": resultados or {}}


def guardar(campaña: dict[str, Any]) -> None:
    _escribir_yaml(archivo_datos(campaña["carpeta"]), campaña["datos"])
    _escribir_yaml(campaña["carpeta"] / ARCHIVO_RESULTADOS, campaña["resultados"])


def _comprobar_ids(seleccion: list[dict[str, Any]]) -> None:
    vistos: set[str] = set()
    for item in seleccion:
        if not item["id"]:
            raise ValueError(f"Hay una prueba sin ID en {item['archivo']}; no se puede incluir en una ejecución.")
        if item["id"] in vistos:
            raise ValueError(f"El ID {item['id']} está repetido; corrígelo antes de crear la ejecución.")
        vistos.add(item["id"])


# Datos de la ejecución que se pueden indicar al crearla y cambiar mientras está abierta.
# `entorno_pruebas` es uno de los entornos de las pruebas (Automático, Maqueta, Torre);
# `entorno` es el detalle libre (banco o instalación).
DATOS_EDITABLES = ("objeto", "entorno_pruebas", "entorno", "responsable")


def entornos_pruebas() -> tuple[str, ...]:
    return esquema.OPCIONES_MULTIPLES["entorno"]


def _limpiar_datos(datos: dict[str, Any]) -> dict[str, str]:
    limpios = {}
    for clave, valor in (datos or {}).items():
        if clave not in DATOS_EDITABLES:
            continue
        texto = str(valor or "").strip()
        if clave == "entorno_pruebas" and texto and texto not in entornos_pruebas():
            raise ValueError(f"El entorno de pruebas debe ser uno de: {', '.join(entornos_pruebas())}.")
        limpios[clave] = texto
    return limpios


def editar_datos(campaña: dict[str, Any], cambios: dict[str, Any]) -> None:
    """Cambia los datos de una ejecución abierta (qué se prueba, entorno, responsable)."""
    _exigir_abierta(campaña)
    for clave, valor in _limpiar_datos(cambios).items():
        if valor:
            campaña["datos"][clave] = valor
        else:
            campaña["datos"].pop(clave, None)
    guardar(campaña)


def crear(carpeta: str | Path, pruebas_yaml: str | Path, nombre: str,
          filtro: dict[str, Any], datos: dict[str, Any] | None = None,
          ids_robot: set[str] | None = None) -> dict[str, Any]:
    """Crea una ejecución nueva con las pruebas que cumplen el filtro (lista congelada)."""
    carpeta = Path(carpeta)
    if es_campaña(carpeta):
        raise ValueError("Esa carpeta ya contiene una ejecución.")
    if carpeta.exists() and any(carpeta.iterdir()):
        raise ValueError("Elige una carpeta vacía (o nueva) para la ejecución.")
    nombre = str(nombre or "").strip()
    if not nombre:
        raise ValueError("La ejecución necesita un nombre.")
    pruebas_yaml = tests_dir(Path(pruebas_yaml).expanduser().resolve())   # admite la carpeta del proyecto
    capitulos = read_chapters(pruebas_yaml)
    seleccion = seleccionar(capitulos, filtro, ids_robot)
    if not seleccion:
        raise ValueError("Ninguna prueba cumple el criterio de selección.")
    _comprobar_ids(seleccion)
    extra = {k: v for k, v in _limpiar_datos(datos or {}).items() if v}
    campaña = {
        "carpeta": carpeta,
        "datos": {
            "nombre": nombre,
            **{k: extra[k] for k in DATOS_EDITABLES if k in extra},
            "inicio": ahora(),
            "estado": "abierta",
            **rutas_pruebas(carpeta, pruebas_yaml),
            "seleccion": {k: v for k, v in filtro.items() if v not in (None, "", [])},
            "pruebas": [{"id": item["id"], "huella": huella(item["prueba"])} for item in seleccion],
        },
        "resultados": {},
    }
    (carpeta / CARPETA_EVIDENCIAS).mkdir(parents=True, exist_ok=True)
    guardar(campaña)
    return campaña


# ----------------------------------------------------------------------
# Resultados
# ----------------------------------------------------------------------
def _exigir_abierta(campaña: dict[str, Any]) -> None:
    if campaña["datos"].get("estado") == "cerrada":
        raise ValueError("La ejecución está cerrada; no se pueden cambiar sus resultados.")


def ids_de(campaña: dict[str, Any]) -> list[str]:
    return [str(p["id"]) for p in campaña["datos"]["pruebas"]]


def estado_de(campaña: dict[str, Any], test_id: str) -> str:
    resultado = campaña["resultados"].get(test_id)
    return str(resultado.get("estado")) if resultado else "pendiente"


def registrar(campaña: dict[str, Any], test_id: str, estado: str, *,
              observaciones: str = "", incidencia: str = "", evidencias: list[str] | None = None,
              ejecutor: str = "", huella_actual: str = "", fecha: str | None = None,
              origen: str = "") -> dict[str, Any]:
    """Apunta el resultado de una prueba. El resultado anterior pasa al historial.

    `fecha` permite indicar cuándo se ejecutó (por defecto, ahora) y `origen`
    de dónde viene el resultado si no es manual (por ejemplo, «robot»).
    """
    _exigir_abierta(campaña)
    if test_id not in ids_de(campaña):
        raise ValueError(f"La prueba {test_id} no forma parte de esta ejecución.")
    if estado not in ESTADOS:
        raise ValueError(f"Estado no válido: {estado}.")
    resultados = campaña["resultados"]
    anterior = resultados.get(test_id)
    if estado == "pendiente":
        # Volver a pendiente deshace el último resultado (si había historial, se recupera).
        if anterior:
            intentos = list(anterior.get("intentos") or [])
            if intentos:
                recuperado = dict(intentos.pop())
                if intentos:
                    recuperado["intentos"] = intentos
                resultados[test_id] = recuperado
            else:
                del resultados[test_id]
        guardar(campaña)
        return resultados.get(test_id) or {"estado": "pendiente"}
    nuevo: dict[str, Any] = {"estado": estado, "fecha": fecha or ahora()}
    for clave, valor in (("ejecutor", ejecutor), ("origen", origen), ("huella", huella_actual),
                         ("observaciones", observaciones), ("incidencia", incidencia)):
        if str(valor or "").strip():
            nuevo[clave] = str(valor).strip()
    if "\n" in str(nuevo.get("observaciones", "")):
        nuevo["observaciones"] = LiteralScalarString(nuevo["observaciones"])   # legible en el YAML
    if evidencias:
        nuevo["evidencias"] = [str(e) for e in evidencias]
    if anterior:
        intentos = list(anterior.get("intentos") or [])
        previo = {k: v for k, v in dict(anterior).items() if k != "intentos"}
        # Solo se omite del historial si es exactamente lo mismo (repetir el mismo guardado);
        # un resultado distinto, aunque tenga el mismo estado, no debe perder el anterior.
        claves = ("estado", "huella", "origen", "observaciones", "incidencia", "evidencias")
        mismo = all(to_plain_simple(previo.get(k)) == to_plain_simple(nuevo.get(k)) for k in claves)
        if not mismo:
            intentos.append(previo)          # otro resultado: el anterior queda en el historial
        if intentos:
            nuevo["intentos"] = intentos
    resultados[test_id] = nuevo
    guardar(campaña)
    return nuevo


def editar_notas(campaña: dict[str, Any], test_id: str, *, observaciones: str | None = None,
                 incidencia: str | None = None, evidencias: list[str] | None = None) -> dict[str, Any]:
    """Corrige observaciones, incidencia o evidencias del resultado vigente sin crear otro intento."""
    _exigir_abierta(campaña)
    resultado = campaña["resultados"].get(test_id)
    if not resultado:
        raise ValueError("Apunta primero un resultado para esta prueba.")
    for clave, valor in (("observaciones", observaciones), ("incidencia", incidencia)):
        if valor is None:
            continue
        if str(valor).strip():
            resultado[clave] = str(valor).strip()
        else:
            resultado.pop(clave, None)
    if evidencias is not None:
        if evidencias:
            resultado["evidencias"] = [str(e) for e in evidencias]
        else:
            resultado.pop("evidencias", None)
    guardar(campaña)
    return resultado


MAX_EVIDENCIA_BYTES = 25 * 1024 * 1024


def guardar_evidencia(campaña: dict[str, Any], test_id: str, nombre: str, contenido: bytes) -> str:
    """Copia un archivo a `evidencias/` como «<ID>_<n>.<ext>» y devuelve su ruta relativa.

    No lo asocia al resultado: eso se hace al registrar (o con `editar_notas`).
    """
    _exigir_abierta(campaña)
    if len(contenido) > MAX_EVIDENCIA_BYTES:
        raise ValueError(f"{nombre or 'El archivo'} supera los 25 MB.")
    carpeta = campaña["carpeta"] / CARPETA_EVIDENCIAS
    carpeta.mkdir(parents=True, exist_ok=True)
    base = "".join(c if c.isalnum() or c in "-_." else "_" for c in test_id) or "evidencia"
    extension = Path(nombre or "").suffix.lower() or ".png"
    numero = 1
    while any(carpeta.glob(f"{base}_{numero:02d}.*")):
        numero += 1
    destino = carpeta / f"{base}_{numero:02d}{extension}"
    destino.write_bytes(contenido)
    return f"{CARPETA_EVIDENCIAS}/{destino.name}"


def ruta_evidencia(campaña: dict[str, Any], relativa: str) -> Path:
    """Ruta absoluta de una evidencia, sin permitir salir de la carpeta de la ejecución."""
    base = campaña["carpeta"].resolve()
    ruta = (base / str(relativa)).resolve()
    if base not in ruta.parents:
        raise ValueError("La evidencia debe estar dentro de la carpeta de la ejecución.")
    return ruta


def resincronizar(campaña: dict[str, Any], capitulos: list[dict[str, Any]],
                  ids_robot: set[str] | None = None) -> dict[str, list[str]]:
    """Vuelve a aplicar el criterio: añade las pruebas nuevas que lo cumplen.

    Las que ya no lo cumplen no se quitan (pueden tener resultados); se informa de ellas.
    """
    _exigir_abierta(campaña)
    seleccion = seleccionar(capitulos, dict(campaña["datos"].get("seleccion") or {}), ids_robot)
    _comprobar_ids(seleccion)
    actuales = set(ids_de(campaña))
    nuevas = [item for item in seleccion if item["id"] not in actuales]
    for item in nuevas:
        campaña["datos"]["pruebas"].append({"id": item["id"], "huella": huella(item["prueba"])})
    seleccionados = {item["id"] for item in seleccion}
    if nuevas:
        guardar(campaña)
    return {"añadidas": [i["id"] for i in nuevas], "ya_no_cumplen": sorted(actuales - seleccionados)}


def filtrar_contenido(contenido: list[Any], ids: set[str]) -> list[Any]:
    """Elementos de un capítulo que afectan a esas pruebas: las pruebas y las secciones que las contienen."""
    quedan = {
        i for i, e in enumerate(contenido)
        if isinstance(e, dict) and isinstance(e.get("prueba"), dict)
        and str(e["prueba"].get("id") or "").strip() in ids
    }
    if not quedan:
        return []
    for i, e in enumerate(contenido):
        if isinstance(e, dict) and isinstance(e.get("seccion"), str):
            fin = section_end_index(contenido, i)
            if any(i < j < fin for j in quedan):
                quedan.add(i)
    return [contenido[i] for i in sorted(quedan)]


def _rutas_imagen(valor: Any) -> set[str]:
    rutas: set[str] = set()
    if isinstance(valor, dict):
        for clave, hijo in valor.items():
            if clave in ("imagenes", "imagen"):
                for ruta in hijo if isinstance(hijo, list) else [hijo]:
                    if isinstance(ruta, str) and ruta.strip():
                        rutas.add(ruta.strip())
            else:
                rutas |= _rutas_imagen(hijo)
    elif isinstance(valor, list):
        for hijo in valor:
            rutas |= _rutas_imagen(hijo)
    return rutas


def congelar(campaña: dict[str, Any], capitulos: list[dict[str, Any]]) -> Path:
    """Copia a `pruebas_congeladas/` las pruebas de la ejecución (con sus secciones e imágenes).

    Tiene el mismo formato que una carpeta de pruebas, así que el informe y la
    revisión de una ejecución cerrada no dependen de cómo evolucionen los YAML.
    """
    destino = campaña["carpeta"] / CARPETA_CONGELADA
    if destino.exists():
        shutil.rmtree(destino)
    destino.mkdir(parents=True)
    ids = set(ids_de(campaña))
    indice, imagenes, base = [], set(), None
    for capitulo in capitulos:
        contenido = filtrar_contenido(capitulo["data"]["contenido"], ids)
        if not contenido:
            continue
        base = base or capitulo["path"].parent
        nombre = capitulo["data"].get("capitulo") or capitulo["path"].stem
        _escribir_yaml(destino / capitulo["path"].name, {"capitulo": nombre, "contenido": contenido})
        indice.append({"capitulo": nombre, "archivo": capitulo["path"].name})
        imagenes |= _rutas_imagen(contenido)
    _escribir_yaml(destino / "indice.yaml", indice)
    if base is not None:
        base = base.resolve()
        for relativa in sorted(imagenes):
            origen = (base / relativa).resolve()
            if base in origen.parents and origen.is_file():
                (destino / relativa).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(origen, destino / relativa)
    return destino


def cerrar(campaña: dict[str, Any], capitulos: list[dict[str, Any]]) -> None:
    """Cierra la ejecución: congela sus pruebas y no admite más cambios. No puede quedar nada pendiente."""
    _exigir_abierta(campaña)
    pendientes = [i for i in ids_de(campaña) if estado_de(campaña, i) == "pendiente"]
    if pendientes:
        raise ValueError(
            f"Quedan {len(pendientes)} pruebas pendientes ({', '.join(pendientes[:5])}"
            f"{'…' if len(pendientes) > 5 else ''}). Ejecútalas o márcalas como «No aplica»."
        )
    congelar(campaña, capitulos)
    campaña["datos"]["estado"] = "cerrada"
    campaña["datos"]["fin"] = ahora()
    guardar(campaña)


def capitulos_de(campaña: dict[str, Any]) -> list[dict[str, Any]]:
    """Capítulos con los que trabajar: los congelados si está cerrada, si no los vigentes."""
    if campaña["datos"].get("estado") == "cerrada":
        congelada = carpeta_congelada(campaña)
        if congelada is not None:
            return read_chapters(congelada)
    vigente = carpeta_pruebas(campaña)
    if vigente is None:
        raise ValueError("No se encuentran las pruebas de la ejecución.")
    return read_chapters(vigente)


# ----------------------------------------------------------------------
# Resumen y validación
# ----------------------------------------------------------------------
def resumen(campaña: dict[str, Any], capitulos: list[dict[str, Any]]) -> dict[str, Any]:
    """Totales por estado, desglose por capítulo y problemas a revisar."""
    por_id = indice_por_id(capitulos)
    nombres = {c["path"].name: str(c["data"].get("capitulo") or c["path"].name) for c in capitulos}
    totales = {estado: 0 for estado in ESTADOS}
    por_capitulo: dict[str, dict[str, int]] = {}
    problemas: list[dict[str, str]] = []
    pruebas = []
    for entrada in campaña["datos"]["pruebas"]:
        test_id = str(entrada["id"])
        estado = estado_de(campaña, test_id)
        resultado = campaña["resultados"].get(test_id) or {}
        totales[estado] += 1
        encontrada = por_id.get(test_id)
        cambiada = False
        if not encontrada:
            problemas.append({"id": test_id, "tipo": "error",
                              "mensaje": "La prueba ya no existe en los YAML de pruebas."})
            capitulo, titulo = "(sin capítulo)", ""
        else:
            prueba = encontrada["prueba"]
            capitulo = nombres.get(encontrada["archivo"], encontrada["archivo"])
            titulo = str(prueba.get("titulo") or prueba.get("nombre") or "")
            actual = huella(prueba)
            ejecutada = resultado.get("huella")
            if estado != "pendiente" and ejecutada and ejecutada != actual:
                cambiada = True
                problemas.append({"id": test_id, "tipo": "aviso",
                                  "mensaje": "La prueba ha cambiado después de ejecutarse."})
        if estado in ("no_ok", "bloqueada") and not str(resultado.get("observaciones") or "").strip():
            problemas.append({"id": test_id, "tipo": "aviso",
                              "mensaje": f"Resultado {ESTADOS_VISIBLES[estado]} sin observaciones."})
        por_capitulo.setdefault(capitulo, {e: 0 for e in ESTADOS})[estado] += 1
        pruebas.append({
            "id": test_id, "estado": estado, "titulo": titulo, "capitulo": capitulo,
            "archivo": encontrada["archivo"] if encontrada else None,
            "indice": encontrada["indice"] if encontrada else None,
            "intentos": len(resultado.get("intentos") or []) + (1 if resultado else 0),
            "cambiada": cambiada,
        })
    total = len(campaña["datos"]["pruebas"])
    ejecutadas = total - totales["pendiente"]
    aplicables = total - totales["no_aplica"]
    return {
        "total": total,
        "totales": totales,
        "ejecutadas": ejecutadas,
        "progreso": round(100 * ejecutadas / total, 1) if total else 0.0,
        # OK sobre lo que aplica: lo que «no aplica» no cuenta ni a favor ni en contra.
        "porcentaje_ok": round(100 * totales["ok"] / aplicables, 1) if aplicables else 0.0,
        "por_capitulo": por_capitulo,
        "problemas": problemas,
        "pruebas": pruebas,
    }
