# Solo puedes importar las siguientes librerías y ninguna otra
from xmlrpc.server import SimpleXMLRPCServer
from sys import argv
import os, json, math, threading, time


class Servel:
    def __init__(self, archivo_configuacion: str, archivo_log: str) -> None:
        with open("votes_configurations/" + archivo_configuacion, 'r', encoding='utf-8') as configuracion:
            self.configuracion = json.load(configuracion)
        self.archivo_log = archivo_log
        with open(archivo_log, 'w', encoding='utf-8') as archivo:
            pass
        self.votos_globales = {}
        for id_votacion in self.configuracion.get("temas_votaciones", {}):
            self.votos_globales[id_votacion] = {}
            for opcion in self.configuracion.get("opciones_votaciones", {}).get(id_votacion, []):
                self.votos_globales[id_votacion][opcion] = 0
            self.votos_globales[id_votacion]["Nulo"] = 0
            self.votos_globales[id_votacion]["Blanco"] = 0
        self.suscriptores = {}
        
    def recibir_votos(self, sucursal: str, votos: dict) -> None:
        total_votos = 0
        for id_votacion, lista_votos in votos.items():
            if id_votacion not in self.votos_globales:
                continue
            for voto in lista_votos:
                if voto not in self.votos_globales[id_votacion]:
                    continue
                self.votos_globales[id_votacion][voto] += 1
                total_votos += 1
        with open(self.archivo_log, 'a', encoding='utf-8') as archivo:
            archivo.write(f"Sucursal {sucursal} ha enviado información: {total_votos}\n")

    def ganador(self, id_votacion: str) -> None:
        tema = self.configuracion["temas_votaciones"].get(id_votacion, "")
        votos = self.votos_globales.get(id_votacion, {})
        opciones_validas = [op for op in votos.keys() if op not in ["Nulo", "Blanco"]]
        votos_validos = sum(votos.get(op, 0) for op in opciones_validas)

        if votos_validos == 0 or not opciones_validas:
            resultado = "No se puede determinar"
        else:
            max_votos = max(votos.get(op, 0) for op in opciones_validas)
            ganadores = [op for op in opciones_validas if votos.get(op, 0) == max_votos]
            if len(ganadores) == 1:
                resultado = ganadores[0]
            else:
                resultado = "Empate"

        with open(self.archivo_log, 'a', encoding='utf-8') as archivo:
            archivo.write(f"Ganador {tema}: {resultado}\n")

    def log(self, id_votacion: str, opcion: str) -> None:
        tema = self.configuracion["temas_votaciones"][id_votacion]
        if opcion not in self.votos_globales[id_votacion].keys():
            resultado = "No existe" 
        else:
            resultado = self.votos_globales[id_votacion][opcion]
        with open(self.archivo_log, 'a', encoding='utf-8') as archivo:
            archivo.write(f"Votos {tema} ({opcion}): {resultado}\n")

    def new_subscriber(self, subscriptor: str) -> None:
        archivo_subscriptor = os.path.join("servel/subscriptors", f"{subscriptor}.txt")
        with open(archivo_subscriptor, 'w', encoding='utf-8') as archivo:
            pass
        self.suscriptores[subscriptor] = set()

    def subscribe(self, subscriptor: str, sucursal: str, evento: str) -> None:
        if subscriptor not in self.suscriptores:
            return None
        self.suscriptores[subscriptor].add((sucursal, evento))

    def unsubscribe(self, subscriptor: str, sucursal: str, evento: str) -> None:
        if subscriptor not in self.suscriptores:
            return None
        if (sucursal, evento) in self.suscriptores[subscriptor]:
            self.suscriptores[subscriptor].remove((sucursal, evento))
    
    def publish(self, sucursal: str, id: str, evento: str) -> None:
        votante_nombre = "Desconocido"
        try:
            with open("votantes.csv", 'r', encoding='utf-8') as archivo:
                for linea in archivo:
                    datos = linea.strip().split(",")
                    if len(datos) >= 2 and str(datos[0]) == str(id):
                        votante_nombre = datos[1]
                        break
        except FileNotFoundError:
            votante_nombre = "Desconocido"

        for subscriptor, filtros in self.suscriptores.items():
            coincide = False
            for filtro_sucursal, filtro_evento in filtros:
                if (filtro_sucursal == "*" or filtro_sucursal == sucursal) and (
                    filtro_evento == "*" or filtro_evento == evento
                ):
                    coincide = True
                    break
            if coincide:
                archivo_subscriptor = os.path.join("servel/subscriptors", f"{subscriptor}.txt")
                with open(archivo_subscriptor, 'a', encoding='utf-8') as archivo:
                    archivo.write(f"{sucursal};{votante_nombre};{evento}\n")





if __name__ == "__main__":
    if len(argv) != 4 or not argv[1].isdigit():
        texto = """
        El comando debe ser ejecutado con el siguiente formato:
        <COMANDO_PYTHON> main.py <PUERTO> <CONFIGURACION> <LOGS>

        Donde:
         - <COMANDO_PYTHON> es el comando para ejecutar Python en tu sistema operativo.
         - <PUERTO> es el puerto en el que se ejecutará el servidor RPC.
         - <CONFIGURACION> es el nombre de un archivo JSON con la configuración de la votación.
         - <LOGS> es el nombre de un archivo TXT donde se guardarán los logs de la votación.
        """
        print(texto)
        exit(1)

    PUERTO = int(argv[1])
    CONFIGURACION = argv[2]
    LOGS = argv[3]

    # DEBES dejar IP_TAREA como "127.0.0.1"
    # porque como "localhost" es un poco más lenta la comunicación
    # para los que tienen sistema Windows
    # Link de interés: https://superuser.com/a/595324
    IP_TAREA = "127.0.0.1"

    servel_votaciones = Servel(CONFIGURACION, LOGS)
    
    # Crear servidor RPC
    server = SimpleXMLRPCServer((IP_TAREA, PUERTO), allow_none=True)
    server.register_instance(servel_votaciones)
    
    print(f"Servidor RPC ejecutándose en {IP_TAREA}:{PUERTO}")
    server.serve_forever()
