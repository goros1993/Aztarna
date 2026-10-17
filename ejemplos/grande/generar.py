#!/usr/bin/env python3
"""Genera el ejemplo grande: 1000 pruebas, 500 requisitos y dos validaciones.

Sirve para ver cómo se comporta el editor con un proyecto del tamaño real
(árbol, pestañas de la validación por capítulos, informes). Los datos son
ficticios y siempre salen iguales (semilla fija, fechas fijas).

    python ejemplos/grande/generar.py

Borra y vuelve a crear `pruebas/`, `requisitos/` y `validaciones/` junto a
este archivo:

- 20 capítulos de pruebas, cada uno con 5 secciones de 10 pruebas;
- 20 capítulos de requisitos de 25 requisitos (3 cambiados, con pruebas por revisar);
- `validaciones/v2.9`: Maqueta y Torre, cerradas;
- `validaciones/v3.0`: Maqueta cerrada y Torre a medias; se compara con la v2.9.
"""
from __future__ import annotations

import random
import re
import shutil
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parents[1]))

from app import ejecucion_core as ej          # noqa: E402
from app import trazabilidad                  # noqa: E402
from app import validacion_core as vc         # noqa: E402
from app.editor_core import read_chapters, save_chapter   # noqa: E402

TEMAS = ["Llamadas", "Puertas", "Nivelación", "Bus CAN", "Seguridad", "Mantenimiento", "Alarmas", "Energía",
         "Display", "Botoneras", "Incendio", "Rescate", "Grupos", "Accesos", "Pesaje", "Ventilación",
         "Iluminación", "Diagnóstico", "Registro", "Configuración"]
SECCIONES = ["Funcionamiento normal", "Límites", "Fallos", "Recuperación", "Configuración"]
ACCIONES = ["responde a la orden", "se mantiene estable", "avisa al operador", "registra el evento", "vuelve al estado inicial",
            "respeta el tiempo máximo", "ignora la orden repetida", "se recupera tras el corte", "informa por el bus", "bloquea la maniobra"]
CABECERA = "# Ejemplo grande (datos ficticios). Lo genera ejemplos/grande/generar.py: no lo edites a mano.\n"


def clave(tema: str) -> str:
    return re.sub(r"[^a-z]", "", tema.lower().translate(str.maketrans("áéíóú", "aeiou")))[:4].upper()


def escribir(ruta: Path, datos: dict) -> None:
    save_chapter({"path": ruta, "data": datos})
    ruta.write_text(CABECERA + ruta.read_text(encoding="utf-8"), encoding="utf-8")


def generar_proyecto(azar: random.Random) -> None:
    for carpeta in ("pruebas", "requisitos"):
        shutil.rmtree(AQUI / carpeta, ignore_errors=True)
        (AQUI / carpeta).mkdir()
    for c, tema in enumerate(TEMAS, 1):
        k = clave(tema)
        requisitos = {"capitulo": f"Requisitos de {tema.lower()}", "contenido": []}
        for n in range(1, 26):
            criterio = ["Inspección"] if n % 12 == 0 else ["Test"]
            requisitos["contenido"].append({"requisito": {
                "nombre": "", "nivel": 2, "id": f"REQ-{k}-{n:03d}",
                "titulo": f"{tema}: el controlador {azar.choice(ACCIONES)} ({n})",
                "descripcion": f"El controlador DEMO-A1 {azar.choice(ACCIONES)} en el ámbito de {tema.lower()}.",
                "tipo": "Funcional", "criterio_validacion": criterio}})
        escribir(AQUI / "requisitos" / f"{c:02d}_{k.lower()}.yaml", requisitos)

        pruebas = {"capitulo": tema, "contenido": []}
        n = 0
        for seccion in SECCIONES:
            pruebas["contenido"].append({"seccion": seccion, "nivel": 2})
            for _ in range(10):
                n += 1
                accion = azar.choice(ACCIONES)
                pruebas["contenido"].append({"prueba": {
                    "nombre": "", "nivel": 3, "id": f"G-{k}-{n:03d}",
                    "titulo": f"{seccion}: el controlador {accion}",
                    "descripcion": f"Comprobar que, en {tema.lower()}, el controlador {accion}.",
                    "pasos": ["Preparar la instalación simulada.", f"Provocar la situación de «{seccion.lower()}»."],
                    "resultado_esperado": [f"El controlador {accion}."],
                    "entorno": azar.choice([["Maqueta"], ["Torre"], ["Maqueta", "Torre"], ["Maqueta", "Torre"]]),
                    "requisitos": sorted({f"REQ-{k}-{azar.randint(1, 25):03d}" for _ in range(azar.choice([1, 1, 2]))}),
                    "tags": ["regresion"] if n % 3 else ["regresion", "humo"]}})
        escribir(AQUI / "pruebas" / f"{c:02d}_{k.lower()}.yaml", pruebas)

    # Tres requisitos «cambiados» desde la última revisión de sus pruebas.
    capitulos_req = read_chapters(AQUI / "requisitos")
    revisiones = {}
    for capitulo, n in ((0, 3), (4, 7), (9, 11)):
        req = capitulos_req[capitulo]["data"]["contenido"][n - 1]["requisito"]
        antes = {**req, "descripcion": req["descripcion"].replace("El controlador", "El equipo")}
        revisiones[req["id"]] = {"huella": trazabilidad.huella(antes), "titulo": req["titulo"], "descripcion": antes["descripcion"]}
    trazabilidad.guardar_revisiones(AQUI / "requisitos", revisiones)


