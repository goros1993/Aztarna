#!/usr/bin/env python3
"""
Word -> YAML. Un YAML por capítulo (cada Título 1) + indice.yaml.
Las imágenes se guardan en salida/yaml/imagenes y se referencian desde el YAML.

Uso:
    python convertir.py tu_archivo.docx            -> carpeta salida/
    python convertir.py tu_archivo.docx -o otra

Requisitos:
    pip install python-docx ruamel.yaml
"""
import argparse
import mimetypes
import re
import unicodedata
from pathlib import Path

from docx import Document
from docx.enum.dml import MSO_COLOR_TYPE
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
from ruamel.yaml import YAML


def sin_tildes(s):
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def norm(s):
    return re.sub(r"\s+", "", sin_tildes(s)).lower()


def slug(s):
    return re.sub(r"\W+", "_", sin_tildes(s).lower()).strip("_")[:40] or "capitulo"


CAMPOS = {"descripcion": "descripcion", "componente": "componente",
          "plataforma": "plataforma", "automatizable": "automatizable",
          "criticidad": "criticidad", "entornodepruebas": "entorno",
          "referencia": "referencia", "fecha": "fecha", "version": "version"}
SECCIONES = {"situacioninicial": "situacion_inicial", "pasos": "pasos",
             "situacionfinal": "situacion_final"}
AUTOMATIZABLE = {"si", "no", "corto", "medio", "largo", "hecho"}

ETIQUETAS_CAMPOS = {
    "Descripción": "descripcion",
    "Componente": "componente",
    "Plataforma": "plataforma",
    "Automatizable": "automatizable",
    "Criticidad": "criticidad",
    "Entorno de pruebas": "entorno",
    "Referencia": "referencia",
    "Fecha": "fecha",
    "Versión": "version",
    "Situación inicial": "situacion_inicial",
    "Condiciones iniciales": "situacion_inicial",
    "Pasos": "pasos",
    "ENSAYO(s) / Proceso(s)": "pasos",
    "Situación final": "situacion_final",
    "Entorno de prueba(s)": "entorno",
    "Entorno de pruebas(s)": "entorno",
}
CAMPOS.update({norm(etiqueta): clave for etiqueta, clave in ETIQUETAS_CAMPOS.items()})

ALIAS_ETIQUETAS_ADICIONALES = {
    "Resultado esperado": "Resultado esperado",
    "Criterio(s) de aceptación": "Criterio(s) de aceptación",
    "Criterio validación": "Criterio validación",
    "Maniobra(s)": "Maniobra(s)",
    "Requisito(s)": "Requisito(s)",
    "Ejecutor prueba": "Ejecutor prueba",
    "Fecha ejecución": "Fecha ejecución",
    "Resultado Obtenido": "Resultado Obtenido",
    "Resultado obtenido": "Resultado Obtenido",
    "Decisión": "Decisión",
    "Resultado": "Resultado",
    "Observaciones": "Observaciones",
    "Tags": "Tags",
    "ENSAYO(s) / Proceso(s)": "ENSAYO(s) / Proceso(s)",
    "ENSAYO(s)/Proceso(s)": "ENSAYO(s) / Proceso(s)",
    "Entorno de prueba(s)": "Entorno de prueba(s)",
    "Entorno de pruebas(s)": "Entorno de pruebas(s)",
}
ETIQUETAS_ADICIONALES = {
    norm(alias): etiqueta
    for alias, etiqueta in ALIAS_ETIQUETAS_ADICIONALES.items()
}

ETIQUETAS_IGNORADAS = {"ejecuciondeprueba"}

# Color de fuente (hex -> nombre) y resaltado (nombre de Word -> nombre)
COLORES = {"FF0000": "rojo", "0070C0": "azul", "00B050": "verde"}
RESALTADOS = {"YELLOW": "amarillo", "BRIGHT_GREEN": "verde", "TURQUOISE": "cian"}


# ----------------------------------------------------------------------
# Texto con formato
# ----------------------------------------------------------------------
def limpiar(l):
    return l.strip().lstrip("•·-–\t ").strip()


