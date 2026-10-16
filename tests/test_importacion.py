"""Importación con mapeo de etiquetas (app/importacion.py)."""
import tempfile
import unittest
from pathlib import Path

from docx import Document

from app import importacion as imp
from app import yaml_a_docx
from app.editor_api import to_plain
from app.editor_core import items_in_chapter, read_chapters

RAIZ = Path(__file__).resolve().parents[1]
EJEMPLOS = RAIZ / "ejemplos" / "yaml"


def _items(carpeta, tipo):
    return {str(e.get("id")): to_plain(e) for c in read_chapters(Path(carpeta)) for _i, e in items_in_chapter(c, tipo)}


def _requisito(doc, ident, titulo, celdas, tabla_en_descripcion=None, despues_de_tabla=None):
    """Tabla de requisito con la forma de la plantilla: «ID | Título» y una celda por fila con «Etiqueta: valor»."""
    t = doc.add_table(rows=1 + len(celdas), cols=2)
    t.cell(0, 0).text, t.cell(0, 1).text = ident, titulo
    for i, texto in enumerate(celdas, start=1):
        celda = t.cell(i, 0).merge(t.cell(i, 1))
        lineas = texto.split("\n")
        celda.paragraphs[0].text = lineas[0]
        for linea in lineas[1:]:
            celda.add_paragraph(linea)
        if tabla_en_descripcion and texto.startswith("Descripción"):
            anidada = celda.add_table(rows=len(tabla_en_descripcion), cols=len(tabla_en_descripcion[0]))
            for f, fila in enumerate(tabla_en_descripcion):
                for c, valor in enumerate(fila):
                    anidada.cell(f, c).text = valor
            if despues_de_tabla:
                celda.add_paragraph(despues_de_tabla)
    return t


class TestEtiquetas(unittest.TestCase):
    def test_clave_y_etiqueta(self):
        self.assertEqual(imp.clave("Requisito(s):"), "requisito")
        self.assertEqual(imp.clave("Criterio  Validación"), "criteriovalidacion")
        self.assertEqual(imp.etiqueta_de("Descripción: el texto"), ("Descripción", 13))
        self.assertIsNone(imp.etiqueta_de("10:30 de la mañana"))
        self.assertIsNone(imp.etiqueta_de("Una frase larga de verdad con muchas palabras: no es etiqueta"))
        self.assertIsNone(imp.etiqueta_de("http://servidor/doc"))

    def test_propuestas(self):
        self.assertEqual(imp.proponer_campo("prueba", "Pasos"), "pasos")
        self.assertEqual(imp.proponer_campo("prueba", "Condiciones iniciales"), "situacion_inicial")
        self.assertEqual(imp.proponer_campo("requisito", "Método de verificación"), "criterio_validacion")
        self.assertEqual(imp.proponer_campo("requisito", "Criterio de validacion"), "criterio_validacion")
        self.assertEqual(imp.proponer_campo("prueba", "Componente"), "ignorar")
        self.assertEqual(imp.proponer_campo("prueba", "Responsable"), "adicional")
        self.assertEqual(imp.proponer_campo("prueba", "Nota", solo_interior=True), "anterior")


