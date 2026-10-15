#!/usr/bin/env python3
"""Núcleo de datos y edición de los YAML de pruebas.

Este módulo no depende de ninguna interfaz gráfica: lo usa la API del editor
web (editor_api.py).
"""
from __future__ import annotations

import os
import re
import tempfile
from io import StringIO
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML


LIST_FIELDS = ("situacion_inicial", "pasos", "situacion_final", "contexto")
ALLOWED_IMAGE_EXTENSIONS = {".bmp", ".emf", ".gif", ".jpeg", ".jpg", ".png", ".tif", ".tiff"}


def roundtrip_yaml() -> YAML:
    yaml = YAML()
    yaml.allow_unicode = True
    yaml.width = 4096
    return yaml


def yaml_to_string(value: Any) -> str:
    buffer = StringIO()
    roundtrip_yaml().dump(value, buffer)
    return buffer.getvalue()


def read_chapters(yaml_dir: Path) -> list[dict[str, Any]]:
    yaml_dir = yaml_dir.resolve()
    index_path = yaml_dir / "indice.yaml"
    yaml = roundtrip_yaml()
    if index_path.exists():
        with index_path.open(encoding="utf-8") as source:
            index = yaml.load(source) or []
        if not isinstance(index, list):
            raise ValueError("indice.yaml debe contener una lista de capítulos.")
        files = []
        for entry in index:
            if not isinstance(entry, dict) or not isinstance(entry.get("archivo"), str):
                raise ValueError("Cada entrada de indice.yaml debe incluir 'archivo'.")
            path = (yaml_dir / entry["archivo"]).resolve()
            if path.parent != yaml_dir or path.suffix.lower() != ".yaml":
                raise ValueError(f"Ruta de capítulo no válida en indice.yaml: {entry['archivo']}")
            files.append(path)
    else:
        files = sorted(path for path in yaml_dir.glob("*.yaml") if path.name != "indice.yaml")

    chapters = []
    for path in files:
        with path.open(encoding="utf-8") as source:
            data = yaml.load(source)
        if not isinstance(data, dict) or not isinstance(data.get("contenido"), list):
            raise ValueError(f"{path.name} debe tener un mapa y una lista 'contenido'.")
        chapters.append({"path": path, "data": data})
    return chapters


def tests_in_chapter(chapter: dict[str, Any]) -> list[tuple[int, dict[str, Any]]]:
    return [
        (index, element["prueba"])
        for index, element in enumerate(chapter["data"]["contenido"])
        if isinstance(element, dict) and isinstance(element.get("prueba"), dict)
    ]


def normalize_level(value: Any, default: int = 3) -> int:
    try:
        level = int(value)
    except (TypeError, ValueError):
        level = default
    return min(max(level, 1), 6)


def headings_in_chapter(chapter: dict[str, Any]) -> list[tuple[int, str, int]]:
    headings = []
    for index, element in enumerate(chapter["data"]["contenido"]):
        if isinstance(element, dict) and isinstance(element.get("seccion"), str):
            headings.append((index, element["seccion"], normalize_level(element.get("nivel"), 2)))
    return headings


def is_table(element: Any) -> bool:
    """Tabla que no es una prueba (historial, parámetros…), conservada del Word."""
    return isinstance(element, dict) and isinstance(element.get("tabla"), dict)


def cell_text(cell: Any) -> str:
    if isinstance(cell, dict):
        return str(cell.get("texto") or "")
    return "" if cell is None else str(cell)


def table_rows(table: dict[str, Any]) -> list[list[Any]]:
    return [row for row in (table.get("filas") or []) if isinstance(row, list)]


def table_title(table: dict[str, Any]) -> str:
    """Primer texto de la tabla (sin marcas de formato), para mostrarla en el árbol."""
    for row in table_rows(table):
        for cell in row:
            text = re.sub(r"\[\[[^\]|]+\||\]\]|\*", "", cell_text(cell))
            text = " ".join(text.split())
            if text:
                return text[:80]
    return ""


