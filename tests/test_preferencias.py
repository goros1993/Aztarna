"""Preferencias de la interfaz y carpeta de los diálogos, guardadas en los ajustes del PC."""
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app import ajustes
from app.validacion_api import EditorValidacionApi


class _Ventana:
    """Sustituye a la ventana de pywebview: devuelve la carpeta que se le indique y apunta dónde empezó."""

    def __init__(self, elegida):
        self.elegida = elegida
        self.inicios = []

    def create_file_dialog(self, _tipo, directory="", **_kw):
        self.inicios.append(directory)
        return [str(self.elegida)] if self.elegida else None


class PreferenciasTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        anterior = os.environ.get("EDITOR_PRUEBAS_AJUSTES")
        os.environ["EDITOR_PRUEBAS_AJUSTES"] = str(self.tmp / "ajustes.json")
        self.addCleanup(lambda: os.environ.pop("EDITOR_PRUEBAS_AJUSTES") if anterior is None
                        else os.environ.__setitem__("EDITOR_PRUEBAS_AJUSTES", anterior))
        self.api = EditorValidacionApi()

    def test_se_guardan_y_se_fusionan(self):
        self.assertEqual(self.api.preferencias()["datos"], {})
        self.api.guardar_preferencias({"modo": "ejecucion", "ejecutor": "Ana"})
        self.api.guardar_preferencias({"ejecutor": None, "ancho-lateral": 340})
        self.assertEqual(EditorValidacionApi().preferencias()["datos"], {"modo": "ejecucion", "ancho-lateral": "340"})
        # No pisan el resto de ajustes del PC.
        ajustes.guardar({"ultima_carpeta": "/x"})
        self.api.guardar_preferencias({"modo": "edicion"})
        datos = json.loads((self.tmp / "ajustes.json").read_text(encoding="utf-8"))
        self.assertEqual((datos["ultima_carpeta"], datos["interfaz"]["modo"]), ("/x", "edicion"))

    def test_el_dialogo_empieza_donde_se_eligio_la_ultima_vez(self):
        compartida = self.tmp / "compartida"
        (compartida / "ejecucion_ana").mkdir(parents=True)
        self.api._window = _Ventana(compartida / "ejecucion_ana")
        self.assertEqual(self.api._dialogo_carpeta(), compartida / "ejecucion_ana")
        self.assertEqual(self.api._window.inicios, [str(Path.home())])
        self.api._dialogo_carpeta()
        self.assertEqual(self.api._window.inicios[-1], str(compartida))


if __name__ == "__main__":
    unittest.main()
