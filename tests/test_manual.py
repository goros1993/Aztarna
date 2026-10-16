"""Manual dentro de la aplicación y versión de la herramienta."""
import io
import re
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import app
import herramientas
from app import manual
from app.editor_api import EditorApi

RAIZ = Path(__file__).resolve().parent.parent


class ManualTests(unittest.TestCase):
    def test_el_indice_enlaza_con_sus_apartados_y_las_capturas_existen(self):
        texto = manual.a_html((RAIZ / "MANUAL.md").read_text(encoding="utf-8"), RAIZ)
        anclajes = set(re.findall(r'id="([^"]+)"', texto))
        enlaces = re.findall(r'href="#([^"]+)"', texto)
        self.assertGreater(len(enlaces), 5)
        self.assertEqual([e for e in enlaces if e not in anclajes], [])
        imagenes = re.findall(r'src="file://([^"]+)"', texto)
        self.assertGreater(len(imagenes), 20)
        self.assertEqual([i for i in imagenes if not Path(i).is_file()], [])

    def test_abrir_sin_ventana_solo_genera(self):
        r = EditorApi().abrir_manual()
        self.assertTrue(r["ok"], r.get("error"))
        self.assertTrue(Path(r["datos"]["archivo"]).is_file())


class VersionTests(unittest.TestCase):
    def test_version_en_un_solo_sitio(self):
        self.assertRegex(app.__version__, r"^\d+\.\d+\.\d+$")
        self.assertIn(f"## {app.__version__}", (RAIZ / "CHANGELOG.md").read_text(encoding="utf-8"))
        with redirect_stdout(io.StringIO()) as salida:
            herramientas.main(["--version"])
        self.assertEqual(salida.getvalue().strip(), app.firma())
        datos = EditorApi().acerca_de()["datos"]
        self.assertEqual((datos["nombre"], datos["version"]), (app.NOMBRE, app.__version__))

    def test_editor_version(self):
        r = subprocess.run([sys.executable, str(RAIZ / "editor_web.py"), "--version"], capture_output=True, text=True)
        self.assertEqual(r.stdout.strip(), app.firma())


if __name__ == "__main__":
    unittest.main()
