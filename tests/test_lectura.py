"""Lecturas en caché para consultar (app/lectura.py)."""
import shutil
import tempfile
import unittest
from pathlib import Path

from app import ejecucion_core as ej
from app import lectura
from app import validacion_core as vc
from app.editor_core import read_chapters, save_chapter

RAIZ = Path(__file__).resolve().parents[1]


class Cache(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name) / "ejemplos"
        shutil.copytree(RAIZ / "ejemplos" / "yaml", self.base / "yaml")
        shutil.copytree(RAIZ / "ejemplos" / "ejecuciones", self.base / "ejecuciones")
        shutil.copytree(RAIZ / "ejemplos" / "validaciones", self.base / "validaciones")
        lectura.vaciar()

    def test_no_relee_si_no_cambia_y_relee_si_cambia(self):
        pruebas = self.base / "yaml" / "pruebas"
        a = lectura.capitulos(pruebas)
        self.assertIs(lectura.capitulos(pruebas), a)
        capitulo = read_chapters(pruebas)[0]
        capitulo["data"]["capitulo"] = "Cambiado"
        save_chapter(capitulo)
        self.assertEqual(lectura.capitulos(pruebas)[0]["data"]["capitulo"], "Cambiado")

    def test_ejecucion_y_validacion_ven_los_resultados_nuevos(self):
        carpeta = self.base / "ejecuciones" / "regresion_v2.3"
        val = self.base / "validaciones" / "validacion_v2.3"
        antes = vc.consolidar(vc.cargar(val))
        self.assertIs(lectura.ejecucion(carpeta), lectura.ejecucion(carpeta))
        ejecucion = ej.cargar(carpeta)
        pendiente = next(i for i in ej.ids_de(ejecucion) if ej.estado_de(ejecucion, i) == "pendiente")
        ej.registrar(ejecucion, pendiente, "no_ok", observaciones="Falla")
        self.assertEqual(lectura.ejecucion(carpeta)["resultados"][pendiente]["estado"], "no_ok")
        despues = vc.consolidar(vc.cargar(val))
        self.assertEqual(despues["totales"]["no_ok"], antes["totales"]["no_ok"] + 1)


if __name__ == "__main__":
    unittest.main()
