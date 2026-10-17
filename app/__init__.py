"""Lógica del editor de pruebas y requisitos, de la trazabilidad y de las ejecuciones (la interfaz está en web/ y se arranca con editor_web.py)."""

# Nombre y versión de la herramienta: el único sitio donde se definen.
# La versión sigue el versionado semántico; cada versión publicada lleva su etiqueta de Git (v0.8.0…)
# y su entrada en CHANGELOG.md.
NOMBRE = "Aztarna"
__version__ = "1.0.0"


def firma() -> str:
    """«Aztarna 1.0.0», para pies de página, ayudas y la ventana «Acerca de»."""
    return f"{NOMBRE} {__version__}"
