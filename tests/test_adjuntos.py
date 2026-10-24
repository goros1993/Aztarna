"""Adjuntos de las pruebas y secciones (app/adjuntos.py): Excel incrustados en el Word, al importar y al exportar."""
import io
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from openpyxl import Workbook

from app import adjuntos, esquema
from app import ejecucion_core as ej
from app import importacion as imp
from app import yaml_a_docx
from app.editor_api import EditorApi, to_plain
from app.editor_core import items_in_chapter, read_chapters, save_chapter, tests_in_chapter
from tests.test_conversion import EMF_MINIMAL

EJEMPLOS = Path(__file__).resolve().parents[1] / "ejemplos" / "yaml"
# Un .xls como los que salen de un Word: archivo compuesto de OLE con la marca «\x01Ole».
XLS_INCRUSTADO = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + bytes(504) + "\x01Ole".encode("utf-16-le") + bytes(64)


def ok(testcase, resultado):
    testcase.assertTrue(resultado["ok"], resultado.get("error"))
    return resultado["datos"]


def _xlsx(valor):
    libro = Workbook()
    libro.active["A1"] = valor
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


def _objetos(docx):
    """(ProgID, DrawAspect) de cada objeto del Word, en orden, y los archivos incrustados."""
    import re
    with zipfile.ZipFile(docx) as z:
        documento = z.read("word/document.xml").decode("utf-8")
        incrustados = sorted(z.read(n) for n in z.namelist() if n.startswith("word/embeddings/"))
    return re.findall(r'ProgID="([^"]+)"[^>]*DrawAspect="([^"]+)"', documento), incrustados, documento


def _dibujos_entre_las_imagenes(carpeta, elemento):
    """Imágenes del elemento que son el dibujo de un objeto (el EMF de las pruebas): no debe haber."""
    return [r for r in adjuntos.rutas_imagen(elemento) if (carpeta / r).read_bytes() == EMF_MINIMAL]


