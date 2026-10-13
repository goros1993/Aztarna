#!/usr/bin/env python3
"""Local Streamlit editor for the chapter and test YAML files."""
from __future__ import annotations

import os
import re
import tempfile
from io import StringIO
from pathlib import Path
from typing import Any

import streamlit as st
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
                heading_index: int | None) -> None:
    contents = chapter["data"]["contenido"]
    if heading_index is None:
        contents.append({"prueba": test})
        return

    selected_heading = contents[heading_index]
    heading_level = int(selected_heading.get("nivel", 2))
    insert_at = heading_index + 1
    while insert_at < len(contents):
        element = contents[insert_at]
        if isinstance(element, dict) and "seccion" in element:
            if int(element.get("nivel", 2)) <= heading_level:
                break
        insert_at += 1
    contents.insert(insert_at, {"prueba": test})


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


def list_editor(label: str, value: Any, key: str) -> str:
    return st.text_area(
        label,
        value=yaml_to_string(value if isinstance(value, list) else []),
        key=key,
        height=120,
        help="Edita una lista YAML. Cada elemento suele ser una línea con guion; también puedes usar mapas con texto, nivel e imagenes.",
    )


def render_test_form(
    chapter: dict[str, Any],
    all_chapters: list[dict[str, Any]],
    test: dict[str, Any] | None,
    selected_index: int | None,
    form_key: str,
    yaml_dir: Path,
    add_heading_index: int | None = None,
    suggested_level: int = 3,
) -> None:
    creating = test is None
    original = test or {
        "nombre": "",
        "nivel": suggested_level,
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
    st.subheader("Nueva prueba" if creating else f"Editar: {original.get('id', '(sin ID)')}")
    with st.form(form_key, clear_on_submit=False):
        first, second = st.columns(2)
        with first:
            name = st.text_input("Nombre / encabezado", value=str(original.get("nombre", "")))
            test_id = st.text_input("ID *", value=str(original.get("id", "")))
            title = st.text_input("Título", value=str(original.get("titulo", "")))
            description = st.text_area("Descripción", value=str(original.get("descripcion", "")))
            component = st.text_input("Componente", value=str(original.get("componente", "")))
            platform = st.text_input("Plataforma", value=str(original.get("plataforma", "")))
        with second:
            level = st.number_input(
                "Nivel del encabezado",
                min_value=1,
                max_value=6,
                value=normalize_level(original.get("nivel"), suggested_level),
            )
            automatable = st.selectbox(
                "Automatizable",
                options=["", "si", "no", "corto", "medio", "largo", "hecho"],
                index=(
                    ["", "si", "no", "corto", "medio", "largo", "hecho"].index(
                        str(original.get("automatizable", "")).lower()
                    )
                    if str(original.get("automatizable", "")).lower()
                    in ["", "si", "no", "corto", "medio", "largo", "hecho"]
                    else 0
                ),
            )
            criticality = st.text_input("Criticidad", value=str(original.get("criticidad", "")))
            environment = st.text_input("Entorno", value=str(original.get("entorno", "")))
            reference = st.text_input("Referencia", value=str(original.get("referencia", "")))
            date = st.text_input("Fecha", value=str(original.get("fecha", "")))
            version = st.text_input("Versión", value=str(original.get("version", "")))

        initial = list_editor("Situación inicial", original.get("situacion_inicial"), f"{form_key}_initial")
        steps = list_editor("Pasos", original.get("pasos"), f"{form_key}_steps")
        final = list_editor("Situación final", original.get("situacion_final"), f"{form_key}_final")
        context = list_editor("Contexto de la prueba", original.get("contexto"), f"{form_key}_context")
        extra_fields = st.text_area(
            "Campos adicionales (YAML)",
            value=yaml_to_string(original.get("campos_adicionales") or {}),
            key=f"{form_key}_extras",
            height=120,
        )
        image_paths = st.text_area(
            "Imágenes asociadas (una ruta relativa por línea)",
            value="\n".join(str(path) for path in original.get("imagenes", [])),
            key=f"{form_key}_images",
            help="Las rutas son relativas a la carpeta YAML. Las nuevas imágenes cargadas se guardan en imagenes/.",
        )
        uploads = st.file_uploader(
            "Añadir imágenes a esta prueba",
            type=[extension.lstrip(".") for extension in sorted(ALLOWED_IMAGE_EXTENSIONS)],
            accept_multiple_files=True,
            key=f"{form_key}_upload",
            help="Se añadirán como imágenes asociadas a la tabla. Para vincularlas a un paso concreto, edita el mapa YAML del paso.",
        )
        submitted = st.form_submit_button("Crear prueba" if creating else "Guardar cambios", type="primary")

    if submitted:
        try:
            fields = {
                "id": test_id,
                "titulo": title,
                "descripcion": description,
                "componente": component,
                "plataforma": platform,
                "automatizable": automatable,
                "criticidad": criticality,
                "entorno": environment,
                "referencia": reference,
                "fecha": date,
                "version": version,
            }
            updated = make_test_from_form({
                "fields": fields,
                "nombre": name,
                "nivel": level,
                "situacion_inicial": initial,
                "pasos": steps,
                "situacion_final": final,
                "contexto": context,
                "campos_adicionales": extra_fields,
                "imagenes": image_paths,
            })
            error = find_duplicate_id(
                all_chapters,
                updated["id"],
                None if creating else (chapter["path"], selected_index),
            )
            if error:
                st.error(error)
                return

            new_images = save_uploaded_images(uploads, yaml_dir / "imagenes")
            updated["imagenes"].extend(new_images)
            if creating:
                insert_test(chapter, updated, add_heading_index)
            else:
                chapter["data"]["contenido"][selected_index]["prueba"].update(updated)
            save_chapter(chapter)
            st.success("Prueba guardada directamente en el YAML del capítulo.")
            st.rerun()
        except (OSError, ValueError, YAMLError) as error:
            st.error(f"No se pudo guardar: {error}")


def main() -> None:
    st.set_page_config(page_title="Editor de pruebas YAML", layout="wide")
    st.title("Editor de pruebas")
    st.caption("Edita los YAML directamente; no se utiliza una base de datos aparte.")

    yaml_dir_text = st.sidebar.text_input("Carpeta de YAML", value="ejemplos/yaml")
    yaml_dir = Path(yaml_dir_text).expanduser()
    if not yaml_dir.is_dir():
        st.info("Indica una carpeta existente que contenga indice.yaml y los capítulos YAML.")
        return

    try:
        chapters = read_chapters(yaml_dir)
    except (OSError, ValueError, YAMLError) as error:
        st.error(f"No se pudieron cargar los capítulos: {error}")
        return
    if not chapters:
        st.warning("No se encontraron capítulos YAML.")
        return

    chapter_labels = [
        f"{chapter['data'].get('capitulo') or chapter['path'].name} ({len(tests_in_chapter(chapter))} pruebas)"
        for chapter in chapters
    ]
    chapter_index = st.sidebar.selectbox(
        "Capítulo",
        range(len(chapters)),
        format_func=lambda index: chapter_labels[index],
    )
    chapter = chapters[chapter_index]
    entries = tests_in_chapter(chapter)
    query = st.sidebar.text_input("Buscar por ID, título o texto", value="").casefold()
    visible = [
        (index, test)
        for index, test in entries
        if not query
        or query in " ".join(str(value) for value in test.values()).casefold()
    ]
    if not visible:
        st.warning("No hay pruebas que coincidan con la búsqueda.")
        selected_entry = None
    else:
        selected_entry = st.sidebar.selectbox(
            f"Pruebas ({len(visible)})",
            [index for index, _ in visible],
            format_func=lambda content_index: (
                f"{chapter['data']['contenido'][content_index]['prueba'].get('id', '(sin ID)')} — "
                f"{chapter['data']['contenido'][content_index]['prueba'].get('titulo') or chapter['data']['contenido'][content_index]['prueba'].get('nombre', '')}"
            ),
            key=f"selected_test_{chapter_index}",
        )

    edit_tab, create_tab = st.tabs(["Editar prueba", "Crear prueba"])
    with edit_tab:
        if selected_entry is None:
            st.info("Selecciona una prueba en la barra lateral.")
        else:
            selected_index = selected_entry
            selected_test = chapter["data"]["contenido"][selected_index]["prueba"]
            render_test_form(
                chapter,
                chapters,
                selected_test,
                selected_index,
                f"edit_{chapter_index}_{selected_index}_{selected_test.get('id', '')}",
                yaml_dir,
            )

    with create_tab:
        headings = headings_in_chapter(chapter)
        heading_options: list[tuple[int, str, int] | None] = [None, *headings]
        heading_index = st.selectbox(
            "Añadir bajo esta sección",
            range(len(heading_options)),
            format_func=lambda option_index: (
                "Al final del capítulo"
                if heading_options[option_index] is None
                else (
                    f"{'  ' * max(0, heading_options[option_index][2] - 2)}"
                    f"{heading_options[option_index][1]}"
                )
            ),
        )
        selected_heading = heading_options[heading_index]
        suggested_level = min((selected_heading[2] + 1) if selected_heading else 3, 6)
        render_test_form(
            chapter,
            chapters,
            None,
            None,
            f"create_{chapter_index}_{selected_heading[0] if selected_heading else 'end'}",
            yaml_dir,
            add_heading_index=selected_heading[0] if selected_heading else None,
            suggested_level=suggested_level,
        )


if __name__ == "__main__":
    main()
