"""Parámetros de las pruebas, repeticiones y pasadas.

En la *Parametrización* de una prueba, además de líneas de texto, puede haber
parámetros: el parámetro que se toca y los valores con los que hay que pasar
la prueba.

    parametrizacion:
    - 'Número de paradas: 4 (PB a P3).'          # texto, como siempre
    - parametro: Velocidad nominal
      valores: ['0,5 m/s', '1,0 m/s', '1,6 m/s']
    - parametro: Carga en cabina
      valores: ['0 %', '100 %']
    repeticiones: 5

Cada combinación de los valores de los parámetros con varios valores es una
configuración (aquí 3 × 2 = 6), y cada configuración se repite `repeticiones`
veces: la prueba tiene 30 **pasadas** en la ejecución, cada una con su
resultado. Un parámetro con un solo valor es fijo y no multiplica. Una prueba
sin parámetros con varios valores ni repeticiones no tiene pasadas: se ejecuta
una vez, como siempre.

El **catálogo de parámetros** del proyecto (un Excel o CSV que indica la clave
`parametros` del aztarna.yaml) dice qué parámetros hay, dónde se tocan en el
configurador, qué son y qué valores admiten; el editor lo usa para proponerlos.
"""
from __future__ import annotations

import csv
import itertools
import re
import unicodedata
from pathlib import Path
from typing import Any

MAX_REPETICIONES = 100
MAX_PASADAS = 500


# ----------------------------------------------------------------------
# Parámetros de una prueba
# ----------------------------------------------------------------------
def es_parametro(elemento: Any) -> bool:
    return isinstance(elemento, dict) and "parametro" in elemento


def valores_de(elemento: Any) -> list[str]:
    valores = elemento.get("valores") if isinstance(elemento, dict) else None
    if valores in (None, ""):
        return []
    if not isinstance(valores, list):
        valores = [valores]
    return [str(v).strip() for v in valores if str(v if v is not None else "").strip()]


def parametros_de(prueba: dict[str, Any]) -> list[dict[str, Any]]:
    """[{parametro, valores}] de la parametrización de la prueba, en su orden."""
    return [{"parametro": str(e.get("parametro") or "").strip(), "valores": valores_de(e)}
            for e in prueba.get("parametrizacion") or [] if es_parametro(e)]


def repeticiones_de(prueba: dict[str, Any]) -> int:
    try:
        return max(int(prueba.get("repeticiones") or 1), 1)
    except (TypeError, ValueError):
        return 1


def texto_parametro(elemento: dict[str, Any]) -> str:
    """«Velocidad nominal: 0,5 m/s / 1,0 m/s» (para el Word, el informe y la vista previa)."""
    nombre = str(elemento.get("parametro") or "").strip()
    valores = valores_de(elemento)
    return f"{nombre}: {' / '.join(valores)}" if valores else nombre


def lineas_documento(prueba: dict[str, Any]) -> list[Any]:
    """La parametrización para el Word: cada parámetro como «**Parámetro:** v1 / v2» y, al final, las repeticiones."""
    lineas: list[Any] = []
    for elemento in prueba.get("parametrizacion") or []:
        if es_parametro(elemento):
            nombre = str(elemento.get("parametro") or "").strip()
            valores = valores_de(elemento)
            lineas.append(f"**{nombre}:** {' / '.join(valores)}" if valores else f"**{nombre}**")
        else:
            lineas.append(elemento)
    repeticiones = repeticiones_de(prueba)
    if repeticiones > 1:
        lineas.append(f"**Repeticiones:** {repeticiones}")
    return lineas


_LINEA_PARAMETRO = re.compile(r"^\*\*(?P<nombre>[^*:\n]+?):\*\*[ \t]*(?P<valores>[^\n]*?)\s*$")


