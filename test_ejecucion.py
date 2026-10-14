"""Pruebas de las campañas de ejecución (ejecucion_core.py)."""
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import ejecucion_core as ej
from editor_core import read_chapters, save_chapter

EJEMPLOS = Path(__file__).parent / "ejemplos" / "yaml"


class CampañaBase(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.pruebas = self.tmp / "pruebas"
        shutil.copytree(EJEMPLOS, self.pruebas)
        self.carpeta = self.tmp / "campañas" / "regresion"

    def tearDown(self):
        self._tmp.cleanup()

    def capitulos(self):
        return read_chapters(self.pruebas)

    def crear(self, filtro=None, **datos):
        return ej.crear(self.carpeta, self.pruebas, "Regresión v2.3",
                        filtro if filtro is not None else {"etiquetas": ["regresion"]}, datos)


class SeleccionTests(CampañaBase):
    def ids(self, filtro):
        return [item["id"] for item in ej.seleccionar(self.capitulos(), filtro)]

    def test_etiquetas_basta_con_una(self):
        ids = self.ids({"etiquetas": ["smoke", "manual"]})
        self.assertEqual(ids, ["DEMO-LLAM-001", "DEMO-NIV-001", "DEMO-PUER-001", "DEMO-SEG-001", "DEMO-VAR-002"])

    def test_se_combinan_criterios(self):
        ids = self.ids({"etiquetas": ["regresion"], "criticidad": ["alta"], "capitulos": ["01_ejemplo_basico.yaml"]})
        self.assertEqual(ids, ["DEMO-LLAM-001", "DEMO-LLAM-003", "DEMO-NIV-001"])

    def test_incluir_y_excluir_ids_mandan(self):
        ids = self.ids({"etiquetas": ["smoke"], "incluir_ids": ["DEMO-DIAG-001"], "excluir_ids": ["DEMO-NIV-001"]})
        self.assertIn("DEMO-DIAG-001", ids)
        self.assertNotIn("DEMO-NIV-001", ids)

    def test_sin_criterio_entran_todas(self):
        self.assertEqual(len(self.ids({})), 14)

    def test_opciones_para_la_interfaz(self):
        opciones = ej.opciones_filtro(self.capitulos())
        self.assertIn("regresion", opciones["etiquetas"])
        self.assertEqual(opciones["criticidad"], ["alta", "baja", "media"])
        self.assertEqual(len(opciones["capitulos"]), 4)


class CrearTests(CampañaBase):
    def test_crea_la_campaña_con_la_lista_congelada(self):
        campaña = self.crear(objeto="Firmware 2.3.0-rc2", responsable="Unai")
        cargada = ej.cargar(self.carpeta)
        self.assertEqual(cargada["datos"]["nombre"], "Regresión v2.3")
        self.assertEqual(cargada["datos"]["objeto"], "Firmware 2.3.0-rc2")
        self.assertEqual(cargada["datos"]["estado"], "abierta")
        self.assertEqual(len(ej.ids_de(cargada)), 10)
        self.assertEqual(ej.ids_de(cargada), ej.ids_de(campaña))
        self.assertTrue(all(len(p["huella"]) == 12 for p in cargada["datos"]["pruebas"]))
        self.assertTrue((self.carpeta / ej.CARPETA_EVIDENCIAS).is_dir())

    def test_no_toca_los_yaml_de_pruebas(self):
        antes = {p.name: p.read_bytes() for p in self.pruebas.glob("*.yaml")}
        campaña = self.crear()
        ej.registrar(campaña, "DEMO-LLAM-001", "ok")
        ej.registrar(campaña, "DEMO-LLAM-002", "no_ok", observaciones="No se ilumina")
        self.assertEqual(antes, {p.name: p.read_bytes() for p in self.pruebas.glob("*.yaml")})

    def test_rechaza_carpeta_con_contenido_y_filtro_sin_pruebas(self):
        self.carpeta.mkdir(parents=True)
        (self.carpeta / "otra.txt").write_text("x")
        with self.assertRaisesRegex(ValueError, "carpeta vacía"):
            self.crear()
        with self.assertRaisesRegex(ValueError, "Ninguna prueba"):
            ej.crear(self.tmp / "vacia", self.pruebas, "X", {"etiquetas": ["no-existe"]})

    def test_rechaza_ids_repetidos(self):
        capitulo = self.capitulos()[0]
        capitulo["data"]["contenido"][2]["prueba"]["id"] = "DEMO-LLAM-002"
        save_chapter(capitulo)
        with self.assertRaisesRegex(ValueError, "repetido"):
            self.crear()

    def test_la_huella_ignora_el_nivel_pero_no_el_contenido(self):
        prueba = {"id": "A", "titulo": "T", "nivel": 3}
        self.assertEqual(ej.huella(prueba), ej.huella({**prueba, "nivel": 5}))
        self.assertNotEqual(ej.huella(prueba), ej.huella({**prueba, "titulo": "Otro"}))


class ResultadosTests(CampañaBase):
    def setUp(self):
        super().setUp()
        self.campaña = self.crear()

    def test_registrar_y_cargar(self):
        ej.registrar(self.campaña, "DEMO-LLAM-001", "ok", ejecutor="Unai", observaciones="Sin incidencias")
        cargada = ej.cargar(self.carpeta)
        self.assertEqual(ej.estado_de(cargada, "DEMO-LLAM-001"), "ok")
        self.assertEqual(cargada["resultados"]["DEMO-LLAM-001"]["ejecutor"], "Unai")
        self.assertEqual(ej.estado_de(cargada, "DEMO-LLAM-002"), "pendiente")

    def test_un_nuevo_resultado_guarda_el_anterior_en_el_historial(self):
        ej.registrar(self.campaña, "DEMO-LLAM-001", "no_ok", observaciones="No nivela", incidencia="BUG-1")
        ej.registrar(self.campaña, "DEMO-LLAM-001", "ok")
        resultado = ej.cargar(self.carpeta)["resultados"]["DEMO-LLAM-001"]
        self.assertEqual(resultado["estado"], "ok")
        self.assertEqual(len(resultado["intentos"]), 1)
        self.assertEqual(resultado["intentos"][0]["incidencia"], "BUG-1")

    def test_volver_a_pendiente_recupera_el_resultado_anterior(self):
        ej.registrar(self.campaña, "DEMO-LLAM-001", "no_ok", observaciones="Falla")
        ej.registrar(self.campaña, "DEMO-LLAM-001", "ok")
        ej.registrar(self.campaña, "DEMO-LLAM-001", "pendiente")
        self.assertEqual(ej.estado_de(self.campaña, "DEMO-LLAM-001"), "no_ok")
        ej.registrar(self.campaña, "DEMO-LLAM-001", "pendiente")
        self.assertEqual(ej.estado_de(self.campaña, "DEMO-LLAM-001"), "pendiente")
        self.assertNotIn("DEMO-LLAM-001", ej.cargar(self.carpeta)["resultados"])

    def test_editar_notas_no_crea_otro_intento(self):
        ej.registrar(self.campaña, "DEMO-LLAM-001", "no_ok")
        ej.editar_notas(self.campaña, "DEMO-LLAM-001", observaciones="Detalle", incidencia="BUG-7")
        resultado = ej.cargar(self.carpeta)["resultados"]["DEMO-LLAM-001"]
        self.assertEqual((resultado["observaciones"], resultado["incidencia"]), ("Detalle", "BUG-7"))
        self.assertNotIn("intentos", resultado)

    def test_rechaza_estado_o_prueba_desconocidos(self):
        with self.assertRaisesRegex(ValueError, "Estado no válido"):
            ej.registrar(self.campaña, "DEMO-LLAM-001", "regular")
        with self.assertRaisesRegex(ValueError, "no forma parte"):
            ej.registrar(self.campaña, "DEMO-DIAG-001", "ok")


class ResumenTests(CampañaBase):
    def setUp(self):
        super().setUp()
        self.campaña = self.crear()

    def test_totales_y_porcentajes(self):
        for test_id, estado in (("DEMO-LLAM-001", "ok"), ("DEMO-LLAM-002", "ok"), ("DEMO-LLAM-003", "no_ok"),
                                ("DEMO-NIV-001", "bloqueada"), ("DEMO-CAN-001", "no_aplica")):
            ej.registrar(self.campaña, test_id, estado, observaciones="x")
        r = ej.resumen(self.campaña, self.capitulos())
        self.assertEqual(r["total"], 10)
        self.assertEqual(r["totales"], {"pendiente": 5, "ok": 2, "no_ok": 1, "bloqueada": 1, "no_aplica": 1})
        self.assertEqual(r["ejecutadas"], 5)
        self.assertEqual(r["porcentaje_ok"], 22.2)        # 2 OK de 9 que aplican
        self.assertEqual(r["por_capitulo"]["Ejemplo básico"]["ok"], 2)
        self.assertEqual(r["por_criticidad"]["alta"]["bloqueada"], 1)

    def test_avisa_de_pruebas_cambiadas_borradas_y_fallos_sin_observaciones(self):
        ej.registrar(self.campaña, "DEMO-LLAM-001", "ok", huella_actual=self.campaña["datos"]["pruebas"][0]["huella"])
        ej.registrar(self.campaña, "DEMO-LLAM-002", "no_ok")
        capitulos = self.capitulos()
        capitulos[0]["data"]["contenido"][2]["prueba"]["titulo"] = "Título cambiado"
        del capitulos[0]["data"]["contenido"][3]          # DEMO-LLAM-002 desaparece
        mensajes = {(p["id"], p["mensaje"]) for p in ej.resumen(self.campaña, capitulos)["problemas"]}
        self.assertIn(("DEMO-LLAM-001", "La prueba ha cambiado después de ejecutarse."), mensajes)
        self.assertIn(("DEMO-LLAM-002", "La prueba ya no existe en los YAML de pruebas."), mensajes)
        self.assertIn(("DEMO-LLAM-002", "Resultado NO OK sin observaciones."), mensajes)


class CicloTests(CampañaBase):
    def test_resincronizar_añade_las_pruebas_nuevas(self):
        campaña = self.crear()
        capitulo = self.capitulos()[1]
        capitulo["data"]["contenido"][4]["prueba"]["etiquetas"] = ["regresion"]   # DEMO-DIAG-001
        save_chapter(capitulo)
        cambios = ej.resincronizar(campaña, self.capitulos())
        self.assertEqual(cambios["añadidas"], ["DEMO-DIAG-001"])
        self.assertIn("DEMO-DIAG-001", ej.ids_de(ej.cargar(self.carpeta)))

    def test_cerrar_exige_que_no_quede_nada_pendiente_y_bloquea_cambios(self):
        campaña = self.crear({"etiquetas": ["manual"]})
        with self.assertRaisesRegex(ValueError, "pendientes"):
            ej.cerrar(campaña, self.capitulos())
        ej.registrar(campaña, "DEMO-VAR-002", "ok")
        ej.cerrar(campaña, self.capitulos())
        cargada = ej.cargar(self.carpeta)
        self.assertEqual(cargada["datos"]["estado"], "cerrada")
        with self.assertRaisesRegex(ValueError, "cerrada"):
            ej.registrar(cargada, "DEMO-VAR-002", "no_ok")

    def test_ruta_relativa_a_las_pruebas(self):
        campaña = self.crear()
        campaña["datos"]["pruebas_yaml"] = "../../pruebas"
        self.assertEqual(ej.carpeta_pruebas(campaña), self.pruebas.resolve())


if __name__ == "__main__":
    unittest.main()