class TestIdaYVuelta(unittest.TestCase):
    """El Word generado desde los ejemplos se vuelve a importar sin perder datos."""

    def test_requisitos(self):
        with tempfile.TemporaryDirectory() as tmp:
            docx = Path(tmp) / "requisitos.docx"
            yaml_a_docx.generar_docx(EJEMPLOS / "requisitos", docx)
            analisis = imp.analizar(docx)
            self.assertEqual(analisis["familias"][0]["tipo"], "requisito")
            self.assertEqual(analisis["familias"][0]["tablas"], 18)
            r = imp.importar(docx, imp.mapeo_propuesto(analisis), Path(tmp) / "proyecto")
            self.assertEqual(r["totales"], {"requisito": 18})
            self.assertTrue((Path(tmp) / "proyecto" / "avisos.txt").is_file())
            original, importado = _items(EJEMPLOS / "requisitos", "requisito"), _items(r["carpetas"]["requisito"], "requisito")
            self.assertEqual(set(original), set(importado))
            for ident, req in original.items():
                for campo in ("titulo", "descripcion", "fuente", "referencia", "tipo", "fase", "fecha", "version"):
                    self.assertEqual(str(req.get(campo) or ""), importado[ident][campo], f"{ident} {campo}")
                self.assertEqual(sorted(req.get("criterio_validacion") or []), importado[ident]["criterio_validacion"])

    def test_pruebas(self):
        with tempfile.TemporaryDirectory() as tmp:
            docx = Path(tmp) / "pruebas.docx"
            yaml_a_docx.generar_docx(EJEMPLOS / "pruebas", docx)
            analisis = imp.analizar(docx)
            r = imp.importar(docx, imp.mapeo_propuesto(analisis), Path(tmp) / "proyecto")
            carpeta = Path(r["carpetas"]["prueba"])
            original, importado = _items(EJEMPLOS / "pruebas", "prueba"), _items(carpeta, "prueba")
            self.assertEqual(set(original), set(importado))

            def textos(lista):
                return [x if isinstance(x, str) else x.get("texto") for x in lista or [] if (x if isinstance(x, str) else x.get("texto"))]
            for ident, prueba in original.items():
                for campo in ("titulo", "descripcion", "automatizable", "fecha", "version"):
                    self.assertEqual(str(prueba.get(campo) or ""), importado[ident][campo], f"{ident} {campo}")
                for campo in ("parametrizacion", "situacion_inicial", "pasos"):
                    self.assertEqual(textos(prueba.get(campo)), textos(importado[ident][campo]), f"{ident} {campo}")
                for campo in ("maniobra", "entorno", "requisitos", "etiquetas"):
                    self.assertEqual(prueba.get(campo) or [], importado[ident][campo], f"{ident} {campo}")
            # Las imágenes se copian a la carpeta de pruebas.
            self.assertTrue(any((carpeta / "imagenes").iterdir()))


