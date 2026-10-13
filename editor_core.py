#!/usr/bin/env python3
"""Core data and editing helpers for the local Tkinter YAML editor."""
from __future__ import annotations

import os
import re
import tempfile
from io import StringIO
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter as tk
from typing import Any

from PIL import Image, ImageTk
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError


TEST_FIELDS = (
    "id",
    "titulo",
    "descripcion",
    "componente",
    "plataforma",
    "situacion_inicial",
    "pasos",
    "situacion_final",
    "automatizable",
    "criticidad",
    "entorno",
    "referencia",
    "fecha",
    "version",
    "contexto",
    "campos_adicionales",
    "imagenes",
)
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


def context_image_paths(context: Any) -> list[str]:
    paths: list[str] = []

    def collect(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "imagenes":
                    image_values = child if isinstance(child, list) else [child]
                    paths.extend(
                        image.strip()
                        for image in image_values
                        if isinstance(image, str) and image.strip()
                    )
                else:
                    collect(child)
        elif isinstance(value, list):
            for item in value:
                collect(item)

    collect(context)
    return paths


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
            or (kind == "test" and matches)
            or (kind == "section" and index in matching_heading_ids)
        )
    ]


def make_test_from_form(values: dict[str, Any]) -> dict[str, Any]:
    test = dict(values["fields"])
    test["nombre"] = values["nombre"].strip()
    test["nivel"] = int(values["nivel"])
    for field in LIST_FIELDS:
        parsed = roundtrip_yaml().load(values[field]) or []
        if not isinstance(parsed, list):
            raise ValueError(f"'{field}' debe ser una lista YAML.")
        test[field] = parsed
    extras = roundtrip_yaml().load(values["campos_adicionales"]) or {}
    if not isinstance(extras, dict) or any(not isinstance(key, str) for key in extras):
        raise ValueError("'campos_adicionales' debe ser un mapa YAML con claves de texto.")
    test["campos_adicionales"] = extras
    test["imagenes"] = [line.strip() for line in values["imagenes"].splitlines() if line.strip()]
    for field in ("id", "titulo", "descripcion", "componente", "plataforma",
                  "automatizable", "criticidad", "entorno", "referencia", "fecha", "version"):
        test[field] = str(test.get(field, "") or "").strip()
    return test


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

    selected_heading = contents[heading_index]
    heading_level = int(selected_heading.get("nivel", 2))
    insert_at = heading_index + 1
    while insert_at < len(contents):
        element = contents[insert_at]
        if isinstance(element, dict):
            if "seccion" in element and normalize_level(element.get("nivel"), 2) <= heading_level:
                break
            existing_test = element.get("prueba")
            if (
                isinstance(existing_test, dict)
                and normalize_level(existing_test.get("nivel"), 3) <= heading_level
            ):
                break
        insert_at += 1
    contents.insert(insert_at, {"prueba": test})


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


def make_section_from_form(name: str, context_yaml: str) -> dict[str, Any]:
    section_name = name.strip()
    if not section_name:
        raise ValueError("El nombre de la sección es obligatorio.")
    context = roundtrip_yaml().load(context_yaml) or []
    if not isinstance(context, list):
        raise ValueError("'contexto' debe ser una lista YAML.")
    return {"seccion": section_name, "contexto": context}


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
    "contexto": [],
    "campos_adicionales": {},
    "imagenes": [],
}

TEXT_FIELDS = {
    "nombre": "Nombre / encabezado",
    "id": "ID *",
    "titulo": "Título",
    "componente": "Componente",
    "plataforma": "Plataforma",
    "criticidad": "Criticidad",
    "entorno": "Entorno",
    "referencia": "Referencia",
    "fecha": "Fecha",
    "version": "Versión",
}

YAML_FIELDS = {
    "situacion_inicial": "Situación inicial (YAML)",
    "pasos": "Pasos (YAML)",
    "situacion_final": "Situación final (YAML)",
    "contexto": "Contexto de la prueba (YAML)",
    "campos_adicionales": "Campos adicionales (YAML)",
}