def table_level(contents: list[Any], index: int) -> int:
    """Nivel con el que se muestra una tabla: el de lo que cuelga del encabezado anterior."""
    for element in reversed(contents[:index]):
        if isinstance(element, dict) and isinstance(element.get("seccion"), str):
            return min(normalize_level(element.get("nivel"), 2) + 1, 6)
        if isinstance(element, dict) and isinstance(element.get("prueba"), dict):
            return normalize_level(element["prueba"].get("nivel"), 3)
    return 3


def navigation_entries(
    chapter: dict[str, Any],
    query: str = "",
) -> list[tuple[str, int, str, int | None, int]]:
    query = query.casefold()
    records: list[tuple[str, int, str, int | None, int, bool]] = []
    heading_stack: list[tuple[int, int]] = []
    matching_heading_ids: set[int] = set()

    for index, element in enumerate(chapter["data"]["contenido"]):
        if not isinstance(element, dict):
            continue
        if isinstance(element.get("seccion"), str):
            level = normalize_level(element.get("nivel"), 2)
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            parent_index = heading_stack[-1][1] if heading_stack else None
            title = element["seccion"]
            records.append(("section", index, title, parent_index, level, False))
            heading_stack.append((level, index))
            continue

        if is_table(element):
            ancestors = [heading[1] for heading in heading_stack]
            searchable = " ".join(cell_text(c) for row in table_rows(element["tabla"]) for c in row).casefold()
            matches = not query or query in searchable
            if matches:
                matching_heading_ids.update(ancestors)
            records.append(("table", index, table_title(element["tabla"]) or "(tabla vacía)",
                            ancestors[-1] if ancestors else None,
                            min(heading_stack[-1][0] + 1, 6) if heading_stack else 3, matches))
            continue

        test = element.get("prueba")
        if not isinstance(test, dict):
            continue
        level = normalize_level(test.get("nivel"), 3)
        while heading_stack and heading_stack[-1][0] >= level:
            heading_stack.pop()
        ancestors = [heading[1] for heading in heading_stack]
        title = str(test.get("titulo") or test.get("nombre") or "(sin título)")
        test_id = str(test.get("id") or "(sin ID)")
        searchable = " ".join(str(value) for value in test.values()).casefold()
        matches = not query or query in searchable
        if matches:
            matching_heading_ids.update(ancestors)
        records.append(
            ("test", index, f"{test_id} — {title}", ancestors[-1] if ancestors else None,
             level, matches)
        )

    return [
        (kind, index, label, parent_index, level)
        for kind, index, label, parent_index, level, matches in records
        if (
            not query
            or (kind in ("test", "table") and matches)
            or (kind == "section" and index in matching_heading_ids)
        )
    ]


def find_duplicate_id(chapters: list[dict[str, Any]], test_id: str,
                      excluded: tuple[Path, int] | None = None) -> str | None:
    if not test_id:
        return "El ID es obligatorio."
    matches = []
    for chapter in chapters:
        for index, test in tests_in_chapter(chapter):
            if test.get("id") == test_id and (
                excluded is None or (chapter["path"], index) != excluded
            ):
                matches.append(chapter["path"].name)
    if matches:
        return f"El ID '{test_id}' ya existe en: {', '.join(matches)}."
    return None


def insert_test(chapter: dict[str, Any], test: dict[str, Any],
                heading_index: int | None,
                after_test_index: int | None = None) -> None:
    contents = chapter["data"]["contenido"]
    if after_test_index is not None:
        if (
            after_test_index < 0
            or after_test_index >= len(contents)
            or not isinstance(contents[after_test_index], dict)
            or not isinstance(contents[after_test_index].get("prueba"), dict)
        ):
            raise ValueError("La posición seleccionada ya no corresponde a una prueba.")
        contents.insert(after_test_index + 1, {"prueba": test})
        return
    if heading_index is None:
        contents.append({"prueba": test})
        return

    contents.insert(section_end_index(contents, heading_index), {"prueba": test})


def insert_table(chapter: dict[str, Any], table: dict[str, Any],
                 heading_index: int | None, after_index: int | None = None) -> int:
    """Inserta una tabla al final de una sección, tras un elemento o al final; devuelve su índice."""
    contents = chapter["data"]["contenido"]
    if after_index is not None:
        if not 0 <= after_index < len(contents):
            raise ValueError("La posición seleccionada ya no existe.")
        position = after_index + 1
    elif heading_index is None:
        position = len(contents)
    else:
        position = section_end_index(contents, heading_index)
    contents.insert(position, {"tabla": table})
    return position


