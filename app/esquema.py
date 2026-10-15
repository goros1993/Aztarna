#!/usr/bin/env python3
"""Esquema de las pruebas y de los requisitos: qué campos tienen, cómo se llaman y qué valores admiten.

Es el único sitio donde se definen. Lo usan el importador del Word, el
editor (formulario y validación), la generación del DOCX y las campañas.
Para añadir, quitar o cambiar un campo en todas las pruebas: cámbialo aquí
(y, si el Word trae datos que convertir, la regla en `migrar_prueba`) y
vuelve a importar el Word.

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
from typing import Any

# ----------------------------------------------------------------------
# Campos
# ----------------------------------------------------------------------
# Texto de una línea (o de varias, en la descripción).
CAMPOS_TEXTO = ("nombre", "id", "titulo", "descripcion", "automatizable", "fecha", "version")
# Listas de elementos con formato, imágenes y subpuntos.
CAMPOS_LISTA = ("contexto", "parametrizacion", "situacion_inicial", "pasos")
# Varias opciones de una lista cerrada (se pueden marcar varias).
OPCIONES_MULTIPLES = {
    "maniobra": ("Simplex", "Dúplex"),
    "entorno": ("Automático", "Maqueta", "Torre"),
}
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


ENTORNO_PALABRAS = {"a": "Automático", "auto": "Automático", "automatico": "Automático", "automatica": "Automático",
                    "m": "Maqueta", "maqueta": "Maqueta", "t": "Torre", "torre": "Torre"}


def normalizar_entorno(valor: Any) -> tuple[list[str], list[str]]:
    """Entornos válidos y lo que no se reconoce. Admite «A», «M», «T» y mezclas («A/M», «AM», «A, T»)."""
    textos = valor if isinstance(valor, list) else [valor]
    validos, descartados = [], []
    for texto in textos:
        for trozo in re.split(r"[/,;]|\s+y\s+|\s+", str(texto or "").strip()):
            if not trozo:
                continue
            clave = _sin_tildes(trozo).lower().strip(".")
            if clave in ENTORNO_PALABRAS:
                encontrados = [ENTORNO_PALABRAS[clave]]
            elif re.fullmatch(r"[amt]{2,3}", clave):              # «AM», «AMT»
                encontrados = [ENTORNO_PALABRAS[letra] for letra in clave]
            else:
                descartados.append(trozo)
                continue
            validos.extend(e for e in encontrados if e not in validos)
    orden = OPCIONES_MULTIPLES["entorno"]
    return sorted(validos, key=orden.index), descartados


def normalizar_maniobra(valor: Any) -> tuple[list[str], list[str]]:
    """Maniobras válidas («S», «Simplex», «D»…) y lo que no se reconoce."""
    textos = valor if isinstance(valor, list) else [valor]
    validos, descartados = [], []
    for texto in textos:
        for trozo in re.split(r"[/,;]|\s+y\s+", str(texto or "")):
            trozo = trozo.strip()
            if not trozo:
                continue
            clave = re.sub(r"[\s_\-]", "", trozo).upper()
            m = re.fullmatch(r"MODO(3|III)(\+?)", clave)
            if m:
                maniobra = "Simplex" + m.group(2)
                if maniobra not in validos:
                    validos.append(maniobra)
            else:
                descartados.append(trozo)
    orden = OPCIONES_MULTIPLES["maniobra"]
    return sorted(validos, key=orden.index), descartados


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
# Requisitos (plantilla en plantillas/tabla_requisito.docx)
# ----------------------------------------------------------------------
#     ID | Título
#     Descripción
#     Fuente
#     Referencia
#     Tipo | Criterio de validación
#     Fase | Fecha | Versión
#
# Van en la carpeta `requisitos/` dentro de la carpeta de pruebas, con el mismo
# formato de capítulos y secciones; cada requisito es un elemento `requisito:`.
CARPETA_REQUISITOS = "requisitos"

REQ_CAMPOS_TEXTO = ("nombre", "id", "titulo", "descripcion", "fuente", "referencia", "tipo", "fase", "fecha", "version")
REQ_CAMPOS_LISTA = ("contexto",)
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
    "nombre", "nivel", "id", "titulo", "descripcion", "fuente", "referencia", "tipo", "criterio_validacion",
    "fase", "fecha", "version", "contexto",
)

REQ_ETIQUETAS = {
    "id": "ID", "nombre": "Encabezado en el documento", "titulo": "Título", "descripcion": "Descripción",
    "fuente": "Fuente", "referencia": "Referencia", "tipo": "Tipo", "criterio_validacion": "Criterio validación",
    "fase": "Fase", "fecha": "Fecha", "version": "Versión", "contexto": "Contexto",
}


def requisito_vacio() -> dict[str, Any]:
    """Requisito nuevo con todos los campos del esquema, vacíos."""
    vacio: dict[str, Any] = {"nombre": "", "nivel": 3}
    for clave in REQ_ORDEN:
        if clave not in vacio:
            vacio[clave] = "" if clave in REQ_CAMPOS_TEXTO else []
    return vacio


def necesita_pruebas(requisito: Any) -> bool:
    """Si el requisito se verifica con pruebas (criterio «Test» o sin criterio, y no informativo)."""
    if str(requisito.get("tipo") or "").strip() == TIPO_SIN_VERIFICACION:
        return False
    criterio = requisito.get("criterio_validacion") or []
    criterio = criterio if isinstance(criterio, list) else [criterio]
    return not criterio or CRITERIO_CON_PRUEBAS in criterio
