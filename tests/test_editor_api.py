"""Pruebas de la API del editor web (no necesitan interfaz ni pywebview)."""
import base64
import io
import shutil
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image
from ruamel.yaml import YAML

from app import editor_api
from app.editor_core import element_level, move_block

EJEMPLOS = Path(__file__).resolve().parent.parent / "ejemplos" / "yaml" / "pruebas"

CAPITULO = """\
capitulo: Demo  # comentario del capítulo
contenido:
- seccion: A
  nivel: 2
- prueba:
    nombre: Uno
    nivel: 3
    id: T-1
    titulo: Primera  # comentario del título
    pasos:
    - texto: hacer algo
    fecha: 2024-05-01
- seccion: B
  nivel: 2
- seccion: B1
  nivel: 3
- prueba:
    nombre: Dos
    nivel: 4
    id: T-2
    titulo: Segunda
- prueba:
    nombre: Tres
    nivel: 3
    id: T-3
    titulo: Tercera
"""


def ok(testcase, resultado):
    testcase.assertTrue(resultado["ok"], resultado.get("error"))
    return resultado["datos"]


class ApiBase(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name) / "yaml"
        self.dir.mkdir()
        (self.dir / "01_demo.yaml").write_text(CAPITULO, encoding="utf-8")
        self.api = editor_api.EditorApi(self.dir)
        ok(self, self.api.iniciar())

    def contenido(self):
        with (self.dir / "01_demo.yaml").open(encoding="utf-8") as fh:
            return YAML().load(fh)["contenido"]