def element_level(element: Any) -> int | None:
    """Nivel de encabezado de una sección o prueba; None si no es ninguna."""
    if not isinstance(element, dict):
        return None
    if isinstance(element.get("seccion"), str):
        return normalize_level(element.get("nivel"), 2)
    if isinstance(element.get("prueba"), dict):
        return normalize_level(element["prueba"].get("nivel"), 3)
    return None


def section_end_index(contents: list[Any], heading_index: int) -> int:
    """Índice donde termina el bloque de una sección (exclusivo).

    El bloque incluye el encabezado y todo lo que cuelga de él hasta la
    siguiente sección o prueba de nivel igual o superior.
    """
    heading = contents[heading_index]
    if not isinstance(heading, dict) or not isinstance(heading.get("seccion"), str):
        raise ValueError("La posición seleccionada ya no corresponde a una sección.")
    heading_level = normalize_level(heading.get("nivel"), 2)
    end = heading_index + 1
    while end < len(contents):
        level = element_level(contents[end])
        if level is not None and level <= heading_level:
            break
        end += 1
    return end


def block_range(contents: list[Any], index: int) -> tuple[int, int]:
    """Rango [inicio, fin) que se mueve junto con el elemento `index`."""
    if 0 <= index < len(contents) and is_table(contents[index]):
        return index, index + 1
    if index < 0 or index >= len(contents) or element_level(contents[index]) is None:
        raise ValueError("La posición seleccionada ya no es una sección ni una prueba.")
    if isinstance(contents[index].get("seccion"), str):
        return index, section_end_index(contents, index)
    return index, index + 1


def _set_level(element: dict[str, Any], level: int) -> None:
    target = element["prueba"] if isinstance(element.get("prueba"), dict) else element
    target["nivel"] = level


def move_block(
    chapter: dict[str, Any],
    index: int,
    target_index: int,
    position: str,
) -> int:
    """Mueve una prueba o una sección (con su contenido) junto a otro elemento.

    `position` puede ser "antes", "despues" o "dentro" (solo si el destino es
    una sección: se añade al final de ella). El nivel del elemento movido se
    ajusta al nuevo lugar y el de sus descendientes, en la misma medida.
    Devuelve el nuevo índice del elemento movido.
    """
    contents = chapter["data"]["contenido"]
    if position not in ("antes", "despues", "dentro"):
        raise ValueError(f"Posición no válida: {position}")
    start, end = block_range(contents, index)
    if target_index < 0 or target_index >= len(contents):
        raise ValueError("El destino ya no existe.")
    target_level = element_level(contents[target_index])
    if target_level is None and is_table(contents[target_index]):
        target_level = table_level(contents, target_index)
    if target_level is None:
        raise ValueError("El destino no es una sección, una prueba ni una tabla.")
    if start <= target_index < end:
        raise ValueError("No se puede mover un elemento dentro de sí mismo.")
    target_is_section = isinstance(contents[target_index].get("seccion"), str)
    if position == "dentro" and not target_is_section:
        raise ValueError("Solo se puede mover dentro de una sección.")

    # Una tabla no tiene nivel: se mueve sin tocar niveles.
    old_level = element_level(contents[index])
    if position == "antes":
        new_level = target_level
        insert_at = target_index
    elif position == "despues":
        new_level = target_level
        insert_at = (
            section_end_index(contents, target_index) if target_is_section else target_index + 1
        )
    else:
        new_level = target_level + 1
        insert_at = section_end_index(contents, target_index)

    delta = new_level - old_level if old_level is not None else 0
    block_levels = [element_level(contents[i]) for i in range(start, end)]
    if any(level is not None and not 1 <= level + delta <= 6 for level in block_levels):
        raise ValueError(
            "El movimiento dejaría algún nivel fuera del rango 1-6. "
            "Elige otro destino."
        )

    block = [contents[i] for i in range(start, end)]
    for element, level in zip(block, block_levels):
        if delta and level is not None:
            _set_level(element, level + delta)
    if insert_at > start:
        insert_at -= end - start
    del contents[start:end]
    for offset, element in enumerate(block):
        contents.insert(insert_at + offset, element)
    return insert_at


