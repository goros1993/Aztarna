from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ruamel.yaml import YAML

import editor_yaml


class EditorYamlTests(unittest.TestCase):
    def test_nivel_none_se_normaliza_sin_romper_el_formulario(self):
        self.assertEqual(editor_yaml.normalize_level(None), 3)
        self.assertEqual(editor_yaml.normalize_level(None, 4), 4)
        self.assertEqual(editor_yaml.normalize_level(12), 6)

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