def texto_md(p):
    out = []
    for r in p.runs:
        t = r.text
        if not t.strip():
            out.append(t)
            continue
        ini = t[:len(t) - len(t.lstrip())]
        fin = t[len(t.rstrip()):]
        core = t.strip()
        if r.bold:
            core = f"**{core}**"
        if r.italic:
            core = f"*{core}*"
        col = r.font.color
        if col is not None and col.type == MSO_COLOR_TYPE.RGB and col.rgb is not None:
            hexa = str(col.rgb)
            if hexa != "000000":
                core = f"[[{COLORES.get(hexa, '#' + hexa)}|{core}]]"
        if r.font.highlight_color is not None:
            n = r.font.highlight_color.name
            core = f"[[res:{RESALTADOS.get(n, n.lower())}|{core}]]"
        out.append(ini + core + fin)
    return "".join(out).replace("****", "").replace("** **", " ")


def imagenes_parrafo(p, guardar_imagen):
    if guardar_imagen is None:
        return []
    imagenes = []
    rel_ids = []
    for blip in p._p.xpath(".//a:blip"):
        rel_id = blip.get(qn("r:embed"))
        if rel_id and rel_id not in rel_ids:
            rel_ids.append(rel_id)
    for imagen in p._p.xpath(".//*[local-name()='imagedata']"):
        rel_id = imagen.get(qn("r:id"))
        if rel_id and rel_id not in rel_ids:
            rel_ids.append(rel_id)
    for rel_id in rel_ids:
        imagenes.append(guardar_imagen(p.part.related_parts[rel_id]))
    return imagenes


def item(p, guardar_imagen=None):
    txt = limpiar(texto_md(p))
    pPr = p._p.pPr
    nivel = 0
    if pPr is not None and pPr.numPr is not None and pPr.numPr.ilvl is not None:
        nivel = pPr.numPr.ilvl.val
    imagenes = imagenes_parrafo(p, guardar_imagen)
    if nivel == 0 and not imagenes:
        return txt
    resultado = {"texto": txt}
    if nivel:
        resultado["nivel"] = nivel
    if imagenes:
        resultado["imagenes"] = imagenes
    return resultado


# ----------------------------------------------------------------------
# Tabla de una prueba
# ----------------------------------------------------------------------
def celdas_unicas(row):
    vistas, out = set(), []
    for c in row.cells:
        if c._tc not in vistas:
            vistas.add(c._tc)
            out.append(c)
    return out


def guardar_campo(d, etiqueta, valor, avisos):
    n = norm(etiqueta)
    clave = CAMPOS.get(n)
    if clave:
        if clave in ("situacion_inicial", "pasos", "situacion_final"):
            items = [limpiar(linea) for linea in valor.splitlines() if limpiar(linea)]
            d.setdefault(clave, []).extend(items)
            return
        valor = " ".join(valor.split())
        if clave == "automatizable" and valor:
            v = norm(valor)
            if v in AUTOMATIZABLE:
                valor = v
            else:
                avisos.append(f"{d['id']}: valor de Automatizable no válido '{valor}'")
        if valor or clave not in d:
            d[clave] = valor
        return

    if n in ETIQUETAS_IGNORADAS:
        return

    campos = d.setdefault("campos_adicionales", {})
    etiqueta_visible = ETIQUETAS_ADICIONALES.get(n, etiqueta.strip())
    valor = "\n".join(linea.strip() for linea in valor.splitlines()).strip()
    if etiqueta_visible in campos:
        anterior = campos[etiqueta_visible]
        if not anterior:
            campos[etiqueta_visible] = valor
        elif valor:
            campos[etiqueta_visible] = f"{anterior}\n{valor}"
    else:
        campos[etiqueta_visible] = valor
    if n not in ETIQUETAS_ADICIONALES:
        avisos.append(f"{d['id']}: etiqueta desconocida '{etiqueta.strip()}' (preservada en campos_adicionales)")


def extraer_etiquetas(texto):
    conocidas = {
        **{etiqueta: clave for etiqueta, clave in ETIQUETAS_CAMPOS.items()},
        **ALIAS_ETIQUETAS_ADICIONALES,
        "EJECUCIÓN DE PRUEBA": None,
    }
    por_normalizada = {}
    for etiqueta in conocidas:
        por_normalizada.setdefault(norm(etiqueta), etiqueta)
    etiquetas = sorted(por_normalizada.values(), key=len, reverse=True)
    patron = re.compile(
        r"(?<!\w)(" + "|".join(re.escape(e) for e in etiquetas) + r")\s*:",
        re.IGNORECASE,
    )
    coincidencias = list(patron.finditer(texto))
    return [
        (m.group(1), texto[m.end():coincidencias[i + 1].start() if i + 1 < len(coincidencias) else None])
        for i, m in enumerate(coincidencias)
    ]