def desde_documento(items: list[Any]) -> tuple[list[Any], int | None]:
    """Lo contrario de `lineas_documento`, al importar un Word: «**Parámetro:** v1 / v2» vuelve a ser un
    parámetro y «**Repeticiones:** 5», las repeticiones. Devuelve (parametrización, repeticiones o None)."""
    salida: list[Any] = []
    repeticiones = None
    for item in items or []:
        coincide = _LINEA_PARAMETRO.match(item) if isinstance(item, str) else None
        if not coincide:
            salida.append(item)
            continue
        nombre, valores = coincide["nombre"].strip(), coincide["valores"].strip()
        if clave_nombre(nombre) == "repeticiones" and valores.isdigit() and repeticiones is None:
            repeticiones = int(valores)
            continue
        salida.append({"parametro": nombre, "valores": [v.strip() for v in valores.split(" / ") if v.strip()]})
    return salida, repeticiones


def configuraciones(prueba: dict[str, Any]) -> list[list[tuple[str, str]]]:
    """Combinaciones de los parámetros con varios valores: [[(parámetro, valor), …], …].

    Sin parámetros con varios valores, una sola configuración vacía.
    """
    variables = [(p["parametro"], p["valores"]) for p in parametros_de(prueba) if len(p["valores"]) > 1]
    if not variables:
        return [[]]
    return [list(zip([n for n, _ in variables], combinacion))
            for combinacion in itertools.product(*[v for _, v in variables])]


def texto_configuracion(configuracion: list[tuple[str, str]]) -> str:
    return " · ".join(f"{n}: {v}" for n, v in configuracion)


def pasadas(prueba: dict[str, Any]) -> list[dict[str, Any]]:
    """Las pasadas de la prueba en la ejecución, en orden; [] si se ejecuta una vez.

    Cada una: {clave, configuracion: [(parámetro, valor)], repeticion, repeticiones, texto}.
    La `clave` identifica el resultado en resultados.yaml: el texto de la
    configuración y, con repeticiones, «#n».
    """
    repeticiones = repeticiones_de(prueba)
    configs = configuraciones(prueba)
    if configs == [[]] and repeticiones == 1:
        return []
    lista = []
    for configuracion in configs:
        base = texto_configuracion(configuracion)
        for n in range(1, repeticiones + 1):
            sufijo = f"#{n}" if repeticiones > 1 else ""
            clave = f"{base} {sufijo}".strip()
            texto = " · ".join(t for t in (base, f"repetición {n}/{repeticiones}" if repeticiones > 1 else "") if t)
            lista.append({"clave": clave, "configuracion": configuracion, "repeticion": n,
                          "repeticiones": repeticiones, "texto": texto})
    return lista


def claves_pasadas(prueba: dict[str, Any] | None) -> list[str]:
    return [p["clave"] for p in pasadas(prueba)] if prueba else []


def problemas(prueba: dict[str, Any], catalogo: dict[str, dict[str, Any]] | None = None) -> list[tuple[str, str]]:
    """(severidad, mensaje) de los parámetros y las repeticiones de una prueba."""
    salida: list[tuple[str, str]] = []
    vistos: set[str] = set()
    for p in parametros_de(prueba):
        if not p["parametro"]:
            salida.append(("error", "Hay un parámetro sin nombre en la parametrización."))
            continue
        clave = clave_nombre(p["parametro"])
        if clave in vistos:
            salida.append(("error", f"El parámetro «{p['parametro']}» está repetido."))
        vistos.add(clave)
        if not p["valores"]:
            salida.append(("aviso", f"El parámetro «{p['parametro']}» no tiene valores."))
        if len(set(p["valores"])) != len(p["valores"]):
            salida.append(("error", f"El parámetro «{p['parametro']}» tiene valores repetidos."))
        if catalogo:
            del_catalogo = catalogo.get(clave)
            if del_catalogo is None:
                salida.append(("aviso", f"El parámetro «{p['parametro']}» no está en el catálogo de parámetros."))
            elif del_catalogo["valores"]:
                admitidos = {clave_nombre(v) for v in del_catalogo["valores"]}
                fuera = [v for v in p["valores"] if clave_nombre(v) not in admitidos]
                if fuera:
                    salida.append(("aviso", f"«{p['parametro']}»: {', '.join(fuera)} no "
                                            f"{'es un valor' if len(fuera) == 1 else 'son valores'} del catálogo."))
    valor = prueba.get("repeticiones")
    if valor not in (None, ""):
        try:
            n = int(valor)
        except (TypeError, ValueError):
            n = 0
        if n < 1 or n > MAX_REPETICIONES or str(valor).strip() != str(n):
            salida.append(("error", f"«Repeticiones» debe ser un número entre 1 y {MAX_REPETICIONES}."))
    total = len(configuraciones(prueba)) * repeticiones_de(prueba)
    if total > MAX_PASADAS:
        salida.append(("error", f"La prueba tiene {total} pasadas (el máximo es {MAX_PASADAS}): "
                                "reduce los valores o las repeticiones."))
    return salida