class AdjuntosBase(unittest.TestCase):
    """Copia de los ejemplos con una prueba con adjuntos: dos en sus pasos (un .xlsx que se ve como
    icono y un .xls que se ve con su contenido), uno añadido a mano sin dibujo y un PDF."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        shutil.copytree(EJEMPLOS, self.tmp / "yaml")
        self.pruebas = self.tmp / "yaml" / "pruebas"
        esquema.configurar(self.pruebas)
        self.hoja, self.manual = _xlsx("de la prueba"), _xlsx("añadido a mano")
        carpeta = self.pruebas / "adjuntos"
        carpeta.mkdir()
        for nombre, datos in (("hoja.xlsx", self.hoja), ("hoja.emf", EMF_MINIMAL), ("antiguo.xls", XLS_INCRUSTADO),
                              ("antiguo.emf", EMF_MINIMAL), ("manual.xlsx", self.manual), ("nota.pdf", b"%PDF-1.4\n")):
            (carpeta / nombre).write_bytes(datos)
        capitulo = read_chapters(self.pruebas)[0]
        _i, prueba = tests_in_chapter(capitulo)[0]
        self.id = str(prueba["id"])
        prueba["pasos"] = [{"texto": "Rellenar la hoja de cargas", "adjuntos": ["adjuntos/hoja.xlsx"]},
                           {"texto": "Comparar con la tabla antigua", "adjuntos": ["adjuntos/antiguo.xls"]}]
        prueba["adjuntos"] = [{"archivo": "adjuntos/hoja.xlsx", "vista_previa": "adjuntos/hoja.emf", "icono": True},
                              {"archivo": "adjuntos/antiguo.xls", "vista_previa": "adjuntos/antiguo.emf"},
                              "adjuntos/manual.xlsx", {"archivo": "adjuntos/nota.pdf"}]
        save_chapter(capitulo)

    def prueba(self, carpeta, ident=None):
        return next(to_plain(p) for c in read_chapters(carpeta) for _i, p in items_in_chapter(c, "prueba")
                    if str(p.get("id")) == (ident or self.id))

    def exportar_e_importar(self, docx=None):
        docx = docx or self.tmp / "pruebas.docx"
        if not docx.exists():
            yaml_a_docx.generar_docx(self.pruebas, docx)
        r = imp.importar(docx, imp.mapeo_propuesto(imp.analizar(docx)), self.tmp / "proyecto")
        return Path(r["carpetas"]["prueba"])


class ExportarTests(AdjuntosBase):
    def test_el_word_lleva_los_adjuntos_incrustados_como_estaban(self):
        docx = self.tmp / "pruebas.docx"
        yaml_a_docx.generar_docx(self.pruebas, docx)
        objetos, incrustados, documento = _objetos(docx)
        # En su paso, como estaban (icono: se abre en Excel); el añadido a mano, al final y como icono.
        self.assertEqual(objetos, [("Excel.Sheet.12", "Icon"), ("Excel.Sheet.8", "Content"), ("Excel.Sheet.12", "Icon")])
        self.assertEqual(incrustados, sorted([self.hoja, XLS_INCRUSTADO, self.manual]))
        self.assertLess(documento.index("Excel.Sheet.8"), documento.index(">Adjuntos:<"))
        self.assertIn("nota.pdf", documento)              # el PDF no se incrusta: sale su nombre

    def test_ida_y_vuelta(self):
        """Se exporta y se vuelve a importar: los adjuntos vuelven a su párrafo; su dibujo no es una imagen."""
        carpeta = self.exportar_e_importar()
        prueba = self.prueba(carpeta)
        lista = adjuntos.lista(prueba.get("adjuntos"))
        self.assertEqual([Path(a["archivo"]).suffix for a in lista], [".xlsx", ".xls", ".xlsx"])
        self.assertTrue(all(a["archivo"].startswith(f"adjuntos/{self.id}_") for a in lista))
        self.assertEqual([(carpeta / a["archivo"]).read_bytes() for a in lista], [self.hoja, XLS_INCRUSTADO, self.manual])
        self.assertTrue(all(a["vista_previa"].startswith("adjuntos/") and (carpeta / a["vista_previa"]).is_file() for a in lista))
        self.assertEqual([bool(a.get("icono")) for a in lista], [True, False, True])
        self.assertEqual(prueba["pasos"][0], {"texto": "Rellenar la hoja de cargas", "adjuntos": [lista[0]["archivo"]]})
        self.assertEqual(prueba["pasos"][1], {"texto": "Comparar con la tabla antigua", "adjuntos": [lista[1]["archivo"]]})
        self.assertFalse(_dibujos_entre_las_imagenes(carpeta, prueba))       # sus dibujos no son imágenes
        self.assertNotIn("Adjuntos", prueba.get("campos_adicionales") or {})
        self.assertIn("se guarda como adjunto", (self.tmp / "proyecto" / "avisos.txt").read_text(encoding="utf-8"))
        # Y otra vez a Word: los mismos objetos, igual que la primera vez.
        otra = self.tmp / "otra.docx"
        yaml_a_docx.generar_docx(carpeta, otra)
        self.assertEqual(_objetos(otra)[:2], _objetos(self.tmp / "pruebas.docx")[:2])

    def test_importar_anadiendo_no_pisa_los_adjuntos_que_ya_hay(self):
        docx = self.tmp / "pruebas.docx"
        yaml_a_docx.generar_docx(self.pruebas, docx)
        analisis = imp.analizar(docx)
        proyecto = self.tmp / "proyecto"
        imp.importar(docx, imp.mapeo_propuesto(analisis), proyecto)
        carpeta = proyecto / esquema.CARPETA_PRUEBAS
        antes = {p.name: p.read_bytes() for p in (carpeta / "adjuntos").iterdir()}
        r = imp.importar(docx, imp.mapeo_propuesto(analisis), proyecto, "anadir", renombrar_propuestos=True)
        self.assertGreater(r["totales"]["prueba"], 0)
        for nombre, datos in antes.items():
            self.assertEqual((carpeta / "adjuntos" / nombre).read_bytes(), datos)
        self.assertGreater(len(list((carpeta / "adjuntos").iterdir())), len(antes))

    def test_objeto_que_no_se_puede_extraer_queda_como_imagen_con_aviso(self):
        docx = self.tmp / "pruebas.docx"
        yaml_a_docx.generar_docx(self.pruebas, docx)
        with zipfile.ZipFile(docx) as z:
            partes = {n: z.read(n) for n in z.namelist()}
        documento = partes["word/document.xml"].decode("utf-8").replace('ProgID="Excel.Sheet.8"', 'ProgID="Package"')
        partes["word/document.xml"] = documento.encode("utf-8")
        with zipfile.ZipFile(docx, "w") as z:
            for nombre, datos in partes.items():
                z.writestr(nombre, datos)
        prueba = self.prueba(self.exportar_e_importar(docx))
        self.assertEqual(len(adjuntos.lista(prueba["adjuntos"])), 2)
        self.assertTrue(prueba["pasos"][1].get("imagenes"))           # su imagen sigue en el paso
        self.assertNotIn("adjuntos", prueba["pasos"][1])
        avisos = (self.tmp / "proyecto" / "avisos.txt").read_text(encoding="utf-8")
        self.assertEqual(avisos.count("no se puede extraer"), 1)


class FueraDeLaTablaTests(unittest.TestCase):
    """Objetos en el contexto de una sección y en el de una prueba (antes de su tabla)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        shutil.copytree(EJEMPLOS, self.tmp / "yaml")
        self.pruebas = self.tmp / "yaml" / "pruebas"
        esquema.configurar(self.pruebas)
        self.cargas, self.prueba_ctx, self.manual = _xlsx("cargas"), _xlsx("contexto de la prueba"), _xlsx("a mano")
        carpeta = self.pruebas / "adjuntos"
        carpeta.mkdir()
        for nombre, datos in (("cargas.xlsx", self.cargas), ("cargas.emf", EMF_MINIMAL), ("ctx.xlsx", self.prueba_ctx),
                              ("ctx.emf", EMF_MINIMAL), ("manual.xlsx", self.manual)):
            (carpeta / nombre).write_bytes(datos)
        capitulo = read_chapters(self.pruebas)[0]
        contenido = capitulo["data"]["contenido"]
        seccion = next(e for e in contenido if isinstance(e, dict) and isinstance(e.get("seccion"), str))
        self.seccion = str(seccion["seccion"])
        seccion["contexto"] = [{"texto": "Tabla de cargas de la sección", "adjuntos": ["adjuntos/cargas.xlsx"]}]
        seccion["adjuntos"] = [{"archivo": "adjuntos/cargas.xlsx", "vista_previa": "adjuntos/cargas.emf", "icono": True},
                               {"archivo": "adjuntos/manual.xlsx"}]
        _i, prueba = tests_in_chapter(capitulo)[0]
        self.id = str(prueba["id"])
        prueba["nombre"] = prueba.get("nombre") or "Con contexto"
        prueba["contexto"] = [{"texto": "Datos de partida", "adjuntos": ["adjuntos/ctx.xlsx"]}]
        prueba["adjuntos"] = [{"archivo": "adjuntos/ctx.xlsx", "vista_previa": "adjuntos/ctx.emf", "icono": True}]
        save_chapter(capitulo)

    def test_ida_y_vuelta(self):
        docx = self.tmp / "pruebas.docx"
        yaml_a_docx.generar_docx(self.pruebas, docx)
        objetos, incrustados, _doc = _objetos(docx)
        self.assertEqual(incrustados, sorted([self.cargas, self.prueba_ctx, self.manual]))
        self.assertEqual({a for _p, a in objetos}, {"Icon"})
        r = imp.importar(docx, imp.mapeo_propuesto(imp.analizar(docx)), self.tmp / "proyecto")
        carpeta = Path(r["carpetas"]["prueba"])
        capitulo = read_chapters(carpeta)[0]
        seccion = next(to_plain(e) for e in capitulo["data"]["contenido"] if isinstance(e, dict) and e.get("seccion") == self.seccion)
        prueba = next(to_plain(p) for _i, p in tests_in_chapter(capitulo) if str(p.get("id")) == self.id)
        de_la_seccion = adjuntos.lista(seccion.get("adjuntos"))
        self.assertEqual([(carpeta / a["archivo"]).read_bytes() for a in de_la_seccion], [self.cargas, self.manual])
        nombrados = [r for item in seccion["contexto"] for r in adjuntos.referencias(item)]
        self.assertIn(de_la_seccion[0]["archivo"], nombrados)                # en su párrafo del contexto
        de_la_prueba = adjuntos.lista(prueba.get("adjuntos"))
        self.assertEqual([(carpeta / a["archivo"]).read_bytes() for a in de_la_prueba], [self.prueba_ctx])
        self.assertIn(de_la_prueba[0]["archivo"], [r for item in prueba["contexto"] for r in adjuntos.referencias(item)])
        self.assertFalse(_dibujos_entre_las_imagenes(carpeta, seccion) + _dibujos_entre_las_imagenes(carpeta, prueba))

    def test_guardar_y_validar_los_de_una_seccion(self):
        api = EditorApi(self.tmp / "yaml")
        ok(self, api.iniciar())
        indice = next(i for i, e in enumerate(api._chapters[0]["data"]["contenido"]) if isinstance(e, dict) and e.get("seccion") == self.seccion)
        ok(self, api.guardar_seccion(0, indice, {
            "adjuntos": ["adjuntos/cargas.xlsx", "adjuntos/no_esta.xlsx"],
            "contexto": [{"texto": "", "adjuntos": ["adjuntos/cargas.xlsx"]}]}))            # un párrafo solo con el adjunto se queda
        seccion = to_plain(api._chapters[0]["data"]["contenido"][indice])
        self.assertEqual(seccion["adjuntos"], [{"archivo": "adjuntos/cargas.xlsx"}, {"archivo": "adjuntos/no_esta.xlsx"}])
        self.assertEqual(seccion["contexto"], [{"texto": "", "adjuntos": ["adjuntos/cargas.xlsx"]}])
        problemas = ok(self, api.validar())["problemas"]
        self.assertTrue(any(p["mensaje"] == "No existe el adjunto: adjuntos/no_esta.xlsx." for p in problemas))


