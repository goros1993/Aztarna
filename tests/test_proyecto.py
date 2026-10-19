"""De qué proyecto es cada ejecución y validación (app/proyecto.py y la API de validación)."""
import os
import shutil
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app import ejecucion_core as ej
from app import esquema
from app import proyecto
from app import validacion_core as vc
from app.validacion_api import EditorValidacionApi

EJEMPLOS = Path(__file__).resolve().parent.parent / "ejemplos" / "yaml"


def ok(testcase, r):
    testcase.assertTrue(r["ok"], r.get("error"))
    return r["datos"]


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        anterior = os.environ.get("AZTARNA_AJUSTES")
        os.environ["AZTARNA_AJUSTES"] = str(self.tmp / "ajustes.json")
        self.addCleanup(lambda: os.environ.__setitem__("AZTARNA_AJUSTES", anterior) if anterior else os.environ.pop("AZTARNA_AJUSTES", None))
        self.addCleanup(esquema.configurar, None)

    def proyecto_nuevo(self, nombre):
        """Una copia de los ejemplos sin nombre de proyecto (se llama como su carpeta)."""
        destino = self.tmp / nombre
        shutil.copytree(EJEMPLOS, destino)
        aztarna = destino / "aztarna.yaml"
        aztarna.write_text(aztarna.read_text(encoding="utf-8").replace("proyecto:\n  nombre: Controlador DEMO-A1\n", ""), encoding="utf-8")
        return destino


class Identidad(Base):
    def test_sin_git_se_crea_un_id_una_vez(self):
        p = self.proyecto_nuevo("ascensor")
        info = proyecto.leer(p / "pruebas")
        self.assertEqual((info["id"], info["nombre"]), (None, "ascensor"))     # el nombre, el de la carpeta
        creado = proyecto.asegurar_id(p / "pruebas")["id"]
        self.assertTrue(creado)
        self.assertEqual(proyecto.asegurar_id(p / "pruebas")["id"], creado)    # no cambia
        texto = (p / "aztarna.yaml").read_text(encoding="utf-8")
        self.assertIn(f"id: {creado}", texto)
        self.assertIn("maniobra: [Simplex, Dúplex]", texto)                   # lo demás sigue igual
        esquema.configurar(p / "pruebas")                                       # aztarna.yaml sigue siendo válido
        self.assertEqual(esquema.OPCIONES_MULTIPLES["maniobra"], ("Simplex", "Dúplex"))

    @unittest.skipUnless(shutil.which("git"), "hace falta git")
    def test_con_git_el_id_es_igual_en_todos_los_clones(self):
        origen = self.tmp / "repo"
        origen.mkdir()
        shutil.copytree(EJEMPLOS, origen / "ascensor")
        git = lambda carpeta, *a: subprocess.run(["git", "-C", str(carpeta), "-c", "user.name=a", "-c", "user.email=a@a", *a],
                                                check=True, capture_output=True)
        git(origen, "init", "-q")
        git(origen, "add", "-A")
        git(origen, "commit", "-qm", "pruebas")
        git(self.tmp, "clone", "-q", str(origen), str(self.tmp / "clon_de_luis"))
        uno = proyecto.leer(origen / "ascensor" / "pruebas")["id"]
        otro = proyecto.leer(self.tmp / "clon_de_luis" / "ascensor" / "pruebas")["id"]
        self.assertTrue(uno.startswith("git:") and uno.endswith(":ascensor/"))
        self.assertEqual(uno, otro)
        aztarna = (origen / "ascensor" / "aztarna.yaml").read_text(encoding="utf-8")
        proyecto.asegurar_id(origen / "ascensor" / "pruebas")
        self.assertEqual((origen / "ascensor" / "aztarna.yaml").read_text(encoding="utf-8"), aztarna)   # no se escribe nada

    def test_nombre_y_carpeta_de_validaciones(self):
        p = self.proyecto_nuevo("ascensor")
        (self.tmp / "compartida").mkdir()
        info = proyecto.configurar(p / "pruebas", nombre="  Controlador   DEMO-A1 ", validaciones=str(self.tmp / "compartida"))
        self.assertEqual((info["nombre"], info["validaciones"]), ("Controlador DEMO-A1", str(self.tmp / "compartida")))
        info = proyecto.configurar(p / "pruebas", validaciones="")
        self.assertIsNone(info["validaciones"])


