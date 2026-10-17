"""Pruebas de la importación de resultados de Robot Framework (robot_core.py)."""
import json
import os
import shutil
import subprocess
import sys
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app import ejecucion_core as ej
from app import robot_core as rc
from app.editor_core import read_chapters
from app.ejecucion_api import EditorEjecucionApi

RAIZ = Path(__file__).resolve().parent.parent
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
        shutil.copytree(RAIZ / "ejemplos" / "yaml", self.tmp / "yaml")
        self.pruebas = self.tmp / "yaml" / "pruebas"
        self.ejecucion = ej.crear(self.tmp / "camp", self.pruebas, "Robot", {"etiquetas": ["regresion"]})

    def capitulos(self):
        return read_chapters(self.pruebas)

    def test_plan_sin_cambiar_nada(self):
        ej.registrar(self.ejecucion, "DEMO-LLAM-002", "no_ok", observaciones="manual")
        antes = (self.tmp / "camp" / ej.ARCHIVO_RESULTADOS).read_text()
        plan = rc.plan(self.ejecucion, rc.leer_output(SALIDA_RF7), self.capitulos())
        self.assertEqual(plan["totales"], {"ok": 4, "no_ok": 1, "no_aplica": 1})
        self.assertEqual(plan["sustituyen_manual"], ["DEMO-LLAM-002"])
        self.assertEqual(plan["sin_id"], ["Diagnóstico del bus sin enlazar"])
        self.assertEqual(plan["inexistentes"], ["DEMO-OLD-999"])
        self.assertIn("DEMO-SEG-001", plan["sin_robot"])
        self.assertEqual(antes, (self.tmp / "camp" / ej.ARCHIVO_RESULTADOS).read_text())

    def test_importar_registra_resultados_y_copia_evidencias(self):
        ej.registrar(self.ejecucion, "DEMO-NIV-001", "no_ok", observaciones="Manual", incidencia="BUG-130")
        datos = rc.importar(self.ejecucion, SALIDA_RF7, self.capitulos())
        ejecucion = ej.cargar(self.tmp / "camp")
        niv = ejecucion["resultados"]["DEMO-NIV-001"]
        self.assertEqual((niv["estado"], niv["origen"], niv["ejecutor"]), ("no_ok", "robot", "Robot Framework"))
        self.assertIn("Desnivel de 7 mm", niv["observaciones"])
        self.assertEqual(niv["intentos"][0]["incidencia"], "BUG-130")      # el manual queda en el historial
        carpeta = self.tmp / "camp" / datos["carpeta_evidencias"]
        for nombre in ("output.xml", "log.html", "report.html", "captura-registro_eventos.png"):
            self.assertTrue((carpeta / nombre).is_file(), nombre)
        self.assertEqual(len(niv["evidencias"]), 2)
        self.assertEqual(ejecucion["resultados"]["DEMO-CAN-001"]["estado"], "no_aplica")
        self.assertEqual(ej.estado_de(ejecucion, "DEMO-SEG-001"), "pendiente")
        self.assertEqual(ej.resumen(ejecucion, self.capitulos())["problemas"], [])

    def test_importar_dos_veces_no_duplica_el_historial(self):
        rc.importar(self.ejecucion, SALIDA_RF7, self.capitulos())
        rc.importar(ej.cargar(self.tmp / "camp"), SALIDA_RF7, self.capitulos())
        self.assertNotIn("intentos", ej.cargar(self.tmp / "camp")["resultados"]["DEMO-LLAM-001"])

    def test_ejecucion_cerrada_no_admite_importar(self):
        ejecucion = ej.crear(self.tmp / "manual", self.pruebas, "Manual", {"etiquetas": ["manual"]})
        ej.registrar(ejecucion, "DEMO-VAR-002", "ok")
        ej.cerrar(ejecucion, self.capitulos())
        with self.assertRaisesRegex(ValueError, "cerrada"):
            rc.importar(ej.cargar(self.tmp / "manual"), SALIDA_RF7, self.capitulos())

    def test_linea_de_comandos(self):
        orden = [sys.executable, str(RAIZ / "herramientas.py"), "robot", str(self.tmp / "camp"), str(SALIDA_RF7)]
        simulado = subprocess.run([*orden, "--simular"], capture_output=True, text=True, cwd=RAIZ)
        self.assertEqual(simulado.returncode, 0, simulado.stderr)
        self.assertIn("Se importarían: 4 OK, 1 NO OK, 1 no aplica", simulado.stdout)
        self.assertEqual(ej.cargar(self.tmp / "camp")["resultados"], {})
        real = subprocess.run(orden, capture_output=True, text=True, cwd=RAIZ)
        self.assertEqual(real.returncode, 0, real.stderr)
        self.assertEqual(len(ej.cargar(self.tmp / "camp")["resultados"]), 6)

    def test_api(self):
        api = EditorEjecucionApi()
        self.assertTrue(api.ejecucion_abrir(str(self.tmp / "camp"))["ok"])
        plan = api.ejecucion_robot_previsualizar(str(SALIDA_RF7))
        self.assertTrue(plan["ok"], plan.get("error"))
        estado = api.ejecucion_robot_importar(str(SALIDA_RF7))
        self.assertTrue(estado["ok"], estado.get("error"))
        self.assertEqual(estado["datos"]["resumen"]["totales"]["ok"], 4)


class EscaneoTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def escribir(self, ruta, texto):
        ruta = self.dir / ruta
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(texto, encoding="utf-8")

    def test_ejemplo(self):
        tests = {t["nombre"]: t["ids"] for t in rc.escanear_suites(RAIZ / "ejemplos" / "robot")["tests"]}
        self.assertEqual(len(tests), 8)
        self.assertEqual(tests["Apertura y reapertura de puertas"], ["DEMO-PUER-001", "DEMO-PUER-002"])
        self.assertEqual(tests["Diagnóstico del bus sin enlazar"], [])

    def test_etiquetas_de_archivo_carpeta_continuacion_y_comentarios(self):
        self.escribir("suite/__init__.robot", "*** Settings ***\nTest Tags    banco\n")
        self.escribir("suite/a.robot", (
            "*** Settings ***\nForce Tags    id:COMUN-1\nDefault Tags    id:DEF-1\n\n"
            "*** Test Cases ***\n"
            "Uno\n    [Tags]    id:A-1    # comentario\n    ...    id:A-2\n    Log    x\n"
            "Dos\n    Log    sin etiquetas propias\n"
            "Tres\n    [Tags]    id:${VARIABLE}    id:B-1\n"
            "# Comentario\n"
        ))
        self.escribir("suite/b.robot", "| *** Test Cases *** |\n| Cuatro | [Tags] | id:C-1 |\n|        | Log    | x      |\n")
        self.escribir("otra.resource", "*** Keywords ***\nNada\n    Log    x\n")
        tests = {t["nombre"]: t for t in rc.escanear_suites(self.dir)["tests"]}
        self.assertEqual(tests["Uno"]["ids"], ["COMUN-1", "A-1", "A-2"])
        self.assertIn("banco", tests["Uno"]["etiquetas"])
        self.assertEqual(tests["Dos"]["ids"], ["COMUN-1", "DEF-1"])
        self.assertEqual(tests["Tres"]["ids"], ["COMUN-1", "B-1"])
        self.assertEqual(tests["Cuatro"]["ids"], ["C-1"])
        self.assertEqual(tests["Uno"]["linea"], 6)

    def test_cobertura(self):
        capitulos = read_chapters(RAIZ / "ejemplos" / "yaml" / "pruebas")
        c = rc.cobertura(capitulos, rc.escanear_suites(RAIZ / "ejemplos" / "robot"))
        self.assertIn("DEMO-NIV-001", c["cubiertas"])
        self.assertEqual(len(c["por_id"]["DEMO-NIV-001"]), 2)
        self.assertEqual(c["inexistentes"], ["DEMO-OLD-999"])
        self.assertEqual(c["hecho_sin_robot"], ["DEMO-DIAG-001"])
        self.assertEqual(c["sin_id"][0]["nombre"], "Diagnóstico del bus sin enlazar")

    def test_keywords_del_ejemplo(self):
        datos = rc.escanear_keywords([RAIZ / "ejemplos" / "robot"])
        self.assertEqual(datos["errores"], [])
        kws = {k["nombre"]: k for k in datos["keywords"]}
        self.assertEqual([a["nombre"] for a in kws["Simular Viaje"]["argumentos"]], ["origen", "destino"])
        self.assertEqual(kws["Comprobar Desnivel"]["usos"], 2)
        self.assertEqual(kws["Comprobar la alarma"]["argumentos"][1], {"nombre": "timeout", "obligatorio": False, "defecto": "5 s"})
        self.assertEqual(kws["Llevar la cabina a ${planta} y esperar a que cierre puertas"]["archivo"], "banco.resource")
        # Python: el argumento incrustado no se repite en la lista; las privadas no son keywords.
        registrar = kws["Registrar una llamada de piso en ${planta}"]
        self.assertEqual((registrar["origen"], registrar["argumentos"]), ("python", []))
        self.assertEqual([a["nombre"] for a in kws["Leer Trama Can"]["argumentos"]], ["identificador", "byte", "timeout"])
        self.assertFalse(any("Conectar" in n for n in kws))

    def test_keywords_de_python_solo_si_es_libreria(self):
        self.escribir("tests/a.robot", (
            "*** Settings ***\nLibrary    ../lib/banco.py\nLibrary    paquete.Equipo\n\n"
            "*** Test Cases ***\nUno\n    ${x}=    Leer Valor    1\n    FOR    ${i}    IN    1    2\n"
            "        Leer valor    ${i}\n    END\n    banco.Leer_Valor    2\n"
        ))
        self.escribir("lib/banco.py", 'def leer_valor(canal, *resto, modo="a", **otros):\n    """Lee.\n\n    Más."""\n\ndef _privada():\n    pass\n')
        self.escribir("lib/utilidades.py", (
            "from robot.api.deco import keyword, not_keyword\n"
            "def ayuda():\n    pass\n"
            "@keyword('Abrir el relé ${n}')\ndef abrir(n):\n    pass\n"
        ))
        self.escribir("lib/paquete/Equipo.py", (
            "class Equipo:\n    ROBOT_AUTO_KEYWORDS = True\n"
            "    def __init__(self):\n        pass\n    def encender(self, voltios=24):\n        pass\n"
            "    @not_keyword\n    def interna(self):\n        pass\n"
            "class Otra:\n    def nada(self):\n        pass\n"
        ))
        self.escribir("lib/sin_auto.py", "ROBOT_AUTO_KEYWORDS = False\ndef escondida():\n    pass\n")
        self.escribir("lib/roto.py", "def (:\n")
        datos = rc.escanear_keywords([self.dir / "tests", self.dir / "lib"])
        kws = {k["nombre"]: k for k in datos["keywords"]}
        self.assertEqual(sorted(kws), ["Abrir el relé ${n}", "Encender", "Leer Valor"])
        self.assertEqual(kws["Leer Valor"]["usos"], 3)
        self.assertEqual(kws["Leer Valor"]["doc"], "Lee.")
        self.assertEqual([a["nombre"] for a in kws["Leer Valor"]["argumentos"]], ["canal", "*resto", "modo", "**otros"])
        self.assertEqual(kws["Encender"]["archivo"], "paquete/Equipo.py")
        self.assertTrue(any("roto.py" in e for e in datos["errores"]))

    def test_preparar_ejecucion(self):
        args = rc.preparar_ejecucion(self.dir / "salida", self.dir / "suites", ["DEMO-ANDEN-1"], ["--loglevel", "DEBUG"])
        texto = (self.dir / "salida" / "argumentos.txt").read_text()
        self.assertIn("--include id:demo-anden-1", texto)       # en minúsculas: AND/OR/NOT no se confunden
        self.assertTrue((self.dir / "salida" / "progreso_editor.py").is_file())
        self.assertEqual(args[-3:], ["--loglevel", "DEBUG", str(self.dir / "suites")])


