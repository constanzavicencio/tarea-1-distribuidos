# Solo puedes importar las siguientes librerías y ninguna otra
from typing import List
from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.client import ServerProxy
from sys import argv
import os, json, math, threading, time


class Sucursal:
    def __init__(self, puerto_servel: str, nombre: str) -> None:
        self.puerto_servel = puerto_servel
        self.nombre = nombre
        self.votos = {}
        self.registro = {}
        self.estado = "Abierta"
        # Conectar con el servidor Servel via RPC
        IP_TAREA = "127.0.0.1"
        self.servel = ServerProxy(f"http://{IP_TAREA}:{puerto_servel}", allow_none=True)

    def solicitar_información(self) -> None:
        # Inicializa estructura de votos y registro según configuración Servel.
        self.votos = {}
        self.registro = {}
        if hasattr(self.servel, 'configuracion') and self.servel.configuracion:
            for id_votacion in self.servel.configuracion.get('temas_votaciones', {}).keys():
                self.votos[id_votacion] = []
                self.registro[id_votacion] = []

    def cerrar_temporal(self) -> None:
        self.estado = "Cerrada"

    def reanudar(self) -> None:
        if self.estado == "Cerrada":
            self.estado = "Abierta"
        else:
            pass

    def reportar(self) -> None:
        if self.estado == "Abierta":
            self.servel.recibir_votos(self.nombre, self.votos)
            # Envío incremental: vaciar buffer de votos ya reportados
            for id_votacion in self.votos:
                self.votos[id_votacion] = []
    
    def votar(
        self,
        id_votante: str,
        id_votacion: str,
        preferencias: List[str],
        estados: List[str],
    ) -> None:
        evento=""
        # Asegurar estructuras por si no se inicializó bien
        self.votos.setdefault(id_votacion, [])
        self.registro.setdefault(id_votacion, [])
        # 1. verificar las condiciones que impiden votar
        ### 1.a. sucursal está cerrada
        if self.estado != "Abierta":
            evento = "Cerrado"
        ### 1.b. la votación no existe
        elif id_votacion not in self.servel.configuracion["temas_votaciones"]:
            evento = "No existe"
        ### 1.d. el votante está indocumentado
        elif "Indocumentado" in estados:
            if "Corrupto" not in estados:
                evento = "Indocumentado"
        ### 1.c. el votante no está inscrito en la sucursal para dicha votación
        elif int(id_votante) not in self.servel.configuracion["votantes_habilitados_sucursal"][self.nombre][id_votacion]:
            if "Mov. Reducida" not in estados:
                evento = "Sucursal incorrecta"
        ### 1.e. el votante ya votó previamente en dicha sucursal para la votación indicada
        elif int(id_votante) in self.registro[id_votacion]: # corregir
            if "Corrupto" not in estados:
                evento = "Repetido"

        # Registrar voto
        if evento == "":
            opciones_validas = self.servel.configuracion["opciones_votaciones"].get(id_votacion, [])
            # Caso negacionista
            if "Negacionista" in estados:
                prefs_nuevas = set(opciones_validas) - set(preferencias)
                preferencias = list(prefs_nuevas)
            prefs_validas = []
            for preferencia in preferencias:
                if preferencia in opciones_validas:
                    prefs_validas.append(preferencia)
            if len(prefs_validas) == 1:
                pref_final = prefs_validas[0]
            elif len(prefs_validas) == 0:
                pref_final = "Blanco"
            elif len(prefs_validas) > 1:
                pref_final = "Nulo"

            # Marcamos que el votante ya votó para la votación dada
            self.registro[id_votacion].append(int(id_votante))
            # Anotamos el voto
            self.votos[id_votacion].append(pref_final)
        
        else:
            self.servel.publish(self.nombre, id_votante, evento)
    






    # Puedes agregar métodos adicionales si lo consideras necesario


if __name__ == "__main__":
    if len(argv) != 4 or not argv[1].isdigit():
        texto = """
        El comando debe ser ejecutado con el siguiente formato:
        <COMANDO_PYTHON> main.py <PUERTO> <PUERTO_SERVEL> <NOMBRE>

        Donde:
         - <COMANDO_PYTHON> es el comando para ejecutar Python en tu sistema operativo.
         - <PUERTO> es el puerto en el que se ejecutará el servidor RPC.
         - <PUERTO_SERVEL> es el puerto en el que se encuentra el servidor Servel.
         - <NOMBRE> es el nombre de la sucursal.
        """
        print(texto)
        exit(1)

    PUERTO = int(argv[1])
    PUERTO_SERVEL = int(argv[2])
    NOMBRE = argv[3]

    # DEBES dejar IP_TAREA como "127.0.0.1"
    # porque como "localhost" es un poco más lenta la comunicación
    # para los que tienen sistema Windows
    # Link de interés: https://superuser.com/a/595324
    IP_TAREA = "127.0.0.1"

    sucursal = Sucursal(PUERTO_SERVEL, NOMBRE)
    
    server = SimpleXMLRPCServer((IP_TAREA, PUERTO), allow_none=True)
    server.register_instance(sucursal)
    
    print(f"Sucursal {NOMBRE} ejecutándose en {IP_TAREA}:{PUERTO}")
    server.serve_forever()

    
