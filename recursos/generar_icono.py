#!/usr/bin/env python3
"""Genera el icono de la aplicación: recursos/icono.png (ventana), recursos/icono.ico
(ejecutable de Windows) y web/img/icono.png (barra superior del editor).

Un rastro de huellas que acaba en una marca de validación: la trazabilidad
(requisito → prueba → resultado) y el nombre, Aztarna («huella, rastro» en euskera).
Colores del editor: petróleo (acento) y ámbar (placa del ID).

Uso: python recursos/generar_icono.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

AQUI = Path(__file__).resolve().parent
LADO = 1024                      # se dibuja grande y se reduce (bordes suaves)
FONDO_ARRIBA, FONDO_ABAJO = (16, 112, 135), (8, 63, 77)
AMBAR = (240, 172, 20)
BLANCO = (255, 255, 255)


def degradado(lado: int) -> Image.Image:
    img = Image.new("RGB", (lado, lado))
    d = ImageDraw.Draw(img)
    for y in range(lado):
        t = y / (lado - 1)
        d.line([(0, y), (lado, y)], fill=tuple(round(a + (b - a) * t) for a, b in zip(FONDO_ARRIBA, FONDO_ABAJO)))
    return img


def huella(capa: Image.Image, cx: float, cy: float, escala: float, angulo: float, color) -> None:
    """Huella de pie estilizada: planta ovalada y cuatro dedos, girada `angulo` grados."""
    tam = int(260 * escala)
    pie = Image.new("RGBA", (tam, tam), (0, 0, 0, 0))
    d = ImageDraw.Draw(pie)
    c = tam / 2
    d.ellipse([c - 0.17 * tam, c - 0.10 * tam, c + 0.17 * tam, c + 0.40 * tam], fill=color)      # planta
    for dx, dy, r in ((-0.13, -0.17, 0.058), (-0.035, -0.235, 0.064), (0.07, -0.225, 0.058), (0.155, -0.15, 0.05)):
        d.ellipse([c + dx * tam - r * tam, c + dy * tam - r * tam, c + dx * tam + r * tam, c + dy * tam + r * tam], fill=color)
    pie = pie.rotate(angulo, resample=Image.BICUBIC, expand=False)
    capa.alpha_composite(pie, (int(cx - tam / 2), int(cy - tam / 2)))


def dibujar() -> Image.Image:
    lado = LADO
    radio = int(lado * 0.22)
    mascara = Image.new("L", (lado, lado), 0)
    ImageDraw.Draw(mascara).rounded_rectangle([0, 0, lado - 1, lado - 1], radius=radio, fill=255)
    icono = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    icono.paste(degradado(lado), (0, 0), mascara)

    capa = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    # Rastro: tres huellas (izquierda, derecha, izquierda) que suben hacia la marca.
    for cx, cy, esc, ang, alfa in ((175, 835, 1.0, -28, 140), (330, 735, 1.08, -32, 200), (300, 520, 1.16, -30, 255)):
        huella(capa, cx, cy, esc, ang, AMBAR[:3] + (alfa,))
    # Marca de validación, blanca y gruesa, al final del rastro.
    d = ImageDraw.Draw(capa)
    puntos = [(495, 560), (625, 690), (860, 330)]
    d.line(puntos, fill=BLANCO, width=112, joint="curve")
    for x, y in (puntos[0], puntos[-1]):
        d.ellipse([x - 56, y - 56, x + 56, y + 56], fill=BLANCO)
    sombra = capa.split()[3].filter(ImageFilter.GaussianBlur(14)).point(lambda a: int(a * 0.35))
    sombra_img = Image.new("RGBA", (lado, lado), (0, 30, 40, 0))
    sombra_img.putalpha(sombra)
    icono.alpha_composite(sombra_img, (0, 10))
    icono.alpha_composite(capa)
    icono.putalpha(Image.composite(icono.split()[3], Image.new("L", (lado, lado), 0), mascara))
    return icono


def main() -> None:
    grande = dibujar()
    grande.resize((512, 512), Image.LANCZOS).save(AQUI / "icono.png")
    grande.resize((256, 256), Image.LANCZOS).save(
        AQUI / "icono.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    (AQUI.parent / "web" / "img").mkdir(exist_ok=True)
    grande.resize((64, 64), Image.LANCZOS).save(AQUI.parent / "web" / "img" / "icono.png")
    print("recursos/icono.png, recursos/icono.ico y web/img/icono.png")


if __name__ == "__main__":
    main()