class EditorTests(AdjuntosBase):
    def setUp(self):
        super().setUp()
        self.api = EditorApi(self.tmp / "yaml")
        ok(self, self.api.iniciar())

    def _posicion(self):
        for ci, c in enumerate(self.api._chapters):
            for i, p in tests_in_chapter(c):
                if str(p.get("id")) == self.id:
                    return ci, i
        raise AssertionError(self.id)

    def test_guardar_y_validar(self):
        ci, i = self._posicion()
        ok(self, self.api.guardar_prueba(ci, i, {"adjuntos": ["adjuntos/hoja.xlsx", {"archivo": "adjuntos/no_esta.xlsx"}]}))
        self.assertEqual(self.prueba(self.pruebas)["adjuntos"], [{"archivo": "adjuntos/hoja.xlsx"}, {"archivo": "adjuntos/no_esta.xlsx"}])
        problemas = ok(self, self.api.validar())["problemas"]
        self.assertTrue(any(p["mensaje"] == "No existe el adjunto: adjuntos/no_esta.xlsx." for p in problemas))
        self.assertFalse(self.api.guardar_prueba(ci, i, {"adjuntos": "adjuntos/hoja.xlsx"})["ok"])

    def test_el_dibujo_y_el_icono_se_conservan_al_guardar(self):
        ci, i = self._posicion()
        antes = self.prueba(self.pruebas)["adjuntos"]
        ok(self, self.api.guardar_prueba(ci, i, {"adjuntos": antes, "pasos": self.prueba(self.pruebas)["pasos"]}))
        despues = self.prueba(self.pruebas)
        self.assertEqual(despues["adjuntos"][0], {"archivo": "adjuntos/hoja.xlsx", "vista_previa": "adjuntos/hoja.emf", "icono": True})
        self.assertEqual(despues["pasos"][0]["adjuntos"], ["adjuntos/hoja.xlsx"])

    def test_copiar_adjuntos_no_pisa_otro_con_el_mismo_nombre(self):
        fuera = self.tmp / "fuera"
        fuera.mkdir()
        (fuera / "hoja.xlsx").write_bytes(self.manual)       # mismo nombre, otro contenido
        (fuera / "nuevo.xlsx").write_bytes(self.hoja)
        nuevos = self.api._copiar_adjuntos([fuera / "hoja.xlsx", fuera / "nuevo.xlsx"])
        self.assertEqual(nuevos, [{"archivo": "adjuntos/hoja_2.xlsx"}, {"archivo": "adjuntos/nuevo.xlsx"}])
        self.assertEqual((self.pruebas / "adjuntos" / "hoja.xlsx").read_bytes(), self.hoja)
        self.assertFalse(self.api.abrir_adjunto("../aztarna.yaml")["ok"])      # solo los de la carpeta de pruebas

    def test_la_ejecucion_cerrada_congela_los_adjuntos(self):
        ejecucion = ej.crear(self.tmp / "ejec", self.pruebas, "E", {"incluir_ids": [self.id], "capitulos": ["__x__"]}, {})
        destino = ej.congelar(ejecucion, read_chapters(self.pruebas))
        for ruta in ("adjuntos/hoja.xlsx", "adjuntos/hoja.emf", "adjuntos/antiguo.xls"):
            self.assertTrue((destino / ruta).is_file(), ruta)


if __name__ == "__main__":
    unittest.main()
