#!/usr/bin/env python3
"""API del editor web de Aztarna (pruebas YAML).

La interfaz HTML/JS llama a los métodos públicos de `EditorApi` (a través de
pywebview: `window.pywebview.api.<método>(...)`). Esta clase no importa
pywebview al cargarse, de modo que se puede probar sin interfaz.

Convenciones:
- Todo método público devuelve un diccionario JSON:
  `{"ok": True, "datos": ...}` o `{"ok": False, "error": "mensaje"}`.
- Los atributos y métodos privados empiezan por `_` (pywebview no expone
  esos nombres a JavaScript).
- Los YAML se leen y se escriben con ruamel en modo roundtrip: solo se
  tocan los campos que cambian, así se conservan comentarios y formato.
"""
from __future__ import annotations

import base64
import contextlib
import functools
import io
import re
import subprocess
import sys
import threading
import traceback
from pathlib import Path
from typing import Any, Callable

from ruamel.yaml.error import YAMLError

from app import adjuntos, ajustes, bloqueos, esquema, formato, trazabilidad
from app.editor_core import (
    ALLOWED_IMAGE_EXTENSIONS,
    LIST_FIELDS,
    block_range,
    change_levels,
    create_chapter,
    delete_section,
    delete_test,
    find_duplicate_id,
    headings_in_chapter,
    insert_section_after_test,
    insert_table,
    insert_test,
    is_table,
    item_key,
    items_in_chapter,
    move_block,
    navigation_entries,
    normalize_level,
    tests_dir,
    read_chapters,
    roundtrip_yaml,
    save_chapter,
    save_uploaded_images,
    section_end_index,
    table_rows,
    table_title,
    tests_in_chapter,
    yaml_to_string,
)

TEXT_FIELDS = esquema.CAMPOS_TEXTO
MAX_IMAGE_BYTES = 25 * 1024 * 1024
EMPTY = (None, "", [], {})