class ApiTests(ApiBase):
    def test_iniciar_y_navegacion_reflejan_la_jerarquia(self):
        estado = ok(self, self.api.iniciar())
        self.assertEqual(estado["capitulos"][0]["pruebas"], 3)
        nodos = ok(self, self.api.navegacion(0))
        self.assertEqual(
            [(n["tipo"], n["titulo"], n["padre"]) for n in nodos],
            [("seccion", "A", None), ("prueba", "Primera", 0),
             ("seccion", "B", None), ("seccion", "B1", 2),
             ("prueba", "Segunda", 3), ("prueba", "Tercera", 2)],
        )
        busqueda = ok(self, self.api.navegacion(0, "segunda"))
        self.assertEqual([n["id"] for n in busqueda if n["tipo"] == "prueba"], ["T-2"])

    def test_guardar_solo_toca_los_campos_enviados_y_conserva_comentarios(self):
        ok(self, self.api.guardar_prueba(0, 1, {"descripcion": "Nueva"}))
        texto = (self.dir / "01_demo.yaml").read_text(encoding="utf-8")
        self.assertIn("# comentario del capítulo", texto)
        self.assertIn("# comentario del título", texto)
        self.assertIn("fecha: 2024-05-01", texto)
        self.assertIn("descripcion: Nueva", texto)
        self.assertNotIn("componente", texto)

    def test_un_campo_vacio_que_no_existe_no_se_anade(self):
        ok(self, self.api.guardar_prueba(0, 1, {"version": "", "contexto": []}))
        self.assertNotIn("version", (self.dir / "01_demo.yaml").read_text(encoding="utf-8"))

    def test_campos_del_esquema(self):
        ok(self, self.api.guardar_prueba(0, 1, {
            "entorno": ["Torre", "Automático"], "maniobra": ["Dúplex"], "requisitos": [" REQ-1 ", "REQ-2", "REQ-1"],
            "automatizable": "Largo", "parametrizacion": ["Velocidad 1 m/s"],
        }))
        prueba = self.contenido()[1]["prueba"]
        self.assertEqual(prueba["entorno"], ["Automático", "Torre"])          # en el orden de las opciones
        self.assertEqual(prueba["requisitos"], ["REQ-1", "REQ-2"])
        self.assertEqual(prueba["automatizable"], "largo")
        self.assertFalse(self.api.guardar_prueba(0, 1, {"entorno": ["HIL"]})["ok"])
        self.assertFalse(self.api.guardar_prueba(0, 1, {"automatizable": "a veces"})["ok"])
        self.assertFalse(self.api.guardar_prueba(0, 1, {"criticidad": "alta"})["ok"])     # ya no existe
        esq = ok(self, self.api.esquema())
        self.assertEqual(esq["opciones"]["maniobra"], ["Simplex", "Dúplex"])
        self.assertEqual(esq["etiquetas"]["pasos"], "Ensayo")

    def test_validacion_del_esquema(self):
        datos = YAML().load((self.dir / "01_demo.yaml").read_text(encoding="utf-8"))
        prueba = datos["contenido"][1]["prueba"]
        prueba["criticidad"] = "alta"
        prueba["entorno"] = ["HIL"]
        del prueba["titulo"]
        with (self.dir / "01_demo.yaml").open("w", encoding="utf-8") as f:
            YAML().dump(datos, f)
        ok(self, self.api.recargar())
        problemas = [(p["severidad"], p["mensaje"]) for p in ok(self, self.api.validar())["problemas"] if p["id"] == "T-1"]
        self.assertIn(("error", "La prueba no tiene título."), problemas)
        self.assertTrue(any("ya no existen: criticidad" in m for _s, m in problemas))
        self.assertTrue(any("«HIL» no es una opción" in m for _s, m in problemas))

    def test_guardar_etiquetas_limpias_y_proponerlas(self):
        ok(self, self.api.guardar_prueba(0, 1, {"etiquetas": [" smoke ", "regresion", "smoke", ""]}))
        self.assertEqual(list(self.contenido()[1]["prueba"]["etiquetas"]), ["smoke", "regresion"])
        self.assertEqual(ok(self, self.api.etiquetas()), ["regresion", "smoke"])
        ok(self, self.api.guardar_prueba(0, 4, {"etiquetas": ["smoke"]}))
        self.assertEqual(ok(self, self.api.etiquetas_uso()),
                         [{"etiqueta": "smoke", "usos": 2}, {"etiqueta": "regresion", "usos": 1}])
        self.assertFalse(self.api.guardar_prueba(0, 1, {"etiquetas": "smoke"})["ok"])

    def test_guardar_listas_con_imagenes(self):
        pasos = [{"texto": "uno", "imagenes": ["imagenes/a.png"]}, "dos", ""]
        ok(self, self.api.guardar_prueba(0, 1, {"pasos": pasos}))
        guardado = self.contenido()[1]["prueba"]["pasos"]
        self.assertEqual([dict(p) if isinstance(p, dict) else p for p in guardado],
                         [{"texto": "uno", "imagenes": ["imagenes/a.png"]}, "dos"])

    def test_id_duplicado_se_rechaza_y_no_cambia_el_archivo(self):
        antes = (self.dir / "01_demo.yaml").read_text(encoding="utf-8")
        resultado = self.api.guardar_prueba(0, 1, {"id": "T-2"})
        self.assertFalse(resultado["ok"])
        self.assertIn("ya existe", resultado["error"])
        self.assertEqual(antes, (self.dir / "01_demo.yaml").read_text(encoding="utf-8"))

    def test_crear_prueba_calcula_el_nivel_segun_la_ubicacion(self):
        nuevo = ok(self, self.api.crear_prueba(
            0, {"tipo": "seccion", "indice": 2}, {"id": "T-4", "titulo": "Cuarta"}))
        contenido = self.contenido()
        self.assertEqual(contenido[nuevo["indice"]]["prueba"]["id"], "T-4")
        self.assertEqual(contenido[nuevo["indice"]]["prueba"]["nivel"], 3)
        despues = ok(self, self.api.crear_prueba(
            0, {"tipo": "despues", "indice": 4}, {"id": "T-5"}))
        self.assertEqual(self.contenido()[despues["indice"]]["prueba"]["nivel"], 4)
        final = ok(self, self.api.crear_prueba(0, {"tipo": "final"}, {"id": "T-6"}))
        self.assertEqual(final["indice"], len(self.contenido()) - 1)

    def test_crear_prueba_exige_id_unico(self):
        self.assertFalse(self.api.crear_prueba(0, {"tipo": "final"}, {"id": ""})["ok"])
        self.assertFalse(self.api.crear_prueba(0, {"tipo": "final"}, {"id": "T-1"})["ok"])

    def test_crear_y_borrar_secciones(self):
        nueva = ok(self, self.api.crear_seccion(0, {"tipo": "seccion", "indice": 0}, " Hija "))
        elemento = self.contenido()[nueva["indice"]]
        self.assertEqual((elemento["seccion"], elemento["nivel"]), ("Hija", 3))
        ok(self, self.api.borrar_seccion(0, nueva["indice"]))
        self.assertNotIn("Hija", [e.get("seccion") for e in self.contenido()])
        self.assertFalse(self.api.crear_seccion(0, {"tipo": "final"}, "  ")["ok"])

    def test_guardar_seccion_cambia_nombre_y_contexto(self):
        ok(self, self.api.guardar_seccion(0, 0, {"nombre": "Alfa", "contexto": ["Nota"]}))
        seccion = self.contenido()[0]
        self.assertEqual((seccion["seccion"], list(seccion["contexto"])), ("Alfa", ["Nota"]))
        self.assertFalse(self.api.guardar_seccion(0, 0, {"nombre": " "})["ok"])

    def test_borrar_prueba(self):
        ok(self, self.api.borrar_prueba(0, 1))
        self.assertEqual(len(self.contenido()), 5)
        self.assertFalse(self.api.borrar_prueba(0, 0)["ok"])

    def test_cambio_externo_se_detecta_antes_de_guardar(self):
        time.sleep(0.01)
        ruta = self.dir / "01_demo.yaml"
        ruta.write_text(CAPITULO.replace("Primera", "Editada fuera"), encoding="utf-8")
        resultado = self.api.guardar_prueba(0, 1, {"descripcion": "x"})
        self.assertFalse(resultado["ok"])
        self.assertIn("ha cambiado en el disco", resultado["error"])
        self.assertEqual(ok(self, self.api.obtener(0, 1))["elemento"]["titulo"], "Editada fuera")
        ok(self, self.api.guardar_prueba(0, 1, {"descripcion": "x"}))

    def test_obtener_convierte_fechas_y_normaliza_nivel(self):
        prueba = ok(self, self.api.obtener(0, 1))
        self.assertEqual(prueba["tipo"], "prueba")
        self.assertEqual(prueba["elemento"]["fecha"], "2024-05-01")
        self.assertEqual(ok(self, self.api.obtener(0, 0))["tipo"], "seccion")

    def test_yaml_en_bruto(self):
        texto = ok(self, self.api.obtener_yaml(0, 1))["texto"]
        self.assertIn("titulo: Primera", texto)
        malo = ok(self, self.api.validar_yaml("a: [1, 2\nb: 3"))
        self.assertFalse(malo["valido"])
        self.assertGreaterEqual(malo["linea"], 1)
        self.assertTrue(ok(self, self.api.validar_yaml(texto))["valido"])
        ok(self, self.api.aplicar_yaml(0, 1, texto.replace("Primera", "Reescrita")))
        self.assertEqual(self.contenido()[1]["prueba"]["titulo"], "Reescrita")
        self.assertFalse(self.api.aplicar_yaml(0, 1, "- no es un mapa")["ok"])
        self.assertFalse(self.api.aplicar_yaml(0, 1, texto.replace("T-1", "T-2"))["ok"])


