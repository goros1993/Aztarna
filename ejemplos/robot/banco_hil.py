"""Librería de Python (ficticia) del banco HIL para los ejemplos de Robot."""
from robot.api.deco import keyword


@keyword("Registrar una llamada de piso en ${planta}")
def registrar_llamada_piso(planta):
    """Pulsa el botón de llamada de la planta en la botonera de piso."""
    print(f"Llamada registrada en {planta}")


@keyword("Capturar ${cantidad} tramas consecutivas")
def capturar_tramas(cantidad):
    """Guarda las tramas de estado de cabina que lleguen por el bus CAN."""
    return []


def leer_trama_can(identificador, byte=0, timeout="1 s"):
    """Devuelve el valor de un byte de la última trama con ese identificador."""
    return 0


def _conectar():
    """Auxiliar: no es una keyword."""
