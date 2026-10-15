"""Pruebas de ids_duplicados.py."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from migracion import ids_duplicados as idd
from app.editor_core import read_chapters, tests_in_chapter

CAPITULO = """\
capitulo: Llamadas
contenido:
- seccion: Cabina
  nivel: 2
- prueba: {nombre: Uno, nivel: 3, id: LLAM_001, titulo: Primera, pasos: [Pulsar el botón 2.]}
- prueba: {nombre: Dos, nivel: 3, id: LLAM_001, titulo: Primera, pasos: [Pulsar el botón 2.]}  # copia
- prueba: {nombre: Tres, nivel: 3, id: LLAM_001, titulo: Otra cosa, pasos: [Abrir puertas.]}
- prueba: {nombre: Cuatro, nivel: 3, id: LLAM_009, titulo: Cuarta}
- prueba: {nombre: Cinco, nivel: 3, id: BOR_LLAM _002, titulo: Con espacio}
- prueba: {nombre: Seis, nivel: 3, id: CASO DE PRUEBA, titulo: Sin ID de verdad}
- prueba: {nombre: Siete, nivel: 3, id: CASO DE PRUEBA, titulo: Otra sin ID}
"""


class IdsDuplicadosTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        (self.dir / "01_llamadas.yaml").write_text(CAPITULO, encoding="utf-8")

    def ids(self):
        return [p.get("id") for c in read_chapters(self.dir) for _i, p in tests_in_chapter(c)]

    def test_propuesta(self):
        filas = {(f["indice"]): f for f in idd.proponer(self.dir)}
        self.assertEqual(filas[1]["id_nuevo"], "LLAM_001")                       # la primera conserva el ID
        self.assertEqual((filas[2]["id_nuevo"], filas[3]["id_nuevo"]), ("LLAM_010", "LLAM_011"))  # tras LLAM_009
        self.assertTrue(filas[2]["parecido"].startswith("idéntica"))
        self.assertTrue(filas[3]["parecido"].startswith("distinta"))
        self.assertEqual(filas[5]["id_nuevo"], "BOR_LLAM_002")                   # sin el espacio
        self.assertEqual((filas[6]["id_nuevo"], filas[7]["id_nuevo"]), ("", ""))  # hay que elegirlos
        self.assertEqual(filas[2]["seccion"], "Cabina")
        self.assertNotIn(4, filas)                                              # LLAM_009 está bien

    def test_aplicar(self):
        ruta = self.dir.parent / "ids.csv"
        filas = idd.proponer(self.dir)
        for f in filas:
            if not f["id_nuevo"]:
                f["id_nuevo"] = f"CASO_{f['indice']:03d}"
        idd.escribir_csv(filas, ruta)
        r = idd.aplicar(self.dir, idd.leer_csv(ruta))
        self.assertEqual(r["errores"], [])
        self.assertEqual(r["aplicados"], 5)
        self.assertEqual(self.ids(), ["LLAM_001", "LLAM_010", "LLAM_011", "LLAM_009", "BOR_LLAM_002", "CASO_006", "CASO_007"])
        self.assertIn("# copia", (self.dir / "01_llamadas.yaml").read_text(encoding="utf-8"))
        self.assertEqual(idd.proponer(self.dir), [])

    def test_no_aplica_nada_si_quedarian_repetidos_o_la_prueba_cambio(self):
        filas = idd.proponer(self.dir)
        filas[1]["id_nuevo"] = "LLAM_009"                                       # ya existe
        r = idd.aplicar(self.dir, filas)
        self.assertTrue(any("LLAM_009" in e for e in r["errores"]))
        self.assertEqual(self.ids()[1], "LLAM_001")                             # sin tocar
        filas = idd.proponer(self.dir)
        filas[1]["indice"] = 4
        self.assertTrue(any("ya no está" in e for e in idd.aplicar(self.dir, filas)["errores"]))