def parsear(tabla, avisos, guardar_imagen=None):
    filas = [celdas_unicas(r) for r in tabla.rows]
    cab = filas[0]
    d = {"id": cab[0].text.strip(),
         "titulo": cab[1].text.strip() if len(cab) > 1 else ""}
    formato_alternativo = False
    parrafos_con_imagenes = set()
    for fila in filas[1:]:
        for c in fila:
            if any(norm(p.text).rstrip(":") in SECCIONES for p in c.paragraphs):
                seccion = None
                for p in c.paragraphs:
                    l = p.text
                    if not l.strip():
                        if seccion:
                            contenido = item(p, guardar_imagen)
                            if isinstance(contenido, dict) and contenido.get("imagenes"):
                                d[seccion].append(contenido)
                                parrafos_con_imagenes.add(p._p)
                        continue
                    n = norm(l).rstrip(":")
                    if n in SECCIONES:
                        seccion = SECCIONES[n]
                        d.setdefault(seccion, [])
                        imagenes = imagenes_parrafo(p, guardar_imagen)
                        if imagenes:
                            d[seccion].append({"texto": "", "imagenes": imagenes})
                            parrafos_con_imagenes.add(p._p)
                    elif seccion:
                        contenido = item(p, guardar_imagen)
                        d[seccion].append(contenido)
                        if isinstance(contenido, dict) and contenido.get("imagenes"):
                            parrafos_con_imagenes.add(p._p)
                    else:
                        avisos.append(f"{d['id']}: texto fuera de sección: {l[:40]}")
            elif (campos := extraer_etiquetas(c.text)):
                for etiqueta, valor in campos:
                    if norm(etiqueta) in {"condicionesiniciales", "ensayo(s)/proceso(s)"}:
                        formato_alternativo = True
                    guardar_campo(d, etiqueta, valor, avisos)
            elif ":" in c.text:
                etiqueta, valor = c.text.split(":", 1)
                guardar_campo(d, etiqueta, valor, avisos)
            elif c.text.strip():
                if norm(c.text.rstrip(":")) not in ETIQUETAS_IGNORADAS:
                    avisos.append(f"{d['id']}: celda sin reconocer: {c.text[:40]}")
    imagenes_tabla = []
    for fila in filas:
        for celda in fila:
            for p in celda.paragraphs:
                if p._p not in parrafos_con_imagenes:
                    imagenes_tabla.extend(imagenes_parrafo(p, guardar_imagen))
    if imagenes_tabla:
        d["imagenes"] = list(dict.fromkeys(imagenes_tabla))
    if formato_alternativo:
        requeridos = ("componente", "automatizable", "criticidad", "entorno",
                      "referencia", "fecha", "version", "situacion_inicial", "pasos")
    else:
        requeridos = list(CAMPOS.values()) + list(SECCIONES.values())
    faltan = [k for k in dict.fromkeys(requeridos) if k not in d]
    if faltan:
        avisos.append(f"{d['id']}: faltan campos {faltan}")
    return d


# ----------------------------------------------------------------------
# Estructura del documento
# ----------------------------------------------------------------------
def nivel_titulo(p):
    m = re.match(r"^(?:heading|t[ií]tulo)\s*(\d+)$", p.style.name.strip(), re.I)
    return int(m.group(1)) if m else None


def crear_guardador_imagenes(directorio):
    directorio = Path(directorio)
    guardadas = {}

    def guardar(parte):
        nombre_parte = str(parte.partname)
        if nombre_parte not in guardadas:
            extension = Path(nombre_parte).suffix
            if not extension:
                extension = mimetypes.guess_extension(parte.content_type) or ".bin"
            nombre = f"imagen_{len(guardadas) + 1:03d}{extension.lower()}"
            ruta = directorio / nombre
            directorio.mkdir(parents=True, exist_ok=True)
            ruta.write_bytes(parte.blob)
            guardadas[nombre_parte] = f"imagenes/{nombre}"
        return guardadas[nombre_parte]

    return guardar