# ----------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------
def to_plain(value: Any) -> Any:
    """Convierte estructuras de ruamel en tipos simples serializables a JSON."""
    if isinstance(value, dict):
        return {str(key): to_plain(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain(child) for child in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


_YAML_EN_ESPANOL = (
    ("mapping values are not allowed here", "Aquí no se permite un valor de clave: revisa los ':' y la sangría"),
    ("could not find expected ':'", "Falta ':' después de la clave"),
    ("found character '\\t'", "Hay una tabulación: usa espacios para la sangría"),
    ("did not find expected '-' indicator", "Falta '-' al inicio de un elemento de lista"),
    ("did not find expected key", "Se esperaba una clave: revisa la sangría"),
    ("expected ',' or ']'", "Falta ',' o ']' en la lista entre corchetes"),
    ("expected ',' or '}'", "Falta ',' o '}' en el mapa entre llaves"),
    ("while scanning a quoted scalar", "Hay una comilla sin cerrar"),
    ("found unexpected end of stream", "El texto termina antes de cerrar una comilla, un corchete o un bloque"),
    ("found duplicate key", "Hay una clave repetida en el mismo bloque"),
    ("expected <block end>", "La sangría no es coherente con las líneas anteriores"),
    ("block sequence entries are not allowed", "Aquí no se permite un elemento de lista"),
)


def mensaje_yaml(error: Exception) -> str:
    """Mensaje de un error de ruamel en español (si se reconoce), sin posición."""
    problem = str(getattr(error, "problem", None) or str(error).strip().splitlines()[0])
    texto = f"{getattr(error, 'context', None) or ''} {problem}"
    return next((es for fragmento, es in _YAML_EN_ESPANOL if fragmento in texto), problem)


def respuesta(function: Callable[..., Any]) -> Callable[..., dict[str, Any]]:
    """Envuelve un método de la API: serializa el resultado y captura errores."""

    @functools.wraps(function)
    def wrapper(self: "EditorApi", *args: Any, **kwargs: Any) -> dict[str, Any]:
        with self._lock:
            try:
                return {"ok": True, "datos": function(self, *args, **kwargs)}
            except YAMLError as error:
                mark = getattr(error, "problem_mark", None)
                donde = f" (línea {mark.line + 1}, columna {mark.column + 1})" if mark else ""
                return {"ok": False, "error": mensaje_yaml(error) + donde}
            except (OSError, ValueError, KeyError, IndexError) as error:
                message = error.args[0] if isinstance(error, KeyError) and error.args else str(error)
                return {"ok": False, "error": str(message) or error.__class__.__name__}
            except Exception as error:  # noqa: BLE001 - la interfaz debe seguir viva
                traceback.print_exc()
                return {"ok": False, "error": f"Error inesperado: {error}"}

    return wrapper


class _ArchivoLocal:
    """Adaptador con la interfaz que espera `save_uploaded_images`."""

    def __init__(self, nombre: str, contenido: bytes) -> None:
        self.name = nombre
        self._contenido = contenido

    def getvalue(self) -> bytes:
        return self._contenido


def _image_values(value: Any) -> list[str]:
    """Rutas de imagen (claves `imagenes` e `imagen`) en cualquier nivel."""
    rutas: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in ("imagenes", "imagen"):
                valores = child if isinstance(child, list) else [child]
                rutas.extend(v.strip() for v in valores if isinstance(v, str) and v.strip())
            else:
                rutas.extend(_image_values(child))
    elif isinstance(value, list):
        for child in value:
            rutas.extend(_image_values(child))
    return rutas


def _clean_item(item: Any) -> Any:
    """Normaliza un elemento de lista recibido de la interfaz."""
    if isinstance(item, str):
        return item.strip()
    if not isinstance(item, dict):
        raise ValueError("Cada elemento de una lista debe ser texto o un mapa.")
    if "tabla" in item:
        # Tabla dentro del contexto (historial, parámetros…): se conserva con sus demás claves (motivo).
        tabla = item["tabla"] if isinstance(item["tabla"], dict) else {}
        return {"tabla": {**{k: v for k, v in tabla.items() if k != "filas"}, "filas": _clean_table(tabla.get("filas"))}}
    cleaned: dict[str, Any] = {}
    for key, value in item.items():
        if key == "texto":
            cleaned[key] = str(value or "").strip()
        elif key == "imagenes":
            images = [str(v).strip() for v in (value or []) if str(v).strip()]
            if images:
                cleaned[key] = images
        elif key == "adjuntos":
            refs = adjuntos.referencias(item)
            if refs:
                cleaned[key] = refs
        elif key == "nivel":
            if value not in (None, "", 0):
                cleaned[key] = int(value)
        else:
            cleaned[key] = value
    return cleaned


def _clean_list(items: Any, field: str) -> list[Any]:
    if items is None:
        return []
    if not isinstance(items, list):
        raise ValueError(f"'{field}' debe ser una lista.")
    result = []
    for item in items:
        cleaned = _clean_item(item)
        empty_text = isinstance(cleaned, str) and not cleaned
        empty_map = (isinstance(cleaned, dict) and not cleaned.get("texto") and not cleaned.get("imagenes")
                     and not cleaned.get("adjuntos") and "tabla" not in cleaned)
        if not (empty_text or empty_map):
            result.append(cleaned)
    return result


def _clean_extras(extras: Any) -> dict[str, Any]:
    if extras is None:
        return {}
    if not isinstance(extras, dict):
        raise ValueError("'campos_adicionales' debe ser un mapa.")
    cleaned: dict[str, Any] = {}
    for key, value in extras.items():
        name = str(key).strip()
        if not name:
            continue
        if name in cleaned:
            raise ValueError(f"El campo adicional «{name}» está repetido.")
        cleaned[name] = value
    return cleaned


def _clean_table(filas: Any) -> list[list[Any]]:
    """Filas de una tabla: cada celda es un texto o {texto, imagenes, columnas}."""
    if not isinstance(filas, list) or not filas:
        raise ValueError("La tabla necesita al menos una fila.")
    limpias = []
    for fila in filas:
        if not isinstance(fila, list) or not fila:
            raise ValueError("Cada fila de la tabla necesita al menos una celda.")
        celdas = []
        for celda in fila:
            if isinstance(celda, dict):
                texto = str(celda.get("texto") or "").replace("\r\n", "\n")
                imagenes = [str(i).strip() for i in (celda.get("imagenes") or []) if str(i).strip()]
                try:
                    columnas = max(int(celda.get("columnas") or 1), 1)
                except (TypeError, ValueError):
                    columnas = 1
            else:
                texto, imagenes, columnas = ("" if celda is None else str(celda)).replace("\r\n", "\n"), [], 1
            if not imagenes and columnas == 1:
                celdas.append(texto)
                continue
            limpia: dict[str, Any] = {"texto": texto}
            if imagenes:
                limpia["imagenes"] = imagenes
            if columnas > 1:
                limpia["columnas"] = columnas
            celdas.append(limpia)
        limpias.append(celdas)
    return limpias


def _clean_tags(tags: Any) -> list[str]:
    """Etiquetas: lista de textos sin espacios a los lados ni repetidas."""
    if tags is None:
        return []
    if not isinstance(tags, list):
        raise ValueError("'etiquetas' debe ser una lista.")
    cleaned: list[str] = []
    for tag in tags:
        if isinstance(tag, (dict, list)):
            raise ValueError("Cada etiqueta debe ser un texto.")
        text = str(tag).strip()
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned


def clean_test_changes(changes: dict[str, Any]) -> dict[str, Any]:
    """Valida y normaliza los campos de una prueba recibidos de la interfaz."""
    cleaned: dict[str, Any] = {}
    for field, value in changes.items():
        if field == "automatizable":
            valor = esquema.normalizar_automatizable(value)
            if valor is None:
                raise ValueError(f"Automatizable no admite «{value}».")
            cleaned[field] = valor
        elif field in TEXT_FIELDS:
            cleaned[field] = str(value if value is not None else "").strip()
        elif field in esquema.OPCIONES_MULTIPLES:
            opciones = esquema.OPCIONES_MULTIPLES[field]
            valores = [str(v).strip() for v in (value or []) if str(v).strip()] if isinstance(value, list) else None
            if valores is None or any(v not in opciones for v in valores):
                raise ValueError(f"«{esquema.ETIQUETAS[field]}» solo admite: {', '.join(opciones)}.")
            cleaned[field] = [o for o in opciones if o in valores]
        elif field == "requisitos":
            cleaned[field] = esquema.lista_de_textos(value)
        elif field in LIST_FIELDS:
            cleaned[field] = _clean_list(value, field)
        elif field == "campos_adicionales":
            cleaned[field] = _clean_extras(value)
        elif field == "imagenes":
            cleaned[field] = _clean_list(value, field)
            if any(not isinstance(v, str) for v in cleaned[field]):
                raise ValueError("'imagenes' debe ser una lista de rutas.")
        elif field == "adjuntos":
            if value not in (None, "") and not isinstance(value, list):
                raise ValueError("'adjuntos' debe ser una lista.")
            cleaned[field] = adjuntos.lista(value)
        elif field == "etiquetas":
            cleaned[field] = _clean_tags(value)
        elif field == "nivel":
            cleaned[field] = normalize_level(value)
        else:
            raise ValueError(f"Campo desconocido: {field}")
    return cleaned


def clean_requirement_changes(changes: dict[str, Any]) -> dict[str, Any]:
    """Valida y normaliza los campos de un requisito recibidos de la interfaz."""
    cleaned: dict[str, Any] = {}
    for field, value in changes.items():
        if field == "tipo":
            valor = str(value if value is not None else "").strip()
            if valor and valor not in esquema.REQ_TIPOS:
                raise ValueError(f"«Tipo» solo admite: {', '.join(esquema.REQ_TIPOS)}.")
            cleaned[field] = valor
        elif field in esquema.REQ_CAMPOS_TEXTO:
            cleaned[field] = str(value if value is not None else "").strip()
        elif field in esquema.REQ_OPCIONES_MULTIPLES:
            opciones = esquema.REQ_OPCIONES_MULTIPLES[field]
            valores = [str(v).strip() for v in (value or []) if str(v).strip()] if isinstance(value, list) else None
            if valores is None or any(v not in opciones for v in valores):
                raise ValueError(f"«{esquema.REQ_ETIQUETAS[field]}» solo admite: {', '.join(opciones)}.")
            cleaned[field] = [o for o in opciones if o in valores]
        elif field in esquema.REQ_CAMPOS_LISTA:
            cleaned[field] = _clean_list(value, field)
        elif field == "campos_adicionales":
            cleaned[field] = _clean_extras(value)
        elif field == "nivel":
            cleaned[field] = normalize_level(value)
        else:
            raise ValueError(f"Campo desconocido: {field}")
    return cleaned


def apply_changes(target: Any, changes: dict[str, Any]) -> None:
    """Aplica cambios sobre un mapa ruamel tocando solo lo que difiere.

    Un campo ausente cuyo nuevo valor es vacío no se añade, para no ensuciar
    los ficheros con claves vacías.
    """
    for key, value in changes.items():
        if key in target:
            if to_plain(target[key]) != value:
                target[key] = value
        elif value not in EMPTY:
            target[key] = value


# ----------------------------------------------------------------------
# API
# ----------------------------------------------------------------------
class EditorApi:
    def __init__(self, carpeta_inicial: str | Path | None = None) -> None:
        self._lock = threading.RLock()
        self._window: Any = None
        self._yaml_dir: Path | None = None
        self._chapters: list[dict[str, Any]] = []          # siempre las pruebas (también para ejecuciones)
        self._req_chapters: list[dict[str, Any]] = []      # requisitos (subcarpeta requisitos/)
        self._req_error: str | None = None                 # por qué no se pudieron leer los requisitos
        self._coleccion = "pruebas"                        # lo que se edita: "pruebas" o "requisitos"
        self._mtimes: dict[Path, int] = {}
        self._thumbs: dict[tuple[str, int, int, int], dict[str, Any]] = {}
        self._carpeta_inicial = Path(carpeta_inicial) if carpeta_inicial else None
        self._al_cargar: Callable[[Path], None] | None = None   # p. ej. recordar la carpeta
        self._solo_lectura = False     # p. ej., las pruebas congeladas de una ejecución cerrada
        self._formato_nuevo: str | None = None   # los datos son de una versión más nueva del programa
        self._sin_guardar = False      # la interfaz avisa cuando hay cambios pendientes
        self._cierre_aceptado = False
        # Bloqueo de capítulos para que dos personas no editen el mismo (ver bloqueos.py).
        self._bloqueos = bloqueos.Bloqueos(persona=self._persona, ocupado=lambda: self._sin_guardar)
        import atexit
        atexit.register(self._bloqueos.cerrar)

    # --- estado ------------------------------------------------------
    def _requisitos(self) -> bool:
        return self._coleccion == "requisitos"

    def _clave(self) -> str:
        """Clave de los elementos de la colección activa: «prueba» o «requisito»."""
        return "requisito" if self._requisitos() else "prueba"

    def _activos(self) -> list[dict[str, Any]]:
        return self._req_chapters if self._requisitos() else self._chapters

    def _require_chapter(self, capitulo: int) -> dict[str, Any]:
        if not self._activos():
            raise ValueError("No hay ningún capítulo de requisitos." if self._requisitos() else "No hay ninguna carpeta cargada.")
        if not isinstance(capitulo, int) or not 0 <= capitulo < len(self._activos()):
            raise ValueError("El capítulo seleccionado ya no existe.")
        return self._activos()[capitulo]

    def _require_dir(self) -> Path:
        """Carpeta de la colección activa (la de pruebas o su subcarpeta de requisitos)."""
        if self._yaml_dir is None:
            raise ValueError("No hay ninguna carpeta cargada.")
        return self._req_dir() if self._requisitos() else self._yaml_dir

    def _yaml_dir_or_fail(self) -> Path:
        if self._yaml_dir is None:
            raise ValueError("No hay ninguna carpeta cargada.")
        return self._yaml_dir

    def _req_dir(self) -> Path:
        if self._yaml_dir is None:
            raise ValueError("No hay ninguna carpeta cargada.")
        return trazabilidad.carpeta_requisitos(self._yaml_dir)

    def _element(self, capitulo: int, indice: int, tipo: str) -> tuple[dict[str, Any], Any]:
        chapter = self._require_chapter(capitulo)
        contents = chapter["data"]["contenido"]
        if not isinstance(indice, int) or not 0 <= indice < len(contents):
            raise ValueError("La posición seleccionada ya no existe.")
        element = contents[indice]
        if tipo == "prueba" and not (isinstance(element, dict) and isinstance(element.get("prueba"), dict)):
            raise ValueError("La posición seleccionada ya no corresponde a una prueba.")
        if tipo == "requisito" and not (isinstance(element, dict) and isinstance(element.get("requisito"), dict)):
            raise ValueError("La posición seleccionada ya no corresponde a un requisito.")
        if tipo == "seccion" and not (isinstance(element, dict) and isinstance(element.get("seccion"), str)):
            raise ValueError("La posición seleccionada ya no corresponde a una sección.")
        if tipo == "tabla" and not is_table(element):
            raise ValueError("La posición seleccionada ya no corresponde a una tabla.")
        return chapter, element

    def _soltar_de_otras_pruebas(self) -> None:
        """Al abrir otra carpeta de pruebas, deja lo que era de la anterior (ejecución, validación)."""

    def _load(self, yaml_dir: Path) -> None:
        self._bloqueos.soltar_todos()           # los de la carpeta anterior
        yaml_dir = tests_dir(yaml_dir)          # si se abre el proyecto, su carpeta pruebas/
        chapters = read_chapters(yaml_dir)
        if not chapters:
            raise ValueError("No se encontraron capítulos YAML en la carpeta.")
        esquema.configurar(yaml_dir)            # opciones de maniobra y entorno del proyecto
        self._solo_lectura = False
        self._yaml_dir = yaml_dir.resolve()
        self._chapters = chapters
        self._mtimes = {c["path"]: c["path"].stat().st_mtime_ns for c in chapters}
        self._cargar_requisitos()
        # Datos de una versión más nueva del programa: se pueden ver, pero no guardar (ver formato.py).
        self._formato_nuevo = None
        for carpeta, que in ((self._yaml_dir, "Esta carpeta de pruebas"), (self._req_dir(), "La carpeta de requisitos")):
            try:
                formato.comprobar_carpeta(carpeta, que)
            except formato.FormatoNuevo as error:
                self._formato_nuevo = str(error)
                break
        self._thumbs.clear()
        if self._al_cargar is not None:
            try:
                self._al_cargar(self._yaml_dir)
            except Exception:  # noqa: BLE001 - un fallo accesorio no debe impedir abrir la carpeta
                traceback.print_exc()

    def _cargar_requisitos(self) -> None:
        """Lee los requisitos de la subcarpeta; un error se guarda y se enseña al abrirlos."""
        self._req_chapters, self._req_error = [], None
        if self._yaml_dir is None:
            return
        try:
            self._req_chapters = trazabilidad.leer_requisitos(self._yaml_dir)
        except (OSError, ValueError, YAMLError) as error:
            self._req_error = f"No se pueden leer los requisitos: {error}"
        for chapter in self._req_chapters:
            self._mtimes[chapter["path"]] = chapter["path"].stat().st_mtime_ns

    def _reload_chapter(self, chapter: dict[str, Any]) -> None:
        with chapter["path"].open(encoding="utf-8") as source:
            chapter["data"] = roundtrip_yaml().load(source)
        self._mtimes[chapter["path"]] = chapter["path"].stat().st_mtime_ns

    def _exigir_escritura(self) -> None:
        if self._formato_nuevo:
            raise formato.FormatoNuevo(self._formato_nuevo)
        if self._solo_lectura:
            raise ValueError(
                "Esta carpeta es la copia congelada de una ejecución cerrada y no se puede modificar. "
                "Para editar las pruebas, abre su carpeta de pruebas."
            )

    @staticmethod
    def _persona() -> str:
        """Nombre para los bloqueos: el ejecutor que se usa en las ejecuciones o, si no hay, el usuario del sistema."""
        interfaz = ajustes.leer().get("interfaz")
        nombre = str(interfaz.get("ejecutor") or "").strip() if isinstance(interfaz, dict) else ""
        return nombre or bloqueos.persona_del_sistema()

    def _nombre_capitulo(self, chapter: dict[str, Any]) -> str:
        return str(chapter["data"].get("capitulo") or chapter["path"].name)

    def _tomar_bloqueo(self, chapter: dict[str, Any], forzar: bool = False) -> None:
        """Toma el bloqueo del capítulo o explica quién lo tiene (sin cambiar nada)."""
        otro = self._bloqueos.tomar(chapter["path"], forzar)
        if otro:
            raise ValueError(f"{bloqueos.texto(otro, self._nombre_capitulo(chapter))}: no se ha guardado. "
                             "Espera a que lo deje o, si sabes que no lo está usando, fuerza el bloqueo.")

    def _persist(self, chapter: dict[str, Any]) -> None:
        """Guarda el capítulo; si falla, vuelve a leer el disco para no divergir."""
        if self._solo_lectura or self._formato_nuevo:
            self._reload_chapter(chapter)      # deshace lo que se cambió en memoria
            self._exigir_escritura()
        try:
            self._tomar_bloqueo(chapter)
        except ValueError:
            self._reload_chapter(chapter)
            raise
        path: Path = chapter["path"]
        if path.exists() and path.stat().st_mtime_ns != self._mtimes.get(path):
            self._reload_chapter(chapter)
            raise ValueError(
                f"{path.name} ha cambiado en el disco desde que se cargó. "
                "Se ha vuelto a leer; revisa el contenido y repite el cambio."
            )
        try:
            save_chapter(chapter)
        except Exception:
            self._reload_chapter(chapter)
            raise
        self._mtimes[path] = path.stat().st_mtime_ns

    def _summary(self) -> dict[str, Any]:
        clave = self._clave()
        return {
            "carpeta": str(self._yaml_dir) if self._yaml_dir else None,
            "solo_lectura": self._solo_lectura,
            "aviso_formato": self._formato_nuevo,
            "coleccion": self._coleccion,
            "hay_requisitos": bool(self._req_chapters),
            "error_requisitos": self._req_error,
            "esquema": self._esquema(),
            "capitulos": [
                {
                    "indice": i,
                    "nombre": str(c["data"].get("capitulo") or c["path"].name),
                    "archivo": c["path"].name,
                    "pruebas": len(items_in_chapter(c, clave)),
                }
                for i, c in enumerate(self._activos())
            ],
        }

    @respuesta
    def coleccion(self, nombre: str) -> dict[str, Any]:
        """Elige qué se edita: «pruebas» o «requisitos» (el árbol, los capítulos y la validación)."""
        if nombre not in ("pruebas", "requisitos"):
            raise ValueError(f"Colección desconocida: {nombre}")
        self._coleccion = nombre
        return self._summary()

    @respuesta
    def crear_catalogo_requisitos(self) -> dict[str, Any]:
        """Crea la carpeta de requisitos con un primer capítulo vacío."""
        self._exigir_escritura()
        carpeta = self._req_dir()
        if self._req_chapters:
            raise ValueError("Ya hay requisitos en esta carpeta.")
        carpeta.mkdir(parents=True, exist_ok=True)
        indice = carpeta / "indice.yaml"
        if not indice.exists():
            indice.write_text("- capitulo: Requisitos\n  archivo: 01_requisitos.yaml\n", encoding="utf-8")
        primero = carpeta / "01_requisitos.yaml"
        if not primero.exists():
            primero.write_text("capitulo: Requisitos\ncontenido: []\n", encoding="utf-8")
        self._cargar_requisitos()
        if self._req_error:
            raise ValueError(self._req_error)
        self._coleccion = "requisitos"
        return self._summary()

    @respuesta
    def crear_capitulo(self, nombre: str) -> dict[str, Any]:
        """Añade un capítulo vacío al final de la colección activa (pruebas o requisitos)."""
        self._exigir_escritura()
        if self._requisitos():
            if self._req_error:
                raise ValueError(self._req_error)
            create_chapter(self._req_dir(), nombre)
            self._cargar_requisitos()
        else:
            create_chapter(self._require_dir(), nombre)
            self._chapters = read_chapters(self._require_dir())
            self._mtimes.update({c["path"]: c["path"].stat().st_mtime_ns for c in self._chapters})
        return {**self._summary(), "capitulo": len(self._activos()) - 1}

    # --- acerca de -------------------------------------------------------------
    @respuesta
    def acerca_de(self) -> dict[str, Any]:
        """Nombre y versión de la herramienta y dónde guarda sus ajustes este PC."""
        import platform

        from app import NOMBRE, __version__

        return {"nombre": NOMBRE, "version": __version__, "ajustes": str(ajustes.archivo()),
                "python": platform.python_version(), "sistema": f"{platform.system()} {platform.release()}"}

    @respuesta
    def abrir_manual(self, ancla: str = "") -> dict[str, Any]:
        """Abre el manual de usuario (MANUAL.md convertido a HTML) en una ventana aparte, en el apartado `ancla` si se indica."""
        from urllib.parse import quote

        from app import firma, manual

        ruta = manual.generar()
        if self._window is None:          # sin interfaz (pruebas): solo se genera
            return {"archivo": str(ruta)}
        import webview

        url = ruta.as_uri() + (f"#{quote(str(ancla))}" if ancla else "")
        webview.create_window(f"Manual · {firma()}", url=url, width=1040, height=820, text_select=True)
        return {"archivo": str(ruta)}

    def zoom(self, nivel: float = 1.0) -> dict[str, Any]:
        """Zoom de la ventana (1 = normal). `aplicado` es False (con el `motivo`) si no se ha podido.

        Sin el cerrojo de la API (no lleva @respuesta): no toca datos y no debe esperar a nada.
        """
        from app import zoom

        try:
            nivel = zoom.limitar(nivel)
            hecho, motivo = zoom.aplicar(self._window, nivel)
        except Exception as error:  # noqa: BLE001 - el zoom es accesorio
            return {"ok": True, "datos": {"nivel": 1.0, "aplicado": False, "motivo": str(error)}}
        return {"ok": True, "datos": {"nivel": nivel, "aplicado": hecho, "motivo": motivo}}

    @respuesta
    def abrir_enlace(self, url: str) -> dict[str, Any]:
        """Abre una dirección web en el navegador del sistema."""
        import webbrowser

        if not str(url).startswith(("https://", "http://")):
            raise ValueError("Solo se abren direcciones web.")
        webbrowser.open(str(url))
        return {}

    # --- ajustes de este PC (⋯ → Ajustes…) ----------------------------------------
    AJUSTES_GENERALES = ("carpeta_versiones", "url_incidencias")

    @respuesta
    def ajustes_generales(self) -> dict[str, Any]:
        """Tu nombre (el ejecutor), la carpeta donde se publica el programa y la dirección de las incidencias."""
        datos = ajustes.leer()
        interfaz = datos.get("interfaz") if isinstance(datos.get("interfaz"), dict) else {}
        return {"persona": str(interfaz.get("ejecutor") or ""), "persona_sistema": bloqueos.persona_del_sistema(),
                **{k: str(datos.get(k) or "") for k in self.AJUSTES_GENERALES}}

    @respuesta
    def guardar_ajustes_generales(self, cambios: dict[str, Any]) -> dict[str, Any]:
        url = str((cambios or {}).get("url_incidencias") or "").strip()
        if url and (not url.startswith(("https://", "http://")) or "{id}" not in url):
            raise ValueError("La dirección de las incidencias tiene que empezar por https:// (o http://) y llevar {id} "
                             "donde va el número, por ejemplo https://jira.empresa.com/browse/{id}.")
        guardar = {k: str(cambios[k] or "").strip() for k in self.AJUSTES_GENERALES if k in (cambios or {})}
        ajustes.guardar(guardar)
        if "persona" in (cambios or {}):
            interfaz = ajustes.leer().get("interfaz")
            interfaz = dict(interfaz) if isinstance(interfaz, dict) else {}
            persona = str(cambios["persona"] or "").strip()
            if persona:
                interfaz["ejecutor"] = persona
            else:
                interfaz.pop("ejecutor", None)
            ajustes.guardar({"interfaz": interfaz})
        return self.ajustes_generales()["datos"]

    @respuesta
    def elegir_carpeta_versiones(self) -> dict[str, Any]:
        import webview

        if self._window is None:
            raise ValueError("El selector de carpetas solo está disponible en la aplicación.")
        kind = getattr(getattr(webview, "FileDialog", None), "FOLDER", None) or webview.FOLDER_DIALOG
        elegida = self._window.create_file_dialog(kind)
        return {"carpeta": str(elegida[0])} if elegida else {"cancelado": True}

    def comprobar_version(self) -> dict[str, Any]:
        """Si en la carpeta donde se publica el programa hay una versión más nueva que esta.

        Sin el cerrojo de la API (no lleva @respuesta): leer una unidad de red lenta no debe parar el editor.
        """
        from app import __version__, actualizaciones
        try:
            datos = actualizaciones.comprobar(ajustes.leer().get("carpeta_versiones"), __version__)
        except Exception as error:  # noqa: BLE001 - un aviso accesorio no debe dar errores
            return {"ok": False, "error": str(error)}
        return {"ok": True, "datos": {**datos, "actual": __version__}}

    # --- preferencias de la interfaz ------------------------------------------
    @respuesta
    def preferencias(self) -> dict[str, str]:
        """Preferencias de la interfaz guardadas en este PC (recientes, modo, ejecutor…).

        Van en los ajustes del PC y no en el almacenamiento del navegador, que
        pywebview borra al cerrar la ventana.
        """
        valor = ajustes.leer().get("interfaz")
        return {str(k): str(v) for k, v in valor.items()} if isinstance(valor, dict) else {}

    @respuesta
    def guardar_preferencias(self, cambios: dict[str, Any]) -> dict[str, Any]:
        """Fusiona `cambios` con las preferencias; un valor None borra la clave."""
        actuales = ajustes.leer().get("interfaz")
        actuales = dict(actuales) if isinstance(actuales, dict) else {}
        for clave, valor in (cambios or {}).items():
            if valor is None:
                actuales.pop(str(clave), None)
            else:
                actuales[str(clave)] = str(valor)
        ajustes.guardar({"interfaz": actuales})
        return {}

    @respuesta
    def iniciar(self) -> dict[str, Any]:
        """Estado al arrancar; intenta cargar la carpeta inicial si existe."""
        if self._yaml_dir is None and self._carpeta_inicial and self._carpeta_inicial.is_dir():
            try:
                self._load(self._carpeta_inicial)
            except (OSError, ValueError, YAMLError) as error:
                return {**self._summary(), "aviso": str(error)}
        return self._summary()

    @respuesta
    def abrir_carpeta(self, ruta: str) -> dict[str, Any]:
        folder = Path(str(ruta)).expanduser()
        if not folder.is_dir():
            raise ValueError("Selecciona una carpeta existente con los capítulos YAML.")
        self._load(folder)
        self._soltar_de_otras_pruebas()
        return self._summary()

    @respuesta
    def elegir_carpeta(self) -> dict[str, Any]:
        """Abre el selector de carpetas del sistema y carga la elegida."""
        import webview

        if self._window is None:
            raise ValueError("El selector de carpetas solo está disponible en la aplicación.")
        kind = getattr(getattr(webview, "FileDialog", None), "FOLDER", None) or webview.FOLDER_DIALOG
        chosen = self._window.create_file_dialog(
            kind, directory=str(self._yaml_dir or Path.cwd())
        )
        if not chosen:
            return {"cancelado": True}
        folder = Path(chosen[0])
        if not read_chapters(tests_dir(folder)):
            # Carpeta sin capítulos (vacía, o con otras cosas): la interfaz ofrece crear ahí un proyecto.
            return {"sin_proyecto": True, "carpeta_elegida": str(folder.resolve())}
        self._load(folder)
        self._soltar_de_otras_pruebas()
        return self._summary()

    @respuesta
    def recargar(self) -> dict[str, Any]:
        self._load(self._require_dir())
        return self._summary()

    # --- navegación ----------------------------------------------------
    @respuesta
    def navegacion(self, capitulo: int, consulta: str = "") -> list[dict[str, Any]]:
        chapter = self._require_chapter(capitulo)
        contents = chapter["data"]["contenido"]
        traza = self._traza_por_id() if self._requisitos() else {}
        nodes = []
        for kind, index, label, parent, level in navigation_entries(chapter, str(consulta or "")):
            element = contents[index]
            if kind == "section":
                nodes.append({
                    "tipo": "seccion", "indice": index, "padre": parent,
                    "nivel": level, "titulo": element["seccion"],
                })
            elif kind == "table":
                filas = table_rows(element["tabla"])
                nodes.append({
                    "tipo": "tabla", "indice": index, "padre": parent, "nivel": level,
                    "titulo": table_title(element["tabla"]), "filas": len(filas),
                    "columnas": max((len(f) for f in filas), default=0),
                })
            elif kind == "requirement":
                req = element["requisito"]
                rid = str(req.get("id") or "").strip()
                info = traza.get(rid)
                nodes.append({
                    "tipo": "requisito", "indice": index, "padre": parent,
                    "nivel": level, "id": rid,
                    "titulo": str(req.get("titulo") or req.get("nombre") or ""),
                    # Un requisito con el ID repetido no cuenta (lo avisa la validación).
                    "cobertura": {"estado": info["estado"], "pruebas": len(info["pruebas"]), "modificado": info["modificado"]}
                    if info and info["capitulo"] == capitulo and info["indice"] == index else None,
                })
            else:
                test = element["prueba"]
                nodes.append({
                    "tipo": "prueba", "indice": index, "padre": parent,
                    "nivel": level, "id": str(test.get("id") or ""),
                    "titulo": str(test.get("titulo") or test.get("nombre") or ""),
                })
        return nodes

    # --- trazabilidad ----------------------------------------------------
    def _revisiones(self) -> dict[str, Any]:
        return trazabilidad.leer_revisiones(self._req_dir()) if self._req_chapters else {}

    def _traza(self) -> dict[str, Any]:
        return trazabilidad.calcular(self._chapters, self._req_chapters, self._revisiones())

    def _traza_por_id(self) -> dict[str, dict[str, Any]]:
        return {r["id"]: r for r in self._traza()["requisitos"]}

    @respuesta
    def trazabilidad(self) -> dict[str, Any]:
        """Cobertura de todos los requisitos, referencias huérfanas y resúmenes (ver trazabilidad.py)."""
        self._require_dir()
        datos = self._traza()
        for bloque in (datos["total"], *datos["capitulos"]):
            bloque["porcentaje"] = trazabilidad.porcentaje(bloque)
        return datos

    @respuesta
    def requisitos_lista(self) -> list[dict[str, Any]]:
        """Requisitos del catálogo (ID, título, estado), para proponerlos en las pruebas."""
        if not self._req_chapters:
            return []
        return [{"id": r["id"], "titulo": r["titulo"], "estado": r["estado"], "modificado": r["modificado"],
                 "pruebas": len(r["pruebas"])} for r in self._traza()["requisitos"]]

    @respuesta
    def ir_a_requisito(self, requisito_id: str) -> dict[str, Any]:
        """Capítulo e índice de un requisito por su ID."""
        for ci, chapter in enumerate(self._req_chapters):
            for index, req in items_in_chapter(chapter, "requisito"):
                if str(req.get("id") or "").strip() == str(requisito_id).strip():
                    return {"capitulo": ci, "indice": index}
        raise ValueError(f"No existe el requisito «{requisito_id}».")

    @respuesta
    def ir_a_prueba(self, prueba_id: str) -> dict[str, Any]:
        """Capítulo e índice de una prueba por su ID."""
        for ci, chapter in enumerate(self._chapters):
            for index, test in tests_in_chapter(chapter):
                if str(test.get("id") or "").strip() == str(prueba_id).strip():
                    return {"capitulo": ci, "indice": index}
        raise ValueError(f"No existe la prueba «{prueba_id}».")

    @respuesta
    def requisito_usos(self, requisito_id: str) -> dict[str, Any]:
        """Cuántas pruebas citan un ID de requisito (para ofrecer cambiarlo también en ellas)."""
        rid = str(requisito_id).strip()
        ids = [str(test.get("id") or "") for chapter in self._chapters for _i, test in tests_in_chapter(chapter)
               if rid in trazabilidad.lista(test.get("requisitos"))]
        return {"pruebas": ids}

    @respuesta
    def revisar_requisito(self, requisito_id: str) -> dict[str, Any]:
        """Marca como revisadas las pruebas de un requisito cambiado (quita su entrada de revisiones.yaml)."""
        self._exigir_escritura()
        revisiones = self._revisiones()
        if revisiones.pop(str(requisito_id).strip(), None) is not None:
            trazabilidad.guardar_revisiones(self._req_dir(), revisiones)
        return {}

    def _renombrar_en_pruebas(self, anterior: str, nuevo: str) -> int:
        """Cambia un ID de requisito en el campo «requisitos» de todas las pruebas que lo citan."""
        # Antes de tocar nada, los capítulos afectados tienen que estar libres.
        for chapter in self._chapters:
            if any(anterior in [str(r).strip() for r in test.get("requisitos") or [] if isinstance(test.get("requisitos"), list)]
                   for _i, test in tests_in_chapter(chapter)):
                self._tomar_bloqueo(chapter)
        cambiadas = 0
        for chapter in self._chapters:
            tocado = False
            for _index, test in tests_in_chapter(chapter):
                refs = test.get("requisitos")
                if isinstance(refs, list) and anterior in [str(r).strip() for r in refs]:
                    nuevos: list[str] = []
                    for r in refs:
                        valor = nuevo if str(r).strip() == anterior else str(r).strip()
                        if valor not in nuevos:
                            nuevos.append(valor)
                    test["requisitos"] = nuevos
                    tocado = True
                    cambiadas += 1
            if tocado:
                self._persist(chapter)
        return cambiadas

    def _anotar_cambio(self, anterior: dict[str, Any], actual: Any) -> None:
        """Apunta el requisito como cambiado si tiene pruebas (ver trazabilidad.anotar_cambio)."""
        revisiones = self._revisiones()
        rid = str(anterior.get("id") or "").strip()
        tiene_pruebas = any(rid in trazabilidad.lista(test.get("requisitos"))
                            for chapter in self._chapters for _i, test in tests_in_chapter(chapter))
        if (tiene_pruebas or rid in revisiones) and trazabilidad.anotar_cambio(revisiones, anterior, actual):
            trazabilidad.guardar_revisiones(self._req_dir(), revisiones)

    @respuesta
    def ubicaciones(self, capitulo: int) -> list[dict[str, Any]]:
        """Secciones disponibles como destino al crear pruebas o secciones."""
        chapter = self._require_chapter(capitulo)
        return [
            {"indice": index, "titulo": title, "nivel": level}
            for index, title, level in headings_in_chapter(chapter)
        ]

    @respuesta
    def esquema(self) -> dict[str, Any]:
        """Campos de las pruebas y sus opciones, para el formulario (ver esquema.py)."""
        return self._esquema()

    @staticmethod
    def _esquema() -> dict[str, Any]:
        return {
            "etiquetas": esquema.ETIQUETAS,
            "opciones": {k: list(v) for k, v in esquema.OPCIONES_MULTIPLES.items()},
            "automatizable": [{"valor": v, "texto": esquema.AUTOMATIZABLE_VISIBLE[v]} for v in esquema.AUTOMATIZABLE],
            "obligatorios": list(esquema.OBLIGATORIOS),
            "requisito": {
                "etiquetas": esquema.REQ_ETIQUETAS,
                "opciones": {k: list(v) for k, v in esquema.REQ_OPCIONES_MULTIPLES.items()},
                "tipos": list(esquema.REQ_TIPOS),
            },
            "configuracion": str(esquema.CONFIGURACION) if esquema.CONFIGURACION else None,
        }

    @respuesta
    def etiquetas_uso(self) -> list[dict[str, Any]]:
        """Etiquetas usadas y en cuántas pruebas, las más usadas primero (para proponerlas)."""
        usos: dict[str, int] = {}
        for chapter in self._chapters:
            for _index, test in tests_in_chapter(chapter):
                valor = test.get("etiquetas") or []
                for tag in {str(t).strip() for t in (valor if isinstance(valor, list) else [valor])} - {""}:
                    usos[tag] = usos.get(tag, 0) + 1
        return [{"etiqueta": t, "usos": n} for t, n in sorted(usos.items(), key=lambda x: (-x[1], x[0].lower()))]

    @respuesta
    def etiquetas(self) -> list[str]:
        """Etiquetas usadas en todas las pruebas, para proponerlas al escribir."""
        usadas: set[str] = set()
        for chapter in self._chapters:
            for _index, test in tests_in_chapter(chapter):
                valor = test.get("etiquetas") or []
                for tag in valor if isinstance(valor, list) else [valor]:
                    if str(tag).strip():
                        usadas.add(str(tag).strip())
        return sorted(usadas, key=str.lower)

    # --- lectura -------------------------------------------------------
    @respuesta
    def obtener(self, capitulo: int, indice: int) -> dict[str, Any]:
        chapter, element = self._element(capitulo, indice, "cualquiera")
        if isinstance(element.get("requisito"), dict):
            req = to_plain(element["requisito"])
            req["nivel"] = normalize_level(req.get("nivel"), 3)
            rid = str(req.get("id") or "").strip()
            info = self._traza_por_id().get(rid)
            if info and (info["capitulo"], info["indice"]) != (capitulo, indice):
                info = None                               # ID repetido: la traza es del otro
            anterior = self._revisiones().get(rid) if info and info["modificado"] else None
            return {"tipo": "requisito", "indice": indice, "elemento": req,
                    "traza": {"estado": info["estado"], "necesita": info["necesita"], "pruebas": info["pruebas"],
                              "modificado": info["modificado"], "anterior": anterior} if info else None}
        if isinstance(element.get("prueba"), dict):
            test = to_plain(element["prueba"])
            test["nivel"] = normalize_level(test.get("nivel"), 3)
            return {"tipo": "prueba", "indice": indice, "elemento": test}
        if isinstance(element.get("seccion"), str):
            section = to_plain(element)
            section["nivel"] = normalize_level(section.get("nivel"), 2)
            return {"tipo": "seccion", "indice": indice, "elemento": section}
        if is_table(element):
            return {"tipo": "tabla", "indice": indice, "elemento": to_plain(element["tabla"])}
        raise ValueError("La posición seleccionada no es una sección, una prueba ni una tabla.")

    @respuesta
    def obtener_yaml(self, capitulo: int, indice: int) -> dict[str, Any]:
        _chapter, element = self._element(capitulo, indice, "cualquiera")
        if item_key(element):
            target = element[item_key(element)]
        elif is_table(element):
            target = element["tabla"]
        else:
            target = element
        return {"texto": yaml_to_string(target)}

    @respuesta
    def validar_yaml(self, texto: str) -> dict[str, Any]:
        try:
            parsed = roundtrip_yaml().load(texto)
        except YAMLError as error:
            mark = getattr(error, "problem_mark", None)
            return {
                "valido": False,
                "linea": (mark.line + 1) if mark else 1,
                "columna": (mark.column + 1) if mark else 1,
                "mensaje": mensaje_yaml(error),
            }
        if not isinstance(parsed, dict):
            return {"valido": False, "linea": 1, "columna": 1,
                    "mensaje": "El YAML debe ser un mapa (clave: valor)."}
        return {"valido": True}

    # --- escritura de pruebas ---------------------------------------------
    def _check_id(self, test_id: str, excluded: tuple[Path, int] | None) -> None:
        problem = find_duplicate_id(self._chapters, test_id, excluded)
        if problem:
            raise ValueError(problem)

    @respuesta
    def guardar_prueba(self, capitulo: int, indice: int, cambios: dict[str, Any]) -> dict[str, Any]:
        chapter, element = self._element(capitulo, indice, "prueba")
        changes = clean_test_changes(cambios)
        changes.pop("nivel", None)
        if "id" in changes:
            self._check_id(changes["id"], (chapter["path"], indice))
        apply_changes(element["prueba"], changes)
        self._persist(chapter)
        return {"indice": indice}

    @staticmethod
    def _level_for(contents: list[Any], ubicacion: dict[str, Any], default: int) -> int:
        kind = ubicacion.get("tipo")
        if kind in ("seccion", "despues"):
            index = ubicacion.get("indice")
            if not isinstance(index, int) or not 0 <= index < len(contents):
                raise ValueError("La ubicación elegida ya no existe.")
            element = contents[index]
            if kind == "seccion":
                if not (isinstance(element, dict) and isinstance(element.get("seccion"), str)):
                    raise ValueError("La ubicación elegida ya no es una sección.")
                return min(normalize_level(element.get("nivel"), 2) + 1, 6)
            if item_key(element) is None:
                raise ValueError("La ubicación elegida ya no es una prueba ni un requisito.")
            return normalize_level(element[item_key(element)].get("nivel"), 3)
        if kind == "final":
            return default
        raise ValueError("Ubicación no válida.")

    @respuesta
    def crear_prueba(self, capitulo: int, ubicacion: dict[str, Any], datos: dict[str, Any]) -> dict[str, Any]:
        chapter = self._require_chapter(capitulo)
        contents = chapter["data"]["contenido"]
        data = clean_test_changes({k: v for k, v in datos.items() if k != "nivel"})
        self._check_id(data.get("id", ""), None)
        test = {**esquema.prueba_vacia(), **data, "nivel": self._level_for(contents, ubicacion, 3)}
        kind = ubicacion.get("tipo")
        insert_test(
            chapter,
            test,
            ubicacion["indice"] if kind == "seccion" else None,
            after_test_index=ubicacion["indice"] if kind == "despues" else None,
        )
        self._persist(chapter)
        new_index = next(i for i, e in enumerate(chapter["data"]["contenido"])
                         if isinstance(e, dict) and e.get("prueba") is test)
        return {"indice": new_index}

    @respuesta
    def borrar_prueba(self, capitulo: int, indice: int) -> dict[str, Any]:
        chapter, _element = self._element(capitulo, indice, "prueba")
        delete_test(chapter, indice)
        self._persist(chapter)
        return {}

    # --- escritura de requisitos ---------------------------------------------
    def _check_req_id(self, req_id: str, excluded: tuple[Path, int] | None) -> None:
        problem = find_duplicate_id(self._req_chapters, req_id, excluded, key="requisito")
        if problem:
            raise ValueError(problem)

    @respuesta
    def guardar_requisito(self, capitulo: int, indice: int, cambios: dict[str, Any],
                          renombrar_en_pruebas: bool = False) -> dict[str, Any]:
        """Guarda un requisito. Si cambia su texto y tiene pruebas, quedan por revisar.

        Con `renombrar_en_pruebas`, un cambio de ID se aplica también en las pruebas que lo citan.
        """
        self._exigir_escritura()
        chapter, element = self._element(capitulo, indice, "requisito")
        changes = clean_requirement_changes(cambios)
        changes.pop("nivel", None)
        if "id" in changes:
            self._check_req_id(changes["id"], (chapter["path"], indice))
        anterior = to_plain(element["requisito"])
        apply_changes(element["requisito"], changes)
        self._persist(chapter)
        self._anotar_cambio(anterior, element["requisito"])
        id_anterior, id_nuevo = str(anterior.get("id") or "").strip(), str(element["requisito"].get("id") or "").strip()
        cambiadas = self._renombrar_en_pruebas(id_anterior, id_nuevo) if renombrar_en_pruebas and id_anterior and id_anterior != id_nuevo else 0
        return {"indice": indice, "pruebas_actualizadas": cambiadas}

    @respuesta
    def crear_requisito(self, capitulo: int, ubicacion: dict[str, Any], datos: dict[str, Any]) -> dict[str, Any]:
        chapter = self._require_chapter(capitulo)
        if not self._requisitos():
            raise ValueError("Abre los requisitos para crear uno.")
        contents = chapter["data"]["contenido"]
        data = clean_requirement_changes({k: v for k, v in datos.items() if k != "nivel"})
        self._check_req_id(data.get("id", ""), None)
        req = {**esquema.requisito_vacio(), **data, "nivel": self._level_for(contents, ubicacion, 3)}
        kind = ubicacion.get("tipo")
        insert_test(chapter, req, ubicacion["indice"] if kind == "seccion" else None,
                    after_test_index=ubicacion["indice"] if kind == "despues" else None, key="requisito")
        self._persist(chapter)
        new_index = next(i for i, e in enumerate(chapter["data"]["contenido"])
                         if isinstance(e, dict) and e.get("requisito") is req)
        return {"indice": new_index}

    @respuesta
    def borrar_requisito(self, capitulo: int, indice: int) -> dict[str, Any]:
        chapter, element = self._element(capitulo, indice, "requisito")
        rid = str(element["requisito"].get("id") or "").strip()
        delete_test(chapter, indice, key="requisito")
        self._persist(chapter)
        revisiones = self._revisiones()
        if rid and not any(str(r.get("id") or "").strip() == rid for c in self._req_chapters
                           for _i, r in items_in_chapter(c, "requisito")) and revisiones.pop(rid, None) is not None:
            trazabilidad.guardar_revisiones(self._req_dir(), revisiones)
        return {}

    # --- secciones ------------------------------------------------------
    @respuesta
    def crear_seccion(self, capitulo: int, ubicacion: dict[str, Any], nombre: str) -> dict[str, Any]:
        chapter = self._require_chapter(capitulo)
        contents = chapter["data"]["contenido"]
        name = str(nombre or "").strip()
        if not name:
            raise ValueError("El nombre de la sección es obligatorio.")
        kind = ubicacion.get("tipo")
        if kind == "despues":
            insert_section_after_test(chapter, name, ubicacion["indice"])
            new_index = ubicacion["indice"] + 1
        else:
            level = self._level_for(contents, ubicacion, 2)
            section = {"seccion": name, "nivel": level}
            if kind == "seccion":
                parent = contents[ubicacion["indice"]]
                if normalize_level(parent.get("nivel"), 2) >= 6:
                    raise ValueError("No se puede crear una subsección bajo una sección de nivel 6.")
                new_index = section_end_index(contents, ubicacion["indice"])
                contents.insert(new_index, section)
            else:
                contents.append(section)
                new_index = len(contents) - 1
        self._persist(chapter)
        return {"indice": new_index}

    @respuesta
    def guardar_seccion(self, capitulo: int, indice: int, cambios: dict[str, Any]) -> dict[str, Any]:
        chapter, element = self._element(capitulo, indice, "seccion")
        changes: dict[str, Any] = {}
        if "nombre" in cambios:
            name = str(cambios["nombre"] or "").strip()
            if not name:
                raise ValueError("El nombre de la sección es obligatorio.")
            changes["seccion"] = name
        if "contexto" in cambios:
            changes["contexto"] = _clean_list(cambios["contexto"], "contexto")
        if "adjuntos" in cambios:
            changes["adjuntos"] = clean_test_changes({"adjuntos": cambios["adjuntos"]})["adjuntos"]
        apply_changes(element, changes)
        self._persist(chapter)
        return {"indice": indice}

    @respuesta
    def borrar_seccion(self, capitulo: int, indice: int) -> dict[str, Any]:
        chapter, _element = self._element(capitulo, indice, "seccion")
        delete_section(chapter, indice)
        self._persist(chapter)
        return {}

    # --- tablas que no son pruebas -----------------------------------------
    @respuesta
    def guardar_tabla(self, capitulo: int, indice: int, cambios: dict[str, Any]) -> dict[str, Any]:
        chapter, element = self._element(capitulo, indice, "tabla")
        if "filas" in cambios:
            element["tabla"]["filas"] = _clean_table(cambios["filas"])
        self._persist(chapter)
        return {"indice": indice}

    @respuesta
    def crear_tabla(self, capitulo: int, ubicacion: dict[str, Any], datos: dict[str, Any] | None = None) -> dict[str, Any]:
        chapter = self._require_chapter(capitulo)
        contents = chapter["data"]["contenido"]
        filas = (datos or {}).get("filas") or [["", ""], ["", ""]]
        tabla = {"filas": _clean_table(filas)}
        kind = ubicacion.get("tipo")
        index = ubicacion.get("indice")
        if kind in ("seccion", "despues") and not (isinstance(index, int) and 0 <= index < len(contents)):
            raise ValueError("La ubicación elegida ya no existe.")
        if kind == "seccion" and not isinstance(contents[index].get("seccion"), str):
            raise ValueError("La ubicación elegida ya no es una sección.")
        if kind not in ("seccion", "despues", "final"):
            raise ValueError("Ubicación no válida.")
        new_index = insert_table(chapter, tabla, index if kind == "seccion" else None,
                                 after_index=index if kind == "despues" else None)
        self._persist(chapter)
        return {"indice": new_index}

    @respuesta
    def borrar_tabla(self, capitulo: int, indice: int) -> dict[str, Any]:
        chapter, _element = self._element(capitulo, indice, "tabla")
        del chapter["data"]["contenido"][indice]
        self._persist(chapter)
        return {}

    # --- mover ------------------------------------------------------------
    @respuesta
    def mover(self, capitulo: int, indice: int, destino: int, posicion: str) -> dict[str, Any]:
        chapter = self._require_chapter(capitulo)
        try:
            new_index = move_block(chapter, indice, destino, posicion)
        except ValueError:
            self._reload_chapter(chapter)
            raise
        self._persist(chapter)
        return {"indice": new_index}

    @respuesta
    def cambiar_niveles(self, capitulo: int, indices: list[int], delta: int) -> dict[str, Any]:
        """Sube o baja un nivel varias secciones, pruebas o requisitos del capítulo (las secciones, con su contenido)."""
        self._exigir_escritura()
        chapter = self._require_chapter(capitulo)
        cambiados = change_levels(chapter, [int(i) for i in indices or []], int(delta))
        self._persist(chapter)
        return {"cambiados": cambiados}

    # --- buscar y reemplazar en todo el proyecto --------------------------------------
    @staticmethod
    def _textos(valor: Any, campo: str = "") -> list[tuple[str, str]]:
        """(campo, texto) de todos los textos de un elemento, sin rutas de imágenes ni niveles."""
        if isinstance(valor, dict):
            fuera = ("nivel", "imagenes", "imagen", "columnas")
            return [x for k, v in valor.items() if k not in fuera for x in EditorApi._textos(v, campo or str(k))]
        if isinstance(valor, list):
            return [x for v in valor for x in EditorApi._textos(v, campo)]
        return [(campo, str(valor))] if isinstance(valor, str) and valor.strip() else []

    @respuesta
    def buscar_global(self, consulta: str, limite: int = 500) -> dict[str, Any]:
        """Pruebas (o requisitos), secciones y tablas de todos los capítulos que contienen el texto (sin mayúsculas).

        `resultados` trae el detalle de los `limite` primeros (para mostrarlos); `elementos`, todos los que
        coinciden ({capitulo, indice}), para poder reemplazar en todos aunque no se muestren."""
        consulta = str(consulta or "").strip()
        if len(consulta) < 2:
            return {"resultados": [], "total": 0}
        patron = re.compile(re.escape(consulta), re.IGNORECASE)
        clave = self._clave()
        nombres = {**(esquema.REQ_ETIQUETAS if clave == "requisito" else esquema.ETIQUETAS), "seccion": "Sección", "tabla": "Tabla",
                   "contexto": "Contexto"}
        resultados: list[dict[str, Any]] = []
        elementos: list[dict[str, int]] = []
        total = 0
        for ci, chapter in enumerate(self._activos()):
            for index, element in enumerate(chapter["data"]["contenido"]):
                if not isinstance(element, dict):
                    continue
                if item_key(element) == clave:
                    item, tipo = element[clave], clave
                    ident, titulo = str(item.get("id") or ""), str(item.get("titulo") or "")
                elif isinstance(element.get("seccion"), str):
                    item, tipo, ident, titulo = element, "seccion", "", element["seccion"]
                elif "tabla" in element:
                    item, tipo, ident, titulo = element, "tabla", "", table_title(element["tabla"])
                else:
                    continue
                coincidencias = [(c, x) for c, x in self._textos(item) if patron.search(x)]
                if not coincidencias:
                    continue
                total += 1
                elementos.append({"capitulo": ci, "indice": index})
                if len(resultados) < limite:
                    campo, texto = coincidencias[0]
                    m = patron.search(texto)
                    inicio = max(m.start() - 40, 0)
                    resultados.append({
                        "capitulo": ci, "nombre_capitulo": self._nombre_capitulo(chapter), "indice": index, "tipo": tipo,
                        "id": ident, "titulo": titulo, "campo": nombres.get(campo, campo),
                        "antes": ("…" if inicio else "") + texto[inicio:m.start()], "coincide": texto[m.start():m.end()],
                        "despues": texto[m.end():m.end() + 60] + ("…" if m.end() + 60 < len(texto) else ""),
                        "veces": sum(len(patron.findall(x)) for _c, x in coincidencias),
                    })
        return {"resultados": resultados, "total": total, "elementos": elementos}

    @respuesta
    def reemplazar_global(self, buscar: str, reemplazo: str, elementos: list[dict[str, int]]) -> dict[str, Any]:
        """Cambia el texto en los elementos indicados ({capitulo, indice}); no toca los ID.

        Un capítulo que edita otra persona se salta (y se dice cuál). Un requisito con pruebas
        cuyo texto cambia queda con sus pruebas por revisar, como al editarlo a mano.
        """
        self._exigir_escritura()
        buscar = str(buscar or "")
        if len(buscar.strip()) < 2:
            raise ValueError("Escribe al menos dos caracteres para buscar.")
        patron = re.compile(re.escape(buscar), re.IGNORECASE)
        clave = self._clave()

        def cambiar(valor: Any, campo: str = "") -> tuple[Any, int]:
            if isinstance(valor, dict):
                total = 0
                for k in list(valor.keys()):
                    if k in ("id", "nivel", "imagenes", "imagen", "columnas"):
                        continue
                    nuevo, n = cambiar(valor[k], k)
                    if n:
                        valor[k] = nuevo
                        total += n
                return valor, total
            if isinstance(valor, list):
                total = 0
                for i, v in enumerate(valor):
                    nuevo, n = cambiar(v, campo)
                    if n:
                        valor[i] = nuevo
                        total += n
                return valor, total
            if isinstance(valor, str):
                return patron.subn(lambda _m: str(reemplazo), valor)
            return valor, 0

        por_capitulo: dict[int, list[int]] = {}
        for e in elementos or []:
            por_capitulo.setdefault(int(e["capitulo"]), []).append(int(e["indice"]))
        cambiados, veces, saltados = 0, 0, []
        for ci, indices in por_capitulo.items():
            chapter = self._require_chapter(ci)
            otro = self._bloqueos.de_otro(chapter["path"])
            if otro:
                saltados.append(bloqueos.texto(otro, self._nombre_capitulo(chapter)))
                continue
            anteriores = []
            antes = cambiados
            contents = chapter["data"]["contenido"]
            for index in sorted(set(indices)):
                if not 0 <= index < len(contents) or not isinstance(contents[index], dict):
                    continue
                element = contents[index]
                objetivo = element[clave] if item_key(element) == clave else element
                anterior = to_plain(objetivo) if item_key(element) == "requisito" else None
                _nuevo, n = cambiar(objetivo)
                if n:
                    cambiados += 1
                    veces += n
                    if anterior is not None:
                        anteriores.append((anterior, objetivo))
            if cambiados == antes:
                continue
            self._persist(chapter)
            for anterior, actual in anteriores:
                self._anotar_cambio(anterior, actual)
        return {"cambiados": cambiados, "veces": veces, "saltados": saltados}

    # --- cambiar campos de varios a la vez ------------------------------------------
    # Campo -> clase: «lista» (se añade, se quita o se pone), «opcion» (se pone una) o «texto» (se pone).
    CAMPOS_VARIOS = {
        "prueba": {"etiquetas": "lista", "requisitos": "lista", "entorno": "lista", "maniobra": "lista",
                   "automatizable": "opcion", "fecha": "texto", "version": "texto"},
        "requisito": {"criterio_validacion": "lista", "tipo": "opcion", "fuente": "texto", "fase": "texto",
                      "fecha": "texto", "version": "texto"},
    }

    @respuesta
    def editar_varios(self, capitulo: int, indices: list[int], campo: str, modo: str, valor: Any) -> dict[str, Any]:
        """Cambia un campo en varias pruebas (o requisitos) del capítulo; una sección elegida cuenta con todo lo suyo.

        `modo`: «anadir» o «quitar» (en las listas: tags, requisitos, entorno, maniobra, criterio) o «poner».
        """
        self._exigir_escritura()
        chapter = self._require_chapter(capitulo)
        clave = self._clave()
        clase = self.CAMPOS_VARIOS[clave].get(campo)
        if clase is None:
            raise ValueError(f"No se puede cambiar «{campo}» en varios a la vez.")
        if modo not in ("anadir", "quitar", "poner") or (clase != "lista" and modo != "poner"):
            raise ValueError("Modo desconocido para ese campo.")
        contents = chapter["data"]["contenido"]
        elegidos: list[int] = []
        for index in indices or []:
            start, end = block_range(contents, int(index))
            elegidos.extend(i for i in range(start, end) if item_key(contents[i]) == clave and i not in elegidos)
        if not elegidos:
            raise ValueError(f"Elige {'requisitos' if clave == 'requisito' else 'pruebas'} (o secciones que los tengan).")
        limpiar = clean_requirement_changes if clave == "requisito" else clean_test_changes
        valores = esquema.lista_de_textos(valor, r"[\n,;]") if clase == "lista" else str(valor or "").strip()
        nuevos: dict[int, Any] = {}
        for i in elegidos:
            item = contents[i][clave]
            if clase == "lista":
                actual = [str(v).strip() for v in (item.get(campo) or [])] if isinstance(item.get(campo), list) else \
                    esquema.lista_de_textos(item.get(campo))
                if modo == "anadir":
                    nuevo = actual + [v for v in valores if v not in actual]
                elif modo == "quitar":
                    nuevo = [v for v in actual if v not in valores]
                else:
                    nuevo = list(valores)
            else:
                nuevo = valores
            limpio = limpiar({campo: nuevo})[campo]           # mismas comprobaciones que el formulario
            if to_plain(item.get(campo)) != limpio and not (item.get(campo) in (None, "", []) and limpio in ("", [])):
                nuevos[i] = limpio
        for i, limpio in nuevos.items():
            apply_changes(contents[i][clave], {campo: limpio})
        if nuevos:
            self._persist(chapter)
        return {"cambiados": len(nuevos), "elegidos": len(elegidos)}

    # --- YAML en bruto ---------------------------------------------------------
    @respuesta
    def aplicar_yaml(self, capitulo: int, indice: int, texto: str) -> dict[str, Any]:
        chapter, element = self._element(capitulo, indice, "cualquiera")
        parsed = roundtrip_yaml().load(texto)
        if not isinstance(parsed, dict):
            raise ValueError("El YAML debe ser un mapa (clave: valor).")
        contents = chapter["data"]["contenido"]
        if isinstance(element.get("requisito"), dict):
            self._exigir_escritura()
            self._check_req_id(str(parsed.get("id") or "").strip(), (chapter["path"], indice))
            if not isinstance(parsed.get("nivel"), int):
                parsed["nivel"] = element["requisito"].get("nivel", 3)
            anterior = to_plain(element["requisito"])
            element["requisito"] = parsed
            self._persist(chapter)
            self._anotar_cambio(anterior, parsed)
            return {"indice": indice}
        if isinstance(element.get("prueba"), dict):
            test_id = str(parsed.get("id") or "").strip()
            self._check_id(test_id, (chapter["path"], indice))
            if not isinstance(parsed.get("nivel"), int):
                parsed["nivel"] = element["prueba"].get("nivel", 3)
            element["prueba"] = parsed
        elif is_table(element):
            parsed["filas"] = _clean_table(parsed.get("filas"))
            element["tabla"] = parsed
        else:
            if not isinstance(parsed.get("seccion"), str) or not parsed["seccion"].strip():
                raise ValueError("La sección necesita la clave 'seccion' con un nombre.")
            contents[indice] = parsed
        self._persist(chapter)
        return {"indice": indice}

    # --- imágenes ------------------------------------------------------------
    def _resolve_image(self, ruta: str) -> Path:
        base = self._require_dir()
        path = (base / str(ruta)).resolve()
        if base != path and base not in path.parents:
            raise ValueError("La imagen debe estar dentro de la carpeta de YAML.")
        return path

    @respuesta
    def imagen(self, ruta: str, ancho: int = 480) -> dict[str, Any]:
        """Devuelve la imagen como data URI (miniatura si `ancho` > 0)."""
        return self._miniatura(self._resolve_image(ruta), ancho)

    def _miniatura(self, path: Path, ancho: int = 480) -> dict[str, Any]:
        from PIL import Image

        if not path.is_file():
            raise ValueError("No se encuentra el archivo.")
        stat = path.stat()
        key = (str(path), stat.st_mtime_ns, stat.st_size, int(ancho))
        if key in self._thumbs:
            return self._thumbs[key]
        suffix = path.suffix.lower()
        try:
            with Image.open(path) as image:
                image.load()
                width, height = image.size
                image = image.convert("RGBA" if "A" in image.getbands() or image.mode == "P" else "RGB")
                limit = ancho if ancho and ancho > 0 else 2000
                if width > limit or height > limit:
                    image.thumbnail((limit, limit))
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
        except Exception as error:  # noqa: BLE001 - formato no soportado, etc.
            if suffix in (".emf", ".wmf"):
                raise ValueError(
                    "Vista previa no disponible para EMF fuera de Windows. "
                    "El archivo se conserva y se incrusta en el DOCX."
                ) from error
            raise ValueError(f"No se puede mostrar la imagen: {error}") from error
        result = {
            "uri": "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii"),
            "ancho": width, "alto": height, "nombre": path.name,
        }
        if len(self._thumbs) > 150:
            self._thumbs.clear()
        self._thumbs[key] = result
        return result

    @respuesta
    def elegir_imagenes(self) -> dict[str, Any]:
        """Selector del sistema; copia las imágenes elegidas a `imagenes/`."""
        import webview

        if self._window is None:
            raise ValueError("El selector de archivos solo está disponible en la aplicación.")
        patterns = ";".join(f"*{ext}" for ext in sorted(ALLOWED_IMAGE_EXTENSIONS))
        kind = getattr(getattr(webview, "FileDialog", None), "OPEN", None) or webview.OPEN_DIALOG
        chosen = self._window.create_file_dialog(
            kind, allow_multiple=True, file_types=(f"Imágenes ({patterns})", "Todos los archivos (*.*)"),
        )
        if not chosen:
            return {"rutas": []}
        return {"rutas": self._import_files([Path(p) for p in chosen])}

    def _import_files(self, files: list[Path]) -> list[str]:
        self._exigir_escritura()
        uploads = []
        for path in files:
            if path.stat().st_size > MAX_IMAGE_BYTES:
                raise ValueError(f"{path.name} supera los 25 MB.")
            uploads.append(_ArchivoLocal(path.name, path.read_bytes()))
        return save_uploaded_images(uploads, self._require_dir() / "imagenes")

    @respuesta
    def importar_imagenes(self, rutas: list[str]) -> dict[str, Any]:
        return {"rutas": self._import_files([Path(r) for r in rutas])}

    @respuesta
    def importar_imagen_base64(self, nombre: str, datos: str) -> dict[str, Any]:
        """Guarda una imagen pegada o arrastrada desde el navegador."""
        self._exigir_escritura()
        if "," in datos[:100]:
            datos = datos.split(",", 1)[1]
        contenido = base64.b64decode(datos)
        if len(contenido) > MAX_IMAGE_BYTES:
            raise ValueError("La imagen supera los 25 MB.")
        name = nombre or "captura.png"
        if Path(name).suffix.lower() not in ALLOWED_IMAGE_EXTENSIONS:
            name += ".png"
        rutas = save_uploaded_images([_ArchivoLocal(name, contenido)], self._require_dir() / "imagenes")
        return {"rutas": rutas}

    # --- adjuntos ------------------------------------------------------------
    @respuesta
    def elegir_adjuntos(self) -> dict[str, Any]:
        """Selector del sistema; copia los archivos elegidos a `adjuntos/` (con su nombre)."""
        import webview

        if self._window is None:
            raise ValueError("El selector de archivos solo está disponible en la aplicación.")
        kind = getattr(getattr(webview, "FileDialog", None), "OPEN", None) or webview.OPEN_DIALOG
        chosen = self._window.create_file_dialog(
            kind, allow_multiple=True, file_types=("Excel, Word… (*.xlsx;*.xlsm;*.xls;*.docx;*.doc;*.pptx;*.pdf)", "Todos los archivos (*.*)"),
        )
        return {"adjuntos": self._copiar_adjuntos([Path(p) for p in chosen or []])}

    def _copiar_adjuntos(self, files: list[Path]) -> list[dict[str, str]]:
        """Copia los archivos a `adjuntos/`. Uno con el mismo nombre y otro contenido se guarda como «nombre_2»."""
        self._exigir_escritura()
        carpeta = self._require_dir() / adjuntos.CARPETA
        nuevos = []
        for path in files:
            if path.stat().st_size > MAX_IMAGE_BYTES:
                raise ValueError(f"{path.name} supera los 25 MB.")
            contenido = path.read_bytes()
            destino, n = carpeta / path.name, 1
            while destino.exists() and destino.read_bytes() != contenido:
                n += 1
                destino = carpeta / f"{path.stem}_{n}{path.suffix}"
            carpeta.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(contenido)
            nuevos.append({"archivo": f"{adjuntos.CARPETA}/{destino.name}"})
        return nuevos

    @respuesta
    def abrir_adjunto(self, ruta: str) -> dict[str, Any]:
        """Abre un adjunto de la prueba con el programa predeterminado del sistema."""
        base = self._require_dir()
        archivo = (base / str(ruta)).resolve()
        if base not in archivo.parents or not archivo.is_file():
            raise ValueError(f"No se encuentra el adjunto: {ruta}.")
        if sys.platform.startswith("win"):
            import os
            os.startfile(archivo)  # noqa: S606 - archivo de la carpeta de pruebas
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(archivo)])  # noqa: S603,S607
        else:
            subprocess.Popen(["xdg-open", str(archivo)])  # noqa: S603,S607
        return {}

    # --- validación ---------------------------------------------------------
    @respuesta
    def validar(self) -> dict[str, Any]:
        """Problemas de la colección activa (pruebas o requisitos)."""
        if self._requisitos():
            return self._validar_requisitos()
        base = self._require_dir()
        issues: list[dict[str, Any]] = []
        catalogo = {str(r.get("id") or "").strip() for c in self._req_chapters for _i, r in items_in_chapter(c, "requisito")}

        def add(kind: str, chapter_index: int, index: int | None, test_id: str, message: str) -> None:
            issues.append({
                "severidad": kind, "capitulo": chapter_index, "indice": index,
                "id": test_id, "mensaje": message,
                "archivo": self._chapters[chapter_index]["path"].name,
            })

        seen: dict[str, list[tuple[int, int]]] = {}
        for ci, chapter in enumerate(self._chapters):
            if not chapter["data"].get("capitulo"):
                add("aviso", ci, None, "", "El capítulo no tiene nombre ('capitulo').")
            for index, element in enumerate(chapter["data"]["contenido"]):
                if not isinstance(element, dict):
                    add("error", ci, index, "", "Elemento del contenido que no es un mapa.")
                    continue
                if isinstance(element.get("seccion"), str):
                    self._check_images(add, base, ci, index, "", _image_values(element))
                    self._check_adjuntos(add, base, ci, index, "", element)
                    self._check_context_tables(add, ci, index, "", element.get("contexto"))
                    continue
                if "tabla" in element:
                    if not is_table(element) or not table_rows(element["tabla"]):
                        add("error", ci, index, "", "La tabla necesita 'filas': una lista de filas con sus celdas.")
                    elif len(table_rows(element["tabla"])) != len(element["tabla"].get("filas") or []):
                        add("error", ci, index, "", "Cada fila de la tabla debe ser una lista de celdas.")
                    self._check_images(add, base, ci, index, "", _image_values(element))
                    self._check_adjuntos(add, base, ci, index, "", element)
                    continue
                test = element.get("prueba")
                if not isinstance(test, dict):
                    if "texto" not in element:
                        add("aviso", ci, index, "", "Elemento sin 'seccion', 'prueba', 'tabla' ni 'texto'.")
                    continue
                test_id = str(test.get("id") or "").strip()
                if not test_id:
                    add("error", ci, index, "", "La prueba no tiene ID.")
                else:
                    seen.setdefault(test_id, []).append((ci, index))
                if not str(test.get("titulo") or "").strip():
                    add("error", ci, index, test_id, "La prueba no tiene título.")
                listas = (*LIST_FIELDS, *esquema.CAMPOS_TEXTOS, *esquema.OPCIONES_MULTIPLES)
                for field in listas:
                    if field in test and test[field] not in (None, "") and not isinstance(test[field], list):
                        add("error", ci, index, test_id, f"'{field}' debe ser una lista.")
                for field, opciones in esquema.OPCIONES_MULTIPLES.items():
                    otros = [str(v) for v in test.get(field) or [] if str(v) not in opciones] if isinstance(test.get(field), list) else []
                    if otros:
                        add("aviso", ci, index, test_id, f"{esquema.ETIQUETAS[field]}: «{', '.join(otros)}» no es una opción ({', '.join(opciones)}).")
                if catalogo and isinstance(test.get("requisitos"), list):
                    faltan = [r for r in trazabilidad.lista(test["requisitos"]) if r not in catalogo]
                    if faltan:
                        add("aviso", ci, index, test_id,
                            f"{'El requisito' if len(faltan) == 1 else 'Los requisitos'} «{', '.join(faltan)}» no "
                            f"{'existe' if len(faltan) == 1 else 'existen'} en el catálogo de requisitos.")
                if esquema.normalizar_automatizable(test.get("automatizable")) is None:
                    add("aviso", ci, index, test_id, f"Automatizable: «{test.get('automatizable')}» no es una opción.")
                obsoletos = [c for c in esquema.OBSOLETOS if c in test]
                if obsoletos:
                    add("aviso", ci, index, test_id,
                        f"Campos que ya no existen: {', '.join(obsoletos)}. Vuelve a importar el Word o quítalos en la vista YAML.")
                self._check_context_tables(add, ci, index, test_id, test.get("contexto"))
                level = test.get("nivel")
                if level is not None and (not isinstance(level, int) or not 1 <= level <= 6):
                    add("aviso", ci, index, test_id, f"Nivel fuera del rango 1-6: {level}.")
                self._check_images(add, base, ci, index, test_id, _image_values(test))
                self._check_adjuntos(add, base, ci, index, test_id, test)
        for test_id, places in seen.items():
            if len(places) > 1:
                where = ", ".join(self._chapters[c]["path"].name for c, _i in places)
                for ci, index in places:
                    add("error", ci, index, test_id, f"ID duplicado ({len(places)} veces): {where}.")
        return self._informe(issues)

    @staticmethod
    def _informe(issues: list[dict[str, Any]]) -> dict[str, Any]:
        issues.sort(key=lambda i: (i["severidad"] != "error", i["capitulo"], i["indice"] or 0))
        return {
            "problemas": issues,
            "errores": sum(1 for i in issues if i["severidad"] == "error"),
            "avisos": sum(1 for i in issues if i["severidad"] == "aviso"),
        }

    def _validar_requisitos(self) -> dict[str, Any]:
        if self._req_error:
            raise ValueError(self._req_error)
        base = self._req_dir()
        issues: list[dict[str, Any]] = []

        def add(kind: str, chapter_index: int, index: int | None, req_id: str, message: str) -> None:
            issues.append({
                "severidad": kind, "capitulo": chapter_index, "indice": index, "id": req_id,
                "mensaje": message, "archivo": self._req_chapters[chapter_index]["path"].name,
            })

        seen: dict[str, list[int]] = {}
        for ci, chapter in enumerate(self._req_chapters):
            if not chapter["data"].get("capitulo"):
                add("aviso", ci, None, "", "El capítulo no tiene nombre ('capitulo').")
            for index, element in enumerate(chapter["data"]["contenido"]):
                if not isinstance(element, dict):
                    add("error", ci, index, "", "Elemento del contenido que no es un mapa.")
                    continue
                if isinstance(element.get("seccion"), str) or "tabla" in element:
                    self._check_images(add, base, ci, index, "", _image_values(element))
                    self._check_context_tables(add, ci, index, "", element.get("contexto"))
                    continue
                req = element.get("requisito")
                if not isinstance(req, dict):
                    if "prueba" in element:
                        add("error", ci, index, "", "Hay una prueba en la carpeta de requisitos.")
                    elif "texto" not in element:
                        add("aviso", ci, index, "", "Elemento sin 'seccion', 'requisito', 'tabla' ni 'texto'.")
                    continue
                req_id = str(req.get("id") or "").strip()
                if not req_id:
                    add("error", ci, index, "", "El requisito no tiene ID.")
                else:
                    seen.setdefault(req_id, []).append(ci)
                    if any(c.isspace() for c in req_id):
                        add("aviso", ci, index, req_id, "El ID tiene espacios: las pruebas no podrán citarlo bien.")
                if not str(req.get("titulo") or "").strip():
                    add("error", ci, index, req_id, "El requisito no tiene título.")
                tipo = str(req.get("tipo") or "").strip()
                if tipo and tipo not in esquema.REQ_TIPOS:
                    add("aviso", ci, index, req_id, f"Tipo: «{tipo}» no es una opción ({', '.join(esquema.REQ_TIPOS)}).")
                for field, opciones in esquema.REQ_OPCIONES_MULTIPLES.items():
                    valor = req.get(field)
                    if valor not in (None, "") and not isinstance(valor, list):
                        add("error", ci, index, req_id, f"'{field}' debe ser una lista.")
                        continue
                    otros = [str(v) for v in valor or [] if str(v) not in opciones]
                    if otros:
                        add("aviso", ci, index, req_id, f"{esquema.REQ_ETIQUETAS[field]}: «{', '.join(otros)}» no es una opción ({', '.join(opciones)}).")
                self._check_context_tables(add, ci, index, req_id, req.get("contexto"))
                self._check_context_tables(add, ci, index, req_id, req.get("detalle"))
                self._check_images(add, base, ci, index, req_id, _image_values(req))
        for req_id, places in seen.items():
            if len(places) > 1:
                where = ", ".join(sorted({self._req_chapters[c]["path"].name for c in places}))
                for ci, chapter in enumerate(self._req_chapters):
                    for index, req in items_in_chapter(chapter, "requisito"):
                        if str(req.get("id") or "").strip() == req_id:
                            add("error", ci, index, req_id, f"ID duplicado ({len(places)} veces): {where}.")
        return self._informe(issues)

    @staticmethod
    def _check_context_tables(add: Callable[..., None], ci: int, index: int, test_id: str, context: Any) -> None:
        for item in context if isinstance(context, list) else []:
            if isinstance(item, dict) and "tabla" in item:
                table = item["tabla"]
                rows = table_rows(table) if isinstance(table, dict) else []
                if not rows or len(rows) != len(table.get("filas") or []):
                    add("error", ci, index, test_id, "Tabla del contexto sin 'filas' válidas (una lista de filas con sus celdas).")

    @staticmethod
    def _check_images(add: Callable[..., None], base: Path, ci: int, index: int,
                      test_id: str, paths: list[str]) -> None:
        for rel in paths:
            full = (base / rel)
            if Path(rel).is_absolute():
                add("aviso", ci, index, test_id, f"Ruta de imagen absoluta: {rel}.")
            elif Path(rel).suffix.lower() not in ALLOWED_IMAGE_EXTENSIONS:
                add("aviso", ci, index, test_id, f"Formato de imagen no admitido: {rel}.")
            elif not full.is_file():
                add("error", ci, index, test_id, f"No existe la imagen: {rel}.")

    @staticmethod
    def _check_adjuntos(add: Callable[..., None], base: Path, ci: int, index: int, test_id: str, elemento: Any) -> None:
        """La lista de adjuntos del elemento y los que nombran sus párrafos: que existan sus archivos y dibujos."""
        if elemento.get("adjuntos") is not None and not isinstance(elemento.get("adjuntos"), list):
            add("error", ci, index, test_id, "'adjuntos' debe ser una lista.")
            return
        for ruta in sorted(adjuntos.archivos(elemento)):
            if Path(ruta).is_absolute():
                add("aviso", ci, index, test_id, f"Ruta de adjunto absoluta: {ruta}.")
            elif not (base / ruta).is_file():
                add("error", ci, index, test_id, f"No existe el adjunto: {ruta}.")

    # --- exportación -----------------------------------------------------------
    @respuesta
    def elegir_destino_docx(self) -> dict[str, Any]:
        """«Guardar como» para el DOCX; la interfaz muestra la espera solo mientras se genera."""
        archivo = self._guardar_como(self._yaml_dir_or_fail().parent, "requisitos.docx" if self._requisitos() else "pruebas.docx")
        return {"archivo": archivo} if archivo else {"cancelado": True}

    def _guardar_como(self, carpeta: Path, nombre: str, tipo: str = "Documento de Word (*.docx)") -> str | None:
        """Diálogo «Guardar como» (por defecto, de un documento de Word); None si se cancela."""
        import webview

        if self._window is None:
            raise ValueError("«Guardar como» solo está disponible en la aplicación.")
        kind = getattr(getattr(webview, "FileDialog", None), "SAVE", None) or webview.SAVE_DIALOG
        elegido = self._window.create_file_dialog(
            kind, directory=str(carpeta), save_filename=nombre, file_types=(tipo,),
        )
        if not elegido:
            return None
        return elegido if isinstance(elegido, str) else elegido[0]

    @respuesta
    def exportar_matriz(self, salida: str | None = None) -> dict[str, Any]:
        """Matriz de trazabilidad en CSV (una fila por requisito). Sin `salida`, abre «Guardar como»."""
        base = self._yaml_dir_or_fail()
        if not self._req_chapters:
            raise ValueError("Esta carpeta no tiene requisitos.")
        if salida is None:
            salida = self._guardar_como(base.parent, "matriz_trazabilidad.csv", "CSV para Excel (*.csv)")
            if salida is None:
                return {"cancelado": True}
        output = Path(salida)
        if output.suffix.lower() != ".csv":
            output = output.with_suffix(".csv")
        datos = self._traza()
        trazabilidad.escribir_matriz(datos, output)
        return {"archivo": str(output), "requisitos": len(datos["requisitos"])}

    @respuesta
    def exportar_docx(self, primer_capitulo: int = 1, salida: str | None = None) -> dict[str, Any]:
        """Genera el DOCX con `yaml_a_docx`. Sin `salida`, abre «Guardar como»."""
        from app import yaml_a_docx

        base = self._require_dir()
        if salida is None:
            salida = self._guardar_como(self._yaml_dir_or_fail().parent, "requisitos.docx" if self._requisitos() else "pruebas.docx")
            if salida is None:
                return {"cancelado": True}
        output = Path(salida)
        if output.suffix.lower() != ".docx":
            output = output.with_suffix(".docx")
        output.parent.mkdir(parents=True, exist_ok=True)
        buffer = io.StringIO()
        try:
            with contextlib.redirect_stdout(buffer):
                yaml_a_docx.main([str(base), "-o", str(output), "--primer-capitulo", str(int(primer_capitulo))])
        except SystemExit as stop:
            if stop.code not in (None, 0):
                raise ValueError(str(stop.code)) from None
        lines = [line.strip() for line in buffer.getvalue().splitlines() if line.strip()]
        return {
            "archivo": str(output),
            "resumen": lines[-1] if lines else "",
            "avisos": [line for line in lines if line.startswith("AVISO")],
        }

    # --- bloqueo de capítulos ---------------------------------------------------
    def _info_bloqueo(self, chapter: dict[str, Any]) -> dict[str, Any]:
        otro = self._bloqueos.de_otro(chapter["path"])
        return {"otro": {**otro, "texto": bloqueos.texto(otro)} if otro else None,
                "mio": self._bloqueos.es_mio(chapter["path"])}

    @respuesta
    def bloqueo(self, capitulo: int) -> dict[str, Any]:
        """Si otra persona está editando el capítulo (y quién)."""
        if self._solo_lectura or not self._activos():
            return {"otro": None, "mio": False}
        return self._info_bloqueo(self._require_chapter(capitulo))

    @respuesta
    def bloquear(self, capitulo: int, forzar: bool = False) -> dict[str, Any]:
        """Toma el bloqueo del capítulo al empezar a editarlo (o lo fuerza). Si lo tiene otra persona, dice quién."""
        if self._solo_lectura:
            return {"otro": None, "mio": False}
        chapter = self._require_chapter(capitulo)
        self._bloqueos.tomar(chapter["path"], bool(forzar))
        return self._info_bloqueo(chapter)

    @respuesta
    def soltar_bloqueos(self) -> dict[str, Any]:
        """Suelta los bloqueos de esta sesión (al cambiar de capítulo o de colección)."""
        self._bloqueos.soltar_todos()
        return {}

    # --- cierre de la ventana -----------------------------------------------------
    @respuesta
    def marcar_cambios(self, pendientes: bool) -> dict[str, Any]:
        """La interfaz indica si hay cambios sin guardar (para avisar al cerrar)."""
        self._sin_guardar = bool(pendientes)
        return {}

    @respuesta
    def cerrar(self) -> dict[str, Any]:
        """Cierra la ventana después de que la interfaz haya resuelto los cambios pendientes."""
        self._cierre_aceptado = True
        if self._window is not None:
            # Se cierra un poco después para que esta respuesta llegue antes a la página.
            threading.Timer(0.2, self._window.destroy).start()
        return {}

    def _al_cerrar_ventana(self) -> bool:
        """Manejador de `closing`: con cambios sin guardar cancela el cierre (False)
        y la página pregunta qué hacer; si se sale, la página llama a `cerrar`.

        Se ejecuta en el hilo de la interfaz gráfica, así que no espera a la página.
        """
        if self._cierre_aceptado or not self._sin_guardar or self._window is None:
            return True
        window = self._window

        def preguntar() -> None:
            try:
                window.evaluate_js("pedirCierre()")
            except Exception:  # noqa: BLE001 - si la página no responde, no se bloquea el cierre
                self._sin_guardar = False

        threading.Thread(target=preguntar, daemon=True).start()
        return False

    @respuesta
    def mostrar_en_carpeta(self, ruta: str) -> dict[str, Any]:
        path = Path(ruta)
        if sys.platform.startswith("win"):
            subprocess.Popen(["explorer", "/select,", str(path)])  # noqa: S603,S607
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(path)])  # noqa: S603,S607
        else:
            subprocess.Popen(["xdg-open", str(path.parent)])  # noqa: S603,S607
        return {}
