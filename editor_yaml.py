#!/usr/bin/env python3
"""Local Streamlit editor for the chapter and test YAML files."""
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


class LocalImageUpload:
    def __init__(self, path: Path) -> None:
        self.name = path.name
        self.path = path

    def getvalue(self) -> bytes:
        return self.path.read_bytes()


class TestForm:
    def __init__(self, parent: ttk.Frame) -> None:
        self.selected_images: list[Path] = []
        self.entries: dict[str, ttk.Entry | ttk.Spinbox | ttk.Combobox] = {}
        self.texts: dict[str, tk.Text] = {}

        canvas = tk.Canvas(parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self.canvas = canvas
        self.content = ttk.Frame(canvas, padding=12)
        self.canvas_window = canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.content.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(self.canvas_window, width=event.width),
        )

        fields_frame = ttk.LabelFrame(self.content, text="Datos de la prueba", padding=8)
        fields_frame.pack(fill="x", pady=(0, 10))
        fields_frame.columnconfigure(1, weight=1)
        fields_frame.columnconfigure(3, weight=1)
        for position, (field, label) in enumerate(TEXT_FIELDS.items()):
            row = position // 2
            column = (position % 2) * 2
            ttk.Label(fields_frame, text=label).grid(
                row=row, column=column, sticky="w", padx=(4, 8), pady=4
            )
            entry = ttk.Entry(fields_frame)
            entry.grid(row=row, column=column + 1, sticky="ew", padx=(0, 12), pady=4)
            self.entries[field] = entry

        row = (len(TEXT_FIELDS) + 1) // 2
        ttk.Label(fields_frame, text="Nivel (calculado)").grid(
            row=row, column=0, sticky="w", padx=4, pady=4
        )
        self.level_spinbox = ttk.Spinbox(
            fields_frame, from_=1, to=6, width=6, state="readonly"
        )
        self.level_spinbox.grid(row=row, column=1, sticky="w", pady=4)
        self.entries["nivel"] = self.level_spinbox
        ttk.Label(fields_frame, text="Automatizable").grid(
            row=row, column=2, sticky="w", padx=(4, 8), pady=4
        )
        self.entries["automatizable"] = ttk.Combobox(
            fields_frame,
            values=("", "si", "no", "corto", "medio", "largo", "hecho"),
            state="readonly",
            width=14,
        )
        self.entries["automatizable"].grid(row=row, column=3, sticky="w", pady=4)

        description_frame = ttk.LabelFrame(self.content, text="Descripción", padding=8)
        description_frame.pack(fill="x", pady=(0, 10))
        self.texts["descripcion"] = self._add_text(description_frame, height=4)

        for field, label in YAML_FIELDS.items():
            frame = ttk.LabelFrame(self.content, text=label, padding=8)
            frame.pack(fill="x", pady=(0, 10))
            self.texts[field] = self._add_text(frame, height=5 if field != "pasos" else 8)

        images_frame = ttk.LabelFrame(
            self.content,
            text="Imágenes asociadas (una ruta relativa por línea)",
            padding=8,
        )
        images_frame.pack(fill="x", pady=(0, 10))
        self.texts["imagenes"] = self._add_text(images_frame, height=4)
        ttk.Button(
            images_frame,
            text="Añadir imágenes…",
            command=self.choose_images,
        ).pack(anchor="w", pady=(6, 0))
        self.image_status = ttk.Label(images_frame, text="")
        self.image_status.pack(anchor="w")

    @staticmethod
    def _add_text(parent: ttk.Frame, height: int) -> tk.Text:
        widget = tk.Text(parent, height=height, wrap="word", undo=True)
        widget.pack(fill="x", expand=True)
        return widget

    def choose_images(self) -> None:
        file_types = [
            (f"{extension[1:].upper()} images", f"*{extension}")
            for extension in sorted(ALLOWED_IMAGE_EXTENSIONS)
        ]
        selected = filedialog.askopenfilenames(
            title="Seleccionar imágenes",
            filetypes=[("Imágenes admitidas", " ".join(item[1] for item in file_types)), *file_types],
        )
        self.selected_images.extend(Path(path) for path in selected)
        self.image_status.configure(
            text=f"{len(self.selected_images)} imagen(es) nueva(s) seleccionada(s)"
            if self.selected_images
            else ""
        )

    def set_test(self, test: dict[str, Any] | None, suggested_level: int = 3) -> None:
        original = {**DEFAULT_TEST, **(test or {})}
        for field, widget in self.entries.items():
            value = original.get(field, "")
            if field == "nivel":
                self.level_spinbox.set(str(normalize_level(value, suggested_level)))
                continue
            elif field == "automatizable":
                value = str(value or "").lower()
            widget.delete(0, "end")
            widget.insert(0, str(value))
        for field, widget in self.texts.items():
            if field in YAML_FIELDS:
                value = original.get(field) or ({} if field == "campos_adicionales" else [])
                serialized = yaml_to_string(value)
            elif field == "imagenes":
                serialized = "\n".join(str(path) for path in original.get(field, []))
            else:
                serialized = str(original.get(field, "") or "")
            widget.delete("1.0", "end")
            widget.insert("1.0", serialized)
        self.selected_images.clear()
        self.image_status.configure(text="")

    def get_values(self) -> dict[str, Any]:
        fields = {
            field: widget.get().strip()
            for field, widget in self.entries.items()
            if field != "nivel" and field != "automatizable"
        }
        fields["automatizable"] = self.entries["automatizable"].get()
        return make_test_from_form(
            {
                "fields": fields,
                "nombre": fields.pop("nombre"),
                "nivel": self.entries["nivel"].get(),
                **{
                    field: widget.get("1.0", "end-1c")
                    for field, widget in self.texts.items()
                },
            }
        )


