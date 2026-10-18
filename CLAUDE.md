# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Aztarna is a local desktop editor (pywebview + plain HTML/JS, no server, no Node build) for test cases and requirements stored as YAML, with traceability, test executions, version validations and Word/PDF reports. Everything — code identifiers, comments, docstrings, UI text, docs, commit messages — is written in **Spanish**; keep it that way. The user manual is `MANUAL.md` (also shown inside the app via `app/manual.py`), the backlog is `PENDIENTE.md`, release notes are `CHANGELOG.md`.

## Commands

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt   # Linux needs python3-gi + gir1.2-webkit2-4.1 (venv with --system-site-packages)
.venv/bin/python editor_web.py [carpeta] [--depurar]     # run the editor (--depurar = devtools)
.venv/bin/python herramientas.py <orden> --help          # CLI tools: importar, convertir, inventario, auditar, ids, word, informe, resultados, validacion, comparar, robot, trazabilidad
.venv/bin/python -m pytest -q                            # all tests (~30 s); unittest.TestCase classes, run with pytest as in Araudi (pytest.ini)
.venv/bin/python -m pytest tests/test_ejecucion.py::ApiTests::test_previsualizar_y_crear   # a single test
node --check web/js/<archivo>.js                         # only "lint" available for the JS
```

There is no linter/formatter configured. `construir_exe.bat` (Windows only) builds `dist\Aztarna.exe` + `dist\version.txt` with PyInstaller.

## Architecture

**Python ↔ UI bridge.** `editor_web.py` creates one pywebview window with `js_api=EditorImportacionApi`. The API is a single inheritance chain, each layer adding one area: `EditorApi` (`app/editor_api.py`: tests/requirements editing, validation panel, images, export) → `EditorEjecucionApi` (`ejecucion_api.py`) → `EditorValidacionApi` (`validacion_api.py`) → `EditorImportacionApi` (`importacion_api.py`). Every public method is wrapped with `@respuesta`, which serializes to `{"ok": bool, "datos"|"error"}` under a lock. In JS, `api` (a Proxy in `web/js/util.js`) unwraps that and throws on error; all state lives in the global `S` (`web/js/main.js`). JS files are plain scripts loaded in order by `web/index.html` and share globals.

**Core vs API.** `*_core.py` modules hold the logic with no UI (`editor_core`, `ejecucion_core`, `validacion_core`, `robot_core`, `trazabilidad`); the `*_api.py` classes only adapt it. CLI entry points are each module's `main(argv, prog)`, dispatched by `herramientas.py`.

**Single sources of truth** (change things only there):
- `app/esquema.py`: fields, labels, order and closed options of tests and requirements, plus migration of old Word formats. Maniobra/Entorno options are **per project**: `esquema.configurar(carpeta)` loads `aztarna.yaml` from the project (or loose tests folder) and mutates the module-level `OPCIONES_MULTIPLES`/`EQUIVALENCIAS` (global state; the editor calls it in `EditorApi._load`, tests must call it or copy the examples' `aztarna.yaml`).
- `app/__init__.py`: name and `__version__`.
- `app/formato.py`: data-format version (`formato.yaml` in data folders, `formato` key in `ejecucion.yaml`/`validacion.yaml`); newer data opens read-only.

**Data layout.** A project is `proyecto/{aztarna.yaml, pruebas/, requisitos/}`; each folder has `indice.yaml` + one YAML per chapter with an ordered `contenido` of sections, `prueba:`/`requisito:` items and context/tables. YAML is read/written with ruamel round-trip so comments and formatting survive (`editor_core.read_chapters`/`save_chapter`); `NOT_CHAPTERS` lists the non-chapter files. The only test→requirement link is each test's `requisitos` list.

**Executions and validations** live outside the tests repo (shared folder). An execution (`ejecucion.yaml` + `resultados.yaml` + `evidencias/`) stores the tests' IDs and a content *huella* (hash) rather than copies, plus relative and absolute paths to the tests folder; on close it freezes a copy in `pruebas_congeladas/` (with `aztarna.yaml`). Per-PC relocation of the tests folder is kept in the PC settings (`app/ajustes.py`, key `pruebas_de_ejecuciones`), never written back to `ejecucion.yaml`, because each person works on their own Git clone at a different path. If the tests are in Git, executions record commit/tag (`app/git_pruebas.py`). A validation (`validacion.yaml`) points to executions and consolidates per test × environment (`validacion_core.consolidar`, cached reads via `app/lectura.py`). Old folders named `campaña.yaml` are still read ("campaña" was renamed to "ejecución" everywhere else).

## Things to keep in mind

- **The public repo must not contain company data**: no real option values (they go in each project's private `aztarna.yaml`), no real test IDs/names, no original Word documents (`*.docx` is gitignored except `plantillas/`). Examples in `ejemplos/` are fictitious (an invented elevator controller "DEMO-A1").
- If you change example tests in `ejemplos/yaml/pruebas`, the example executions' stored *huellas* go stale (`test_la_ejecucion_de_ejemplo_abre_sin_avisos` fails): recompute them in `ejemplos/ejecuciones/*/{ejecucion,resultados}.yaml`.
- Tests that touch PC settings must point `AZTARNA_AJUSTES` to a temp file (see `tests/test_ejecucion.py` `ApiTests.setUp`), or they write the real user settings.
- Manual screenshots (`docs/manual/*.png`) are produced by driving the real app with pywebview and a WebKit snapshot; update MANUAL/README/screenshots only right before pushing, not while iterating.
- Work on `main`; branch only for big features. Releases: bump `app/__init__.py`, add the `CHANGELOG.md` entry, tag `vX.Y.Z` and push the tag: `.github/workflows/exe.yml` builds the .exe on Windows (via `construir_exe.bat`), runs the tests there and publishes the Release (Aztarna.exe + version.txt, notes from the CHANGELOG entry); it fails if the tag ≠ `__version__` or the entry is missing. `ci.yml` runs the tests on every push to `main`/PR. After touching `construir_exe.bat`, run `exe.yml` by hand (workflow_dispatch).
