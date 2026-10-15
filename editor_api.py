#!/usr/bin/env python3
"""API del editor web de pruebas YAML.

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
import subprocess
import sys
import threading
import traceback
from pathlib import Path
from typing import Any, Callable

from ruamel.yaml.error import YAMLError

from editor_core import (
    ALLOWED_IMAGE_EXTENSIONS,
    DEFAULT_TEST,
    LIST_FIELDS,
    delete_section,
    delete_test,
    find_duplicate_id,
    headings_in_chapter,
    insert_section_after_test,
    insert_test,
    move_block,
    navigation_entries,
    normalize_level,
    read_chapters,
    roundtrip_yaml,
    save_chapter,
    save_uploaded_images,
    section_end_index,
    tests_in_chapter,
    yaml_to_string,
)

TEXT_FIELDS = (
    "nombre", "id", "titulo", "descripcion", "componente", "plataforma",
    "automatizable", "criticidad", "entorno", "referencia", "fecha", "version",
)
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
    cleaned: dict[str, Any] = {}
    for key, value in item.items():
        if key == "texto":
            cleaned[key] = str(value or "").strip()
        elif key == "imagenes":
            images = [str(v).strip() for v in (value or []) if str(v).strip()]
            if images:
                cleaned[key] = images
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
        empty_map = isinstance(cleaned, dict) and not cleaned.get("texto") and not cleaned.get("imagenes")
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
        if field in TEXT_FIELDS:
            cleaned[field] = str(value if value is not None else "").strip()
        elif field in LIST_FIELDS:
            cleaned[field] = _clean_list(value, field)
        elif field == "campos_adicionales":
            cleaned[field] = _clean_extras(value)
        elif field == "imagenes":
            cleaned[field] = _clean_list(value, field)
            if any(not isinstance(v, str) for v in cleaned[field]):
                raise ValueError("'imagenes' debe ser una lista de rutas.")
        elif field == "etiquetas":
            cleaned[field] = _clean_tags(value)
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
        self._chapters: list[dict[str, Any]] = []
        self._mtimes: dict[Path, int] = {}
        self._thumbs: dict[tuple[str, int, int, int], dict[str, Any]] = {}
        self._carpeta_inicial = Path(carpeta_inicial) if carpeta_inicial else None
        self._al_cargar: Callable[[Path], None] | None = None   # p. ej. recordar la carpeta
        self._solo_lectura = False     # p. ej., las pruebas congeladas de una campaña cerrada
        self._sin_guardar = False      # la interfaz avisa cuando hay cambios pendientes
        self._cierre_aceptado = False

    # --- estado ------------------------------------------------------
    def _require_chapter(self, capitulo: int) -> dict[str, Any]:
        if not self._chapters:
            raise ValueError("No hay ninguna carpeta cargada.")
        if not isinstance(capitulo, int) or not 0 <= capitulo < len(self._chapters):
            raise ValueError("El capítulo seleccionado ya no existe.")
        return self._chapters[capitulo]

    def _require_dir(self) -> Path:
        if self._yaml_dir is None:
            raise ValueError("No hay ninguna carpeta cargada.")
        return self._yaml_dir

    def _element(self, capitulo: int, indice: int, tipo: str) -> tuple[dict[str, Any], Any]:
        chapter = self._require_chapter(capitulo)
        contents = chapter["data"]["contenido"]
        if not isinstance(indice, int) or not 0 <= indice < len(contents):
            raise ValueError("La posición seleccionada ya no existe.")
        element = contents[indice]
        if tipo == "prueba" and not (isinstance(element, dict) and isinstance(element.get("prueba"), dict)):
            raise ValueError("La posición seleccionada ya no corresponde a una prueba.")
        if tipo == "seccion" and not (isinstance(element, dict) and isinstance(element.get("seccion"), str)):
            raise ValueError("La posición seleccionada ya no corresponde a una sección.")
        return chapter, element

    def _load(self, yaml_dir: Path) -> None:
        chapters = read_chapters(yaml_dir)
        if not chapters:
            raise ValueError("No se encontraron capítulos YAML en la carpeta.")
        self._solo_lectura = False
        self._yaml_dir = yaml_dir.resolve()
        self._chapters = chapters
        self._mtimes = {c["path"]: c["path"].stat().st_mtime_ns for c in chapters}
        self._thumbs.clear()
        if self._al_cargar is not None:
            try:
                self._al_cargar(self._yaml_dir)
            except Exception:  # noqa: BLE001 - un fallo accesorio no debe impedir abrir la carpeta
                traceback.print_exc()

    def _reload_chapter(self, chapter: dict[str, Any]) -> None:
        with chapter["path"].open(encoding="utf-8") as source:
            chapter["data"] = roundtrip_yaml().load(source)
        self._mtimes[chapter["path"]] = chapter["path"].stat().st_mtime_ns

    def _exigir_escritura(self) -> None:
        if self._solo_lectura:
            raise ValueError(
                "Esta carpeta es la copia congelada de una campaña cerrada y no se puede modificar. "
                "Para editar las pruebas, abre su carpeta de pruebas."
            )

    def _persist(self, chapter: dict[str, Any]) -> None:
        """Guarda el capítulo; si falla, vuelve a leer el disco para no divergir."""
        if self._solo_lectura:
            self._reload_chapter(chapter)      # deshace lo que se cambió en memoria
            self._exigir_escritura()
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
        return {
            "carpeta": str(self._yaml_dir) if self._yaml_dir else None,
            "solo_lectura": self._solo_lectura,
            "capitulos": [
                {
                    "indice": i,
                    "nombre": str(c["data"].get("capitulo") or c["path"].name),
                    "archivo": c["path"].name,
                    "pruebas": len(tests_in_chapter(c)),
                }
                for i, c in enumerate(self._chapters)
            ],
        }

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
        self._load(folder)
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
        nodes = []
        for kind, index, label, parent, level in navigation_entries(chapter, str(consulta or "")):
            element = contents[index]
            if kind == "section":
                nodes.append({
                    "tipo": "seccion", "indice": index, "padre": parent,
                    "nivel": level, "titulo": element["seccion"],
                })
            else:
                test = element["prueba"]
                nodes.append({
                    "tipo": "prueba", "indice": index, "padre": parent,
                    "nivel": level, "id": str(test.get("id") or ""),
                    "titulo": str(test.get("titulo") or test.get("nombre") or ""),
                })
        return nodes

    @respuesta
    def ubicaciones(self, capitulo: int) -> list[dict[str, Any]]:
        """Secciones disponibles como destino al crear pruebas o secciones."""
        chapter = self._require_chapter(capitulo)
        return [
            {"indice": index, "titulo": title, "nivel": level}
            for index, title, level in headings_in_chapter(chapter)
        ]

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
        if isinstance(element.get("prueba"), dict):
            test = to_plain(element["prueba"])
            test["nivel"] = normalize_level(test.get("nivel"), 3)
            return {"tipo": "prueba", "indice": indice, "elemento": test}
        if isinstance(element.get("seccion"), str):
            section = to_plain(element)
            section["nivel"] = normalize_level(section.get("nivel"), 2)
            return {"tipo": "seccion", "indice": indice, "elemento": section}
        raise ValueError("La posición seleccionada no es una sección ni una prueba.")

    @respuesta
    def obtener_yaml(self, capitulo: int, indice: int) -> dict[str, Any]:
        _chapter, element = self._element(capitulo, indice, "cualquiera")
        target = element["prueba"] if isinstance(element.get("prueba"), dict) else element
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
            if not (isinstance(element, dict) and isinstance(element.get("prueba"), dict)):
                raise ValueError("La ubicación elegida ya no es una prueba.")
            return normalize_level(element["prueba"].get("nivel"), 3)
        if kind == "final":
            return default
        raise ValueError("Ubicación no válida.")

    @respuesta
    def crear_prueba(self, capitulo: int, ubicacion: dict[str, Any], datos: dict[str, Any]) -> dict[str, Any]:
        chapter = self._require_chapter(capitulo)
        contents = chapter["data"]["contenido"]
        data = clean_test_changes({k: v for k, v in datos.items() if k != "nivel"})
        self._check_id(data.get("id", ""), None)
        test = {**DEFAULT_TEST, **data, "nivel": self._level_for(contents, ubicacion, 3)}
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
        apply_changes(element, changes)
        self._persist(chapter)
        return {"indice": indice}

    @respuesta
    def borrar_seccion(self, capitulo: int, indice: int) -> dict[str, Any]:
        chapter, _element = self._element(capitulo, indice, "seccion")
        delete_section(chapter, indice)
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

    # --- YAML en bruto ---------------------------------------------------------
    @respuesta
    def aplicar_yaml(self, capitulo: int, indice: int, texto: str) -> dict[str, Any]:
        chapter, element = self._element(capitulo, indice, "cualquiera")
        parsed = roundtrip_yaml().load(texto)
        if not isinstance(parsed, dict):
            raise ValueError("El YAML debe ser un mapa (clave: valor).")
        contents = chapter["data"]["contenido"]
        if isinstance(element.get("prueba"), dict):
            test_id = str(parsed.get("id") or "").strip()
            self._check_id(test_id, (chapter["path"], indice))
            if not isinstance(parsed.get("nivel"), int):
                parsed["nivel"] = element["prueba"].get("nivel", 3)
            element["prueba"] = parsed
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

    # --- validación ---------------------------------------------------------
    @respuesta
    def validar(self) -> dict[str, Any]:
        base = self._require_dir()
        issues: list[dict[str, Any]] = []

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
                    continue
                test = element.get("prueba")
                if not isinstance(test, dict):
                    if "texto" not in element and "tabla" not in element:
                        add("aviso", ci, index, "", "Elemento sin 'seccion', 'prueba', 'tabla' ni 'texto'.")
                    continue
                test_id = str(test.get("id") or "").strip()
                if not test_id:
                    add("error", ci, index, "", "La prueba no tiene ID.")
                else:
                    seen.setdefault(test_id, []).append((ci, index))
                if not str(test.get("titulo") or "").strip():
                    add("aviso", ci, index, test_id, "La prueba no tiene título.")
                for field in (*LIST_FIELDS, "etiquetas"):
                    if field in test and test[field] not in (None, "") and not isinstance(test[field], list):
                        add("error", ci, index, test_id, f"'{field}' debe ser una lista.")
                if not any(test.get(f) for f in ("pasos", "situacion_inicial", "situacion_final")):
                    add("aviso", ci, index, test_id, "La prueba no tiene pasos ni situaciones.")
                level = test.get("nivel")
                if level is not None and (not isinstance(level, int) or not 1 <= level <= 6):
                    add("aviso", ci, index, test_id, f"Nivel fuera del rango 1-6: {level}.")
                self._check_images(add, base, ci, index, test_id, _image_values(test))
        for test_id, places in seen.items():
            if len(places) > 1:
                where = ", ".join(self._chapters[c]["path"].name for c, _i in places)
                for ci, index in places:
                    add("error", ci, index, test_id, f"ID duplicado ({len(places)} veces): {where}.")
        issues.sort(key=lambda i: (i["severidad"] != "error", i["capitulo"], i["indice"] or 0))
        return {
            "problemas": issues,
            "errores": sum(1 for i in issues if i["severidad"] == "error"),
            "avisos": sum(1 for i in issues if i["severidad"] == "aviso"),
        }

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

    # --- exportación -----------------------------------------------------------
    @respuesta
    def exportar_docx(self, primer_capitulo: int = 1, salida: str | None = None) -> dict[str, Any]:
        """Genera el DOCX con `yaml_a_docx`. Sin `salida`, abre «Guardar como»."""
        import yaml_a_docx

        base = self._require_dir()
        if salida is None:
            import webview

            if self._window is None:
                raise ValueError("«Guardar como» solo está disponible en la aplicación.")
            kind = getattr(getattr(webview, "FileDialog", None), "SAVE", None) or webview.SAVE_DIALOG
            chosen = self._window.create_file_dialog(
                kind, directory=str(base.parent), save_filename="pruebas.docx",
                file_types=("Documento de Word (*.docx)",),
            )
            if not chosen:
                return {"cancelado": True}
            salida = chosen if isinstance(chosen, str) else chosen[0]
        output = Path(salida)
        if output.suffix.lower() != ".docx":
            output = output.with_suffix(".docx")
        output.parent.mkdir(parents=True, exist_ok=True)
        buffer = io.StringIO()
        old_argv = sys.argv
        sys.argv = ["yaml_a_docx", str(base), "-o", str(output), "--primer-capitulo", str(int(primer_capitulo))]
        try:
            with contextlib.redirect_stdout(buffer):
                yaml_a_docx.main()
        except SystemExit as stop:
            if stop.code not in (None, 0):
                raise ValueError(str(stop.code)) from None
        finally:
            sys.argv = old_argv
        lines = [line.strip() for line in buffer.getvalue().splitlines() if line.strip()]
        return {
            "archivo": str(output),
            "resumen": lines[-1] if lines else "",
            "avisos": [line for line in lines if line.startswith("AVISO")],
        }

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
