from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ruamel.yaml import YAML

import editor_core as editor_yaml  # el núcleo no depende de Tkinter


class EditorYamlTests(unittest.TestCase):
    def test_nivel_none_se_normaliza_sin_romper_el_formulario(self):
        self.assertEqual(editor_yaml.normalize_level(None), 3)
        self.assertEqual(editor_yaml.normalize_level(None, 4), 4)
        self.assertEqual(editor_yaml.normalize_level(12), 6)

    def test_make_test_from_form_parsea_listas_y_campos_adicionales(self):
        test = editor_yaml.make_test_from_form({
            "fields": {"id": "NUEVA", "titulo": "Título"},
            "nombre": "Encabezado",
            "nivel": 4,
            "situacion_inicial": "- sistema preparado",
            "pasos": "- ejecutar\n- comprobar",
            "situacion_final": "- sistema estable",
            "contexto": "- texto: Nota\n  nivel: 2",
            "campos_adicionales": "origen: formulario",
            "imagenes": "imagenes/a.png\nimagenes/b.png",
        })

        self.assertEqual(test["id"], "NUEVA")
        self.assertEqual(test["nivel"], 4)
        self.assertEqual(test["situacion_inicial"], ["sistema preparado"])
        self.assertEqual(test["pasos"], ["ejecutar", "comprobar"])
        self.assertEqual(test["contexto"], [{"texto": "Nota", "nivel": 2}])
        self.assertEqual(test["campos_adicionales"], {"origen": "formulario"})
        self.assertEqual(test["imagenes"], ["imagenes/a.png", "imagenes/b.png"])

    def test_make_test_from_form_rechaza_una_lista_no_valida(self):
        with self.assertRaisesRegex(ValueError, "debe ser una lista YAML"):
            editor_yaml.make_test_from_form({
                "fields": {"id": "NUEVA"},
                "nombre": "",
                "nivel": 3,
                "situacion_inicial": "no es lista",
                "pasos": "[]",
                "situacion_final": "[]",
                "contexto": "[]",
                "campos_adicionales": "{}",
                "imagenes": "",
            })

    def test_make_section_from_form_preserves_text_and_images_in_context(self):
        section = editor_yaml.make_section_from_form(
            "  Nueva sección  ",
            '- "Texto contextual"\n'
            '- texto: Captura\n'
            '  imagenes:\n'
            '  - imagenes/captura.png\n',
        )

        self.assertEqual(section["seccion"], "Nueva sección")
        self.assertEqual(
            section["contexto"],
            [
                "Texto contextual",
                {"texto": "Captura", "imagenes": ["imagenes/captura.png"]},
            ],
        )

    def test_make_section_from_form_rejects_non_list_context(self):
        with self.assertRaisesRegex(ValueError, "debe ser una lista YAML"):
            editor_yaml.make_section_from_form("Sección", "texto: valor")

    def test_context_image_paths_finds_paths_in_section_context(self):
        self.assertEqual(
            editor_yaml.context_image_paths([
                {"texto": "", "imagenes": ["imagenes/imagen_006.png"]},
                {
                    "texto": "Otra imagen",
                    "detalle": {"imagenes": "imagenes/imagen_007.jpg"},
                },
            ]),
            ["imagenes/imagen_006.png", "imagenes/imagen_007.jpg"],
        )

    def test_ejemplos_indexados_cargan_y_tienen_todas_sus_imagenes(self):
        yaml_dir = Path(__file__).parent / "ejemplos" / "yaml"
        chapters = editor_yaml.read_chapters(yaml_dir)

        self.assertIn(
            "Ejemplo de secciones e imágenes",
            [chapter["data"]["capitulo"] for chapter in chapters],
        )
        self.assertIn(
            "Ejemplo de edición y variantes",
            [chapter["data"]["capitulo"] for chapter in chapters],
        )
        for chapter in chapters:
            for element in chapter["data"]["contenido"]:
                image_paths = editor_yaml.context_image_paths(element)
                for image_path in image_paths:
                    self.assertTrue(
                        (yaml_dir / image_path).is_file(),
                        f"Falta la imagen de ejemplo {image_path}",
                    )

    def test_navigation_entries_preserves_section_hierarchy(self):
        chapter = {
            "data": {
                "contenido": [
                    {"seccion": "Operaciones", "nivel": 2},
                    {"prueba": {"id": "T-1", "titulo": "Arranque", "nivel": 3}},
                    {"seccion": "Arranque normal", "nivel": 3},
                    {"prueba": {"id": "T-2", "titulo": "Preparación", "nivel": 4}},
                    {"seccion": "Incidencias", "nivel": 2},
                    {"prueba": {"id": "T-3", "titulo": "Alarma", "nivel": 3}},
                ]
            }
        }

        entries = editor_yaml.navigation_entries(chapter)

        self.assertEqual(
            [(kind, index, parent) for kind, index, _label, parent, _level in entries],
            [
                ("section", 0, None),
                ("test", 1, 0),
                ("section", 2, 0),
                ("test", 3, 2),
                ("section", 4, None),
                ("test", 5, 4),
            ],
        )

    def test_navigation_search_keeps_matching_test_ancestors(self):
        chapter = {
            "data": {
                "contenido": [
                    {"seccion": "Operaciones", "nivel": 2},
                    {"prueba": {"id": "T-1", "titulo": "Arranque", "nivel": 3}},
                    {"seccion": "Arranque normal", "nivel": 3},
                    {"prueba": {"id": "T-2", "titulo": "Preparación", "nivel": 4}},
                    {"seccion": "Incidencias", "nivel": 2},
                    {"prueba": {"id": "T-3", "titulo": "Alarma", "nivel": 3}},
                ]
            }
        }

        entries = editor_yaml.navigation_entries(chapter, "preparación")

        self.assertEqual(
            [(kind, index) for kind, index, _label, _parent, _level in entries],
            [("section", 0), ("section", 2), ("test", 3)],
        )

    def test_insertar_prueba_al_final_de_la_seccion_correcta(self):
        with TemporaryDirectory() as temporary_directory:
            yaml_dir = Path(temporary_directory)
            chapter_path = yaml_dir / "chapter.yaml"
            chapter_path.write_text(
                "# comentario conservado\n"
                "capitulo: Capítulo\n"
                "contenido:\n"
                "- seccion: Grupo\n"
                "  nivel: 2\n"
                "- prueba:\n"
                "    id: EXISTENTE\n"
                "- seccion: Siguiente grupo\n"
                "  nivel: 2\n",
                encoding="utf-8",
            )
            chapter = editor_yaml.read_chapters(yaml_dir)[0]
            new_test = {"id": "NUEVA", "nombre": "Prueba nueva", "nivel": 3}

            editor_yaml.insert_test(chapter, new_test, 0)
            editor_yaml.save_chapter(chapter)

            loaded = YAML().load(chapter_path)
            contents = loaded["contenido"]
            self.assertEqual(contents[1]["prueba"]["id"], "EXISTENTE")
            self.assertEqual(contents[2]["prueba"]["id"], "NUEVA")
            self.assertEqual(contents[3]["seccion"], "Siguiente grupo")
            self.assertIn("# comentario conservado", chapter_path.read_text(encoding="utf-8"))

    def test_insertar_prueba_despues_de_la_prueba_seleccionada(self):
        chapter = {
            "path": Path("chapter.yaml"),
            "data": {
                "contenido": [
                    {"seccion": "Grupo", "nivel": 2},
                    {"prueba": {"id": "PRIMERA"}},
                    {"prueba": {"id": "SEGUNDA"}},
                    {"seccion": "Siguiente grupo", "nivel": 2},
                ]
            },
        }

        editor_yaml.insert_test(
            chapter,
            {"id": "NUEVA"},
            heading_index=None,
            after_test_index=1,
        )

        self.assertEqual(
            [
                element.get("prueba", {}).get("id", element.get("seccion"))
                for element in chapter["data"]["contenido"]
            ],
            ["Grupo", "PRIMERA", "NUEVA", "SEGUNDA", "Siguiente grupo"],
        )

    def test_insertar_tras_indice_que_ya_no_es_una_prueba_falla(self):
        chapter = {
            "path": Path("chapter.yaml"),
            "data": {"contenido": [{"seccion": "Grupo", "nivel": 2}]},
        }

        with self.assertRaisesRegex(ValueError, "ya no corresponde a una prueba"):
            editor_yaml.insert_test(
                chapter,
                {"id": "NUEVA"},
                heading_index=None,
                after_test_index=0,
            )

    def test_crear_seccion_va_despues_de_prueba_y_no_crea_prueba(self):
        chapter = {
            "path": Path("chapter.yaml"),
            "data": {
                "contenido": [
                    {"seccion": "Operaciones", "nivel": 2},
                    {"prueba": {"id": "EXISTENTE", "nivel": 3}},
                ]
            },
        }
        editor_yaml.insert_section_after_test(chapter, "Grupo nuevo", 1)

        contents = chapter["data"]["contenido"]
        self.assertEqual(contents[1]["prueba"]["id"], "EXISTENTE")
        self.assertEqual(contents[2], {"seccion": "Grupo nuevo", "nivel": 3})
        self.assertEqual(len(editor_yaml.tests_in_chapter(chapter)), 1)

        editor_yaml.insert_test(
            chapter,
            {"id": "NUEVA", "nivel": 4},
            heading_index=2,
        )
        self.assertEqual(
            [
                (kind, index, parent)
                for kind, index, _label, parent, _level
                in editor_yaml.navigation_entries(chapter)
            ],
            [
                ("section", 0, None),
                ("test", 1, 0),
                ("section", 2, 0),
                ("test", 3, 2),
            ],
        )

    def test_crear_seccion_bajo_prueba_nivel_seis_falla(self):
        chapter = {
            "path": Path("chapter.yaml"),
            "data": {
                "contenido": [
                    {"prueba": {"id": "PROFUNDA", "nivel": 6}},
                ]
            },
        }

        with self.assertRaisesRegex(ValueError, "nivel 6"):
            editor_yaml.insert_section_after_test(chapter, "Grupo nuevo", 0)

    def test_borrar_prueba_elimina_solo_esa_prueba(self):
        chapter = {
            "path": Path("chapter.yaml"),
            "data": {
                "contenido": [
                    {"seccion": "Grupo", "nivel": 2},
                    {"prueba": {"id": "A", "nivel": 3}},
                    {"prueba": {"id": "B", "nivel": 3}},
                ]
            },
        }

        editor_yaml.delete_test(chapter, 1)

        self.assertEqual(
            [test["id"] for _, test in editor_yaml.tests_in_chapter(chapter)],
            ["B"],
        )

    def test_borrar_seccion_promueve_contenido_sin_eliminarlo(self):
        chapter = {
            "path": Path("chapter.yaml"),
            "data": {
                "contenido": [
                    {"seccion": "Exterior", "nivel": 2},
                    {
                        "seccion": "Eliminar",
                        "nivel": 3,
                        "contexto": [
                            "nota",
                            {"texto": "captura", "imagenes": ["imagenes/a.png"]},
                        ],
                    },
                    {"seccion": "Interior", "nivel": 4},
                    {"prueba": {"id": "A", "nivel": 5}},
                    {"prueba": {"id": "B", "nivel": 3}},
                    {"seccion": "Siguiente", "nivel": 3},
                ]
            },
        }

        editor_yaml.delete_section(chapter, 1)

        contents = chapter["data"]["contenido"]
        self.assertEqual(
            [(element.get("seccion"), element.get("nivel")) for element in contents if "seccion" in element],
            [("Exterior", 2), ("Interior", 3), ("Siguiente", 3)],
        )
        self.assertEqual(contents[1], {"texto": "nota"})
        self.assertEqual(
            contents[2],
            {"texto": {"texto": "captura", "imagenes": ["imagenes/a.png"]}},
        )
        self.assertEqual(contents[4]["prueba"], {"id": "A", "nivel": 4})
        self.assertEqual(contents[5]["prueba"], {"id": "B", "nivel": 3})

    def test_rechaza_ids_duplicados_en_otros_capitulos(self):
        chapters = [
            {
                "path": Path("capitulo.yaml"),
                "data": {
                    "contenido": [
                        {"prueba": {"id": "DUPLICADO"}},
                    ]
                },
            }
        ]

        error = editor_yaml.find_duplicate_id(chapters, "DUPLICADO")

        self.assertIn("ya existe", error)
        self.assertIsNone(
            editor_yaml.find_duplicate_id(
                chapters,
                "DUPLICADO",
                (Path("capitulo.yaml"), 0),
            )
        )


if __name__ == "__main__":
    unittest.main()