class MoverTests(ApiBase):
    def test_mover_prueba_dentro_de_otra_seccion_ajusta_el_nivel(self):
        resultado = ok(self, self.api.mover(0, 1, 0 + 2, "dentro"))
        contenido = self.contenido()
        movida = contenido[resultado["indice"]]["prueba"]
        self.assertEqual(movida["id"], "T-1")
        self.assertEqual(movida["nivel"], 3)
        self.assertLess(contenido.index(contenido[2]), resultado["indice"])

    def test_mover_seccion_arrastra_a_sus_hijos_y_reajusta_niveles(self):
        resultado = ok(self, self.api.mover(0, 2, 0, "dentro"))
        niveles = [(e.get("seccion") or e["prueba"]["id"], element_level(e))
                   for e in self.contenido()]
        self.assertEqual(niveles, [
            ("A", 2), ("T-1", 3), ("B", 3), ("B1", 4), ("T-2", 5), ("T-3", 4)])
        self.assertEqual(resultado["indice"], 2)

    def test_no_se_puede_mover_dentro_de_si_mismo_ni_pasar_de_nivel_seis(self):
        self.assertFalse(self.api.mover(0, 2, 3, "dentro")["ok"])
        chapter = {"data": {"contenido": [
            {"seccion": "S", "nivel": 5}, {"prueba": {"id": "x", "nivel": 6}},
            {"seccion": "R", "nivel": 2}, {"prueba": {"id": "y", "nivel": 3}}]}}
        with self.assertRaises(ValueError):
            move_block(chapter, 2, 0, "dentro")

    def test_mover_antes_y_despues(self):
        ok(self, self.api.mover(0, 5, 1, "antes"))
        ids = [e["prueba"]["id"] for e in self.contenido() if "prueba" in e]
        self.assertEqual(ids, ["T-3", "T-1", "T-2"])
        ok(self, self.api.mover(0, 1, 5, "despues"))
        ids = [e["prueba"]["id"] for e in self.contenido() if "prueba" in e]
        self.assertEqual(ids, ["T-1", "T-2", "T-3"])


