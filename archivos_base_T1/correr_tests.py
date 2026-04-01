import json
import os
import re
import shutil
import time
import random
from xmlrpc.client import ServerProxy
from constantes import TIEMPO_ENTRE_EVENTOS, COMANDO_PYTHON
from subprocess import Popen, DEVNULL, STDOUT
import threading


def load_jsonc(path):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    # eliminar comentarios estilo //
    content = re.sub(r"//.*", "", content)
    return json.loads(content)


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def levantar_procesos(
    puerto_servel, sucursales, puertos_sucursal, configuration, nombre, mostrar_print_alumnos
):
    procesos = []

    # Ingresar a carpeta "servel"
    os.chdir("servel")

    # Levantar main.py de servel
    comando = [COMANDO_PYTHON, "main.py", str(puerto_servel), configuration, nombre]
    if mostrar_print_alumnos:
        procesos.append(Popen(comando))
    else:
        procesos.append(Popen(comando, stdout=DEVNULL, stderr=STDOUT))

    # Esperar un momento para que el RPC se levante
    time.sleep(0.5)

    # Salir de "servel" e ingresar a carpeta "sucursal"
    os.chdir(os.path.join("..", "sucursal"))

    # Levantar main.py de sucursal para cada sucursal posible
    for sucursal, puerto in zip(sucursales, puertos_sucursal):
        comando = [
            COMANDO_PYTHON,
            "main.py",
            str(puerto),
            str(puerto_servel),
            sucursal,
        ]
        if mostrar_print_alumnos:
            proceso = Popen(comando)
        else:
            proceso = Popen(comando, stdout=DEVNULL, stderr=STDOUT)
        procesos.append(proceso)

    # Esperar un momento para que todos los RPC se levante
    time.sleep(0.5)
    os.chdir("..")
    return procesos


def terminar_procesos(procesos):
    for p in procesos:
        try:
            p.terminate()
            p.wait()
        except Exception as e:
            print(f"Error al terminar el proceso: {e}")
            continue
    time.sleep(2)


def run_event(evento, sucursal_rpcs, servel_rpc):
    tipo = evento[0]
    try:
        # Eventos de sucursal
        if tipo == "votar":
            sucursal, id_votante, id_votacion, prefencia, estados = evento[1:]
            sucursal_rpcs[sucursal].votar(id_votante, id_votacion, prefencia, estados)
        elif tipo == "reportar":
            sucursal = evento[1]
            sucursal_rpcs[sucursal].reportar()
        elif tipo == "cerrar":
            sucursal = evento[1]
            sucursal_rpcs[sucursal].cerrar_temporal()
        elif tipo == "reanudar":
            sucursal = evento[1]
            sucursal_rpcs[sucursal].reanudar()

        # Eventos de servel
        elif tipo == "crear_subscriptor":
            subscriptor = evento[1]
            servel_rpc.new_subscriber(subscriptor)
        elif tipo == "subscribir":
            subscriptor, sucursal, evento = evento[1:]
            servel_rpc.subscribe(subscriptor, sucursal, evento)
        elif tipo == "desubscribir":
            subscriptor, sucursal, evento = evento[1:]
            servel_rpc.unsubscribe(subscriptor, sucursal, evento)
        elif tipo == "ganador":
            id_votacion = evento[1]
            servel_rpc.ganador(id_votacion)
        elif tipo == "log":
            id_votacion, opcion = evento[1:]
            servel_rpc.log(id_votacion, opcion)

    except Exception:
        pass


def run_test(CARPETA, testname, mostrar_print_alumnos=False, index=0):
    ALL_PUERTOS = list(range(4444, 44440))
    path = os.path.join(CARPETA, testname, "data.jsonc")
    data = load_jsonc(path)
    configuration = data["configuracion"]
    name_log = data["nombre"]
    eventos = data["eventos"]

    # Buscar archivo configuration y copiarlo en servel/votes_configurations
    config_path = os.path.join("votes_configurations", f"{configuration}.json")
    
    shutil.copy(
        config_path, os.path.join("servel", "votes_configurations", f"{configuration}.json")
    )

    configuration_json = load_json(config_path)
    sucursales = configuration_json["sucursales"]

    # Generar un subconjunto de 10 puertos para este test
    PUERTOS = ALL_PUERTOS[index * 10 : (index + 1) * 10]

    # Seleccionar aleatoriamente puertos para el servel y las sucursales de este subconjunto
    PUERTOS = random.sample(PUERTOS, len(sucursales) + 1)

    PUERTO_SERVEL = PUERTOS[0]
    PUERTOS_SUCURSALES = PUERTOS[1:len(sucursales) + 1]

    procesos = levantar_procesos(
        PUERTO_SERVEL,
        sucursales,
        PUERTOS_SUCURSALES,
        configuration,
        name_log,
        mostrar_print_alumnos,
    )

    # Conectarse al RPC de servel
    servel_rpc = ServerProxy(f"http://127.0.0.1:{PUERTO_SERVEL}")

    # Conectarse a los RPC de las sucursales
    sucursal_rpcs = {}
    for sucursal, puerto in zip(sucursales, PUERTOS_SUCURSALES):
        sucursal_rpc = ServerProxy(f"http://127.0.0.1:{puerto}")
        sucursal_rpc.solicitar_información()
        sucursal_rpcs[sucursal] = sucursal_rpc

    # Esperar un momento para que los RPC se sincronicen dad o "solicitar_información"
    time.sleep(1)

    # Ejecutar cada eventos
    cantidad_eventos = len(eventos)

    eventos_validos = {
        "votar",
        "reportar",
        "cerrar",
        "reanudar",
        "crear_subscriptor",
        "subscribir",
        "desubscribir",
        "ganador",
        "log",
    }
    for i, evento in enumerate(eventos, start=1):
        print(f"\tEventos {i}/{cantidad_eventos}")
        print("\t\tEvento:", evento)

        tipo = evento[0]
        if tipo not in eventos_validos:
            print(f"\t\tEvento {tipo} no reconocido. Saltando.")
            terminar_procesos(procesos)
            raise Exception(f"Evento {tipo} no reconocido")

        thread = threading.Thread(
            target=run_event, args=(evento, sucursal_rpcs, servel_rpc)
        )
        thread.start()
        time.sleep(TIEMPO_ENTRE_EVENTOS)  # Esperar un momento para que el evento se procese

    # Esperar un momento antes de cerrar los procesos
    time.sleep(2)
    # Terminar procesos
    terminar_procesos(procesos)

def preparar_entorno():
    carpetas_necesarias = ["logs", "subscriptors", "votes_configurations"]

    for carpeta in carpetas_necesarias:
        ruta_carpeta = os.path.join("servel", carpeta)
        # Eliminar carpeta si existe
        if os.path.exists(ruta_carpeta):
            shutil.rmtree(ruta_carpeta)
        # Crear carpeta
        os.makedirs(ruta_carpeta)
    

if __name__ == "__main__":
    CARPETA = "tests_publicos"
    MOSTRAR_PRINTS = False

    preparar_entorno()

    for i, test in enumerate(os.listdir(CARPETA)):
        if test in [".DS_Store"]:
            continue

        print(f"Ejecutando {test}...")
        run_test(CARPETA, test, mostrar_print_alumnos=MOSTRAR_PRINTS, index=i)
        print(f"{test} finalizado.\n")
        print("#" * 50 + "\n")