def ejecucion(validacion: dict, nombre: str, entorno: str, dia: str, azar: random.Random,
              fallos: float, completa: bool, responsable: str) -> None:
    carpeta = validacion["carpeta"] / f"{dia}_{entorno}"
    campaña = ej.crear(carpeta, AQUI / "pruebas", nombre, {"entorno": [entorno]},
                       {"entorno_pruebas": entorno, "responsable": responsable})
    campaña["datos"]["inicio"] = f"{dia}T08:00"
    for i, test_id in enumerate(ej.ids_de(campaña)):
        x = azar.random()
        if not completa and x > 0.75:
            continue                                   # sin ejecutar todavía
        estado = "no_ok" if x < fallos else "bloqueada" if x < fallos + 0.02 else "no_aplica" if x < fallos + 0.03 else "ok"
        ej.registrar(campaña, test_id, estado, ejecutor=responsable, fecha=f"{dia}T{9 + i % 9:02d}:{i % 60:02d}",
                     observaciones="No cumple el resultado esperado." if estado == "no_ok" else
                     "Falta el equipo de pruebas." if estado == "bloqueada" else "",
                     guardar_ahora=False)
    ej.guardar(campaña)
    if completa:
        ej.cerrar(campaña, read_chapters(AQUI / "pruebas"))
        campaña = ej.cargar(carpeta)
        campaña["datos"]["fin"] = f"{dia}T18:00"
        ej.guardar(campaña)
    vc.anadir_ejecucion(validacion, carpeta)


def generar_validaciones(azar: random.Random) -> None:
    shutil.rmtree(AQUI / "validaciones", ignore_errors=True)
    v29 = vc.crear(AQUI / "validaciones" / "v2.9", AQUI / "pruebas", "Validación v2.9 (ejemplo grande)", "Controlador DEMO-A1, firmware 2.9.0")
    ejecucion(v29, "Regresión v2.9 en Maqueta", "Maqueta", "2026-09-01", azar, 0.08, True, "Ana Pérez")
    ejecucion(v29, "Regresión v2.9 en Torre", "Torre", "2026-09-03", azar, 0.06, True, "Luis Gómez")
    v30 = vc.crear(AQUI / "validaciones" / "v3.0", AQUI / "pruebas", "Validación v3.0 (ejemplo grande)", "Controlador DEMO-A1, firmware 3.0.0")
    ejecucion(v30, "Regresión v3.0 en Maqueta", "Maqueta", "2026-10-05", azar, 0.05, True, "Ana Pérez")
    ejecucion(v30, "Regresión v3.0 en Torre", "Torre", "2026-10-07", azar, 0.04, False, "Luis Gómez")
    vc.comparar_con(v30, AQUI / "validaciones" / "v2.9")
    for creada, v in (("2026-09-01T07:30", v29), ("2026-10-05T07:30", v30)):
        v["datos"]["creada"] = creada
        vc.guardar(v)
    # Solo rutas relativas: el ejemplo tiene que funcionar en cualquier carpeta.
    for ruta in (AQUI / "validaciones").rglob("*.yaml"):
        texto = ruta.read_text(encoding="utf-8")
        limpio = "".join(l for l in texto.splitlines(keepends=True) if "_absoluta:" not in l)
        if limpio != texto:
            ruta.write_text(limpio, encoding="utf-8")


def main() -> None:
    azar = random.Random(2026)
    generar_proyecto(azar)
    generar_validaciones(azar)
    d = vc.consolidar(vc.cargar(AQUI / "validaciones" / "v3.0"))
    print(f"{d['total']} pruebas, {len(d['requisitos']['lista'])} requisitos; v3.0: {d['totales']}")


if __name__ == "__main__":
    main()