class TablasTests(ApiBase):
    """Tablas que no son pruebas: se ven en el árbol, se editan, crean, mueven y borran."""

    def nodos(self):
        return ok(self, self.api.navegacion(0))

    def crear(self, ubicacion, filas=None):
        return ok(self, self.api.crear_tabla(0, ubicacion, {"filas": filas} if filas else None))["indice"]

    def leer(self):
        return YAML().load((self.dir / "01_demo.yaml").read_text(encoding="utf-8"))["contenido"]

    def test_crear_editar_y_borrar(self):
        indice = self.crear({"tipo": "seccion", "indice": 0})            # al final de la sección A
        self.assertEqual(indice, 2)
        nodo = self.nodos()[2]
        self.assertEqual((nodo["tipo"], nodo["padre"], nodo["filas"], nodo["columnas"]), ("tabla", 0, 2, 2))
        ok(self, self.api.guardar_tabla(0, indice, {"filas": [
            [{"texto": "**Parámetro**", "columnas": 2}],
            ["Velocidad", {"texto": "1 m/s", "imagenes": [], "columnas": 1}],
        ]}))
        self.assertEqual(self.leer()[2]["tabla"]["filas"],
                         [[{"texto": "**Parámetro**", "columnas": 2}], ["Velocidad", "1 m/s"]])
        datos = ok(self, self.api.obtener(0, indice))
        self.assertEqual(datos["tipo"], "tabla")
        self.assertEqual(self.nodos()[2]["titulo"], "Parámetro")             # sin marcas de formato
        self.assertEqual([n["tipo"] for n in ok(self, self.api.navegacion(0, "velocidad"))], ["seccion", "tabla"])
        self.assertFalse(self.api.guardar_tabla(0, indice, {"filas": []})["ok"])
        self.assertFalse(self.api.guardar_tabla(0, 1, {"filas": [["x"]]})["ok"])   # 1 es una prueba
        ok(self, self.api.borrar_tabla(0, indice))
        self.assertFalse(any("tabla" in e for e in self.leer()))

    def test_crear_despues_y_al_final(self):
        self.assertEqual(self.crear({"tipo": "despues", "indice": 1}, [["a"]]), 2)
        self.assertEqual(self.crear({"tipo": "final"}), len(self.leer()) - 1)
        self.assertFalse(self.api.crear_tabla(0, {"tipo": "seccion", "indice": 1}, None)["ok"])

    def test_mover_tablas_y_mover_junto_a_una_tabla(self):
        tabla = self.crear({"tipo": "final"}, [["t"]])
        nuevo = ok(self, self.api.mover(0, tabla, 0, "dentro"))["indice"]      # al final de la sección A
        self.assertEqual(nuevo, 2)
        self.assertIn("tabla", self.leer()[2])
        # Una prueba que se suelta antes de la tabla toma el nivel de lo que hay en esa sección.
        nuevo = ok(self, self.api.mover(0, 5, 2, "antes"))["indice"]           # T-2 (nivel 4)
        contenido = self.leer()
        self.assertEqual(contenido[nuevo]["prueba"]["id"], "T-2")
        self.assertEqual(contenido[nuevo]["prueba"]["nivel"], 3)
        # Mover la sección A arrastra su tabla con ella.
        ok(self, self.api.mover(0, 0, len(contenido) - 1, "despues"))
        claves = [next(iter(e)) for e in self.leer()]
        self.assertEqual(claves[-4:], ["seccion", "prueba", "prueba", "tabla"])

    def test_yaml_y_validacion(self):
        indice = self.crear({"tipo": "final"}, [["a", "b"]])
        texto = ok(self, self.api.obtener_yaml(0, indice))["texto"]
        self.assertTrue(texto.startswith("filas:"))
        ok(self, self.api.aplicar_yaml(0, indice, "filas:\n- [x, y]\n- [z]\nmotivo: importada\n"))
        self.assertEqual(self.leer()[indice]["tabla"], {"filas": [["x", "y"], ["z"]], "motivo": "importada"})
        self.assertFalse(self.api.aplicar_yaml(0, indice, "filas: []\n")["ok"])
        contenido = self.leer()
        contenido.append({"tabla": {"filas": "no es una lista"}})
        datos = YAML().load((self.dir / "01_demo.yaml").read_text(encoding="utf-8"))
        datos["contenido"] = contenido
        with (self.dir / "01_demo.yaml").open("w", encoding="utf-8") as f:
            YAML().dump(datos, f)
        ok(self, self.api.recargar())
        mensajes = [p["mensaje"] for p in ok(self, self.api.validar())["problemas"]]
        self.assertTrue(any("filas" in m for m in mensajes))