def insert_section_after_test(
    chapter: dict[str, Any],
    section_name: str,
    test_index: int,
) -> None:
    contents = chapter["data"]["contenido"]
    if (
        test_index < 0
        or test_index >= len(contents)
        or not isinstance(contents[test_index], dict)
        or not isinstance(contents[test_index].get("prueba"), dict)
    ):
        raise ValueError("La posición seleccionada ya no corresponde a una prueba.")
    if not section_name.strip():
        raise ValueError("El nombre de la sección es obligatorio.")
    test = contents[test_index]["prueba"]
    level = normalize_level(test.get("nivel"), 3)
    if level >= 6:
        raise ValueError(
            "No se puede crear una sección para una prueba con nivel 6."
        )
    contents.insert(
        test_index + 1,
        {"seccion": section_name.strip(), "nivel": level},
    )


def delete_test(chapter: dict[str, Any], test_index: int) -> None:
    contents = chapter["data"]["contenido"]
    if (
        test_index < 0
        or test_index >= len(contents)
        or not isinstance(contents[test_index], dict)
        or not isinstance(contents[test_index].get("prueba"), dict)
    ):
        raise ValueError("La posición seleccionada ya no corresponde a una prueba.")
    del contents[test_index]


def delete_section(chapter: dict[str, Any], section_index: int) -> None:
    contents = chapter["data"]["contenido"]
    if (
        section_index < 0
        or section_index >= len(contents)
        or not isinstance(contents[section_index], dict)
        or not isinstance(contents[section_index].get("seccion"), str)
    ):
        raise ValueError("La posición seleccionada ya no corresponde a una sección.")

    section = contents[section_index]
    section_level = normalize_level(section.get("nivel"), 2)
    section_context = section.get("contexto") or []
    context_nodes = [
        {"texto": item}
        for item in section_context
    ] if isinstance(section_context, list) else [{"texto": section_context}]
    for element in contents[section_index + 1:]:
        if not isinstance(element, dict):
            continue
        if isinstance(element.get("seccion"), str):
            level = normalize_level(element.get("nivel"), 2)
            if level <= section_level:
                break
            element["nivel"] = max(1, level - 1)
        elif isinstance(element.get("prueba"), dict):
            test = element["prueba"]
            level = normalize_level(test.get("nivel"), 3)
            if level > section_level:
                test["nivel"] = max(1, level - 1)
    contents[section_index:section_index + 1] = context_nodes


def save_chapter(chapter: dict[str, Any]) -> None:
    path: Path = chapter["path"]
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temp_path = Path(temporary.name)
            roundtrip_yaml().dump(chapter["data"], temporary)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def save_uploaded_images(uploaded_files: list[Any], image_dir: Path) -> list[str]:
    if not uploaded_files:
        return []
    image_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    existing = list(image_dir.iterdir())
    next_number = max(
        (
            int(match.group(1))
            for path in existing
            if (match := re.fullmatch(r"imagen_(\d+)\.[^.]+", path.name))
        ),
        default=0,
    ) + 1
    for uploaded in uploaded_files:
        extension = Path(uploaded.name).suffix.lower()
        if extension not in ALLOWED_IMAGE_EXTENSIONS:
            raise ValueError(f"Formato de imagen no admitido: {uploaded.name}")
        filename = f"imagen_{next_number:03d}{extension}"
        destination = image_dir / filename
        destination.write_bytes(uploaded.getvalue())
        paths.append(f"{image_dir.name}/{filename}")
        next_number += 1
    return paths


DEFAULT_TEST: dict[str, Any] = {
    "nombre": "",
    "nivel": 3,
    "id": "",
    "titulo": "",
    "descripcion": "",
    "componente": "",
    "plataforma": "",
    "situacion_inicial": [],
    "pasos": [],
    "situacion_final": [],
    "automatizable": "",
    "criticidad": "",
    "entorno": "",
    "referencia": "",
    "fecha": "",
    "version": "",
    "etiquetas": [],
    "contexto": [],
    "campos_adicionales": {},
    "imagenes": [],
}