# Robot falso: lee el archivo de argumentos, escribe el avance como el listener
# y deja un output.xml de ejemplo. Así se prueba el lanzamiento sin instalar Robot.
ROBOT_FALSO = r"""
import json, shutil, sys
from pathlib import Path
if "--version" in sys.argv:
    print("Robot Framework 7.0 (falso)"); sys.exit(251)
lineas = Path(sys.argv[sys.argv.index("--argumentfile") + 1]).read_text().splitlines()
salida = Path(next(l.split(" ", 1)[1] for l in lineas if l.startswith("--outputdir")))
progreso = Path(next(l.split(" ", 1)[1] for l in lineas if l.startswith("--listener")).split(";")[1])
with open(progreso, "a") as f:
    f.write(json.dumps({"tipo": "inicio", "total": 1}) + "\n")
    f.write(json.dumps({"tipo": "fin_test", "nombre": "Uno", "estado": "PASS", "mensaje": ""}) + "\n")
    f.write(json.dumps({"tipo": "fin"}) + "\n")
shutil.copy(%r, salida / "output.xml")
print("Output:  " + str(salida / "output.xml"))
sys.exit(1)
""" % str(SALIDA_RF7)


class LanzarTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.anterior = os.environ.get("AZTARNA_AJUSTES")
        os.environ["AZTARNA_AJUSTES"] = str(self.tmp / "ajustes.json")
        self.addCleanup(self.restaurar)
        for carpeta in ("yaml", "robot"):
            shutil.copytree(RAIZ / "ejemplos" / carpeta, self.tmp / carpeta)
        falso = self.tmp / "robot_falso.py"
        falso.write_text(ROBOT_FALSO)
        self.comando = f'"{sys.executable}" "{falso}"'
        ej.crear(self.tmp / "camp", self.tmp / "yaml", "Robot", {"etiquetas": ["regresion"]})
        self.api = EditorEjecucionApi()
        self.assertTrue(self.api.ejecucion_abrir(str(self.tmp / "camp"))["ok"])

    def restaurar(self):
        if self.anterior is None:
            os.environ.pop("AZTARNA_AJUSTES", None)
        else:
            os.environ["AZTARNA_AJUSTES"] = self.anterior

    def configurar(self):
        r = self.api.robot_guardar_config({"suites": str(self.tmp / "robot"), "comando": self.comando})
        self.assertTrue(r["ok"], r.get("error"))
        return r["datos"]["cobertura"]

    def test_configuracion_cobertura_y_validacion(self):
        self.assertIsNone(self.api.robot_cobertura()["datos"])
        self.assertFalse(self.api.robot_guardar_config({"suites": str(self.tmp / "no-existe")})["ok"])
        cobertura = self.configurar()
        self.assertEqual(len(cobertura["cubiertas"]), 6)
        guardado = json.loads((self.tmp / "ajustes.json").read_text())
        self.assertIn(str((self.tmp / "yaml" / "pruebas").resolve()), guardado["robot"])
        avisos = [p["mensaje"] for p in self.api.validar()["datos"]["problemas"]]
        self.assertTrue(any("DEMO-DIAG-001" in m for m in avisos))
        self.assertEqual(self.api.robot_comprobar(self.comando)["datos"]["version"], "Robot Framework 7.0 (falso)")

    def test_keywords_de_la_configuracion(self):
        self.assertIsNone(self.api.robot_keywords()["datos"])
        (self.tmp / "libs").mkdir()
        (self.tmp / "libs" / "extra.resource").write_text("*** Keywords ***\nPulsar el botón ${n}\n    Log    ${n}\n", encoding="utf-8")
        self.assertFalse(self.api.robot_guardar_config({"suites": str(self.tmp / "robot"), "keywords": str(self.tmp / "no")})["ok"])
        r = self.api.robot_guardar_config({"suites": str(self.tmp / "robot"), "keywords": str(self.tmp / "libs")})
        self.assertTrue(r["ok"], r.get("error"))
        nombres = [k["nombre"] for k in r["datos"]["keywords"]["keywords"]]
        self.assertIn("Pulsar el botón ${n}", nombres)
        self.assertIn("Simular Viaje", nombres)
        self.assertEqual(self.api.robot_keywords()["datos"]["keywords"][0]["nombre"], nombres[0])

    def test_filtro_con_y_sin_robot(self):
        self.configurar()
        con = self.api.ejecucion_previsualizar({"robot": ["con"]})["datos"]
        sin = self.api.ejecucion_previsualizar({"robot": ["sin"]})["datos"]
        self.assertEqual(len(con), 6)
        self.assertEqual(len(con) + len(sin), 14)
        self.assertEqual(self.api.ejecucion_opciones()["datos"]["robot"], ["con", "sin"])

    def test_lanzar_seguir_e_importar(self):
        self.configurar()
        datos = self.api.ejecucion_robot_lanzar(["DEMO-LLAM-001"])
        self.assertTrue(datos["ok"], datos.get("error"))
        for _ in range(100):
            progreso = self.api.ejecucion_robot_progreso()["datos"]
            if not progreso["en_marcha"]:
                break
            time.sleep(0.1)
        self.assertFalse(progreso["en_marcha"])
        self.assertEqual(progreso["total"], 1)
        self.assertEqual(progreso["terminados"][0]["estado"], "PASS")
        self.assertTrue(progreso["output"])
        importado = self.api.ejecucion_robot_importar(progreso["output"])["datos"]["importacion"]
        # Los resultados ya estaban dentro de la ejecución: no se copian a otra carpeta.
        self.assertEqual(Path(datos["datos"]["carpeta"]).name, Path(importado["carpeta_evidencias"]).name)
        self.assertFalse((Path(datos["datos"]["carpeta"]) / "__pycache__").exists())

    def test_lanzar_sin_configurar(self):
        r = self.api.ejecucion_robot_lanzar(["DEMO-LLAM-001"])
        self.assertFalse(r["ok"])
        self.assertIn("Configura", r["error"])


if __name__ == "__main__":
    unittest.main()
