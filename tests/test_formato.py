"""Versión del formato de los datos (app/formato.py)."""
import shutil
import tempfile
import unittest
from pathlib import Path

from app import ejecucion_core as ej
from app import formato
from app import validacion_core as vc
from app.editor_api import EditorApi
from app.editor_core import read_chapters

RAIZ = Path(__file__).resolve().parents[1]


def ok(test, r):
    test.assertTrue(r["ok"], r.get("error"))
    return r.get("datos")


class Formato(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        shutil.copytree(RAIZ / "ejemplos" / "yaml", self.tmp / "yaml")
        self.pruebas = self.tmp / "yaml" / "pruebas"
        (self.pruebas / formato.ARCHIVO).unlink(missing_ok=True)

    def subir(self, carpeta, numero=formato.FORMATO + 1):
        (carpeta / formato.ARCHIVO).write_text(f"formato: {numero}\nescrito_con: Aztarna 9.0.0\n", encoding="utf-8")

    def test_carpeta_sin_marca_es_formato_1_y_se_marca_al_guardar(self):
        self.assertEqual(formato.de_carpeta(self.pruebas), 1)
        api = EditorApi(self.tmp / "yaml")
        self.addCleanup(api._bloqueos.cerrar)
        ok(self, api.iniciar())
        indice = next(n["indice"] for n in ok(self, api.navegacion(0, "")) if n["tipo"] == "prueba")
        ok(self, api.guardar_prueba(0, indice, {"descripcion": "cambio"}))
        texto = (self.pruebas / formato.ARCHIVO).read_text(encoding="utf-8")
        self.assertIn(f"formato: {formato.FORMATO}", texto)
        self.assertIn("escrito_con: Aztarna", texto)
        # No es un capítulo.
        self.assertNotIn(formato.ARCHIVO, [c["path"].name for c in read_chapters(self.pruebas)])
        (self.pruebas / "indice.yaml").unlink()
        self.assertNotIn(formato.ARCHIVO, [c["path"].name for c in read_chapters(self.pruebas)])

    def test_formato_mas_nuevo_se_ve_pero_no_se_guarda(self):
        self.subir(self.pruebas)
        api = EditorApi(self.tmp / "yaml")
        self.addCleanup(api._bloqueos.cerrar)
        resumen = ok(self, api.iniciar())
        self.assertIn("versión más nueva", resumen["aviso_formato"])
        self.assertTrue(resumen["capitulos"])                                     # se puede consultar
        indice = next(n["indice"] for n in ok(self, api.navegacion(0, "")) if n["tipo"] == "prueba")
        antes = (self.pruebas / "01_ejemplo_basico.yaml").read_text(encoding="utf-8")
        r = api.guardar_prueba(0, indice, {"descripcion": "cambio"})
        self.assertFalse(r["ok"])
        self.assertIn("actualiza el programa", r["error"])
        self.assertEqual((self.pruebas / "01_ejemplo_basico.yaml").read_text(encoding="utf-8"), antes)
        self.assertIn("formato: 2", (self.pruebas / formato.ARCHIVO).read_text(encoding="utf-8"))   # no se baja
        # También si la más nueva es la de requisitos.
        self.subir(self.pruebas, 1)
        self.subir(self.tmp / "yaml" / "requisitos")
        self.assertIn("requisitos", ok(self, api.recargar())["aviso_formato"])

    def test_ejecucion_y_validacion(self):
        ejecucion = ej.crear(self.tmp / "ej", self.pruebas, "E", {}, {"entorno_pruebas": "Torre"})
        self.assertEqual(ej.cargar(self.tmp / "ej")["datos"]["formato"], formato.FORMATO)
        ejecucion["datos"]["formato"] = formato.FORMATO + 1
        with self.assertRaises(formato.FormatoNuevo):
            ej.registrar(ejecucion, ejecucion["datos"]["pruebas"][0]["id"], "ok")
        validacion = vc.crear(self.tmp / "val", self.pruebas, "V")
        self.assertEqual(vc.cargar(self.tmp / "val")["datos"]["formato"], formato.FORMATO)
        validacion["datos"]["formato"] = formato.FORMATO + 1
        with self.assertRaises(formato.FormatoNuevo):
            vc.editar(validacion, {"nombre": "Otra"})
        # Las de antes de la marca valen como formato 1 y la reciben al guardar.
        antigua = ej.cargar(RAIZ / "ejemplos" / "ejecuciones" / "regresion_v2.3")
        self.assertEqual(formato.de_datos(antigua["datos"]), 1)

    def test_importar_en_una_carpeta_mas_nueva(self):
        from app import importacion as imp
        from app import yaml_a_docx
        yaml_a_docx.generar_docx(self.tmp / "yaml" / "requisitos", self.tmp / "r.docx")
        self.subir(self.tmp / "yaml" / "requisitos")
        mapeo = imp.mapeo_propuesto(imp.analizar(self.tmp / "r.docx"))
        with self.assertRaises(formato.FormatoNuevo):
            imp.importar(self.tmp / "r.docx", mapeo, self.tmp / "yaml", "anadir")
        r = imp.importar(self.tmp / "r.docx", mapeo, self.tmp / "nuevo")
        self.assertEqual(formato.de_carpeta(r["carpetas"]["requisito"]), formato.FORMATO)
        self.assertTrue((self.tmp / "nuevo" / "requisitos" / formato.ARCHIVO).is_file())


if __name__ == "__main__":
    unittest.main()