class TablasEnContextoTests(ApiBase):
    def test_guardar_contexto_con_tabla_no_la_pierde(self):
        contexto = ["Antes de la tabla.", {"tabla": {"filas": [["a", {"texto": "b", "columnas": 1}]], "motivo": "importada"}}, ""]
        ok(self, self.api.guardar_seccion(0, 0, {"contexto": contexto}))
        guardado = self.contenido()[0]["contexto"]
        self.assertEqual(guardado, ["Antes de la tabla.", {"tabla": {"motivo": "importada", "filas": [["a", "b"]]}}])
        ok(self, self.api.guardar_prueba(0, 1, {"contexto": [{"tabla": {"filas": [["x"]]}}]}))
        self.assertEqual(self.contenido()[1]["prueba"]["contexto"], [{"tabla": {"filas": [["x"]]}}])
        self.assertFalse(self.api.guardar_prueba(0, 1, {"contexto": [{"tabla": {"filas": []}}]})["ok"])

    def test_validacion_de_tablas_del_contexto(self):
        datos = YAML().load((self.dir / "01_demo.yaml").read_text(encoding="utf-8"))
        datos["contenido"][0]["contexto"] = [{"tabla": {"filas": "mal"}}]
        with (self.dir / "01_demo.yaml").open("w", encoding="utf-8") as f:
            YAML().dump(datos, f)
        ok(self, self.api.recargar())
        mensajes = [p["mensaje"] for p in ok(self, self.api.validar())["problemas"]]
        self.assertTrue(any("Tabla del contexto" in m for m in mensajes))


class ValidacionTests(ApiBase):
    def test_validar_detecta_duplicados_imagenes_y_campos_vacios(self):
        ok(self, self.api.guardar_prueba(0, 1, {
            "pasos": [{"texto": "x", "imagenes": ["imagenes/no_existe.png"]}]}))
        # un ID duplicado solo puede llegar editando el archivo a mano
        ruta = self.dir / "01_demo.yaml"
        ruta.write_text(ruta.read_text(encoding="utf-8").replace("id: T-3", "id: T-2"),
                        encoding="utf-8")
        ok(self, self.api.recargar())
        informe = ok(self, self.api.validar())
        mensajes = [p["mensaje"] for p in informe["problemas"]]
        self.assertTrue(any("ID duplicado" in m for m in mensajes))
        self.assertTrue(any("No existe la imagen" in m for m in mensajes))
        self.assertGreaterEqual(informe["errores"], 3)

    def test_ejemplos_del_repositorio_validan_sin_errores(self):
        with TemporaryDirectory() as tmp:
            destino = Path(tmp) / "yaml"
            shutil.copytree(EJEMPLOS, destino)
            api = editor_api.EditorApi(destino)
            ok(self, api.iniciar())
            informe = ok(self, api.validar())
            self.assertEqual(informe["errores"], 0, informe["problemas"])


