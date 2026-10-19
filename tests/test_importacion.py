"""Importación con mapeo de etiquetas (app/importacion.py)."""
import tempfile
import unittest
from pathlib import Path

from docx import Document

from app import esquema
from app import importacion as imp
from app import yaml_a_docx
from app.editor_api import to_plain
from app.editor_core import items_in_chapter, navigation_entries, read_chapters

RAIZ = Path(__file__).resolve().parents[1]
EJEMPLOS = RAIZ / "ejemplos" / "yaml"


def _items(carpeta, tipo):
    return {str(e.get("id")): to_plain(e) for c in read_chapters(Path(carpeta)) for _i, e in items_in_chapter(c, tipo)}


def _estructura(carpeta):
    """Árbol de cada capítulo: (tipo, ID o título, nivel, padre), sin las tablas informativas."""
    resultado = []
    for c in read_chapters(Path(carpeta)):
        nav = navigation_entries(c)
        titulos = {i: t for _k, i, t, _p, _n in nav}
        resultado.append([(k, t.split(" — ")[0], n, titulos.get(p)) for k, _i, t, p, n in nav if k != "table"])
    return resultado


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
            # Mismas secciones y niveles: los títulos con varias tablas (o sin tabla propia) son secciones.
            self.assertEqual(_estructura(EJEMPLOS / "requisitos"), _estructura(r["carpetas"]["requisito"]))
            for ident, req in original.items():
                for campo in ("titulo", "descripcion", "fuente", "referencia", "tipo", "fase", "fecha", "version"):
                    self.assertEqual(str(req.get(campo) or ""), importado[ident][campo], f"{ident} {campo}")
                self.assertEqual(sorted(req.get("criterio_validacion") or []), importado[ident]["criterio_validacion"])

    def test_pruebas(self):
        esquema.configurar(EJEMPLOS / "pruebas")
        with tempfile.TemporaryDirectory() as tmp:
            docx = Path(tmp) / "pruebas.docx"
            yaml_a_docx.generar_docx(EJEMPLOS / "pruebas", docx)
            analisis = imp.analizar(docx)
            r = imp.importar(docx, imp.mapeo_propuesto(analisis), Path(tmp) / "proyecto")
            carpeta = Path(r["carpetas"]["prueba"])
            self.assertTrue((Path(tmp) / "proyecto" / "aztarna.yaml").is_file())   # conserva las opciones
            original, importado = _items(EJEMPLOS / "pruebas", "prueba"), _items(carpeta, "prueba")
            self.assertEqual(set(original), set(importado))
            self.assertEqual(_estructura(EJEMPLOS / "pruebas"), _estructura(carpeta))     # cada prueba con su título

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


