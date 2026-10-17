#!/usr/bin/env python3
"""Esquema de las pruebas y de los requisitos: qué campos tienen, cómo se llaman y qué valores admiten.

Es el único sitio donde se definen. Lo usan el importador del Word, el
editor (formulario y validación), la generación del DOCX y las ejecuciones.
Para añadir, quitar o cambiar un campo en todas las pruebas: cámbialo aquí
(y, si el Word trae datos que convertir, la regla en `migrar_prueba`) y
vuelve a importar el Word.

Las opciones de maniobra y de entorno son de cada proyecto: se leen de su
`aztarna.yaml` (ver `configurar`). Sin ese archivo, maniobra no tiene opciones
y entorno usa las de los ejemplos.

Orden de la tabla de cada prueba (plantilla en plantillas/tabla_prueba.docx):

    ID | Título
    Descripción
    Parametrización (lista)
    Situación inicial (lista) y Ensayo (lista numerada)
    Maniobra | Automatizable | Entorno de pruebas
    Requisitos | Tags
    Fecha | Versión
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

# ----------------------------------------------------------------------
# Campos
# ----------------------------------------------------------------------
# Texto de una línea (o de varias, en la descripción).
CAMPOS_TEXTO = ("nombre", "id", "titulo", "descripcion", "automatizable", "fecha", "version")
# Listas de elementos con formato, imágenes y subpuntos.
CAMPOS_LISTA = ("contexto", "parametrizacion", "situacion_inicial", "pasos")
# Varias opciones de una lista cerrada (se pueden marcar varias). Son las de
# partida: `configurar` las cambia por las del aztarna.yaml del proyecto.
OPCIONES_BASE: dict[str, tuple[str, ...]] = {
    "maniobra": (),
    "entorno": ("Automático", "Maqueta", "Torre"),
}
# Otras formas de escribir una opción que se reconocen al importar («A» → Automático).
EQUIVALENCIAS_BASE: dict[str, dict[str, str]] = {
    "maniobra": {},
    "entorno": {"A": "Automático", "Auto": "Automático", "Automática": "Automático", "M": "Maqueta", "T": "Torre"},
}
OPCIONES_MULTIPLES: dict[str, tuple[str, ...]] = dict(OPCIONES_BASE)
EQUIVALENCIAS: dict[str, dict[str, str]] = {k: dict(v) for k, v in EQUIVALENCIAS_BASE.items()}
# Una opción de una lista cerrada.
AUTOMATIZABLE = ("si", "no", "corto", "medio", "largo", "hecho")
AUTOMATIZABLE_VISIBLE = {"si": "Sí", "no": "No", "corto": "Corto", "medio": "Medio", "largo": "Largo", "hecho": "Hecho"}
# Listas de textos sencillos (sin formato).
CAMPOS_TEXTOS = ("requisitos", "etiquetas")
# Obligatorios: la validación da error si faltan.
OBLIGATORIOS = ("id", "titulo")

# Orden de las claves en el YAML.
ORDEN = (
    "nombre", "nivel", "id", "titulo", "descripcion", "parametrizacion", "situacion_inicial", "pasos",
    "maniobra", "automatizable", "entorno", "requisitos", "etiquetas", "fecha", "version",
    "contexto", "campos_adicionales", "imagenes",
)

ETIQUETAS = {
    "id": "ID", "nombre": "Encabezado en el documento", "titulo": "Título", "descripcion": "Descripción",
    "parametrizacion": "Parametrización", "situacion_inicial": "Situación inicial", "pasos": "Ensayo",
    "maniobra": "Maniobra", "automatizable": "Automatizable", "entorno": "Entorno de pruebas",
    "requisitos": "Requisitos", "etiquetas": "Tags", "fecha": "Fecha", "version": "Versión",
    "contexto": "Contexto", "campos_adicionales": "Campos adicionales", "imagenes": "Imágenes",
}

# Campos que ya no existen. `migrar_prueba` los quita (situacion_final pasa a Ensayo).
OBSOLETOS = ("componente", "plataforma", "criticidad", "referencia", "situacion_final")

# Campos adicionales del Word antiguo: los que pasan a un campo propio y los que se eliminan.
ADICIONALES_A_CAMPO = {
    "maniobra(s)": "maniobra", "maniobra": "maniobra",
    "requisito(s)": "requisitos", "requisitos": "requisitos",
    "tags": "etiquetas",
}
ADICIONALES_ELIMINADOS = (
    "Resultado esperado", "Criterio(s) de aceptación", "Criterio validación",
    "Ejecutor prueba", "Fecha ejecución", "Resultado Obtenido", "Resultado obtenido",
    "Decisión", "Resultado", "Observaciones",
)


def prueba_vacia() -> dict[str, Any]:
    """Prueba nueva con todos los campos del esquema, vacíos."""
    vacia: dict[str, Any] = {"nombre": "", "nivel": 3}
    for clave in ORDEN:
        if clave in vacia:
            continue
        if clave in CAMPOS_TEXTO:
            vacia[clave] = ""
        elif clave == "campos_adicionales":
            vacia[clave] = {}
        else:
            vacia[clave] = []
    return vacia


# ----------------------------------------------------------------------
# Normalizar valores
# ----------------------------------------------------------------------
def _sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def _clave(texto: str) -> str:
    return re.sub(r"\s+", "", _sin_tildes(str(texto))).lower()


def _clave_opcion(texto: Any) -> str:
    """Forma de comparar opciones: sin tildes, espacios, guiones ni mayúsculas («Modo 1» = «modo1»)."""
    return re.sub(r"[\s_\-.]", "", _sin_tildes(str(texto))).lower()


def _reconocer(campo: str, trozo: str) -> list[str] | None:
    """Opciones que nombra un trozo de texto (una opción, una equivalencia o, si son
    letras sueltas, varias juntas: «AM» → Automático y Maqueta); None si no encaja."""
    claves = {_clave_opcion(o): o for o in OPCIONES_MULTIPLES[campo]}
    claves.update({_clave_opcion(k): v for k, v in EQUIVALENCIAS[campo].items()})
    clave = _clave_opcion(trozo)
    if clave in claves:
        return [claves[clave]]
    palabras = trozo.split()
    if len(palabras) > 1 and all(_clave_opcion(p) in claves for p in palabras):
        return [claves[_clave_opcion(p)] for p in palabras]
    if len(clave) > 1 and all(letra in claves for letra in clave):
        return [claves[letra] for letra in clave]
    return None


def normalizar_opciones(campo: str, valor: Any) -> tuple[list[str], list[str]]:
    """Opciones válidas de `campo` y lo que no se reconoce. Admite las opciones escritas
    de otra forma, sus equivalencias y mezclas («A/M», «AM», «A, T»)."""
    textos = valor if isinstance(valor, list) else [valor]
    validos, descartados = [], []
    for texto in textos:
        for trozo in re.split(r"[/,;]|\s+y\s+", str(texto or "")):
            trozo = trozo.strip()
            if not trozo:
                continue
            encontrados = _reconocer(campo, trozo)
            if encontrados is None:
                descartados.append(trozo)
            else:
                validos.extend(e for e in encontrados if e not in validos)
    orden = OPCIONES_MULTIPLES[campo]
    return sorted(validos, key=orden.index), descartados


def normalizar_entorno(valor: Any) -> tuple[list[str], list[str]]:
    """Entornos válidos y lo que no se reconoce («A», «M», «T» y mezclas como «A/M» o «AM»)."""
    return normalizar_opciones("entorno", valor)


def normalizar_maniobra(valor: Any) -> tuple[list[str], list[str]]:
    """Maniobras válidas (las del proyecto y sus equivalencias) y lo que no se reconoce."""
    return normalizar_opciones("maniobra", valor)


def normalizar_automatizable(valor: Any) -> str | None:
    """Valor válido de Automatizable ("" si está vacío) o None si no se reconoce."""
    clave = _clave(valor or "").rstrip(".")
    if not clave:
        return ""
    return clave if clave in AUTOMATIZABLE else None


def lista_de_textos(valor: Any, separador: str = r"\n") -> list[str]:
    """Lista de textos sencillos a partir de una lista o de un texto con varias líneas."""
    if valor in (None, ""):
        return []
    elementos = valor if isinstance(valor, list) else re.split(separador, str(valor))
    resultado = []
    for e in elementos:
        texto = " ".join(str(e).split()).strip(" ,;")
        if texto and texto not in resultado:
            resultado.append(texto)
    return resultado


# ----------------------------------------------------------------------
# Migración del esquema anterior
# ----------------------------------------------------------------------
def _poner(prueba: Any, clave: str, valor: Any) -> None:
    """Pone `clave` en su sitio del ORDEN (o la actualiza si ya existe)."""
    if clave in prueba:
        prueba[clave] = valor
        return
    posicion = len(prueba)
    anteriores = ORDEN[:ORDEN.index(clave)] if clave in ORDEN else ORDEN
    claves = list(prueba.keys())
    for i in range(len(claves) - 1, -1, -1):
        if claves[i] in anteriores:
            posicion = i + 1
            break
    if hasattr(prueba, "insert"):                 # CommentedMap de ruamel (conserva comentarios)
        prueba.insert(posicion, clave, valor)
    else:
        elementos = list(prueba.items())
        elementos.insert(posicion, (clave, valor))
        prueba.clear()
        prueba.update(elementos)


def migrar_prueba(prueba: Any) -> list[tuple[str, str]]:
    """Pasa una prueba del esquema anterior a este. Devuelve avisos (tipo, mensaje).

    - Situación final se añade al final de Ensayo (pasos).
    - Componente, plataforma, criticidad y referencia se eliminan.
    - Maniobra(s), Requisito(s) y Tags de campos adicionales pasan a su campo.
    - Resultado esperado, criterios y los campos de resultado se eliminan.
    - Entorno y maniobra pasan a lista de opciones; lo que no encaja se descarta.
    No cambia nada si la prueba ya sigue el esquema.
    """
    avisos: list[tuple[str, str]] = []
    final = prueba.get("situacion_final")
    if final:
        pasos = prueba.get("pasos")
        pasos = list(pasos) if isinstance(pasos, list) else ([pasos] if pasos else [])
        _poner(prueba, "pasos", pasos + (list(final) if isinstance(final, list) else [final]))
    eliminados = [c for c in OBSOLETOS if c in prueba and c != "situacion_final" and prueba.get(c) not in (None, "", [])]
    for clave in OBSOLETOS:
        prueba.pop(clave, None)
    if eliminados:
        avisos.append(("campos_eliminados", f"se eliminan {', '.join(eliminados)}"))

    extras = prueba.get("campos_adicionales")
    if isinstance(extras, dict) and extras:
        for etiqueta in list(extras.keys()):
            clave = _clave(etiqueta)
            destino = ADICIONALES_A_CAMPO.get(clave)
            if destino:
                valor = extras.pop(etiqueta)
                actual = prueba.get(destino) or []
                actual = actual if isinstance(actual, list) else [actual]
                nuevos = lista_de_textos(valor, r"[\n,]" if destino == "etiquetas" else r"\n")
                if destino == "maniobra":
                    nuevos = [str(valor or "")]
                _poner(prueba, destino, list(actual) + [n for n in nuevos if n not in actual])
            elif clave in {_clave(e) for e in ADICIONALES_ELIMINADOS}:
                if str(extras.get(etiqueta) or "").strip():
                    avisos.append(("campos_eliminados", f"se elimina «{etiqueta}» (con datos)"))
                extras.pop(etiqueta)
        if not extras:                              # se quedó vacío al pasar sus campos a su sitio
            prueba.pop("campos_adicionales", None)

    for campo, normalizar in (("entorno", normalizar_entorno), ("maniobra", normalizar_maniobra)):
        if campo in prueba and prueba[campo] not in (None, "", []):
            validos, descartados = normalizar(prueba[campo])
            if validos != (list(prueba[campo]) if isinstance(prueba[campo], list) else None):
                _poner(prueba, campo, validos)
            if descartados:
                avisos.append(("valor_descartado", f"{ETIQUETAS[campo]}: se descarta «{', '.join(descartados)}»"))
        elif campo in prueba and not isinstance(prueba[campo], list):
            _poner(prueba, campo, [])

    if "automatizable" in prueba:
        valor = normalizar_automatizable(prueba["automatizable"])
        if valor is None:
            avisos.append(("valor_descartado", f"Automatizable: se descarta «{prueba['automatizable']}»"))
            valor = ""
        if valor != prueba["automatizable"]:
            prueba["automatizable"] = valor
    if "requisitos" in prueba and not isinstance(prueba["requisitos"], list):
        _poner(prueba, "requisitos", lista_de_textos(prueba["requisitos"]))
    return avisos


def completar(prueba: Any) -> None:
    """Añade, vacíos, los campos del esquema que falten (para que todas las tablas sean iguales)."""
    for clave, valor in prueba_vacia().items():
        if clave not in prueba and clave not in ("nombre", "nivel", "contexto", "campos_adicionales", "imagenes"):
            _poner(prueba, clave, valor)


# ----------------------------------------------------------------------
# Opciones del proyecto (aztarna.yaml)
# ----------------------------------------------------------------------
#     opciones:
#       maniobra: [Simplex, Dúplex]
#       entorno: [Automático, Maqueta, Torre]
#     equivalencias:                  # otras formas de escribirlas en el Word
#       maniobra: {S: Simplex, D: Dúplex}
#
# Va en la carpeta del proyecto (junto a pruebas/ y requisitos/) o, en una
# carpeta de pruebas suelta, dentro de ella. Un campo que no aparece conserva sus
# opciones de partida; uno con opciones y sin equivalencias usa las de partida que
# lleven a una de sus opciones.
ARCHIVO_CONFIGURACION = "aztarna.yaml"
# El aztarna.yaml que se está usando (None: las opciones de partida) y su contenido.
CONFIGURACION: Path | None = None
_CONTENIDO_CONFIGURACION: bytes = b""


def archivo_configuracion(carpeta_pruebas: str | Path) -> Path | None:
    """El aztarna.yaml de una carpeta de pruebas (o del proyecto que la contiene), si lo hay."""
    carpeta = Path(carpeta_pruebas)
    candidatos = [carpeta / ARCHIVO_CONFIGURACION]
    if carpeta.name == CARPETA_PRUEBAS:
        candidatos.append(carpeta.parent / ARCHIVO_CONFIGURACION)
    return next((c for c in candidatos if c.is_file()), None)


def _leer_configuracion(ruta: Path) -> tuple[dict[str, tuple[str, ...]], dict[str, dict[str, str]]]:
    from ruamel.yaml import YAML
    from ruamel.yaml.error import YAMLError

    try:
        with ruta.open(encoding="utf-8") as f:
            datos = YAML(typ="safe").load(f) or {}
    except (OSError, YAMLError) as error:
        raise ValueError(f"No se puede leer {ruta}: {error}") from error
    if not isinstance(datos, dict) or set(datos) - {"opciones", "equivalencias"}:
        raise ValueError(f"{ruta}: solo admite «opciones» y «equivalencias».")
    opciones, equivalencias = {}, {}
    for campo, valores in (datos.get("opciones") or {}).items():
        if campo not in OPCIONES_BASE:
            raise ValueError(f"{ruta}: «{campo}» no es un campo con opciones ({', '.join(OPCIONES_BASE)}).")
        valores = [str(v).strip() for v in (valores if isinstance(valores, list) else [valores]) if str(v or "").strip()]
        if len({_clave_opcion(v) for v in valores}) != len(valores):
            raise ValueError(f"{ruta}: hay opciones repetidas en «{campo}».")
        opciones[campo] = tuple(valores)
    for campo, pares in (datos.get("equivalencias") or {}).items():
        if campo not in OPCIONES_BASE or not isinstance(pares, dict):
            raise ValueError(f"{ruta}: las equivalencias de «{campo}» deben ser «forma: opción».")
        validas = opciones.get(campo, OPCIONES_BASE[campo])
        for forma, opcion in pares.items():
            if str(opcion) not in validas:
                raise ValueError(f"{ruta}: la equivalencia «{forma}» lleva a «{opcion}», que no es una opción de «{campo}».")
        equivalencias[campo] = {str(k): str(v) for k, v in pares.items()}
    return opciones, equivalencias


def configurar(carpeta_pruebas: str | Path | None) -> Path | None:
    """Usa las opciones del aztarna.yaml de esa carpeta (o las de partida si no tiene).

    También admite la ruta del propio archivo. Devuelve el archivo leído. Un archivo
    mal escrito da ValueError y deja las opciones como estaban.
    """
    global CONFIGURACION, _CONTENIDO_CONFIGURACION
    ruta = None
    if carpeta_pruebas is not None:
        ruta = Path(carpeta_pruebas) if Path(carpeta_pruebas).is_file() else archivo_configuracion(carpeta_pruebas)
    opciones, equivalencias = _leer_configuracion(ruta) if ruta else ({}, {})
    for campo, base in OPCIONES_BASE.items():
        OPCIONES_MULTIPLES[campo] = opciones.get(campo, base)
        if campo in equivalencias:
            EQUIVALENCIAS[campo] = equivalencias[campo]
        else:
            EQUIVALENCIAS[campo] = {k: v for k, v in EQUIVALENCIAS_BASE[campo].items() if v in OPCIONES_MULTIPLES[campo]}
    CONFIGURACION = ruta
    _CONTENIDO_CONFIGURACION = ruta.read_bytes() if ruta else b""
    return ruta


def copiar_configuracion(destino: str | Path) -> None:
    """Deja en `destino` (un proyecto o una carpeta de pruebas nuevos) el aztarna.yaml que se está usando."""
    if CONFIGURACION is not None and not (Path(destino) / ARCHIVO_CONFIGURACION).exists():
        Path(destino).mkdir(parents=True, exist_ok=True)
        (Path(destino) / ARCHIVO_CONFIGURACION).write_bytes(_CONTENIDO_CONFIGURACION)


# ----------------------------------------------------------------------
# Requisitos (plantilla en plantillas/tabla_requisito.docx)
# ----------------------------------------------------------------------
#     ID | Título
#     Descripción (con sus tablas e imágenes, en `detalle`)
#     Fuente
#     Referencia
#     Tipo | Criterio de validación
#     Fase | Fecha | Versión
#
# Van en la carpeta `requisitos/`, junto a la de pruebas (`proyecto/pruebas` y
# `proyecto/requisitos`) o, en una carpeta de pruebas suelta, dentro de ella. Tienen
# el mismo formato de capítulos y secciones; cada requisito es un elemento `requisito:`.
CARPETA_PRUEBAS = "pruebas"
CARPETA_REQUISITOS = "requisitos"

REQ_CAMPOS_TEXTO = ("nombre", "id", "titulo", "descripcion", "fuente", "referencia", "tipo", "fase", "fecha", "version")
# `detalle`: tablas, imágenes y párrafos que siguen a la descripción dentro de su celda.
REQ_CAMPOS_LISTA = ("detalle", "contexto")
REQ_OPCIONES_MULTIPLES = {
    "criterio_validacion": ("Inspección", "Análisis", "Test"),
}
# Una opción de una lista cerrada.
REQ_TIPOS = ("Informativo", "Obligatorio", "Opcional")
REQ_OBLIGATORIOS = ("id", "titulo")
# Criterio de validación que pide pruebas: un requisito sin criterio también las pide.
CRITERIO_CON_PRUEBAS = "Test"
# Un requisito de este tipo no se verifica (no necesita pruebas).
TIPO_SIN_VERIFICACION = "Informativo"

REQ_ORDEN = (
    "nombre", "nivel", "id", "titulo", "descripcion", "detalle", "fuente", "referencia", "tipo", "criterio_validacion",
    "fase", "fecha", "version", "contexto", "campos_adicionales",
)

REQ_ETIQUETAS = {
    "id": "ID", "nombre": "Encabezado en el documento", "titulo": "Título", "descripcion": "Descripción",
    "fuente": "Fuente", "referencia": "Referencia", "tipo": "Tipo", "criterio_validacion": "Criterio validación",
    "fase": "Fase", "fecha": "Fecha", "version": "Versión", "contexto": "Contexto",
    "detalle": "Tablas e imágenes de la descripción", "campos_adicionales": "Campos adicionales",
}


def requisito_vacio() -> dict[str, Any]:
    """Requisito nuevo con todos los campos del esquema, vacíos."""
    vacio: dict[str, Any] = {"nombre": "", "nivel": 3}
    for clave in REQ_ORDEN:
        if clave not in vacio and clave not in ("detalle", "campos_adicionales"):
            vacio[clave] = "" if clave in REQ_CAMPOS_TEXTO else []
    return vacio


def normalizar_tipo_requisito(valor: Any) -> str | None:
    """Tipo del requisito con su forma de la lista («obligatorio» → «Obligatorio»); "" si está vacío y None si no es una opción."""
    clave = _clave(valor or "").rstrip(".")
    if not clave:
        return ""
    return next((t for t in REQ_TIPOS if _clave(t) == clave), None)


def normalizar_criterio(valor: Any) -> tuple[list[str], list[str]]:
    """Criterios de validación válidos («Test», «inspeccion / analisis»…) y lo que no se reconoce."""
    textos = valor if isinstance(valor, list) else [valor]
    opciones = REQ_OPCIONES_MULTIPLES["criterio_validacion"]
    validos, descartados = [], []
    for texto in textos:
        for trozo in re.split(r"[/,;]|\s+y\s+|\s+o\s+", str(texto or "")):
            trozo = trozo.strip().rstrip(".")
            if not trozo:
                continue
            opcion = next((o for o in opciones if _clave(o) == _clave(trozo) or _clave(o).startswith(_clave(trozo)[:4]) and len(_clave(trozo)) >= 4), None)
            if opcion is None:
                descartados.append(trozo)
            elif opcion not in validos:
                validos.append(opcion)
    return sorted(validos, key=opciones.index), descartados


def necesita_pruebas(requisito: Any) -> bool:
    """Si el requisito se verifica con pruebas (criterio «Test» o sin criterio, y no informativo)."""
    if str(requisito.get("tipo") or "").strip() == TIPO_SIN_VERIFICACION:
        return False
    criterio = requisito.get("criterio_validacion") or []
    criterio = criterio if isinstance(criterio, list) else [criterio]
    return not criterio or CRITERIO_CON_PRUEBAS in criterio