# ----------------------------------------------------------------------
# Resultado de una prueba a partir del de sus pasadas
# ----------------------------------------------------------------------
def estado_agregado(estados: list[str]) -> str:
    """NO OK si alguna falla; bloqueada si alguna no se pudo; pendiente si falta alguna;
    No aplica si ninguna aplica; si no, OK (todas OK o No aplica)."""
    if not estados:
        return "pendiente"
    for estado in ("no_ok", "bloqueada", "pendiente"):
        if estado in estados:
            return estado
    return "no_aplica" if all(e == "no_aplica" for e in estados) else "ok"


# ----------------------------------------------------------------------
# Catálogo de parámetros
# ----------------------------------------------------------------------
COLUMNAS = {
    "parametro": ("parametro", "parametros", "nombre"),
    "ubicacion": ("ubicacion", "donde", "configurador", "ruta"),
    "descripcion": ("descripcion", "detalle"),
    "valores": ("valores", "valoresposibles", "valoresadmitidos"),
    "unidad": ("unidad", "unidades"),
}


def clave_nombre(texto: Any) -> str:
    """Forma de comparar nombres: sin tildes, mayúsculas, espacios ni signos."""
    sin = "".join(c for c in unicodedata.normalize("NFD", str(texto)) if unicodedata.category(c) != "Mn")
    return re.sub(r"[\W_]+", "", sin).lower()


def _texto_celda(valor: Any) -> str:
    """Una celda de Excel como se ve: 4 y no 4.0, 0,5 y no 0.5."""
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "Sí" if valor else "No"
    if isinstance(valor, float):
        return (str(int(valor)) if valor.is_integer() else f"{valor:g}").replace(".", ",")
    return str(valor).strip()


def _tiene_cabecera(filas: list[list[str]]) -> bool:
    return any(clave_nombre(c) in COLUMNAS["parametro"] for fila in filas for c in fila)


def _filas(ruta: Path) -> list[list[str]]:
    if ruta.suffix.lower() in (".xlsx", ".xlsm"):
        from openpyxl import load_workbook

        libro = load_workbook(ruta, read_only=True, data_only=True)
        try:
            hojas = []
            for hoja in libro.worksheets:
                if hasattr(hoja, "reset_dimensions"):
                    hoja.reset_dimensions()      # algunos programas guardan mal el tamaño de la hoja
                hojas.append([[_texto_celda(c) for c in fila] for fila in hoja.iter_rows(values_only=True)])
        finally:
            libro.close()
        # La hoja con una columna «Parámetro»; si ninguna la tiene, la primera.
        return next((h for h in hojas if _tiene_cabecera(h)), hojas[0] if hojas else [])
    if ruta.suffix.lower() == ".xls":
        raise ValueError(f"{ruta.name}: es un Excel antiguo (.xls); guárdalo como .xlsx o como CSV.")
    if ruta.suffix.lower() in (".csv", ".txt"):
        texto = ruta.read_text(encoding="utf-8-sig")
        try:
            dialecto = csv.Sniffer().sniff(texto[:4096], delimiters=";,\t")
        except csv.Error:
            dialecto = csv.excel
        return [[c.strip() for c in fila] for fila in csv.reader(texto.splitlines(), dialecto)]
    raise ValueError(f"{ruta.name}: el catálogo de parámetros debe ser un Excel (.xlsx) o un CSV.")


