"""Opciones de maniobra y entorno de cada proyecto (aztarna.yaml, app/esquema.py)."""
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app import ejecucion_core as ej
from app import esquema
from app.editor_core import read_chapters

EJEMPLOS = Path(__file__).resolve().parent.parent / "ejemplos" / "yaml"


class Configuracion(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(esquema.configurar, None)
        self.tmp = Path(self._tmp.name)

    def escribir(self, texto, carpeta=None):
        ruta = (carpeta or self.tmp) / esquema.ARCHIVO_CONFIGURACION
        ruta.write_text(texto, encoding="utf-8")
        return ruta

    def test_sin_archivo_maniobra_no_tiene_opciones(self):
        self.assertIsNone(esquema.configurar(self.tmp))
        self.assertEqual(esquema.OPCIONES_MULTIPLES["maniobra"], ())
        self.assertEqual(esquema.OPCIONES_MULTIPLES["entorno"], ("Automático", "Maqueta", "Torre"))
        self.assertEqual(esquema.normalizar_entorno("A/M"), (["Automático", "Maqueta"], []))
        self.assertEqual(esquema.normalizar_maniobra("Simplex"), ([], ["Simplex"]))

    def test_el_del_proyecto_vale_para_su_carpeta_de_pruebas(self):
        (self.tmp / "pruebas").mkdir()
        ruta = self.escribir("opciones:\n  maniobra: [Simplex, Dúplex]\n")
        self.assertEqual(esquema.configurar(self.tmp / "pruebas"), ruta)
        self.assertEqual(esquema.OPCIONES_MULTIPLES["maniobra"], ("Simplex", "Dúplex"))
        self.assertEqual(esquema.OPCIONES_MULTIPLES["entorno"], ("Automático", "Maqueta", "Torre"))   # no lo cambia

    def test_opciones_y_equivalencias_propias(self):
        self.escribir("opciones:\n  maniobra: [Modo 1, Modo 2]\n  entorno: [Banco HIL, Obra]\n"
                      "equivalencias:\n  maniobra: {M1: Modo 1, M2: Modo 2}\n  entorno: {H: Banco HIL, O: Obra}\n")
        esquema.configurar(self.tmp)
        self.assertEqual(esquema.normalizar_maniobra("m2 / MODO 1, Modo 3"), (["Modo 1", "Modo 2"], ["Modo 3"]))
        self.assertEqual(esquema.normalizar_entorno("banco hil y O"), (["Banco HIL", "Obra"], []))
        self.assertEqual(esquema.normalizar_entorno("HO"), (["Banco HIL", "Obra"], []))
        self.assertEqual(esquema.normalizar_entorno("A"), ([], ["A"]))       # las de partida ya no llevan a nada

    def test_al_cambiar_de_proyecto_vuelven_las_de_partida(self):
        self.escribir("opciones:\n  maniobra: [Simplex]\n")
        esquema.configurar(self.tmp)
        otro = self.tmp / "otro"
        otro.mkdir()
        esquema.configurar(otro)
        self.assertEqual(esquema.OPCIONES_MULTIPLES["maniobra"], ())
        self.assertIsNone(esquema.CONFIGURACION)

    def test_un_archivo_mal_escrito_se_explica(self):
        for texto, error in (("opciones:\n  color: [Rojo]\n", "no es un campo con opciones"),
                             ("opciones:\n  maniobra: [A, a]\n", "repetidas"),
                             ("equivalencias:\n  maniobra: {X: Otra}\n", "no es una opción"),
                             ("otra_cosa: 1\n", "solo admite"),
                             ("opciones: [\n", "No se puede leer")):
            self.escribir(texto)
            with self.assertRaisesRegex(ValueError, error):
                esquema.configurar(self.tmp)

    def test_no_es_un_capitulo(self):
        pruebas = self.tmp / "pruebas"
        shutil.copytree(EJEMPLOS / "pruebas", pruebas)
        (pruebas / "indice.yaml").unlink()
        self.escribir("opciones:\n  maniobra: [Simplex]\n", pruebas)
        self.assertNotIn(esquema.ARCHIVO_CONFIGURACION, [c["path"].name for c in read_chapters(pruebas)])

    def test_la_ejecucion_cerrada_guarda_las_opciones_de_entonces(self):
        shutil.copytree(EJEMPLOS, self.tmp / "proyecto")
        pruebas = self.tmp / "proyecto" / "pruebas"
        esquema.configurar(pruebas)
        ejecucion = ej.crear(self.tmp / "ejecucion", pruebas, "Regresión", {"etiquetas": ["smoke"]}, {})
        congelada = ej.congelar(ejecucion, read_chapters(pruebas))
        self.assertEqual((congelada / esquema.ARCHIVO_CONFIGURACION).read_text(encoding="utf-8"),
                         (EJEMPLOS / esquema.ARCHIVO_CONFIGURACION).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