class ImagenesTests(ApiBase):
    def setUp(self):
        super().setUp()
        (self.dir / "imagenes").mkdir()
        Image.new("RGB", (1200, 600), "teal").save(self.dir / "imagenes" / "grande.png")

    def test_miniatura_en_data_uri_y_cache(self):
        datos = ok(self, self.api.imagen("imagenes/grande.png", 300))
        self.assertTrue(datos["uri"].startswith("data:image/png;base64,"))
        self.assertEqual((datos["ancho"], datos["alto"]), (1200, 600))
        raw = base64.b64decode(datos["uri"].split(",", 1)[1])
        self.assertLessEqual(Image.open(io.BytesIO(raw)).size[0], 300)
        self.assertIs(ok(self, self.api.imagen("imagenes/grande.png", 300))["uri"], datos["uri"])

    def test_no_sale_de_la_carpeta_ni_acepta_archivos_inexistentes(self):
        self.assertFalse(self.api.imagen("../fuera.png")["ok"])
        self.assertFalse(self.api.imagen("imagenes/no.png")["ok"])

    def test_importar_imagen_pegada_numera_sin_pisar(self):
        buffer = io.BytesIO()
        Image.new("RGB", (10, 10), "red").save(buffer, format="PNG")
        b64 = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
        primera = ok(self, self.api.importar_imagen_base64("captura.png", b64))["rutas"]
        segunda = ok(self, self.api.importar_imagen_base64("captura.png", b64))["rutas"]
        self.assertEqual((primera, segunda), (["imagenes/imagen_001.png"], ["imagenes/imagen_002.png"]))
        rara = ok(self, self.api.importar_imagen_base64("sin_extension", b64))["rutas"]
        self.assertTrue(rara[0].endswith(".png"))

    def test_importar_desde_archivos_locales(self):
        origen = Path(self._tmp.name) / "foto.jpg"
        Image.new("RGB", (8, 8), "blue").save(origen)
        rutas = ok(self, self.api.importar_imagenes([str(origen)]))["rutas"]
        self.assertEqual(rutas, ["imagenes/imagen_001.jpg"])
        self.assertTrue((self.dir / rutas[0]).is_file())


class ExportarTests(unittest.TestCase):
    def test_exportar_docx_de_los_ejemplos(self):
        with TemporaryDirectory() as tmp:
            destino = Path(tmp) / "yaml"
            shutil.copytree(EJEMPLOS, destino)
            api = editor_api.EditorApi(destino)
            ok(self, api.iniciar())
            datos = ok(self, api.exportar_docx(1, str(Path(tmp) / "salida" / "pruebas")))
            self.assertTrue(Path(datos["archivo"]).is_file())
            self.assertTrue(datos["archivo"].endswith(".docx"))
            self.assertIn("pruebas", datos["resumen"])


class MensajesYamlTests(ApiBase):
    """Los errores de YAML llegan a la interfaz en español y con posición."""

    def setUp(self):
        super().setUp()
        ok(self, self.api.iniciar())

    def test_validar_yaml_traduce_el_error_y_da_la_linea(self):
        datos = ok(self, self.api.validar_yaml("id: A\ntitulo: [roto\n  x: y: z\n"))
        self.assertFalse(datos["valido"])
        self.assertEqual(datos["linea"], 3)
        self.assertIn("Falta ','", datos["mensaje"])
        self.assertNotIn("expected", datos["mensaje"])

    def test_validar_yaml_con_tabulacion_avisa_de_la_sangria(self):
        datos = ok(self, self.api.validar_yaml("pasos:\n\t- uno\n"))
        self.assertFalse(datos["valido"])
        self.assertIn("tabulación", datos["mensaje"])

    def test_aplicar_yaml_roto_devuelve_error_en_espanol_con_linea(self):
        resultado = self.api.aplicar_yaml(0, 1, "id: T-1\ntitulo: [roto\n  x: y: z\n")
        self.assertFalse(resultado["ok"])
        self.assertIn("Falta ','", resultado["error"])
        self.assertRegex(resultado["error"], r"línea \d+, columna \d+")
        self.assertIn("comentario del título", (self.dir / "01_demo.yaml").read_text(encoding="utf-8"))

    def test_ventana_permite_seleccionar_texto(self):
        # pywebview deshabilita la selección de texto salvo que se pida (text_select=True).
        self.assertIn("text_select=True", (Path(__file__).resolve().parent.parent / "editor_web.py").read_text(encoding="utf-8"))


