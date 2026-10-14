import base64
from io import BytesIO
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from docx import Document

import convertir
import yaml_a_docx


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/"
    "p3sAAAAASUVORK5CYII="
)

EMF_MINIMAL = (
    struct.pack(
        "<II4i4iIIII",
        1, 108,
        0, 0, 1, 1,
        0, 0, 1000, 500,
        0x464D4520, 0x10000, 128, 2,
    )
    + bytes(108 - 56)
    + struct.pack("<IIIII", 14, 20, 0, 0, 20)
)


class ParsearTablaVarianteTests(unittest.TestCase):
    def test_exporta_emf_nativo_en_el_docx(self):
        with TemporaryDirectory() as temp:
            base_dir = Path(temp)
            emf = base_dir / "vector.emf"
            emf.write_bytes(EMF_MINIMAL)
            doc = Document()
            parrafo = doc.add_paragraph()
            yaml_a_docx.agregar_imagen(parrafo.add_run(), emf, yaml_a_docx.Cm(10))
            destino = base_dir / "salida.docx"
            doc.save(destino)

            with ZipFile(destino) as paquete:
                emf_en_docx = next(
                    nombre for nombre in paquete.namelist()
                    if nombre.endswith(".emf")
                )
                self.assertEqual(paquete.read(emf_en_docx), EMF_MINIMAL)

            reabierto = Document(destino)
            self.assertEqual(len(reabierto.inline_shapes), 1)

    def test_extrae_imagenes_del_contexto_y_de_la_tabla(self):
        doc = Document()
        doc.add_heading("Capítulo", level=1)
        doc.add_heading("Prueba", level=2)
        parrafo_contexto = doc.add_paragraph("Contexto con imagen ")
        parrafo_contexto.add_run().add_picture(BytesIO(PNG_1X1))

        tabla = doc.add_table(rows=2, cols=2)
        tabla.cell(0, 0).text = "TEST-IMG"
        tabla.cell(0, 1).text = "Prueba con imagen"
        tabla.cell(1, 0).text = "Situación inicial:"
        parrafo_seccion = tabla.cell(1, 0).add_paragraph("Ver el estado ")
        parrafo_seccion.add_run().add_picture(BytesIO(PNG_1X1))
        tabla.cell(1, 1).text = "Imagen general"
        tabla.cell(1, 1).paragraphs[0].add_run().add_picture(BytesIO(PNG_1X1))

        with TemporaryDirectory() as temp:
            salida = Path(temp)
            guardar = convertir.crear_guardador_imagenes(salida / "imagenes")
            capitulos = convertir.extraer_capitulos(doc, [], guardar)

            prueba = next(
                e["prueba"] for e in capitulos[0]["contenido"] if "prueba" in e
            )
            contexto = prueba["contexto"][0]

            self.assertEqual(contexto["texto"], "Contexto con imagen")
            self.assertEqual(contexto["imagenes"], ["imagenes/imagen_001.png"])
            self.assertEqual(
                prueba["situacion_inicial"][0]["imagenes"],
                ["imagenes/imagen_001.png"],
            )
            self.assertEqual(prueba["imagenes"], ["imagenes/imagen_001.png"])
            self.assertEqual(
                (salida / "imagenes" / "imagen_001.png").read_bytes(),
                PNG_1X1,
            )

    def test_exporta_imagenes_desde_contexto_lista_y_tabla(self):
        with TemporaryDirectory() as temp:
            base_dir = Path(temp)
            imagen = base_dir / "tiny.png"
            imagen.write_bytes(PNG_1X1)
            doc = Document()
            yaml_a_docx.escribir_contexto(
                doc,
                [{"texto": "Contexto", "imagenes": ["tiny.png"]}],
                base_dir,
            )
            yaml_a_docx.tabla_prueba(
                doc,
                {
                    "id": "TEST-IMG",
                    "situacion_inicial": [
                        {"texto": "Inicio", "imagenes": ["tiny.png"]}
                    ],
                    "imagenes": ["tiny.png"],
                },
                base_dir,
            )

            self.assertEqual(len(doc.inline_shapes), 3)

    def test_asocia_texto_suelto_a_pruebas_o_grupos_segun_titulos(self):
        doc = Document()
        doc.add_heading("Capítulo", level=1)
        doc.add_heading("Grupo", level=2)
        doc.add_paragraph("Contexto aplicable al grupo.")
        doc.add_heading("Subgrupo", level=3)
        doc.add_heading("Prueba uno", level=4)
        doc.add_paragraph("Contexto aplicable solo a la primera tabla.")
        primera = doc.add_table(rows=1, cols=2)
        primera.cell(0, 0).text = "TEST-001"
        primera.cell(0, 1).text = "Primera prueba"
        doc.add_heading("Prueba dos", level=4)
        segunda = doc.add_table(rows=1, cols=2)
        segunda.cell(0, 0).text = "TEST-002"
        segunda.cell(0, 1).text = "Segunda prueba"

        avisos = []
        capitulos = convertir.extraer_capitulos(doc, avisos)
        elementos = capitulos[0]["contenido"]
        grupo = next(e for e in elementos if e.get("seccion") == "Grupo")
        primera_prueba = next(
            e["prueba"] for e in elementos if e.get("prueba", {}).get("id") == "TEST-001"
        )
        segunda_prueba = next(
            e["prueba"] for e in elementos if e.get("prueba", {}).get("id") == "TEST-002"
        )

        self.assertEqual(grupo["contexto"], ["Contexto aplicable al grupo."])
        self.assertEqual(
            primera_prueba["contexto"],
            ["Contexto aplicable solo a la primera tabla."],
        )
        self.assertNotIn("contexto", segunda_prueba)

    def test_mantiene_el_parseo_del_formato_estandar(self):
        doc = Document()
        tabla = doc.add_table(rows=4, cols=4)
        tabla.cell(0, 0).text = "TEST-001"
        tabla.cell(0, 1).text = "Prueba estándar"
        tabla.cell(1, 0).text = "Descripción: Verificar la llamada."
        tabla.cell(1, 1).text = "Componente: CPU_A"
        tabla.cell(1, 2).text = "Plataforma: HIL"
        tabla.cell(2, 0).text = (
            "Situación inicial:\nAscensor en reposo.\n"
            "Pasos:\nRealizar una llamada.\n"
            "Situación final:\nLa llamada se atiende."
        )
        tabla.cell(3, 0).text = "Automatizable: Sí"
        tabla.cell(3, 1).text = "Criticidad: Alta"
        tabla.cell(3, 2).text = "Entorno de pruebas: HIL"
        tabla.cell(3, 3).text = "Referencia: REF-1 Fecha: 2026 Versión: 1"

        avisos = []
        prueba = convertir.parsear(tabla, avisos)

        self.assertEqual(prueba["descripcion"], "Verificar la llamada.")
        self.assertEqual(prueba["situacion_inicial"], ["Ascensor en reposo."])
        self.assertEqual(prueba["pasos"], ["Realizar una llamada."])
        self.assertEqual(prueba["situacion_final"], ["La llamada se atiende."])
        self.assertEqual(prueba["automatizable"], "si")
        self.assertFalse(avisos)

    def test_parsea_campos_de_formato_alternativo_y_preserva_campos_extra(self):
        doc = Document()
        tabla = doc.add_table(rows=6, cols=2)
        tabla.cell(0, 0).text = "DEMO-FUNC-007"
        tabla.cell(0, 1).text = "Accionamiento vertical regulado"
        tabla.cell(1, 0).text = (
            "Condiciones iniciales:\n"
            "• CPU_A en PLACA_B\n"
            "• CPU_A parametrizada"
        )
        tabla.cell(1, 1).text = (
            "ENSAYO(s) / Proceso(s): ENSAYO 1 (Tipos de movimiento)\n"
            "• Ascensor en una planta intermedia."
        )
        tabla.cell(2, 0).text = (
            "Resultado esperado: Indicado en ensayo. "
            "Criterio(s) de aceptación: Indicado en ensayo. "
            "Componente: CPU_A"
        )
        tabla.cell(2, 1).text = (
            "Maniobra(s): Triplex "
            "Criterio validación: Test "
            "Entorno de prueba(s): BANCO-02"
        )
        tabla.cell(3, 0).text = "Automatizable: Largo"
        tabla.cell(3, 1).text = "Entorno de pruebas: "
        tabla.cell(4, 0).text = "Ejecutor prueba:  Fecha ejecución: "
        tabla.cell(4, 1).text = "Resultado Obtenido: Decisión: Resultado:"
        tabla.cell(5, 0).text = "Criticidad: "
        tabla.cell(5, 1).text = "Referencia: <N.A> Fecha: 15/11/2024 Versión: 1.0"

        avisos = []
        prueba = convertir.parsear(tabla, avisos)

        self.assertEqual(prueba["id"], "DEMO-FUNC-007")
        self.assertEqual(prueba["componente"], "CPU_A")
        self.assertEqual(prueba["automatizable"], "largo")
        self.assertEqual(prueba["situacion_inicial"], ["CPU_A en PLACA_B", "CPU_A parametrizada"])
        self.assertEqual(
            prueba["pasos"],
            ["ENSAYO 1 (Tipos de movimiento)", "Ascensor en una planta intermedia."],
        )
        self.assertEqual(prueba["entorno"], "BANCO-02")
        self.assertEqual(
            prueba["campos_adicionales"],
            {
                "Resultado esperado": "Indicado en ensayo.",
                "Criterio(s) de aceptación": "Indicado en ensayo.",
                "Maniobra(s)": "Triplex",
                "Criterio validación": "Test",
                "Ejecutor prueba": "",
                "Fecha ejecución": "",
                "Resultado Obtenido": "",
                "Decisión": "",
                "Resultado": "",
            },
        )
        self.assertFalse(avisos)

    def test_exporta_campos_adicionales_en_el_docx(self):
        doc = Document()
        yaml_a_docx.escribir_contexto(doc, ["Contexto asociado a la prueba."], docx_base_dir())
        yaml_a_docx.tabla_prueba(
            doc,
            {
                "id": "TEST-001",
                "campos_adicionales": {
                    "Resultado esperado": "Indicado en ensayo.",
                    "Requisito(s)": "REQ-001",
                },
            },
            docx_base_dir(),
        )

        self.assertEqual(doc.paragraphs[0].text, "Contexto asociado a la prueba.")
        textos = [celda.text for fila in doc.tables[0].rows for celda in fila.cells]
        self.assertTrue(any("Resultado esperado: Indicado en ensayo." in texto for texto in textos))
        self.assertTrue(any("Requisito(s): REQ-001" in texto for texto in textos))


def docx_base_dir():
    from pathlib import Path

    return Path(".")


class TamañoImagenesTests(unittest.TestCase):
    def test_las_imagenes_altas_no_superan_el_alto_maximo(self):
        from docx.shared import Cm
        from PIL import Image

        with TemporaryDirectory() as tmp:
            alta, ancha = Path(tmp) / "alta.png", Path(tmp) / "ancha.png"
            Image.new("RGB", (300, 900), "white").save(alta)
            Image.new("RGB", (900, 300), "white").save(ancha)
            doc = Document()
            yaml_a_docx.agregar_imagen(doc.add_paragraph().add_run(), alta, Cm(10))
            yaml_a_docx.agregar_imagen(doc.add_paragraph().add_run(), ancha, Cm(10))
            primera, segunda = doc.inline_shapes
            self.assertLessEqual(primera.height, Cm(yaml_a_docx.ALTO_MAX_IMAGEN_CM) + 1)
            self.assertLess(primera.width, Cm(10))
            self.assertEqual(segunda.width, Cm(10))


if __name__ == "__main__":
    unittest.main()