class TestMapeo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        doc = Document()
        doc.add_heading("Requisitos del sistema", 1)
        doc.add_heading("Arranque", 2)
        _requisito(doc, "SR-001", "El sistema arranca en menos de 5 s",
                   ["Descripción: Desde que se alimenta.", "Origen: cliente", "Tipo: obligatorio",
                    "Método de verificación: test / análisis", "Prioridad: alta"],
                   tabla_en_descripcion=[["Modo", "Tiempo"], ["Frío", "5 s"], ["Caliente", "2 s"]],
                   despues_de_tabla="Los tiempos se miden en el banco.")
        doc.add_heading("Parada", 2)
        _requisito(doc, "SR-002", "El sistema para en menos de 1 s",
                   ["Descripción: Al pulsar la seta.\nNota: también por software.", "Origen: norma", "Tipo: Clave"])
        _requisito(doc, "SR-002", "Requisito con el ID repetido", ["Descripción: otro.", "Origen: norma"])
        doc.add_paragraph("Historial")
        t = doc.add_table(rows=2, cols=3)
        t.cell(0, 0).text, t.cell(0, 1).text, t.cell(0, 2).text = "Versión", "Fecha", "Cambio"
        self.docx = self.dir / "requisitos.docx"
        doc.save(self.docx)

    def tearDown(self):
        self.tmp.cleanup()

    def test_analisis(self):
        a = imp.analizar(self.docx, "requisito")
        self.assertEqual(a["tablas"], 4)
        # Las tres tablas de requisito (una con menos etiquetas) forman una familia.
        familia = a["familias"][0]
        self.assertEqual((familia["tablas"], familia["tipo"], familia["anidadas"]), (3, "requisito", 1))
        propuestas = {e["etiqueta"]: e["propuesta"]["requisito"] for e in familia["etiquetas"]}
        self.assertEqual(propuestas["Origen"], "fuente")
        self.assertEqual(propuestas["Método de verificación"], "criterio_validacion")
        self.assertEqual(propuestas["Prioridad"], "adicional")
        self.assertEqual(propuestas["Nota"], "anterior")           # solo aparece en mitad de una celda
        self.assertEqual(a["familias"][1]["tipo"], "tabla")

    def test_conversion_y_revision(self):
        a = imp.analizar(self.docx, "requisito")
        mapeo = imp.mapeo_propuesto(a)
        conversion = imp.preparar(self.docx, mapeo)["conversion"]
        reqs = imp.elementos(conversion["capitulos"], "requisito")
        r1, r2 = reqs[0], reqs[1]
        self.assertEqual(r1["nombre"], "Arranque")
        self.assertEqual(r1["descripcion"], "Desde que se alimenta.")
        self.assertEqual(r1["fuente"], "cliente")
        self.assertEqual(r1["tipo"], "Obligatorio")
        self.assertEqual(r1["criterio_validacion"], ["Análisis", "Test"])
        self.assertEqual(r1["campos_adicionales"], {"Prioridad": "alta"})
        # La tabla de la descripción y el texto que la sigue van, en orden, a `detalle`.
        self.assertEqual(r1["detalle"][0]["tabla"]["filas"], [["Modo", "Tiempo"], ["Frío", "5 s"], ["Caliente", "2 s"]])
        self.assertEqual(r1["detalle"][1], "Los tiempos se miden en el banco.")
        # «Nota:» en mitad de la celda sigue en la descripción; un tipo que no es opción, a campos adicionales.
        self.assertEqual(r2["descripcion"], "Al pulsar la seta.\nNota: también por software.")
        self.assertEqual((r2["tipo"], r2["campos_adicionales"]), ("", {"Tipo": "Clave"}))

        revision = imp.revision(conversion)
        self.assertEqual(revision["totales"]["requisito"], 3)
        ids = revision["tipos"]["requisito"]["ids"]
        self.assertEqual([(p["orden"], p["id"], p["propuesta"]) for p in ids], [(2, "SR-002", "SR-003")])
        self.assertIn("valor_descartado", {g["tipo"] for g in revision["avisos"]})

    def test_mapeo_elegido(self):
        mapeo = imp.mapeo_propuesto(imp.analizar(self.docx, "requisito"))
        mapeo["campos"]["requisito"].update({"prioridad": "ignorar", "origen": "referencia", "nota": "adicional"})
        reqs = imp.elementos(imp.preparar(self.docx, mapeo)["conversion"]["capitulos"], "requisito")
        self.assertNotIn("campos_adicionales", reqs[0])
        self.assertEqual(reqs[0]["referencia"], "cliente")
        self.assertEqual(reqs[1]["descripcion"], "Al pulsar la seta.")
        self.assertEqual(reqs[1]["campos_adicionales"]["Nota"], "también por software.")
        # Una familia marcada como «no importar» desaparece.
        familia = imp.analizar(self.docx, "requisito")["familias"][0]["firma"]
        mapeo["tipos"][familia] = "ignorar"
        conversion = imp.preparar(self.docx, mapeo)["conversion"]
        self.assertEqual(imp.elementos(conversion["capitulos"], "requisito"), [])
        self.assertEqual(conversion["totales"]["ignorar"], 3)

    def test_mapeo_recordado(self):
        a = imp.analizar(self.docx, "requisito")
        mapeo = imp.mapeo_propuesto(a, {"campos": {"requisito": {"prioridad": "fase"}}, "tipos": {a["familias"][1]["firma"]: "ignorar"}})
        self.assertEqual(mapeo["campos"]["requisito"]["prioridad"], "fase")
        self.assertEqual(mapeo["campos"]["requisito"]["origen"], "fuente")
        self.assertEqual(mapeo["tipos"][a["familias"][1]["firma"]], "ignorar")

    def test_importar_en_proyecto_abierto(self):
        proyecto = self.dir / "proyecto"
        mapeo = imp.mapeo_propuesto(imp.analizar(self.docx, "requisito"))
        r = imp.importar(self.docx, mapeo, proyecto, "nuevo", renombrar_propuestos=True)
        self.assertEqual(r["ids_cambiados"], {"requisito": 1})
        self.assertEqual(sorted(_items(proyecto / "requisitos", "requisito")), ["SR-001", "SR-002", "SR-003"])
        with self.assertRaises(ValueError):
            imp.importar(self.docx, mapeo, proyecto, "nuevo")         # la carpeta ya no está vacía
        # Segunda vez, añadiendo al proyecto: todos chocan con los que ya hay y se proponen otros.
        revision = imp.revision(imp.preparar(self.docx, mapeo, proyecto, "anadir")["conversion"],
                                imp.ids_existentes(imp.carpetas_destino(proyecto, "anadir")))
        self.assertEqual([p["motivo"] for p in revision["tipos"]["requisito"]["ids"]], ["ya existe en el proyecto"] * 3)
        r = imp.importar(self.docx, mapeo, proyecto, "anadir", renombrar_propuestos=True)
        self.assertEqual(r["archivos"]["requisito"], ["02_requisitos_del_sistema.yaml"])
        ids = _items(proyecto / "requisitos", "requisito")
        self.assertEqual(len(ids), 6)
        self.assertEqual(len(read_chapters(proyecto / "requisitos")), 2)

    def test_detalle_y_adicionales_en_el_word(self):
        """Las tablas de la descripción y los campos adicionales salen en el Word y se vuelven a importar igual."""
        mapeo = imp.mapeo_propuesto(imp.analizar(self.docx, "requisito"))
        imp.importar(self.docx, mapeo, self.dir / "p", renombrar_propuestos=True)
        yaml_a_docx.generar_docx(self.dir / "p" / "requisitos", self.dir / "otra_vez.docx")
        mapeo = imp.mapeo_propuesto(imp.analizar(self.dir / "otra_vez.docx", "requisito"))
        imp.importar(self.dir / "otra_vez.docx", mapeo, self.dir / "q")
        antes, despues = _items(self.dir / "p" / "requisitos", "requisito"), _items(self.dir / "q" / "requisitos", "requisito")
        for campo in ("descripcion", "detalle", "campos_adicionales", "tipo", "criterio_validacion"):
            self.assertEqual(antes["SR-001"].get(campo), despues["SR-001"].get(campo), campo)


