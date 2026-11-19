"""Parámetros de la parametrización, repeticiones y pasadas (app/parametros.py y su uso en ejecuciones)."""
import os
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from openpyxl import Workbook

from app import ejecucion_core as ej
from app import esquema, parametros
from app import validacion_core as vc
from app.editor_api import EditorApi, apply_changes, clean_test_changes
from app.editor_core import read_chapters, save_chapter, tests_in_chapter
from app.ejecucion_api import EditorEjecucionApi

EJEMPLOS = Path(__file__).resolve().parent.parent / "ejemplos" / "yaml"
VELOCIDAD = {"parametro": "Velocidad nominal", "valores": ["0,5", "1,0", "1,6"]}
CARGA = {"parametro": "Carga en cabina", "valores": ["0 %", "100 %"]}


def ok(testcase, respuesta):
    testcase.assertTrue(respuesta["ok"], respuesta.get("error"))
    return respuesta["datos"]


class ModeloTests(unittest.TestCase):
    def test_sin_parametros_ni_repeticiones_no_hay_pasadas(self):
        self.assertEqual(parametros.pasadas({"parametrizacion": ["Texto"]}), [])
        self.assertEqual(parametros.pasadas({"parametrizacion": [{"parametro": "Modo", "valores": ["Simplex"]}]}), [])

    def test_combinaciones_por_repeticiones(self):
        prueba = {"parametrizacion": ["Tolerancia: ±5 mm", VELOCIDAD, CARGA, {"parametro": "Modo", "valores": ["Dúplex"]}],
                  "repeticiones": 2}
        pasadas = parametros.pasadas(prueba)
        self.assertEqual(len(pasadas), 3 * 2 * 2)          # el parámetro de un valor no multiplica
        self.assertEqual(pasadas[0]["clave"], "Velocidad nominal: 0,5 · Carga en cabina: 0 % #1")
        self.assertEqual(pasadas[1]["texto"], "Velocidad nominal: 0,5 · Carga en cabina: 0 % · repetición 2/2")
        self.assertEqual(pasadas[-1]["configuracion"], [("Velocidad nominal", "1,6"), ("Carga en cabina", "100 %")])
        self.assertEqual(len(set(p["clave"] for p in pasadas)), len(pasadas))

    def test_solo_repeticiones(self):
        self.assertEqual([p["clave"] for p in parametros.pasadas({"repeticiones": 3})], ["#1", "#2", "#3"])
        self.assertEqual([p["clave"] for p in parametros.pasadas({"parametrizacion": [CARGA]})],
                         ["Carga en cabina: 0 %", "Carga en cabina: 100 %"])

    def test_estado_agregado(self):
        agregado = parametros.estado_agregado
        self.assertEqual(agregado(["ok", "ok", "no_aplica"]), "ok")
        self.assertEqual(agregado(["ok", "pendiente"]), "pendiente")
        self.assertEqual(agregado(["ok", "no_ok", "pendiente"]), "no_ok")
        self.assertEqual(agregado(["ok", "bloqueada"]), "bloqueada")
        self.assertEqual(agregado(["no_aplica", "no_aplica"]), "no_aplica")

    def test_problemas(self):
        catalogo = parametros.indice_catalogo([{"parametro": "Velocidad nominal", "valores": ["0,5", "1,0"]}])
        mensajes = [m for _s, m in parametros.problemas(
            {"parametrizacion": [VELOCIDAD, {"parametro": "velocidad  NOMINAL", "valores": ["1"]}, CARGA,
                                 {"parametro": "", "valores": []}], "repeticiones": "0"}, catalogo)]
        texto = " | ".join(mensajes)
        self.assertIn("1,6 no es un valor del catálogo", texto)
        self.assertIn("«velocidad  NOMINAL» está repetido", texto)
        self.assertIn("«Carga en cabina» no está en el catálogo", texto)
        self.assertIn("sin nombre", texto)
        self.assertIn("«Repeticiones» debe ser un número", texto)
        self.assertIn("pasadas", " ".join(m for _s, m in parametros.problemas(
            {"parametrizacion": [{"parametro": f"P{i}", "valores": ["a", "b", "c"]} for i in range(6)]})))

    def test_desde_el_documento(self):
        items, repeticiones = parametros.desde_documento(
            ["Texto", "**Velocidad nominal:** 0,5 / 1,0", "**Carga:** 50 %", "**Repeticiones:** 4", "Un **dato:** suelto"])
        self.assertEqual(items, ["Texto", {"parametro": "Velocidad nominal", "valores": ["0,5", "1,0"]},
                                 {"parametro": "Carga", "valores": ["50 %"]}, "Un **dato:** suelto"])
        self.assertEqual(repeticiones, 4)

    def test_lineas_para_el_documento(self):
        self.assertEqual(parametros.lineas_documento({"parametrizacion": ["Texto", VELOCIDAD], "repeticiones": 5}),
                         ["Texto", "**Velocidad nominal:** 0,5 / 1,0 / 1,6", "**Repeticiones:** 5"])


class CatalogoTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_csv_del_ejemplo(self):
        catalogo = parametros.leer_catalogo(EJEMPLOS / "parametros.csv")
        velocidad = parametros.indice_catalogo(catalogo)["velocidadnominal"]
        self.assertEqual(velocidad["ubicacion"], "Accionamiento › Perfil › Vnom")
        self.assertEqual(velocidad["valores"], ["0,5", "1,0", "1,6", "2,5"])
        self.assertEqual(velocidad["unidad"], "m/s")
        self.assertEqual(velocidad["otros"], [["Valor por defecto", "1,0"]])

    def test_excel_con_titulo_encima_y_columnas_en_otro_orden(self):
        libro = Workbook()
        hoja = libro.active
        hoja.append(["Parámetros del configurador"])
        hoja.append(["Valores posibles", "Nombre", "Dónde"])
        hoja.append(["4\n8", "Número de paradas", "Instalación"])
        hoja.append([None, None, None])
        libro.save(self.tmp / "catalogo.xlsx")
        self.assertEqual(parametros.leer_catalogo(self.tmp / "catalogo.xlsx"),
                         [{"parametro": "Número de paradas", "ubicacion": "Instalación", "descripcion": "",
                           "valores": ["4", "8"], "unidad": "", "otros": []}])

    def test_otras_columnas_se_conservan_tal_cual(self):
        (self.tmp / "c.csv").write_text("Nombre en el configurador;Parámetro;Valor por defecto;Módulo\n"
                                        "Vnom;Velocidad nominal;1,0;\n", encoding="utf-8")
        p = parametros.leer_catalogo(self.tmp / "c.csv")[0]
        self.assertEqual((p["parametro"], p["otros"]),
                         ("Velocidad nominal", [["Nombre en el configurador", "Vnom"], ["Valor por defecto", "1,0"]]))

    def test_sin_columna_parametro_vale_la_primera(self):
        (self.tmp / "d.csv").write_text("\nSeñal;Rango\nT_puertas;2..8 s\n", encoding="utf-8")
        self.assertEqual(parametros.leer_catalogo(self.tmp / "d.csv"),
                         [{"parametro": "T_puertas", "ubicacion": "", "descripcion": "", "valores": [], "unidad": "",
                           "otros": [["Rango", "2..8 s"]]}])

    def test_vacio(self):
        (self.tmp / "vacio.csv").write_text("\n;\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "vacío"):
            parametros.leer_catalogo(self.tmp / "vacio.csv")

    def test_aztarna_yaml_indica_el_catalogo(self):
        try:
            esquema.configurar(EJEMPLOS / "pruebas")
            self.assertEqual(esquema.CATALOGO_PARAMETROS, (EJEMPLOS / "parametros.csv").resolve())
            (self.tmp / "aztarna.yaml").write_text("parametros: [1]\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "ruta del catálogo"):
                esquema.configurar(self.tmp / "aztarna.yaml")
        finally:
            esquema.configurar(None)


class EditorTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        shutil.copytree(EJEMPLOS, self.tmp / "yaml")
        self.pruebas = self.tmp / "yaml" / "pruebas"
        anterior = os.environ.get("AZTARNA_AJUSTES")
        os.environ["AZTARNA_AJUSTES"] = str(self.tmp / "ajustes.json")
        self.addCleanup(lambda: os.environ.__setitem__("AZTARNA_AJUSTES", anterior) if anterior else os.environ.pop("AZTARNA_AJUSTES", None))
        self.addCleanup(esquema.configurar, None)
        self.api = EditorApi(self.pruebas)
        ok(self, self.api.iniciar())

    def test_limpiar_parametros_y_repeticiones(self):
        limpio = clean_test_changes({"parametrizacion": ["Texto", {"parametro": " Velocidad ", "valores": ["1", " 2 ", "1", ""]},
                                                         {"parametro": "", "valores": []}],
                                     "repeticiones": "1"})
        self.assertEqual(limpio, {"parametrizacion": ["Texto", {"parametro": "Velocidad", "valores": ["1", "2"]}],
                                  "repeticiones": None})
        self.assertEqual(clean_test_changes({"repeticiones": 5})["repeticiones"], 5)
        with self.assertRaisesRegex(ValueError, "entre 1 y"):
            clean_test_changes({"repeticiones": "500"})

    def test_repeticiones_va_tras_la_parametrizacion_y_se_quita_con_una(self):
        prueba = {"id": "X", "parametrizacion": [], "situacion_inicial": [], "pasos": []}
        from ruamel.yaml.comments import CommentedMap
        mapa = CommentedMap(prueba)
        apply_changes(mapa, {"repeticiones": 3}, esquema.ORDEN)
        self.assertEqual(list(mapa), ["id", "parametrizacion", "repeticiones", "situacion_inicial", "pasos"])
        apply_changes(mapa, {"repeticiones": None}, esquema.ORDEN)
        self.assertNotIn("repeticiones", mapa)

    def test_guardar_y_ayuda_y_problemas(self):
        indice = next(n["indice"] for n in ok(self, self.api.navegacion(0, "")) if n.get("id") == "DEMO-NIV-001")
        ok(self, self.api.guardar_prueba(0, indice, {"parametrizacion": [VELOCIDAD, {"parametro": "Inventado", "valores": ["x"]}],
                                                      "repeticiones": "2"}))
        prueba = dict(tests_in_chapter(read_chapters(self.pruebas)[0])[3][1])
        self.assertEqual(prueba["repeticiones"], 2)
        ayuda = ok(self, self.api.parametros_ayuda())
        self.assertIn("Velocidad nominal", [p["parametro"] for p in ayuda["catalogo"]])
        usados = {u["parametro"]: u for u in ayuda["usados"]}
        self.assertEqual((usados["Velocidad nominal"]["valores"], usados["Inventado"]["usos"]), (["0,5", "1,0", "1,6"], 1))
        mensajes = [p["mensaje"] for p in ok(self, self.api.validar())["problemas"] if p["id"] == "DEMO-NIV-001"]
        self.assertIn("El parámetro «Inventado» no está en el catálogo de parámetros.", mensajes)

    def test_word_con_parametros(self):
        from docx import Document
        from app import yaml_a_docx
        capitulos = read_chapters(self.pruebas)
        _i, prueba = tests_in_chapter(capitulos[0])[3]
        prueba["parametrizacion"] = [VELOCIDAD]
        prueba["repeticiones"] = 5
        save_chapter(capitulos[0])
        salida = self.tmp / "pruebas.docx"
        yaml_a_docx.main([str(self.pruebas), "-o", str(salida)])
        texto = "\n".join(c.text for t in Document(salida).tables for f in t.rows for c in f.cells)
        self.assertIn("Velocidad nominal: 0,5 / 1,0 / 1,6", texto)
        self.assertIn("Repeticiones: 5", texto)


class EjecucionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name).resolve()
        shutil.copytree(EJEMPLOS, self.tmp / "yaml")
        self.pruebas = self.tmp / "yaml" / "pruebas"
        esquema.configurar(self.pruebas)
        self.addCleanup(esquema.configurar, None)
        capitulos = read_chapters(self.pruebas)
        _i, prueba = tests_in_chapter(capitulos[0])[3]           # DEMO-NIV-001
        prueba["parametrizacion"] = [VELOCIDAD, CARGA]
        save_chapter(capitulos[0])
        self.prueba = dict(prueba)
        self.claves = parametros.claves_pasadas(self.prueba)
        self.carpeta = self.tmp / "ejec"
        self.ejecucion = ej.crear(self.carpeta, self.pruebas, "Nivelación",
                                  {"incluir_ids": ["DEMO-NIV-001", "DEMO-LLAM-001"], "capitulos": ["__ninguno__"]},
                                  {"entorno_pruebas": "Torre"})

    def apuntar(self, clave, estado, **kw):
        return ej.registrar(self.ejecucion, "DEMO-NIV-001", estado, pasada=clave, pasadas_esperadas=self.claves,
                            huella_actual=ej.huella(self.prueba), **kw)

    def test_resultado_de_la_prueba_sale_de_sus_pasadas(self):
        self.assertEqual(len(self.claves), 6)
        self.apuntar(self.claves[0], "ok", ejecutor="Ana")
        self.assertEqual(ej.estado_de(self.ejecucion, "DEMO-NIV-001"), "pendiente")
        for clave in self.claves[1:]:
            self.apuntar(clave, "ok")
        cargada = ej.cargar(self.carpeta)
        self.assertEqual(ej.estado_de(cargada, "DEMO-NIV-001"), "ok")
        self.assertEqual(cargada["resultados"]["DEMO-NIV-001"]["huella"], ej.huella(self.prueba))
        self.apuntar(self.claves[2], "no_ok", observaciones="Desnivel de 7 mm")
        self.assertEqual(ej.estado_de(self.ejecucion, "DEMO-NIV-001"), "no_ok")
        self.assertEqual(len(self.ejecucion["resultados"]["DEMO-NIV-001"]["pasadas"][self.claves[2]]["intentos"]), 1)
        self.apuntar(self.claves[2], "pendiente")              # deshace: vuelve el OK anterior
        self.assertEqual(ej.estado_de(self.ejecucion, "DEMO-NIV-001"), "ok")

    def test_volver_todas_a_pendiente_quita_el_resultado(self):
        self.apuntar(self.claves[0], "ok")
        self.apuntar(self.claves[0], "pendiente")
        self.assertNotIn("DEMO-NIV-001", self.ejecucion["resultados"])

    def test_reglas(self):
        with self.assertRaisesRegex(ValueError, "cada pasada"):
            ej.registrar(self.ejecucion, "DEMO-NIV-001", "ok", pasadas_esperadas=self.claves)
        with self.assertRaisesRegex(ValueError, "no tiene la pasada"):
            self.apuntar("Velocidad nominal: 9", "ok")
        ej.registrar(self.ejecucion, "DEMO-LLAM-001", "ok")
        with self.assertRaisesRegex(ValueError, "una sola pasada"):
            ej.registrar(self.ejecucion, "DEMO-LLAM-001", "ok", pasada="#1")

    def test_notas_de_una_pasada(self):
        self.apuntar(self.claves[1], "no_ok")
        ej.editar_notas(self.ejecucion, "DEMO-NIV-001", pasada=self.claves[1], observaciones="Ruido", incidencia="BUG-1")
        pasada = ej.cargar(self.carpeta)["resultados"]["DEMO-NIV-001"]["pasadas"][self.claves[1]]
        self.assertEqual((pasada["observaciones"], pasada["incidencia"]), ("Ruido", "BUG-1"))
        with self.assertRaisesRegex(ValueError, "esta pasada"):
            ej.editar_notas(self.ejecucion, "DEMO-NIV-001", pasada=self.claves[0], observaciones="x")

    def test_resumen_y_cierre(self):
        self.apuntar(self.claves[0], "no_ok")
        ej.registrar(self.ejecucion, "DEMO-LLAM-001", "ok")
        resumen = ej.resumen(self.ejecucion, read_chapters(self.pruebas))
        self.assertEqual(resumen["pasadas"], {"total": 6, "hechas": 1})
        niv = next(p for p in resumen["pruebas"] if p["id"] == "DEMO-NIV-001")
        self.assertEqual((niv["estado"], niv["pasadas"]), ("no_ok", {"total": 6, "hechas": 1}))
        self.assertIn(f"Pasada «{self.claves[0]}»: NO OK sin observaciones.", [p["mensaje"] for p in resumen["problemas"]])
        with self.assertRaisesRegex(ValueError, r"pasadas pendientes en DEMO-NIV-001 \(5\)"):
            ej.cerrar(self.ejecucion, read_chapters(self.pruebas))
        for clave in self.claves[1:]:
            self.apuntar(clave, "no_aplica")
        ej.cerrar(self.ejecucion, read_chapters(self.pruebas))

    def test_la_validacion_usa_el_resultado_de_la_prueba(self):
        val = vc.crear(self.tmp / "val", self.tmp / "yaml", "V", "2.4",
                       {"incluir_ids": ["DEMO-NIV-001"], "capitulos": ["__ninguno__"]})
        vc.anadir_ejecucion(val, self.carpeta)
        for clave in self.claves:
            self.apuntar(clave, "ok")
        celda = next(p for p in vc.consolidar(val)["pruebas"] if p["id"] == "DEMO-NIV-001")["entornos"]["Torre"]
        self.assertEqual(celda["estado"], "ok")

    def test_robot_deja_fuera_las_pruebas_con_pasadas(self):
        from app import robot_core
        robot = {"generador": "Robot", "tests": [{"nombre": "Nivelar", "ids": ["DEMO-NIV-001"], "estado": "PASS",
                                                  "fin": None, "imagenes": [], "mensaje": ""}]}
        plan = robot_core.plan(self.ejecucion, robot, read_chapters(self.pruebas))
        self.assertEqual((plan["resultados"], plan["con_pasadas"]), ([], ["DEMO-NIV-001"]))

    def test_api(self):
        anterior = os.environ.get("AZTARNA_AJUSTES")
        os.environ["AZTARNA_AJUSTES"] = str(self.tmp / "ajustes.json")
        self.addCleanup(lambda: os.environ.__setitem__("AZTARNA_AJUSTES", anterior) if anterior else os.environ.pop("AZTARNA_AJUSTES", None))
        api = EditorEjecucionApi()
        ok(self, api.ejecucion_abrir(str(self.carpeta)))
        self.assertIn("elige la pasada", api.ejecucion_registrar("DEMO-NIV-001", "ok")["error"])
        estado = ok(self, api.ejecucion_registrar("DEMO-NIV-001", "no_ok", "Falla", "", [], "Ana", self.claves[3]))
        self.assertEqual(estado["resumen"]["pasadas"]["hechas"], 1)
        ok(self, api.ejecucion_registrar("DEMO-NIV-001", "no_ok", "Falla a 1,0", "", [], "Ana", self.claves[3]))   # solo notas
        info = ok(self, api.ejecucion_resultado("DEMO-NIV-001"))
        self.assertEqual([p["clave"] for p in info["pasadas"]], self.claves)
        pasada = info["pasadas"][3]["resultado"]
        self.assertEqual((pasada["observaciones"], "intentos" in pasada), ("Falla a 1,0", False))
        self.assertEqual(info["resultado"]["estado"], "no_ok")


if __name__ == "__main__":
    unittest.main()
