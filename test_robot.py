"""Pruebas de la importación de resultados de Robot Framework (robot_core.py)."""
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import ejecucion_core as ej
import robot_core as rc
from editor_core import read_chapters
from ejecucion_api import EditorEjecucionApi

RAIZ = Path(__file__).parent
SALIDA_RF7 = RAIZ / "ejemplos" / "robot" / "resultados" / "output.xml"
SALIDA_RF6 = RAIZ / "ejemplos" / "robot" / "resultados_rf6" / "output.xml"


class LecturaTests(unittest.TestCase):
    def test_rf6_y_rf7_se_leen_igual(self):
        rf7, rf6 = rc.leer_output(SALIDA_RF7), rc.leer_output(SALIDA_RF6)
        self.assertIn("Robot 7", rf7["generador"])
        self.assertIn("Robot 6", rf6["generador"])
        clave = lambda t: (t["nombre"], t["ids"], t["estado"], t["mensaje"], t["imagenes"])
        self.assertEqual([clave(t) for t in rf7["tests"]], [clave(t) for t in rf6["tests"]])
        self.assertTrue(all(t["fin"] is not None for t in rf6["tests"] + rf7["tests"]))

    def test_tests_etiquetas_y_capturas(self):
        tests = {t["nombre"]: t for t in rc.leer_output(SALIDA_RF7)["tests"]}
        fallo = tests["Nivelación con carga máxima"]
        self.assertEqual((fallo["estado"], fallo["ids"]), ("FAIL", ["DEMO-NIV-001"]))
        self.assertEqual(fallo["mensaje"], "Desnivel de 7 mm: supera el límite de ±5 mm")
        self.assertEqual(fallo["imagenes"], ["captura-registro_eventos.png"])
        self.assertEqual(tests["Trama de estado de cabina"]["estado"], "SKIP")
        self.assertEqual(tests["Apertura y reapertura de puertas"]["ids"], ["DEMO-PUER-001", "DEMO-PUER-002"])
        self.assertEqual(tests["Diagnóstico del bus sin enlazar"]["ids"], [])

    def test_estado_consolidado(self):
        self.assertEqual(rc.estado_consolidado(["PASS", "FAIL"]), "no_ok")
        self.assertEqual(rc.estado_consolidado(["PASS", "SKIP"]), "ok")
        self.assertEqual(rc.estado_consolidado(["SKIP"]), "no_aplica")
        self.assertIsNone(rc.estado_consolidado(["NOT RUN"]))

    def test_archivo_que_no_es_de_robot(self):
        with TemporaryDirectory() as tmp:
            malo = Path(tmp) / "x.xml"
            malo.write_text("<otro/>")
            with self.assertRaisesRegex(ValueError, "no es un output.xml"):
                rc.leer_output(malo)
            malo.write_text("<robot")
            with self.assertRaisesRegex(ValueError, "no es un XML válido"):
                rc.leer_output(malo)


class ImportarTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.pruebas = self.tmp / "yaml"
        shutil.copytree(RAIZ / "ejemplos" / "yaml", self.pruebas)
        self.campaña = ej.crear(self.tmp / "camp", self.pruebas, "Robot", {"etiquetas": ["regresion"]})

    def capitulos(self):
        return read_chapters(self.pruebas)

    def test_plan_sin_cambiar_nada(self):
        ej.registrar(self.campaña, "DEMO-LLAM-002", "no_ok", observaciones="manual")
        antes = (self.tmp / "camp" / ej.ARCHIVO_RESULTADOS).read_text()
        plan = rc.plan(self.campaña, rc.leer_output(SALIDA_RF7), self.capitulos())
        self.assertEqual(plan["totales"], {"ok": 4, "no_ok": 1, "no_aplica": 1})
        self.assertEqual(plan["sustituyen_manual"], ["DEMO-LLAM-002"])
        self.assertEqual(plan["sin_id"], ["Diagnóstico del bus sin enlazar"])
        self.assertEqual(plan["inexistentes"], ["DEMO-OLD-999"])
        self.assertIn("DEMO-SEG-001", plan["sin_robot"])
        self.assertEqual(antes, (self.tmp / "camp" / ej.ARCHIVO_RESULTADOS).read_text())

    def test_importar_registra_resultados_y_copia_evidencias(self):
        ej.registrar(self.campaña, "DEMO-NIV-001", "no_ok", observaciones="Manual", incidencia="BUG-130")
        datos = rc.importar(self.campaña, SALIDA_RF7, self.capitulos())
        campaña = ej.cargar(self.tmp / "camp")
        niv = campaña["resultados"]["DEMO-NIV-001"]
        self.assertEqual((niv["estado"], niv["origen"], niv["ejecutor"]), ("no_ok", "robot", "Robot Framework"))
        self.assertIn("Desnivel de 7 mm", niv["observaciones"])
        self.assertEqual(niv["intentos"][0]["incidencia"], "BUG-130")      # el manual queda en el historial
        carpeta = self.tmp / "camp" / datos["carpeta_evidencias"]
        for nombre in ("output.xml", "log.html", "report.html", "captura-registro_eventos.png"):
            self.assertTrue((carpeta / nombre).is_file(), nombre)
        self.assertEqual(len(niv["evidencias"]), 2)
        self.assertEqual(campaña["resultados"]["DEMO-CAN-001"]["estado"], "no_aplica")
        self.assertEqual(ej.estado_de(campaña, "DEMO-SEG-001"), "pendiente")
        self.assertEqual(ej.resumen(campaña, self.capitulos())["problemas"], [])

    def test_importar_dos_veces_no_duplica_el_historial(self):
        rc.importar(self.campaña, SALIDA_RF7, self.capitulos())
        rc.importar(ej.cargar(self.tmp / "camp"), SALIDA_RF7, self.capitulos())
        self.assertNotIn("intentos", ej.cargar(self.tmp / "camp")["resultados"]["DEMO-LLAM-001"])

    def test_campaña_cerrada_no_admite_importar(self):
        campaña = ej.crear(self.tmp / "manual", self.pruebas, "Manual", {"etiquetas": ["manual"]})
        ej.registrar(campaña, "DEMO-VAR-002", "ok")
        ej.cerrar(campaña, self.capitulos())
        with self.assertRaisesRegex(ValueError, "cerrada"):
            rc.importar(ej.cargar(self.tmp / "manual"), SALIDA_RF7, self.capitulos())

    def test_linea_de_comandos(self):
        orden = [sys.executable, str(RAIZ / "importar_robot.py"), str(self.tmp / "camp"), str(SALIDA_RF7)]
        simulado = subprocess.run([*orden, "--simular"], capture_output=True, text=True, cwd=RAIZ)
        self.assertEqual(simulado.returncode, 0, simulado.stderr)
        self.assertIn("Se importarían: 4 OK, 1 NO OK, 1 no aplica", simulado.stdout)
        self.assertEqual(ej.cargar(self.tmp / "camp")["resultados"], {})
        real = subprocess.run(orden, capture_output=True, text=True, cwd=RAIZ)
        self.assertEqual(real.returncode, 0, real.stderr)
        self.assertEqual(len(ej.cargar(self.tmp / "camp")["resultados"]), 6)

    def test_api(self):
        api = EditorEjecucionApi()
        self.assertTrue(api.campana_abrir(str(self.tmp / "camp"))["ok"])
        plan = api.campana_robot_previsualizar(str(SALIDA_RF7))
        self.assertTrue(plan["ok"], plan.get("error"))
        estado = api.campana_robot_importar(str(SALIDA_RF7))
        self.assertTrue(estado["ok"], estado.get("error"))
        self.assertEqual(estado["datos"]["resumen"]["totales"]["ok"], 4)


if __name__ == "__main__":
    unittest.main()