class AjustesTests(ApiBase):
    """La última carpeta se recuerda entre ejecuciones (útil con el .exe)."""

    def setUp(self):
        super().setUp()
        import os
        import editor_web
        self.web = editor_web
        self.ajustes = Path(self._tmp.name) / "ajustes" / "ajustes.json"
        previo = os.environ.get("AZTARNA_AJUSTES")
        os.environ["AZTARNA_AJUSTES"] = str(self.ajustes)
        self.addCleanup(lambda: os.environ.__setitem__("AZTARNA_AJUSTES", previo)
                        if previo is not None else os.environ.pop("AZTARNA_AJUSTES", None))

    def test_sin_ajustes_no_hay_ultima_carpeta(self):
        self.assertIsNone(self.web.ultima_carpeta())

    def test_al_cargar_una_carpeta_se_recuerda(self):
        api = editor_api.EditorApi(self.dir)      # nueva: el gancho debe estar antes de cargar
        api._al_cargar = self.web.recordar_carpeta
        ok(self, api.iniciar())
        self.assertTrue(self.ajustes.is_file())
        self.assertEqual(self.web.ultima_carpeta(), self.dir.resolve())

    def test_carpeta_recordada_que_ya_no_existe_se_ignora(self):
        self.web.recordar_carpeta(Path(self._tmp.name) / "borrada")
        self.assertIsNone(self.web.ultima_carpeta())

    def test_un_fallo_al_recordar_no_impide_abrir(self):
        def roto(_carpeta):
            raise RuntimeError("disco lleno")
        api = editor_api.EditorApi(self.dir)
        api._al_cargar = roto
        datos = ok(self, api.iniciar())
        self.assertEqual(len(datos["capitulos"]), 1)

    def test_sin_carpeta_inicial_la_app_arranca_vacia(self):
        datos = ok(self, editor_api.EditorApi(None).iniciar())
        self.assertIsNone(datos["carpeta"])
        self.assertEqual(datos["capitulos"], [])


class VentanaFalsa:
    def __init__(self):
        self.js = []
        self.destruida = False

    def evaluate_js(self, codigo):
        self.js.append(codigo)

    def destroy(self):
        self.destruida = True


class CierreTests(unittest.TestCase):
    """Al cerrar con cambios sin guardar, la página pregunta antes de salir."""

    def setUp(self):
        self.api = editor_api.EditorApi()
        self.ventana = VentanaFalsa()
        self.api._window = self.ventana

    def test_sin_cambios_se_cierra(self):
        self.assertTrue(self.api._al_cerrar_ventana())
        self.assertEqual(self.ventana.js, [])

    def test_con_cambios_cancela_y_pregunta(self):
        ok(self, self.api.marcar_cambios(True))
        self.assertFalse(self.api._al_cerrar_ventana())
        time.sleep(0.1)  # la pregunta se lanza en otro hilo
        self.assertEqual(self.ventana.js, ["pedirCierre()"])

    def test_tras_guardar_o_descartar_se_cierra(self):
        ok(self, self.api.marcar_cambios(True))
        ok(self, self.api.marcar_cambios(False))
        self.assertTrue(self.api._al_cerrar_ventana())

    def test_cerrar_destruye_la_ventana_aunque_haya_cambios(self):
        ok(self, self.api.marcar_cambios(True))
        ok(self, self.api.cerrar())
        time.sleep(0.4)
        self.assertTrue(self.ventana.destruida)
        self.assertTrue(self.api._al_cerrar_ventana())  # el cierre ya está aceptado


if __name__ == "__main__":
    unittest.main()