class TestNiveles(unittest.TestCase):
    def test_titulos_con_estilo_propio_y_secciones_profundas(self):
        from docx.enum.style import WD_STYLE_TYPE
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        doc = Document()
        doc.add_heading("Capítulo", 1)
        doc.add_heading("Sistema", 2)
        propio = doc.styles.add_style("Requisitos 3", WD_STYLE_TYPE.PARAGRAPH)
        propio.base_style = doc.styles["Heading 3"]
        doc.add_paragraph("Arranque", style=propio)                  # estilo propio basado en Título 3
        _requisito(doc, "R-1", "Uno", ["Descripción: a"])
        _requisito(doc, "R-2", "Dos", ["Descripción: b"])
        p = doc.add_paragraph("Parada")                              # texto normal con nivel de esquema 3
        ppr = p._p.get_or_add_pPr()
        nivel = OxmlElement("w:outlineLvl")
        nivel.set(qn("w:val"), "2")
        ppr.append(nivel)
        _requisito(doc, "R-3", "Tres", ["Descripción: c"])
        with tempfile.TemporaryDirectory() as tmp:
            docx = Path(tmp) / "niveles.docx"
            doc.save(docx)
            r = imp.importar(docx, imp.mapeo_propuesto(imp.analizar(docx, "requisito")), Path(tmp) / "p")
            self.assertEqual(_estructura(r["carpetas"]["requisito"]), [[
                ("section", "Sistema", 2, None), ("section", "Arranque", 3, "Sistema"),
                ("requirement", "R-1", 4, "Arranque"), ("requirement", "R-2", 4, "Arranque"),
                ("section", "Parada", 3, "Sistema"), ("requirement", "R-3", 4, "Parada")]])


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
        self.assertEqual((r1["nombre"], r1["nivel"]), ("", 3))          # «Arranque» es una sección
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
        # El capítulo ya existe: los nuevos van a él, no a un capítulo repetido.
        self.assertEqual((r["archivos"]["requisito"], r["unidos"]["requisito"]), ([], ["01_requisitos_del_sistema.yaml"]))
        ids = _items(proyecto / "requisitos", "requisito")
        self.assertEqual(len(ids), 6)
        self.assertEqual(len(read_chapters(proyecto / "requisitos")), 1)

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
        self._entorno = os.environ.get("AZTARNA_AJUSTES")
        os.environ["AZTARNA_AJUSTES"] = str(self.dir / "ajustes.json")
        doc = Document()
        doc.add_heading("Requisitos", 1)
        _requisito(doc, "SR-001", "Arranque", ["Descripción: rápido.", "Prioridad: alta"],
                   tabla_en_descripcion=[["Modo", "Tiempo"], ["Frío", "5 s"]])
        self.docx = self.dir / "req.docx"
        doc.save(self.docx)

    def tearDown(self):
        import os
        if self._entorno is None:
            os.environ.pop("AZTARNA_AJUSTES", None)
        else:
            os.environ["AZTARNA_AJUSTES"] = self._entorno
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