if __name__ == "__main__":
    unittest.main()


class TestApi(unittest.TestCase):
    """El asistente del editor: analizar, revisar, importar y editar lo importado."""

    def setUp(self):
        import os
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self._entorno = os.environ.get("EDITOR_PRUEBAS_AJUSTES")
        os.environ["EDITOR_PRUEBAS_AJUSTES"] = str(self.dir / "ajustes.json")
        doc = Document()
        doc.add_heading("Requisitos", 1)
        _requisito(doc, "SR-001", "Arranque", ["Descripción: rápido.", "Prioridad: alta"],
                   tabla_en_descripcion=[["Modo", "Tiempo"], ["Frío", "5 s"]])
        self.docx = self.dir / "req.docx"
        doc.save(self.docx)

    def tearDown(self):
        import os
        if self._entorno is None:
            os.environ.pop("EDITOR_PRUEBAS_AJUSTES", None)
        else:
            os.environ["EDITOR_PRUEBAS_AJUSTES"] = self._entorno
        self.tmp.cleanup()

    def test_flujo_completo(self):
        from app import ajustes
        from app.importacion_api import EditorImportacionApi
        api = EditorImportacionApi()
        r = api.importar_analizar(str(self.docx), "requisito")
        self.assertTrue(r["ok"], r)
        mapeo = r["datos"]["mapeo"]
        self.assertEqual(r["datos"]["nombre_propuesto"], "req")
        self.assertIn({"valor": "anterior", "texto": imp.ESPECIALES["anterior"]}, r["datos"]["opciones"]["requisito"])
        self.assertFalse(api.importar_revisar(str(self.docx), mapeo, "anadir")["ok"])     # no hay proyecto abierto
        rev = api.importar_revisar(str(self.docx), mapeo, "nuevo")["datos"]
        self.assertEqual(rev["tipos"]["requisito"]["total"], 1)
        mapeo["campos"]["requisito"]["prioridad"] = "fase"
        r = api.importar_ejecutar(str(self.docx), mapeo, "nuevo", carpeta=str(self.dir / "proyecto"))
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["datos"]["carpeta"]["coleccion"], "requisitos")
        self.assertEqual(r["datos"]["carpeta"]["capitulos"][0]["pruebas"], 1)
        # Sin pruebas en el documento, el proyecto empieza con un capítulo de pruebas vacío.
        self.assertTrue((self.dir / "proyecto" / "pruebas" / "indice.yaml").is_file())
        # El mapeo elegido se recuerda para la próxima vez.
        self.assertEqual(ajustes.leer()["importacion_mapeo"]["campos"]["requisito"]["prioridad"], "fase")
        self.assertEqual(api.importar_analizar(str(self.docx), "requisito")["datos"]["mapeo"]["campos"]["requisito"]["prioridad"], "fase")
        # Lo importado se edita y se guarda con sus tablas y campos adicionales.
        indice = next(n["indice"] for n in api.navegacion(0, "")["datos"] if n.get("id") == "SR-001")
        r = api.guardar_requisito(0, indice, {"campos_adicionales": {"Prioridad": "baja"},
                                              "detalle": [{"tabla": {"filas": [["a", "b"]]}}, "nota"]})
        self.assertTrue(r["ok"], r)
        self.assertIn("'Prioridad': 'baja'", str(api.obtener(0, indice)["datos"]))
        self.assertIn("'nota'", str(api.obtener(0, indice)["datos"]))
        self.assertEqual(api.validar()["datos"]["errores"], 0)