class SectionForm:
    def __init__(self, parent: ttk.Frame) -> None:
        self.selected_images: list[Path] = []
        self.yaml_dir: Path | None = None
        self.preview_photos: list[ImageTk.PhotoImage] = []
        self._preview_after_id: str | None = None
        self.name = ttk.Entry(parent)
        self.context = tk.Text(parent, height=12, wrap="word", undo=True)
        parent.columnconfigure(1, weight=1)
        ttk.Label(parent, text="Nombre de la sección").grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=6
        )
        self.name.grid(row=0, column=1, sticky="ew", pady=6)
        ttk.Label(
            parent,
            text="Contexto (lista YAML; admite texto y mapas con texto/imagenes)",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(12, 4))
        self.context.grid(row=2, column=0, columnspan=2, sticky="nsew")
        parent.rowconfigure(2, weight=1)
        self.context.bind("<KeyRelease>", self._schedule_preview)
        ttk.Button(
            parent,
            text="Añadir imágenes al contexto…",
            command=self.choose_images,
        ).grid(row=3, column=0, sticky="w", pady=8)
        self.image_status = ttk.Label(parent, text="")
        self.image_status.grid(row=3, column=1, sticky="w", pady=8)
        preview_frame = ttk.LabelFrame(parent, text="Vista previa de imágenes", padding=6)
        preview_frame.grid(row=4, column=0, columnspan=2, sticky="nsew")
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)
        self.preview_canvas = tk.Canvas(
            preview_frame, height=220, highlightthickness=0
        )
        preview_scrollbar = ttk.Scrollbar(
            preview_frame, orient="vertical", command=self.preview_canvas.yview
        )
        self.preview_canvas.configure(yscrollcommand=preview_scrollbar.set)
        self.preview_canvas.grid(row=0, column=0, sticky="nsew")
        preview_scrollbar.grid(row=0, column=1, sticky="ns")
        self.preview_content = ttk.Frame(self.preview_canvas)
        self.preview_window = self.preview_canvas.create_window(
            (0, 0), window=self.preview_content, anchor="nw"
        )
        self.preview_content.bind(
            "<Configure>",
            lambda _event: self.preview_canvas.configure(
                scrollregion=self.preview_canvas.bbox("all")
            ),
        )
        self.preview_canvas.bind(
            "<Configure>",
            lambda event: self.preview_canvas.itemconfigure(
                self.preview_window, width=event.width
            ),
        )
        parent.rowconfigure(4, weight=1)

    def choose_images(self) -> None:
        extensions = sorted(ALLOWED_IMAGE_EXTENSIONS)
        selected = filedialog.askopenfilenames(
            title="Seleccionar imágenes para el contexto",
            filetypes=[
                ("Imágenes admitidas", " ".join(f"*{extension}" for extension in extensions)),
                *[(f"{extension[1:].upper()} images", f"*{extension}") for extension in extensions],
            ],
        )
        self.selected_images.extend(Path(path) for path in selected)
        self.image_status.configure(
            text=f"{len(self.selected_images)} imagen(es) nueva(s) seleccionada(s)"
            if self.selected_images
            else ""
        )
        self.refresh_image_previews()

    def set_section(
        self,
        section: dict[str, Any] | None = None,
        yaml_dir: Path | None = None,
    ) -> None:
        self.yaml_dir = yaml_dir
        self.name.delete(0, "end")
        self.name.insert(0, str((section or {}).get("seccion", "")))
        context = (section or {}).get("contexto") or []
        self.context.delete("1.0", "end")
        self.context.insert("1.0", yaml_to_string(context))
        self.selected_images.clear()
        self.image_status.configure(text="")
        self.refresh_image_previews()

    def _schedule_preview(self, _event: tk.Event[Any] | None = None) -> None:
        if self._preview_after_id is not None:
            self.context.after_cancel(self._preview_after_id)
        self._preview_after_id = self.context.after(300, self.refresh_image_previews)

    def refresh_image_previews(self) -> None:
        self._preview_after_id = None
        for child in self.preview_content.winfo_children():
            child.destroy()
        self.preview_photos.clear()

        try:
            context = roundtrip_yaml().load(self.context.get("1.0", "end-1c")) or []
        except YAMLError as error:
            ttk.Label(
                self.preview_content,
                text=f"No se pueden cargar las vistas previas: contexto YAML no válido ({error})",
                wraplength=700,
            ).grid(row=0, column=0, sticky="w", padx=6, pady=6)
            return

        image_sources: list[tuple[Path, str]] = []
        if self.yaml_dir is not None:
            image_sources.extend(
                (
                    path if Path(path).is_absolute() else self.yaml_dir / path,
                    path,
                )
                for path in context_image_paths(context)
            )
        image_sources.extend(
            (path, f"Nueva imagen: {path.name}") for path in self.selected_images
        )

        if not image_sources:
            ttk.Label(
                self.preview_content,
                text="No hay imágenes en el contexto.",
            ).grid(row=0, column=0, sticky="w", padx=6, pady=6)
            return

        for row, (path, label) in enumerate(image_sources):
            if not path.is_file():
                ttk.Label(
                    self.preview_content,
                    text=f"No se encuentra la imagen «{label}» ({path})",
                    wraplength=700,
                ).grid(row=row, column=0, sticky="w", padx=6, pady=6)
                continue
            try:
                with Image.open(path) as source:
                    image = source.convert("RGBA")
                    image.thumbnail((360, 180))
                    photo = ImageTk.PhotoImage(image, master=self.preview_canvas)
            except OSError as error:
                ttk.Label(
                    self.preview_content,
                    text=f"No se pudo abrir «{label}»: {error}",
                    wraplength=700,
                ).grid(row=row, column=0, sticky="w", padx=6, pady=6)
                continue
            self.preview_photos.append(photo)
            item_frame = ttk.Frame(self.preview_content)
            item_frame.grid(row=row, column=0, sticky="ew", padx=6, pady=6)
            ttk.Label(item_frame, image=photo).pack(side="left", padx=(0, 8))
            ttk.Label(item_frame, text=label, wraplength=450).pack(
                side="left", anchor="n"
            )

    def get_values(self, yaml_dir: Path) -> dict[str, Any]:
        section = make_section_from_form(
            self.name.get(),
            self.context.get("1.0", "end-1c"),
        )
        if self.selected_images:
            image_paths = save_uploaded_images(
                [LocalImageUpload(path) for path in self.selected_images],
                yaml_dir / "imagenes",
            )
            section["contexto"].append({"texto": "", "imagenes": image_paths})
        return section


