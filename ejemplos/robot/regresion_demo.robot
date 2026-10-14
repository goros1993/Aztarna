*** Settings ***
Documentation     Tests automáticos de ejemplo (ficticios) del controlador DEMO-A1.
...
...               Cada test se enlaza con su prueba YAML mediante la etiqueta
...               id:<ID de la prueba>. Las palabras clave simulan el banco HIL
...               para que el ejemplo se pueda ejecutar en cualquier PC:
...               robot --outputdir resultados ejemplos/robot
Library           OperatingSystem
Library           banco_hil.py
Resource          banco.resource


*** Variables ***
${IMAGENES}       ${CURDIR}/../yaml/imagenes


*** Test Cases ***
Llamada de cabina lleva a la planta pedida
    [Documentation]    Automatiza DEMO-LLAM-001.
    [Tags]    id:DEMO-LLAM-001    regresion
    ${planta}=    Simular Viaje    origen=0    destino=2
    Should Be Equal As Integers    ${planta}    2

Llamada de piso queda registrada
    [Tags]    id:DEMO-LLAM-002    regresion
    Log    Pulsador de P1 iluminado

Nivelación sin carga
    [Documentation]    Primera variante de DEMO-NIV-001.
    [Tags]    id:DEMO-NIV-001    regresion
    Comprobar Desnivel    3

Nivelación con carga máxima
    [Documentation]    Segunda variante de DEMO-NIV-001: falla y deja una captura.
    [Tags]    id:DEMO-NIV-001    regresion
    Guardar Captura    registro_eventos.png
    Comprobar Desnivel    7

Trama de estado de cabina
    [Tags]    id:DEMO-CAN-001    regresion
    Skip    No hay analizador CAN conectado en este PC

Apertura y reapertura de puertas
    [Documentation]    Un mismo test cubre dos pruebas YAML.
    [Tags]    id:DEMO-PUER-001    id:DEMO-PUER-002    regresion
    Log    Apertura en 2,1 s; reapertura en 180 ms

Diagnóstico del bus sin enlazar
    [Documentation]    Sin etiqueta id: todavía no se ha enlazado con ninguna prueba YAML.
    [Tags]    diagnostico
    Log    Mensaje DIAG 0x7E recibido

Prueba retirada
    [Documentation]    Su ID ya no existe en los YAML: el importador avisa.
    [Tags]    id:DEMO-OLD-999
    Log    Prueba antigua


*** Keywords ***
Simular Viaje
    [Arguments]    ${origen}    ${destino}
    Sleep    0.6s    Tiempo de viaje simulado
    Log    Viaje simulado de ${origen} a ${destino}
    RETURN    ${destino}

Comprobar Desnivel
    [Arguments]    ${mm}
    Sleep    0.6s    Medida simulada del sensor de nivel
    Should Be True    ${mm} <= 5    Desnivel de ${mm} mm: supera el límite de ±5 mm

Guardar Captura
    [Arguments]    ${imagen}
    Copy File    ${IMAGENES}/${imagen}    ${OUTPUT DIR}/captura-${imagen}
    Log    <img src="captura-${imagen}" width="400">    HTML
