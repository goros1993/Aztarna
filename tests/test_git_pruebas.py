"""Versión de las pruebas en Git (app/git_pruebas.py): qué se guarda en las ejecuciones y los avisos."""
import shutil
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app import ejecucion_core as ej
from app import git_pruebas
from app import validacion_core as vc
from app.editor_core import read_chapters, save_chapter

EJEMPLOS = Path(__file__).resolve().parent.parent / "ejemplos" / "yaml"


@unittest.skipUnless(shutil.which("git"), "hace falta git")
class GitPruebas(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.proyecto = self.tmp / "proyecto"
        shutil.copytree(EJEMPLOS, self.proyecto)
        self.pruebas = self.proyecto / "pruebas"
        self.git("init", "-q", "-b", "main")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "Pruebas")
        self.git("tag", "-a", "v2.3", "-m", "v2.3")

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.proyecto), "-c", "user.name=Prueba", "-c", "user.email=prueba@ejemplo.org", *args],
                       check=True, capture_output=True)

    def commit_actual(self):
        return subprocess.run(["git", "-C", str(self.proyecto), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()

    def cambiar_un_titulo(self):
        capitulo = read_chapters(self.pruebas)[0]
        prueba = next(e["prueba"] for e in capitulo["data"]["contenido"] if isinstance(e, dict) and "prueba" in e)
        prueba["titulo"] = "Cambiado en mi copia"
        save_chapter(capitulo)

    def crear(self, nombre="Regresión", entorno="Torre"):
        return ej.crear(self.tmp / "ejecuciones" / nombre, self.pruebas, nombre, {"etiquetas": ["regresion"]},
                        {"entorno_pruebas": entorno})

    def test_sin_git_no_hay_version(self):
        suelta = self.tmp / "suelta"
        shutil.copytree(EJEMPLOS / "pruebas", suelta)
        self.assertIsNone(git_pruebas.estado(suelta))
        self.assertEqual(git_pruebas.texto(None), "")

    def test_commit_etiqueta_y_cambios(self):
        estado = git_pruebas.estado(self.pruebas)
        self.assertEqual((estado["commit"], estado["etiqueta"], estado["rama"], estado["cambios"]),
                         (self.commit_actual(), "v2.3", "main", False))
        self.assertEqual(git_pruebas.texto(estado), f"v2.3 ({self.commit_actual()[:7]})")
        self.cambiar_un_titulo()
        self.assertTrue(git_pruebas.estado(self.pruebas)["cambios"])
        self.git("commit", "-q", "-am", "Otro")
        estado = git_pruebas.estado(self.pruebas)
        self.assertTrue(estado["etiqueta"].startswith("v2.3-1-g"))          # un commit después de la etiqueta
        self.assertFalse(estado["cambios"])

    def test_solo_cuentan_los_cambios_de_las_pruebas(self):
        (self.proyecto / "notas.txt").write_text("otra cosa", encoding="utf-8")
        self.assertFalse(git_pruebas.estado(self.pruebas)["cambios"])
        (self.proyecto / "aztarna.yaml").write_text("opciones:\n  maniobra: [Otra]\n", encoding="utf-8")
        self.assertTrue(git_pruebas.estado(self.pruebas)["cambios"])        # las opciones también son de las pruebas

    def test_la_ejecucion_apunta_la_version_al_crearla_y_al_cerrarla(self):
        ejecucion = self.crear()
        datos = ej.cargar(ejecucion["carpeta"])["datos"]
        self.assertEqual((datos["git"]["commit"], datos["git"]["etiqueta"]), (self.commit_actual(), "v2.3"))
        self.assertEqual(ej.resumen(ejecucion, read_chapters(self.pruebas))["problemas"], [])
        for test_id in ej.ids_de(ejecucion):
            ej.registrar(ejecucion, test_id, "ok")
        self.cambiar_un_titulo()
        ej.cerrar(ejecucion, read_chapters(self.pruebas))
        datos = ej.cargar(ejecucion["carpeta"])["datos"]
        self.assertTrue(datos["git_cierre"]["cambios"])
        self.assertIn("al cerrarla", git_pruebas.texto_ejecucion(datos))
        mensajes = [p["mensaje"] for p in ej.resumen(ej.cargar(ejecucion["carpeta"]), read_chapters(self.pruebas))["problemas"]]
        self.assertTrue(any("se cerró con cambios sin commit" in m for m in mensajes))

    def test_la_validacion_avisa_de_versiones_distintas(self):
        val = vc.crear(self.tmp / "validacion", self.proyecto, "Validación v2.3", "2.3.0", {"etiquetas": ["regresion"]})
        vc.anadir_ejecucion(val, self.crear("ana", "Maqueta")["carpeta"])
        self.assertFalse([a for a in vc.consolidar(val)["avisos"] if "versiones distintas" in a["mensaje"]])
        self.cambiar_un_titulo()
        self.git("commit", "-q", "-am", "Luis tiene otra versión")
        vc.anadir_ejecucion(val, self.crear("luis", "Torre")["carpeta"])
        avisos = [a["mensaje"] for a in vc.consolidar(vc.cargar(self.tmp / "validacion"))["avisos"]]
        self.assertTrue(any("versiones distintas de las pruebas" in a and "ana" in a and "luis" in a for a in avisos), avisos)


if __name__ == "__main__":
    unittest.main()