class YamlTestEditor:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Editor de pruebas YAML")
        self.root.geometry("1280x900")
        self.root.minsize(900, 650)
        self.yaml_dir = Path("ejemplos/yaml").expanduser().resolve()
        self.chapters: list[dict[str, Any]] = []
        self.tree_items: dict[str, int] = {}
        self.tree_sections: dict[str, int] = {}
        self.open_sections: dict[tuple[Path, int], bool] = {}
        self.tree_chapter_path: Path | None = None

        self._build_window()
        self._load_chapters()

    def _build_window(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        path_frame = ttk.Frame(self.root, padding=10)
        path_frame.grid(row=0, column=0, sticky="ew")
        path_frame.columnconfigure(1, weight=1)
        ttk.Label(path_frame, text="Carpeta de YAML").grid(row=0, column=0, padx=(0, 8))
        self.path_var = tk.StringVar(value=str(self.yaml_dir))
        ttk.Entry(path_frame, textvariable=self.path_var).grid(row=0, column=1, sticky="ew")
        ttk.Button(path_frame, text="Examinar…", command=self._browse_directory).grid(
            row=0, column=2, padx=(8, 0)
        )
        ttk.Button(path_frame, text="Cargar", command=self._load_chapters).grid(
            row=0, column=3, padx=(8, 0)
        )

        body = ttk.Panedwindow(self.root, orient="horizontal")
        body.grid(row=1, column=0, sticky="nsew")
        sidebar = ttk.Frame(body, padding=10)
        editor = ttk.Frame(body, padding=(0, 10, 10, 10))
        body.add(sidebar, weight=1)
        body.add(editor, weight=4)
        sidebar.rowconfigure(4, weight=1)
        sidebar.columnconfigure(0, weight=1)

        ttk.Label(sidebar, text="Capítulo").grid(row=0, column=0, sticky="w")
        self.chapter_combo = ttk.Combobox(sidebar, state="readonly")
        self.chapter_combo.grid(row=1, column=0, sticky="ew", pady=(4, 10))
        self.chapter_combo.bind("<<ComboboxSelected>>", self._chapter_changed)
        ttk.Label(sidebar, text="Buscar por ID o texto").grid(row=2, column=0, sticky="w")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_args: self._refresh_test_list())
        ttk.Entry(sidebar, textvariable=self.search_var).grid(
            row=3, column=0, sticky="ew", pady=(4, 6)
        )
        self.test_tree = ttk.Treeview(sidebar, show="tree", selectmode="browse")
        tree_scrollbar = ttk.Scrollbar(
            sidebar, orient="vertical", command=self.test_tree.yview
        )
        self.test_tree.configure(yscrollcommand=tree_scrollbar.set)
        self.test_tree.grid(row=4, column=0, sticky="nsew")
        tree_scrollbar.grid(row=4, column=1, sticky="ns")
        self.test_tree.bind("<<TreeviewSelect>>", self._navigation_selected)
        self.test_tree.bind("<<TreeviewOpen>>", self._section_toggle)
        self.test_tree.bind("<<TreeviewClose>>", self._section_toggle)

        editor.rowconfigure(0, weight=1)
        editor.columnconfigure(0, weight=1)
        self.notebook = ttk.Notebook(editor)
        self.notebook.grid(row=0, column=0, sticky="nsew")
        edit_tab = ttk.Frame(self.notebook)
        create_tab = ttk.Frame(self.notebook)
        section_tab = ttk.Frame(self.notebook, padding=16)
        edit_section_tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(edit_tab, text="Editar prueba")
        self.notebook.add(create_tab, text="Crear prueba")
        self.notebook.add(section_tab, text="Nueva sección")
        self.notebook.add(edit_section_tab, text="Editar sección")
        edit_tab.rowconfigure(0, weight=1)
        edit_tab.columnconfigure(0, weight=1)
        create_tab.rowconfigure(1, weight=1)
        create_tab.columnconfigure(0, weight=1)
        self.edit_form = TestForm(edit_tab)
        self.create_heading_var = tk.StringVar()
        heading_frame = ttk.Frame(create_tab, padding=(12, 8, 12, 0))
        heading_frame.grid(row=0, column=0, sticky="ew")
        heading_frame.columnconfigure(1, weight=1)
        ttk.Label(heading_frame, text="Posición de la nueva prueba").grid(
            row=0, column=0, sticky="w", padx=(0, 8)
        )
        self.heading_combo = ttk.Combobox(
            heading_frame, textvariable=self.create_heading_var, state="readonly"
        )
        self.heading_combo.grid(row=0, column=1, sticky="ew")
        self.create_form_frame = ttk.Frame(create_tab)
        self.create_form_frame.grid(row=1, column=0, sticky="nsew")
        self.create_form_frame.rowconfigure(0, weight=1)
        self.create_form_frame.columnconfigure(0, weight=1)
        self.create_form = TestForm(self.create_form_frame)
        self.heading_combo.bind("<<ComboboxSelected>>", self._heading_changed)
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.root.bind_all(sequence, self._on_mousewheel, add="+")

        edit_buttons = ttk.Frame(edit_tab, padding=(12, 0, 12, 12))
        edit_buttons.pack(side="bottom", fill="x")
        ttk.Button(
            edit_buttons,
            text="Borrar prueba",
            command=self._delete_selected_test,
        ).pack(side="left")
        ttk.Button(edit_buttons, text="Guardar cambios", command=self._save_edit).pack(
            side="right"
        )
        create_buttons = ttk.Frame(create_tab, padding=(12, 0, 12, 12))
        create_buttons.grid(row=2, column=0, sticky="ew")
        ttk.Button(create_buttons, text="Crear prueba", command=self._save_new).pack(
            side="right"
        )

        section_tab.columnconfigure(1, weight=1)
        ttk.Label(
            section_tab,
            text="La nueva sección se insertará justo después de la prueba seleccionada.",
            wraplength=600,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))
        ttk.Label(section_tab, text="Prueba seleccionada").grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=4
        )
        self.section_target_var = tk.StringVar(value="Selecciona una prueba en el navegador.")
        ttk.Label(
            section_tab,
            textvariable=self.section_target_var,
            wraplength=600,
        ).grid(row=1, column=1, sticky="w", pady=4)
        ttk.Label(section_tab, text="Nombre de la sección").grid(
            row=2, column=0, sticky="w", padx=(0, 8), pady=4
        )
        self.new_section_var = tk.StringVar()
        ttk.Entry(section_tab, textvariable=self.new_section_var).grid(
            row=2, column=1, sticky="ew", pady=4
        )
        ttk.Button(
            section_tab,
            text="Crear sección",
            command=self._create_section,
        ).grid(row=3, column=1, sticky="e", pady=(12, 0))
        section_form_frame = ttk.Frame(edit_section_tab, padding=(0, 0, 0, 12))
        section_form_frame.pack(fill="both", expand=True)
        section_form_frame.rowconfigure(0, weight=1)
        section_form_frame.columnconfigure(0, weight=1)
        self.edit_section_form = SectionForm(section_form_frame)
        section_buttons = ttk.Frame(edit_section_tab)
        section_buttons.pack(fill="x")
        ttk.Button(
            section_buttons,
            text="Borrar sección",
            command=self._delete_selected_section,
        ).pack(side="left")
        ttk.Button(
            section_buttons,
            text="Guardar sección",
            command=self._save_selected_section,
        ).pack(side="right")

    def _on_mousewheel(self, event: tk.Event[Any]) -> str | None:
        target = self.root.winfo_containing(event.x_root, event.y_root)
        canvases = (
            self.edit_form.canvas,
            self.create_form.canvas,
            self.edit_section_form.preview_canvas,
        )
        while target is not None:
            if target in canvases:
                if getattr(event, "num", None) == 4:
                    direction = -1
                elif getattr(event, "num", None) == 5:
                    direction = 1
                else:
                    delta = getattr(event, "delta", 0)
                    direction = -1 if delta > 0 else 1
                target.yview_scroll(direction, "units")
                return "break"
            target = getattr(target, "master", None)
        return None

    def _browse_directory(self) -> None:
        selected = filedialog.askdirectory(
            title="Seleccionar carpeta de YAML",
            initialdir=self.path_var.get() or str(Path.cwd()),
        )
        if selected:
            self.path_var.set(selected)
            self._load_chapters()

    def _load_chapters(
        self,
        preferred_path: Path | None = None,
        preferred_test_id: str | None = None,
    ) -> None:
        yaml_dir = Path(self.path_var.get()).expanduser()
        if not yaml_dir.is_dir():
            messagebox.showerror(
                "Carpeta no válida",
                "Selecciona una carpeta existente con los capítulos YAML.",
                parent=self.root,
            )
            return
        try:
            chapters = read_chapters(yaml_dir)
        except (OSError, ValueError, YAMLError) as error:
            messagebox.showerror("No se pudieron cargar los capítulos", str(error), parent=self.root)
            return
        if not chapters:
            messagebox.showwarning("Sin capítulos", "No se encontraron capítulos YAML.", parent=self.root)
            return

        self.yaml_dir = yaml_dir.resolve()
        self.chapters = chapters
        labels = [
            f"{chapter['data'].get('capitulo') or chapter['path'].name} "
            f"({len(tests_in_chapter(chapter))} pruebas)"
            for chapter in chapters
        ]
        self.chapter_combo.configure(values=labels)
        chapter_index = next(
            (
                index for index, chapter in enumerate(chapters)
                if preferred_path is not None and chapter["path"] == preferred_path
            ),
            0,
        )
        self.chapter_combo.current(chapter_index)
        self._refresh_heading_options()
        self._refresh_test_list(preferred_test_id)

    def _current_chapter(self) -> dict[str, Any] | None:
        index = self.chapter_combo.current()
        return self.chapters[index] if 0 <= index < len(self.chapters) else None

    def _chapter_changed(self, _event: tk.Event[Any] | None = None) -> None:
        self._refresh_heading_options()
        self._refresh_test_list()

    def _refresh_heading_options(self, reset_form: bool = True) -> None:
        chapter = self._current_chapter()
        headings = headings_in_chapter(chapter) if chapter else []
        self.heading_options: list[tuple[str, int | None, int | None]] = [
            ("end", None, None),
            *(("section", index, level) for index, _title, level in headings),
        ]
        labels = ["Al final del capítulo"] + [
            f"{'  ' * max(0, level - 2)}{title}"
            for _index, title, level in headings
        ]
        self.heading_combo.configure(values=labels)
        self.heading_combo.current(0)
        if reset_form:
            self.create_form.set_test(None)

    def _heading_changed(self, _event: tk.Event[Any] | None = None) -> None:
        kind, _index, level = self.heading_options[self.heading_combo.current()]
        if kind in ("section", "new_section") and level:
            suggested_level = min(level + 1, 6)
        elif kind == "after_test" and level:
            suggested_level = level
        else:
            suggested_level = 3
        self.create_form.level_spinbox.set(str(suggested_level))

    def _refresh_test_list(self, preferred_test_id: str | None = None) -> None:
        chapter = self._current_chapter()
        for item_id in self.test_tree.get_children(""):
            self.test_tree.delete(item_id)
        self.tree_items.clear()
        self.tree_sections.clear()
        if chapter is None:
            self.tree_chapter_path = None
            self.edit_form.set_test(None)
            self._refresh_heading_options()
            return

        chapter_path = chapter["path"]
        query = self.search_var.get().casefold()
        entries = navigation_entries(chapter, query)
        selected_item = None
        for kind, index, label, parent_index, _ in entries:
            item_id = f"{'section' if kind == 'section' else 'test'}-{index}"
            parent_id = f"section-{parent_index}" if parent_index is not None else ""
            if kind == "section":
                is_open = self.open_sections.get((chapter_path, index), True)
                if query:
                    is_open = True
                self.test_tree.insert(
                    parent_id,
                    "end",
                    iid=item_id,
                    text=label,
                    open=is_open,
                    tags=("section",),
                )
                self.tree_sections[item_id] = index
            else:
                self.test_tree.insert(parent_id, "end", iid=item_id, text=label, tags=("test",))
                self.tree_items[item_id] = index
                test = chapter["data"]["contenido"][index]["prueba"]
                if preferred_test_id is not None and test.get("id") == preferred_test_id:
                    selected_item = item_id

        self.tree_chapter_path = chapter_path
        if selected_item is not None:
            parent_id = self.test_tree.parent(selected_item)
            while parent_id:
                self.test_tree.item(parent_id, open=True)
                parent_id = self.test_tree.parent(parent_id)
            self.test_tree.selection_set(selected_item)
            self.test_tree.focus(selected_item)
            self.test_tree.see(selected_item)
            self._navigation_selected()
        else:
            self.edit_form.set_test(None)
            self._refresh_heading_options(reset_form=False)
            self.section_target_var.set("Selecciona una prueba en el navegador.")

    def _section_toggle(self, event: tk.Event[Any]) -> None:
        if self.search_var.get() or self.tree_chapter_path is None:
            return
        item_id = event.widget.focus()
        if item_id.startswith("section-"):
            content_index = int(item_id.removeprefix("section-"))
            chapter_path = self.tree_chapter_path
            event.widget.after_idle(
                lambda: self.open_sections.__setitem__(
                    (chapter_path, content_index),
                    bool(event.widget.item(item_id, "open")),
                )
            )

    def _navigation_selected(self, _event: tk.Event[Any] | None = None) -> None:
        selection = self.test_tree.selection()
        if not selection:
            return
        chapter = self._current_chapter()
        item_id = selection[0]
        if chapter is None:
            return
        if item_id in self.tree_items:
            index = self.tree_items[item_id]
            test = chapter["data"]["contenido"][index]["prueba"]
            self.edit_form.set_test(test)
            self.notebook.select(0)
            self.section_target_var.set(
                f"{test.get('id') or '(sin ID)'} — "
                f"{test.get('titulo') or test.get('nombre') or '(sin título)'}"
            )
            headings = headings_in_chapter(chapter)
            after_label = (
                f"Después de {test.get('id') or '(sin ID)'} — "
                f"{test.get('titulo') or test.get('nombre') or '(sin título)'}"
            )
            test_level = normalize_level(test.get("nivel"), 3)
            options: list[tuple[str, int | None, int | None]] = [
                ("after_test", index, test_level),
                ("end", None, None),
                *(("section", heading_index, level) for heading_index, _title, level in headings),
            ]
            labels = [
                after_label,
                "Al final del capítulo",
            ]
            labels.extend(
                f"{'  ' * max(0, level - 2)}{title}"
                for _heading_index, title, level in headings
            )
            self.heading_options = options
            self.heading_combo.configure(values=labels)
            self.heading_combo.current(1 if test_level < 6 else 0)
            self._heading_changed()
        elif item_id in self.tree_sections:
            index = self.tree_sections[item_id]
            section = chapter["data"]["contenido"][index]
            self.edit_section_form.set_section(section, self.yaml_dir)
            self.notebook.select(3)

    def _save_form(self, form: TestForm, creating: bool) -> None:
        chapter = self._current_chapter()
        if chapter is None:
            messagebox.showerror("Sin capítulo", "Selecciona un capítulo.", parent=self.root)
            return
        try:
            updated = form.get_values()
            selected_index = None
            if not creating:
                selection = self.test_tree.selection()
                if not selection or selection[0] not in self.tree_items:
                    messagebox.showerror(
                        "Sin prueba seleccionada",
                        "Selecciona una prueba antes de guardar.",
                        parent=self.root,
                    )
                    return
                selected_index = self.tree_items[selection[0]]
            duplicate = find_duplicate_id(
                self.chapters,
                updated["id"],
                None if creating else (chapter["path"], selected_index),
            )
            if duplicate:
                messagebox.showerror("ID no válido", duplicate, parent=self.root)
                return

            kind = "edit"
            position = None
            if creating:
                kind, position, _level = self.heading_options[self.heading_combo.current()]
            uploads = [LocalImageUpload(path) for path in form.selected_images]
            updated["imagenes"].extend(
                save_uploaded_images(uploads, self.yaml_dir / "imagenes")
            )
            if creating:
                insert_test(
                    chapter,
                    updated,
                    position if kind == "section" else None,
                    after_test_index=position if kind == "after_test" else None,
                )
            else:
                chapter["data"]["contenido"][selected_index]["prueba"].update(updated)
            save_chapter(chapter)
        except (OSError, ValueError, YAMLError) as error:
            messagebox.showerror("No se pudo guardar", str(error), parent=self.root)
            return

        self.search_var.set("")
        self._load_chapters(chapter["path"], updated["id"])
        messagebox.showinfo(
            "Prueba guardada",
            "La prueba se ha guardado directamente en el YAML del capítulo.",
            parent=self.root,
        )
        if creating:
            self.notebook.select(0)

    def _save_edit(self) -> None:
        self._save_form(self.edit_form, creating=False)

    def _save_new(self) -> None:
        self._save_form(self.create_form, creating=True)

    def _selected_navigation_item(self) -> tuple[str, int] | None:
        selection = self.test_tree.selection()
        if not selection:
            return None
        item_id = selection[0]
        if item_id in self.tree_items:
            return "test", self.tree_items[item_id]
        if item_id in self.tree_sections:
            return "section", self.tree_sections[item_id]
        return None

    def _delete_selected_test(self) -> None:
        chapter = self._current_chapter()
        selected = self._selected_navigation_item()
        if chapter is None or selected is None or selected[0] != "test":
            messagebox.showerror(
                "Sin prueba seleccionada",
                "Selecciona una prueba en el navegador.",
                parent=self.root,
            )
            return
        index = selected[1]
        test = chapter["data"]["contenido"][index]["prueba"]
        test_label = f"{test.get('id') or '(sin ID)'} — {test.get('titulo') or test.get('nombre', '')}"
        if not messagebox.askyesno(
            "Borrar prueba",
            f"¿Quieres borrar esta prueba?\n\n{test_label}",
            parent=self.root,
        ):
            return
        try:
            delete_test(chapter, index)
            save_chapter(chapter)
        except (OSError, ValueError, YAMLError) as error:
            self._load_chapters(chapter["path"])
            messagebox.showerror("No se pudo borrar la prueba", str(error), parent=self.root)
            return
        self.search_var.set("")
        self._load_chapters(chapter["path"])

    def _save_selected_section(self) -> None:
        chapter = self._current_chapter()
        selected = self._selected_navigation_item()
        if chapter is None or selected is None or selected[0] != "section":
            messagebox.showerror(
                "Sin sección seleccionada",
                "Selecciona una sección en el navegador.",
                parent=self.root,
            )
            return
        index = selected[1]
        try:
            updated = self.edit_section_form.get_values(self.yaml_dir)
            chapter["data"]["contenido"][index].update(updated)
            save_chapter(chapter)
        except (OSError, ValueError, YAMLError) as error:
            self._load_chapters(chapter["path"])
            messagebox.showerror("No se pudo guardar la sección", str(error), parent=self.root)
            return
        section_name = updated["seccion"]
        self.search_var.set("")
        self._load_chapters(chapter["path"])
        self._select_section_by_name(section_name)
        messagebox.showinfo(
            "Sección guardada",
            "La información de la sección se ha guardado en el YAML.",
            parent=self.root,
        )

    def _select_section_by_name(self, section_name: str) -> None:
        chapter = self._current_chapter()
        if chapter is None:
            return
        section_index = next(
            (
                index
                for index, element in enumerate(chapter["data"]["contenido"])
                if isinstance(element, dict) and element.get("seccion") == section_name
            ),
            None,
        )
        if section_index is not None:
            item_id = f"section-{section_index}"
            self.test_tree.selection_set(item_id)
            self.test_tree.focus(item_id)
            self._navigation_selected()

    def _delete_selected_section(self) -> None:
        chapter = self._current_chapter()
        selected = self._selected_navigation_item()
        if chapter is None or selected is None or selected[0] != "section":
            messagebox.showerror(
                "Sin sección seleccionada",
                "Selecciona una sección en el navegador.",
                parent=self.root,
            )
            return
        index = selected[1]
        section_name = chapter["data"]["contenido"][index]["seccion"]
        if not messagebox.askyesno(
            "Borrar sección",
            f"¿Quieres borrar el encabezado de la sección «{section_name}»?\n\n"
            "Las pruebas, subsecciones y su información se conservarán; "
            "el contenido se promocionará un nivel.",
            parent=self.root,
        ):
            return
        try:
            delete_section(chapter, index)
            save_chapter(chapter)
        except (OSError, ValueError, YAMLError) as error:
            self._load_chapters(chapter["path"])
            messagebox.showerror("No se pudo borrar la sección", str(error), parent=self.root)
            return
        self.search_var.set("")
        self._load_chapters(chapter["path"])

    def _create_section(self) -> None:
        chapter = self._current_chapter()
        selection = self.test_tree.selection()
        if chapter is None:
            messagebox.showerror("Sin capítulo", "Selecciona un capítulo.", parent=self.root)
            return
        if not selection or selection[0] not in self.tree_items:
            messagebox.showerror(
                "Sin prueba seleccionada",
                "Selecciona una prueba antes de crear la sección.",
                parent=self.root,
            )
            return

        test_index = self.tree_items[selection[0]]
        selected_test = chapter["data"]["contenido"][test_index]["prueba"]
        test_id = selected_test.get("id")
        try:
            insert_section_after_test(
                chapter,
                self.new_section_var.get(),
                test_index,
            )
            save_chapter(chapter)
        except (OSError, ValueError, YAMLError) as error:
            messagebox.showerror("No se pudo crear la sección", str(error), parent=self.root)
            return

        self.new_section_var.set("")
        self.search_var.set("")
        self._load_chapters(chapter["path"], test_id)
        messagebox.showinfo(
            "Sección creada",
            "La sección se ha guardado en el YAML. Ya puedes crear pruebas bajo ella.",
            parent=self.root,
        )


def main() -> None:
    root = tk.Tk()
    YamlTestEditor(root)
    root.mainloop()


if __name__ == "__main__":
    main()