def contenido_parrafo(p, guardar_imagen):
    texto = texto_md(p).strip()
    imagenes = imagenes_parrafo(p, guardar_imagen)
    if imagenes:
        return {"texto": texto, "imagenes": imagenes}
    return texto


def extraer_capitulos(doc, avisos, guardar_imagen=None):
    capitulos = [{"capitulo": None, "contenido": []}]
    pendiente = None
    texto_pendiente = []
    grupos = []

    def volcar():
        nonlocal pendiente, texto_pendiente
        if pendiente:
            entrada = {
                "seccion": pendiente[0],
                "nivel": pendiente[1],
            }
            if texto_pendiente:
                entrada["contexto"] = texto_pendiente
            capitulos[-1]["contenido"].append(entrada)
            grupos.append({"nivel": pendiente[1], "entrada": entrada})
            pendiente = None
            texto_pendiente = []

    def guardar_texto(texto):
        if grupos:
            grupos[-1]["entrada"].setdefault("contexto", []).append(texto)
        else:
            capitulos[-1]["contenido"].append({"texto": texto, "alcance": "capitulo"})

    for el in doc.element.body.iterchildren():
        if el.tag.endswith("}p"):
            p = Paragraph(el, doc)
            texto = contenido_parrafo(p, guardar_imagen)
            tiene_texto = texto.get("texto", "").strip() if isinstance(texto, dict) else texto
            if not tiene_texto and not isinstance(texto, dict):
                continue
            nivel = nivel_titulo(p)
            if nivel == 1:
                volcar()
                capitulos.append({"capitulo": p.text.strip(), "contenido": []})
                if isinstance(texto, dict) and texto.get("imagenes"):
                    capitulos[-1]["contenido"].append({
                        "texto": {"texto": "", "imagenes": texto["imagenes"]}
                    })
                grupos = []
            elif nivel:
                volcar()
                grupos = [g for g in grupos if g["nivel"] < nivel]
                pendiente = (p.text.strip(), nivel)
                if isinstance(texto, dict) and texto.get("imagenes"):
                    texto_pendiente.append(texto)
            elif pendiente:
                texto_pendiente.append(texto)
            else:
                guardar_texto(texto)
        elif el.tag.endswith("}tbl"):
            prueba = parsear(Table(el, doc), avisos, guardar_imagen)
            if pendiente:
                cab = {"nombre": pendiente[0], "nivel": pendiente[1]}
                if texto_pendiente:
                    prueba["contexto"] = texto_pendiente
                pendiente = None
                texto_pendiente = []
            else:
                cab = {"nombre": "", "nivel": None}
                avisos.append(f"{prueba['id']}: tabla sin título previo")
            capitulos[-1]["contenido"].append({"prueba": {**cab, **prueba}})
    volcar()

    if not capitulos[0]["contenido"]:
        capitulos.pop(0)
    return capitulos


def main():
    ap = argparse.ArgumentParser(description="Word -> YAML por capítulos")
    ap.add_argument("docx")
    ap.add_argument("-o", "--salida", default="salida")
    args = ap.parse_args()

    doc = Document(args.docx)
    avisos = []
    out = Path(args.salida) / "yaml"
    out.mkdir(parents=True, exist_ok=True)
    guardar_imagen = crear_guardador_imagenes(out / "imagenes")
    capitulos = extraer_capitulos(doc, avisos, guardar_imagen)

    yaml = YAML()
    yaml.allow_unicode = True
    yaml.width = 4096
    indice = []
    for i, cap in enumerate(capitulos, 1):
        archivo = f"{i:02d}_{slug(cap['capitulo'] or 'sin_capitulo')}.yaml"
        with open(out / archivo, "w", encoding="utf-8") as f:
            yaml.dump(cap, f)
        indice.append({"capitulo": cap["capitulo"], "archivo": archivo})
    with open(out / "indice.yaml", "w", encoding="utf-8") as f:
        yaml.dump(indice, f)
    (Path(args.salida) / "avisos.txt").write_text("\n".join(avisos), encoding="utf-8")

    n = sum(1 for c in capitulos for e in c["contenido"] if "prueba" in e)
    print(f"{n} pruebas, {len(capitulos)} capítulos, {len(avisos)} avisos "
          f"(ver {Path(args.salida) / 'avisos.txt'})")


if __name__ == "__main__":
    main()