def _separar_valores(texto: str) -> list[str]:
    return [v.strip() for v in re.split(r"[;\n|]", texto) if v.strip()]


def _columnas(claves: list[str]) -> dict[str, int | None]:
    """Columna de cada dato que se reconoce (por orden de preferencia de sus nombres)."""
    posicion: dict[str, int | None] = {}
    usadas: set[int] = set()
    for campo, nombres in COLUMNAS.items():
        posicion[campo] = next((i for nombre in nombres for i, c in enumerate(claves) if c == nombre and i not in usadas), None)
        if posicion[campo] is not None:
            usadas.add(posicion[campo])
    return posicion


def leer_catalogo(ruta: str | Path) -> list[dict[str, Any]]:
    """Parámetros del catálogo: [{parametro, ubicacion, descripcion, valores, unidad, otros}].

    La cabecera es la primera fila con una columna «Parámetro» (o, si ninguna la
    tiene, la primera fila con algo, y el parámetro es su primera columna). Las
    demás columnas son opcionales y van en cualquier orden: Ubicación,
    Descripción, Valores (separados por «;» o en líneas) y Unidad se reconocen
    por su nombre; las que tengan otro nombre van en `otros` como
    [[columna, valor], …], para enseñarlas tal cual.
    """
    ruta = Path(ruta)
    try:
        filas = _filas(ruta)
    except OSError as error:
        raise ValueError(f"No se puede leer el catálogo de parámetros {ruta}: {error}") from error
    cabecera, posicion = None, {}
    for n, fila in enumerate(filas):
        claves = [clave_nombre(c) for c in fila]
        if any(c in COLUMNAS["parametro"] for c in claves):
            cabecera, posicion = n, _columnas(claves)
            break
    if cabecera is None:
        # Sin columna «Parámetro»: la primera fila con algo es la cabecera y el parámetro, su primera columna.
        cabecera = next((n for n, fila in enumerate(filas) if any(c.strip() for c in fila)), None)
        if cabecera is None:
            raise ValueError(f"{ruta.name}: el catálogo de parámetros está vacío.")
        primera = next(i for i, c in enumerate(filas[cabecera]) if c.strip())
        claves = [clave_nombre(c) if i != primera else "parametro" for i, c in enumerate(filas[cabecera])]
        posicion = _columnas(claves)
    reconocidas = {i for i in posicion.values() if i is not None}
    otras = [(i, c.strip()) for i, c in enumerate(filas[cabecera]) if i not in reconocidas and c.strip()]
    catalogo, vistos = [], set()
    for fila in filas[cabecera + 1:]:
        def celda(i: int | None) -> str:
            return fila[i].strip() if i is not None and i < len(fila) else ""
        nombre = celda(posicion.get("parametro"))
        if not nombre or clave_nombre(nombre) in vistos:
            continue
        vistos.add(clave_nombre(nombre))
        catalogo.append({"parametro": nombre, "ubicacion": celda(posicion.get("ubicacion")),
                         "descripcion": celda(posicion.get("descripcion")),
                         "valores": _separar_valores(celda(posicion.get("valores"))), "unidad": celda(posicion.get("unidad")),
                         "otros": [[columna, celda(i)] for i, columna in otras if celda(i)]})
    return catalogo


def indice_catalogo(catalogo: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {clave_nombre(p["parametro"]): p for p in catalogo}
