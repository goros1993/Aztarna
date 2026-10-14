*** Settings ***
Documentation     Keywords del banco HIL (ficticias) escritas como pasos de prueba.
...
...               Los nombres son frases, con los datos como argumentos
...               incrustados (${planta}): así el mismo texto sirve de paso en
...               las pruebas YAML y de paso en Robot. El editor las propone al
...               escribir los pasos.


*** Keywords ***
Llevar la cabina a ${planta} y esperar a que cierre puertas
    [Documentation]    Envía la cabina a la planta y espera a puertas cerradas.
    Log    Cabina en ${planta} con puertas cerradas

Activar el interruptor de inspección del techo de cabina
    [Documentation]    Pone el controlador en modo inspección.
    Log    Modo inspección activado

Desconectar el bus CAN desde el panel del banco HIL
    [Documentation]    Abre el relé del bus CAN de cabina.
    Log    Bus CAN desconectado

Esperar al menos ${tiempo}
    [Documentation]    Espera el tiempo indicado (por ejemplo «1 s» o «500 ms»).
    Log    Espera de ${tiempo}

Comprobar la alarma
    [Documentation]    Comprueba que el registro de eventos tiene la alarma indicada.
    [Arguments]    ${codigo}    ${timeout}=5 s
    Log    Alarma ${codigo} (esperando hasta ${timeout})
