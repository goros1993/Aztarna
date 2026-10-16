"""Bloqueo de capítulos (app/bloqueos.py) y su uso en el editor."""
import json
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from app import bloqueos
from app.editor_api import EditorApi

RAIZ = Path(__file__).resolve().parents[1]


def ok(test, r):
    test.assertTrue(r["ok"], r.get("error"))
    return r.get("datos")


class Sesiones(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.capitulo = Path(self._tmp.name) / "01_capitulo.yaml"
        self.capitulo.write_text("capitulo: A\ncontenido: []\n", encoding="utf-8")
        self.ana = bloqueos.Bloqueos(persona=lambda: "Ana")
        self.luis = bloqueos.Bloqueos(persona=lambda: "Luis")

    def test_uno_lo_toma_y_el_otro_ve_quien(self):
        self.assertIsNone(self.ana.tomar(self.capitulo))
        self.assertTrue(bloqueos.ruta_bloqueo(self.capitulo).name.startswith(".01_capitulo.yaml"))
        otro = self.luis.tomar(self.capitulo)
        self.assertEqual(otro["persona"], "Ana")
        self.assertIn("Ana", bloqueos.texto(otro, "A"))
        self.assertIsNone(self.ana.de_otro(self.capitulo))                 # el mío no es «de otro»
        self.assertIsNone(self.ana.tomar(self.capitulo))                   # volver a tomarlo no falla
        self.ana.soltar(self.capitulo)
        self.assertFalse(bloqueos.ruta_bloqueo(self.capitulo).exists())
        self.assertIsNone(self.luis.tomar(self.capitulo))

    def test_caduca_si_no_se_renueva_y_se_puede_forzar(self):
        self.ana.tomar(self.capitulo)
        ruta = bloqueos.ruta_bloqueo(self.capitulo)
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        ruta.write_text(json.dumps({**datos, "renovado": time.time() - bloqueos.CADUCIDAD_S - 1}), encoding="utf-8")
        self.assertIsNone(self.luis.tomar(self.capitulo))                  # el editor de Ana se cerró mal
        self.assertEqual(self.ana.tomar(self.capitulo)["persona"], "Luis")
        self.assertIsNone(self.ana.tomar(self.capitulo, forzar=True))      # Ana lo fuerza
        self.assertEqual(self.luis.renovar(), [self.capitulo])            # Luis se entera de que lo ha perdido
        self.assertFalse(self.luis.es_mio(self.capitulo))

    def test_se_suelta_tras_un_rato_sin_cambios(self):
        self.ana.tomar(self.capitulo)
        with mock.patch.object(bloqueos.time, "time", return_value=time.time() + bloqueos.INACTIVO_S + 1):
            self.ana.renovar()
        self.assertFalse(self.ana.es_mio(self.capitulo))
        self.assertFalse(bloqueos.ruta_bloqueo(self.capitulo).exists())
        # Con cambios sin guardar no se suelta.
        ocupada = bloqueos.Bloqueos(persona=lambda: "Ana", ocupado=lambda: True)
        ocupada.tomar(self.capitulo)
        with mock.patch.object(bloqueos.time, "time", return_value=time.time() + bloqueos.INACTIVO_S + 1):
            ocupada.renovar()
        self.assertTrue(ocupada.es_mio(self.capitulo))
        ocupada.cerrar()
        self.assertFalse(bloqueos.ruta_bloqueo(self.capitulo).exists())


class EnElEditor(unittest.TestCase):
    """Dos editores abiertos sobre la misma carpeta (como dos PCs con la unidad de red)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name) / "yaml"
        shutil.copytree(RAIZ / "ejemplos" / "yaml", self.dir)
        self.ana, self.luis = EditorApi(self.dir), EditorApi(self.dir)
        self.ana._bloqueos._persona = lambda: "Ana"
        self.luis._bloqueos._persona = lambda: "Luis"
        self.addCleanup(self.ana._bloqueos.cerrar)
        self.addCleanup(self.luis._bloqueos.cerrar)
        ok(self, self.ana.iniciar())
        ok(self, self.luis.iniciar())
        self.indice = next(n["indice"] for n in ok(self, self.ana.navegacion(0, "")) if n["tipo"] == "prueba")

    def test_el_segundo_no_puede_guardar_y_sabe_quien(self):
        self.assertEqual(ok(self, self.ana.bloquear(0)), {"otro": None, "mio": True})
        ok(self, self.ana.guardar_prueba(0, self.indice, {"descripcion": "Cambio de Ana"}))
        info = ok(self, self.luis.bloqueo(0))
        self.assertEqual(info["otro"]["persona"], "Ana")
        self.assertIn("está editando", info["otro"]["texto"])
        r = self.luis.guardar_prueba(0, self.indice, {"descripcion": "Cambio de Luis"})
        self.assertFalse(r["ok"])
        self.assertIn("Ana", r["error"])
        self.assertIn("no se ha guardado", r["error"])
        # Otro capítulo sí lo puede editar.
        otro_indice = next(n["indice"] for n in ok(self, self.luis.navegacion(1, "")) if n["tipo"] == "prueba")
        ok(self, self.luis.guardar_prueba(1, otro_indice, {"descripcion": "Otro capítulo"}))
        # Cuando Ana lo deja, Luis ya puede.
        ok(self, self.ana.soltar_bloqueos())
        self.assertIsNone(ok(self, self.luis.bloqueo(0))["otro"])
        ok(self, self.luis.recargar())
        ok(self, self.luis.guardar_prueba(0, self.indice, {"descripcion": "Cambio de Luis"}))

    def test_forzar(self):
        ok(self, self.ana.bloquear(0))
        self.assertIsNotNone(ok(self, self.luis.bloquear(0))["otro"])
        self.assertEqual(ok(self, self.luis.bloquear(0, True)), {"otro": None, "mio": True})
        self.assertFalse(self.ana.guardar_prueba(0, self.indice, {"descripcion": "x"})["ok"])


if __name__ == "__main__":
    unittest.main()
