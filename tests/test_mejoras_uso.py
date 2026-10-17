"""Ajustes, aviso de versión nueva, campos de varios a la vez, buscar en todo, CSV, tendencia y .gitignore de los bloqueos."""
import csv
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from app import actualizaciones, bloqueos
from app import ejecucion_core as ej
from app import exportar_resultados as er
from app import validacion_core as vc
from app.editor_api import EditorApi

RAIZ = Path(__file__).resolve().parents[1]


def ok(test, r):
    test.assertTrue(r["ok"], r.get("error"))
    return r.get("datos")


class ConCarpeta(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        shutil.copytree(RAIZ / "ejemplos", self.tmp / "ejemplos")
        anterior = os.environ.get("AZTARNA_AJUSTES")
        os.environ["AZTARNA_AJUSTES"] = str(self.tmp / "ajustes.json")
        self.addCleanup(lambda: os.environ.__setitem__("AZTARNA_AJUSTES", anterior) if anterior else os.environ.pop("AZTARNA_AJUSTES", None))
        self.api = EditorApi(self.tmp / "ejemplos" / "yaml")
        self.addCleanup(self.api._bloqueos.cerrar)
        ok(self, self.api.iniciar())

    def pruebas(self, capitulo=0):
        return [n for n in ok(self, self.api.navegacion(capitulo, "")) if n["tipo"] == "prueba"]


class Ajustes(ConCarpeta):
    def test_version_nueva(self):
        self.assertGreater(actualizaciones.numero("0.12.0"), actualizaciones.numero("0.11.3"))
        self.assertEqual(actualizaciones.numero("v1.2"), (1, 2))
        r = self.api.comprobar_version()
        self.assertEqual(r["datos"]["configurada"], False)
        programa = self.tmp / "programa"
        programa.mkdir()
        (programa / "version.txt").write_text("99.0.0\n", encoding="utf-8")
        ok(self, self.api.guardar_ajustes_generales({"carpeta_versiones": str(programa)}))
        r = self.api.comprobar_version()["datos"]
        self.assertTrue(r["nueva"])
        self.assertEqual(r["version"], "99.0.0")
        (programa / "version.txt").write_text("0.1.0", encoding="utf-8")
        self.assertFalse(self.api.comprobar_version()["datos"]["nueva"])
        (programa / "version.txt").unlink()
        self.assertFalse(self.api.comprobar_version()["datos"]["accesible"])

    def test_ajustes_y_persona(self):
        self.assertFalse(self.api.guardar_ajustes_generales({"url_incidencias": "jira/browse"})["ok"])
        d = ok(self, self.api.guardar_ajustes_generales({"url_incidencias": "https://jira.x/browse/{id}", "persona": "Ana Pérez"}))
        self.assertEqual((d["url_incidencias"], d["persona"]), ("https://jira.x/browse/{id}", "Ana Pérez"))
        self.assertEqual(self.api._persona(), "Ana Pérez")                         # la usan los bloqueos
        self.assertEqual(ok(self, self.api.preferencias())["ejecutor"], "Ana Pérez")  # y las ejecuciones


class Varios(ConCarpeta):
    def test_anadir_quitar_y_poner(self):
        idx = [n["indice"] for n in self.pruebas()]
        r = ok(self, self.api.editar_varios(0, idx, "etiquetas", "anadir", "migrada, revisar"))
        self.assertEqual(r["cambiados"], len(idx))
        etiquetas = lambda i: ok(self, self.api.obtener(0, i))["elemento"]["etiquetas"]
        self.assertIn("migrada", etiquetas(idx[0]))
        ok(self, self.api.editar_varios(0, idx, "etiquetas", "quitar", ["revisar"]))
        self.assertNotIn("revisar", etiquetas(idx[0]))
        self.assertEqual(ok(self, self.api.editar_varios(0, idx, "entorno", "poner", ["Torre"]))["cambiados"], len(idx))
        self.assertFalse(self.api.editar_varios(0, idx, "entorno", "poner", ["Torreta"])["ok"])   # no es una opción
        self.assertFalse(self.api.editar_varios(0, idx, "titulo", "poner", "x")["ok"])            # no se cambia en masa
        # Una sección cuenta con sus pruebas.
        seccion = next(n["indice"] for n in ok(self, self.api.navegacion(0, "")) if n["tipo"] == "seccion")
        self.assertGreaterEqual(ok(self, self.api.editar_varios(0, [seccion], "automatizable", "poner", "no"))["elegidos"], 1)

    def test_requisitos(self):
        ok(self, self.api.coleccion("requisitos"))
        idx = [n["indice"] for n in ok(self, self.api.navegacion(0, "")) if n["tipo"] == "requisito"][:2]
        ok(self, self.api.editar_varios(0, idx, "fase", "poner", "Fase 2"))
        self.assertEqual(ok(self, self.api.obtener(0, idx[0]))["elemento"]["fase"], "Fase 2")
        self.assertFalse(self.api.editar_varios(0, idx, "tipo", "poner", "Rarísimo")["ok"])


class BuscarEnTodo(ConCarpeta):
    def test_buscar_y_reemplazar(self):
        r = ok(self, self.api.buscar_global("panel del banco"))
        self.assertGreaterEqual(r["total"], 2)
        capitulos = {x["capitulo"] for x in r["resultados"]}
        self.assertGreater(len(capitulos), 1)                                        # en varios capítulos
        self.assertEqual(r["resultados"][0]["coincide"].lower(), "panel del banco")
        self.assertEqual(ok(self, self.api.buscar_global("x"))["total"], 0)          # mínimo dos letras
        hecho = ok(self, self.api.reemplazar_global("panel del banco", "panel del banco HIL",
                                                    [{"capitulo": x["capitulo"], "indice": x["indice"]} for x in r["resultados"]]))
        self.assertEqual(hecho["cambiados"], r["total"])
        self.assertEqual(ok(self, self.api.buscar_global("panel del banco HIL"))["total"], r["total"])

    def test_reemplaza_en_todos_aunque_no_se_muestren(self):
        r = ok(self, self.api.buscar_global("panel del banco", limite=1))
        self.assertEqual(len(r["resultados"]), 1)
        self.assertEqual(len(r["elementos"]), r["total"])
        hecho = ok(self, self.api.reemplazar_global("panel del banco", "panel del banco HIL", r["elementos"]))
        self.assertEqual(hecho["cambiados"], r["total"])

    def test_no_toca_los_id_ni_capitulos_de_otros(self):
        r = ok(self, self.api.buscar_global("DEMO-LLAM-001"))
        hecho = ok(self, self.api.reemplazar_global("DEMO-LLAM-001", "OTRO-001", [{"capitulo": x["capitulo"], "indice": x["indice"]} for x in r["resultados"]]))
        self.assertIn("DEMO-LLAM-001", [n["id"] for n in self.pruebas()])
        self.assertEqual(hecho["veces"], 0)
        # Un capítulo que edita otra persona se salta.
        otra = bloqueos.Bloqueos(persona=lambda: "Ana")
        otra.tomar(self.api._chapters[1]["path"])
        self.addCleanup(otra.cerrar)
        r = ok(self, self.api.buscar_global("panel del banco"))
        hecho = ok(self, self.api.reemplazar_global("panel del banco", "PANEL", [{"capitulo": x["capitulo"], "indice": x["indice"]} for x in r["resultados"]]))
        self.assertEqual(len(hecho["saltados"]), 1)
        self.assertIn("Ana", hecho["saltados"][0])


class CsvYTendencia(unittest.TestCase):
    def test_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            consolidado = vc.consolidar(vc.cargar(RAIZ / "ejemplos" / "validaciones" / "validacion_v2.3"))
            ruta = er.csv_validacion(consolidado, Path(tmp) / "val")
            with open(ruta, encoding="utf-8-sig", newline="") as f:
                filas = list(csv.reader(f, delimiter=";"))
            self.assertEqual(filas[0][:4], ["Capítulo", "ID", "Título", "Resultado de la versión"])
            self.assertIn("Torre: resultado", filas[0])
            self.assertEqual(len(filas), 1 + consolidado["total"])
            ejecucion = ej.cargar(RAIZ / "ejemplos" / "ejecuciones" / "2026-11-05_Torre_Luis")
            ruta = er.csv_ejecucion(ejecucion, ej.capitulos_de(ejecucion), Path(tmp) / "ej.csv")
            with open(ruta, encoding="utf-8-sig", newline="") as f:
                filas = list(csv.reader(f, delimiter=";"))
            self.assertEqual(filas[0][3], "Resultado")
            self.assertEqual(len(filas), 1 + len(ejecucion["datos"]["pruebas"]))

    def test_tendencia(self):
        t = vc.consolidar(vc.cargar(RAIZ / "ejemplos" / "validaciones" / "validacion_v2.3"))["tendencia"]
        self.assertEqual([f["nombre"] for f in t], ["Validación v2.2 (ejemplo)", "Validación v2.3 (ejemplo)"])
        self.assertEqual(t[0]["totales"]["validada"], 6)


class GitIgnore(unittest.TestCase):
    def test_anade_la_regla_una_vez(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            pruebas = repo / "pruebas"
            pruebas.mkdir(parents=True)
            (repo / ".git").mkdir()
            self.assertTrue(bloqueos.asegurar_gitignore(pruebas))
            self.assertIn(bloqueos.PATRON_GIT, (pruebas / ".gitignore").read_text(encoding="utf-8"))
            self.assertFalse(bloqueos.asegurar_gitignore(pruebas))
            # Si el repositorio ya los ignora, no se toca nada; fuera de Git, tampoco.
            otra = repo / "requisitos"
            otra.mkdir()
            (repo / ".gitignore").write_text("*.lock\n", encoding="utf-8")
            self.assertFalse(bloqueos.asegurar_gitignore(otra))
            sin_git = Path(tmp) / "suelta"
            sin_git.mkdir()
            self.assertFalse(bloqueos.asegurar_gitignore(sin_git))


if __name__ == "__main__":
    unittest.main()


class Zoom(unittest.TestCase):
    def test_limites_y_sin_ventana(self):
        from app import zoom
        self.assertEqual(zoom.limitar("1.25"), 1.25)
        self.assertEqual(zoom.limitar(10), zoom.MAXIMO)
        self.assertEqual(zoom.limitar(0.1), zoom.MINIMO)
        self.assertEqual(zoom.limitar("x"), 1.0)
        hecho, motivo = zoom.aplicar(None, 1.5)            # sin interfaz no hace nada
        self.assertFalse(hecho)
        self.assertTrue(motivo)