class TestActualizar(unittest.TestCase):
    """Volver a importar un Word en el proyecto: actualizar los que ya existen, omitirlos o importarlos como nuevos."""

    def documento(self, ruta, descripcion):
        doc = Document()
        doc.add_heading("Requisitos", 1)
        doc.add_heading("Arranque", 2)
        _requisito(doc, "SR-001", "Arranque rápido", [f"Descripción: {descripcion}", "Tipo: Obligatorio"])
        _requisito(doc, "SR-002", "Parada", ["Descripción: igual", "Tipo: Obligatorio"])
        _requisito(doc, "SR-009", "Nuevo", ["Descripción: nuevo", "Tipo: Opcional"])
        doc.save(ruta)

    def test_actualizar_omitir_y_nuevo(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            self.documento(tmp / "v1.docx", "en menos de 5 s")
            mapeo = imp.mapeo_propuesto(imp.analizar(tmp / "v1.docx", "requisito"))
            imp.importar(tmp / "v1.docx", mapeo, tmp / "p")
            # Una prueba cita SR-001: al cambiar el requisito, quedará por revisar.
            (tmp / "p" / "pruebas" / "01_pruebas.yaml").write_text(
                "capitulo: Pruebas\ncontenido:\n- prueba:\n    id: T-1\n    titulo: Arranca\n    requisitos: [SR-001]\n", encoding="utf-8")
            self.documento(tmp / "v2.docx", "en menos de 3 s")
            p = imp.preparar(tmp / "v2.docx", mapeo, tmp / "p", "anadir")
            rev = imp.revision(p["conversion"], p["existentes"], p["carpetas"], p["imagenes"])["tipos"]["requisito"]
            self.assertEqual([(c["id"], c["cambios"]) for c in rev["existentes"]],
                             [("SR-001", ["Descripción"]), ("SR-002", []), ("SR-009", [])])
            self.assertEqual(rev["existentes"][0]["propuesta"], "SR-010")
            self.assertEqual(rev["ids"], [])
            # SR-001 se actualiza, SR-002 se omite y SR-009 se importa como nuevo con otro ID.
            r = imp.importar(tmp / "v2.docx", mapeo, tmp / "p", "anadir", ids={"requisito": {"2": "SR-020"}},
                             acciones={"requisito": {"0": "actualizar", "1": "omitir", "2": "nuevo"}})
            self.assertEqual((r["actualizados"], r["omitidos"], r["totales"]), ({"requisito": 1}, {"requisito": 1}, {"requisito": 1}))
            reqs = _items(tmp / "p" / "requisitos", "requisito")
            self.assertEqual(sorted(reqs), ["SR-001", "SR-002", "SR-009", "SR-020"])
            self.assertEqual(reqs["SR-001"]["descripcion"], "en menos de 3 s")
            self.assertEqual(reqs["SR-001"]["nivel"], 3)                         # conserva su sitio
            capitulos = read_chapters(tmp / "p" / "requisitos")
            self.assertEqual(len(capitulos), 1)                                  # el capítulo ya existía: no se repite
            self.assertEqual(r["unidos"], {"requisito": [capitulos[0]["path"].name]})
            self.assertEqual([e["id"] for _i, e in items_in_chapter(capitulos[0], "requisito")],
                             ["SR-001", "SR-002", "SR-009", "SR-020"])            # SR-020, al final de «Arranque»
            from app import trazabilidad
            revisiones = trazabilidad.leer_revisiones(tmp / "p" / "requisitos")
            self.assertEqual(revisiones["SR-001"]["descripcion"], "en menos de 5 s")   # texto anterior, para revisar T-1
            # Si todo se omite, no hay nada que importar.
            with self.assertRaisesRegex(ValueError, "No importar"):
                imp.importar(tmp / "v2.docx", mapeo, tmp / "p", "anadir",
                             acciones={"requisito": {"0": "omitir", "1": "omitir", "2": "omitir", "3": "omitir"}})

    def test_reimportar_el_word_exportado_no_cambia_nada(self):
        """Exportar las pruebas a Word y volver a importarlas sobre el proyecto: solo cambia lo que el mapeo deja fuera."""
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            shutil.copytree(EJEMPLOS, tmp / "yaml")
            for coleccion, tipo, esperado in (("pruebas", "prueba", [("DEMO-VAR-001", ["Campos adicionales"])]),
                                              ("requisitos", "requisito", [])):
                yaml_a_docx.generar_docx(tmp / "yaml" / coleccion, tmp / f"{coleccion}.docx")
                mapeo = imp.mapeo_propuesto(imp.analizar(tmp / f"{coleccion}.docx"))
                p = imp.preparar(tmp / f"{coleccion}.docx", mapeo, tmp / "yaml", "anadir")
                ya = imp.revision(p["conversion"], p["existentes"], p["carpetas"], p["imagenes"])["tipos"][tipo]["existentes"]
                self.assertEqual(len(ya), len(_items(EJEMPLOS / coleccion, tipo)))
                # «Criterio de aceptación» (formato antiguo) se propone como «No importar».
                self.assertEqual([(c["id"], c["cambios"]) for c in ya if c["cambios"]], esperado)

    def test_importar_poco_a_poco_en_los_capitulos_que_ya_existen(self):
        """Cada vez se importa un Word con unas pocas pruebas: van a su capítulo y su sección, sin repetirlos."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            def word(ruta, secciones):
                doc = Document()
                doc.add_heading("Requisitos", 1)
                doc.add_paragraph("Texto del capítulo.")
                for seccion, reqs in secciones:
                    doc.add_heading(seccion, 2)
                    for ident in reqs:
                        _requisito(doc, ident, f"Título {ident}", [f"Descripción: {ident}", "Tipo: Obligatorio"])
                doc.save(ruta)
            word(tmp / "1.docx", [("Arranque", ["SR-001", "SR-005"]), ("Parada", ["SR-002", "SR-006"])])
            mapeo = imp.mapeo_propuesto(imp.analizar(tmp / "1.docx", "requisito"))
            imp.importar(tmp / "1.docx", mapeo, tmp / "p")
            # Segunda tanda: una nueva en «Parada», una sección nueva y SR-001 otra vez (sin cambios).
            word(tmp / "2.docx", [("Arranque", ["SR-001", "SR-005"]), ("Parada", ["SR-003", "SR-007"]), ("Alarmas", ["SR-004", "SR-008"])])
            p = imp.preparar(tmp / "2.docx", mapeo, tmp / "p", "anadir")
            rev = imp.revision(p["conversion"], p["existentes"], p["carpetas"], p["imagenes"])["tipos"]["requisito"]
            self.assertEqual([(c["nombre"], c["existente"]) for c in rev["capitulos"]], [("Requisitos", True)])
            imp.importar(tmp / "2.docx", mapeo, tmp / "p", "anadir", acciones={"requisito": {"0": "omitir", "1": "omitir"}})
            capitulos = read_chapters(tmp / "p" / "requisitos")
            self.assertEqual(len(capitulos), 1)
            self.assertEqual(_estructura(tmp / "p" / "requisitos"), [[
                ("section", "Arranque", 2, None), ("requirement", "SR-001", 3, "Arranque"), ("requirement", "SR-005", 3, "Arranque"),
                ("section", "Parada", 2, None), ("requirement", "SR-002", 3, "Parada"), ("requirement", "SR-006", 3, "Parada"),
                ("requirement", "SR-003", 3, "Parada"), ("requirement", "SR-007", 3, "Parada"),
                ("section", "Alarmas", 2, None), ("requirement", "SR-004", 3, "Alarmas"), ("requirement", "SR-008", 3, "Alarmas")]])
            textos = [e for e in capitulos[0]["data"]["contenido"] if isinstance(e, dict) and "texto" in e]
            self.assertEqual(len(textos), 1)                                     # el texto del capítulo no se repite
            # Una tercera tanda solo con lo que ya está: no hay nada nuevo que escribir.
            with self.assertRaisesRegex(ValueError, "No importar"):
                imp.importar(tmp / "2.docx", mapeo, tmp / "p", "anadir",
                             acciones={"requisito": {str(i): "omitir" for i in range(6)}})

    def test_unir_ajusta_los_niveles_y_crea_las_subsecciones(self):
        capitulo = {"data": {"capitulo": "C", "contenido": [
            {"seccion": "A", "nivel": 3}, {"prueba": {"id": "T-1", "nivel": 4}},
            {"seccion": "B", "nivel": 3}]}}
        importado = [
            {"seccion": "A", "nivel": 2}, {"prueba": {"id": "T-2", "nivel": 3}},
            {"seccion": "A1", "nivel": 3}, {"prueba": {"id": "T-3", "nivel": 4}},
            {"seccion": "Vacía", "nivel": 2},
            {"seccion": "Nueva", "nivel": 2}, {"prueba": {"id": "T-4", "nivel": 3}}]
        self.assertEqual(imp.unir_capitulo(capitulo, importado), 3)
        resumen = [(e.get("seccion") or e["prueba"]["id"], e.get("nivel") or e["prueba"]["nivel"]) for e in capitulo["data"]["contenido"]]
        self.assertEqual(resumen, [("A", 3), ("T-1", 4), ("T-2", 4), ("A1", 4), ("T-3", 5), ("B", 3), ("Nueva", 2), ("T-4", 3)])

    def test_texto_no_importado(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = Document()
            doc.add_heading("Requisitos", 1)
            _requisito(doc, "SR-001", "Uno", ["Descripción: algo"])
            doc.save(Path(tmp) / "a.docx")
            lector = imp._Lector("requisito", {}, None)
            tabla = Document(Path(tmp) / "a.docx").tables[0]
            segmentos = lector.segmentos(imp.cv.filas_sin_repetir(tabla))
            avisos = []
            lector.comprobar_texto(segmentos, {"id": "SR-001", "titulo": "Uno", "descripcion": ""}, avisos)
            self.assertEqual([a.tipo for a in avisos], ["texto_no_importado"])
            avisos = []
            lector.comprobar_texto(segmentos, {"id": "SR-001", "descripcion": "**algo**"}, avisos)
            self.assertEqual(avisos, [])