class EnElEditor(Base):
    def setUp(self):
        super().setUp()
        self.ascensor = self.proyecto_nuevo("ascensor")
        self.escaleras = self.proyecto_nuevo("escaleras")
        self.api = EditorValidacionApi(self.ascensor)
        ok(self, self.api.iniciar())

    def test_lo_nuevo_apunta_su_proyecto(self):
        val = ok(self, self.api.validacion_crear("V1", "1.0", {"etiquetas": ["smoke"]}, str(self.tmp / "val")))
        self.assertEqual(val["proyecto"]["nombre"], "ascensor")
        self.assertEqual(val["relacion"], "mismo")
        e = ok(self, self.api.validacion_nueva_ejecucion("Torre", {"etiquetas": ["smoke"]}, {"entorno_pruebas": "Torre"}))
        self.assertEqual(e["datos"]["proyecto"], val["proyecto"])
        self.assertEqual(vc.cargar(self.tmp / "val")["datos"]["proyecto"]["id"], proyecto.leer(self.ascensor / "pruebas")["id"])

    def test_abrir_la_de_otro_proyecto_pregunta_primero(self):
        otra = EditorValidacionApi(self.escaleras)
        ok(self, otra.iniciar())
        ok(self, otra.validacion_crear("De escaleras", "", {"etiquetas": ["smoke"]}, str(self.tmp / "val_esc")))
        r = ok(self, self.api.validacion_abrir(str(self.tmp / "val_esc")))
        self.assertTrue(r["otro_proyecto"])
        self.assertEqual((r["su_proyecto"], r["proyecto_abierto"]), ("escaleras", "ascensor"))
        self.assertIsNone(ok(self, self.api.validacion_estado()))              # no se ha abierto
        self.assertEqual(self.api._yaml_dir, (self.ascensor / "pruebas").resolve())   # ni han cambiado las pruebas
        r = ok(self, self.api.validacion_abrir(str(self.tmp / "val_esc"), True))
        self.assertEqual(r["relacion"], "mismo")                                # ahora las pruebas son las suyas
        self.assertEqual(self.api._yaml_dir, (self.escaleras / "pruebas").resolve())

    def test_las_antiguas_se_reconocen_por_sus_pruebas_y_se_apuntan(self):
        vieja = vc.crear(self.tmp / "vieja", self.ascensor / "pruebas", "Vieja", "", {"etiquetas": ["smoke"]})   # sin proyecto
        de_otro = vc.crear(self.tmp / "otra_vieja", self.escaleras / "pruebas", "Otra", "", {"etiquetas": ["smoke"]})
        ejecucion = ej.crear(self.tmp / "ej_vieja", self.ascensor / "pruebas", "Suelta", {"etiquetas": ["smoke"]}, {})
        portada = ok(self, self.api.validacion_portada([str(vieja["carpeta"]), str(de_otro["carpeta"])], [str(ejecucion["carpeta"])]))
        self.assertEqual([(v["nombre"], v["relacion"]) for v in portada["validaciones"]], [("Vieja", "mismo"), ("Otra", "otro")])
        self.assertEqual([(e["nombre"], e["relacion"]) for e in portada["ejecuciones"]], [("Suelta", "mismo")])
        proyecto.asegurar_id(self.ascensor / "pruebas")
        ok(self, self.api.recargar())
        ok(self, self.api.validacion_abrir(str(vieja["carpeta"])))
        self.assertEqual(vc.cargar(vieja["carpeta"])["datos"]["proyecto"]["nombre"], "ascensor")   # se le apunta al abrirla
        self.assertNotIn("proyecto", vc.cargar(de_otro["carpeta"])["datos"])

    def test_la_ejecucion_de_otra_copia_del_mismo_proyecto_no_pregunta(self):
        copia = self.tmp / "copia_de_luis"
        shutil.copytree(self.ascensor, copia)
        luis = EditorValidacionApi(copia)
        ok(self, luis.iniciar())
        ok(self, luis.ejecucion_crear("De Luis", {"etiquetas": ["smoke"]}, {"entorno_pruebas": "Torre"}, str(self.tmp / "ej_luis")))
        shutil.rmtree(copia)                                                    # su copia no está en este PC
        r = ok(self, self.api.ejecucion_abrir(str(self.tmp / "ej_luis")))
        self.assertNotIn("otro_proyecto", r)                                    # mismas pruebas: es de este proyecto
        self.assertEqual(r["relacion"], "mismo")

    def test_carpeta_de_validaciones_del_proyecto(self):
        compartida = self.tmp / "compartida"
        compartida.mkdir()
        ok(self, self.api.proyecto_configurar(None, str(compartida)))
        vc.crear(compartida / "v2.3", self.ascensor / "pruebas", "Validación 2.3", "2.3", {"etiquetas": ["smoke"]})
        vc.crear(compartida / "antiguas" / "v2.2", self.ascensor / "pruebas", "Validación 2.2", "2.2", {"etiquetas": ["smoke"]})
        portada = ok(self, self.api.validacion_portada([], []))
        self.assertEqual(portada["proyecto"]["validaciones"], str(compartida))
        self.assertEqual(sorted((v["nombre"], v["en_carpeta"], v["relacion"]) for v in portada["validaciones"]),
                         [("Validación 2.2", True, "mismo"), ("Validación 2.3", True, "mismo")])
        self.assertIn("validaciones:", (self.ascensor / "aztarna.yaml").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
