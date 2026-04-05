# Solo puedes importar las siguientes librerías y ninguna otra
from xmlrpc.server import SimpleXMLRPCServer
from sys import argv
import os
import json


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


class Servel:
    def __init__(self, archivo_configuracion: str, archivo_log: str) -> None:
        self.config_path = os.path.join(
            'votes_configurations',
            f'{archivo_configuracion}.json')
        self.log_path = os.path.join('logs', f'{archivo_log}.txt')
        # Creamos el archivo para el log (vacío)
        with open(self.log_path, 'w', encoding='utf-8'):
            pass
        # Cargamos la configuración
        self.configuration = load_json(self.config_path)
        self.ids_votaciones = self.configuration['temas_votaciones']
        self.temas = self.configuration['temas_votaciones']
        self.opciones = self.configuration['opciones_votaciones']

        # Inicializamos un contador de votos_globales (dict)
        self.votos_globales = {}
        for id_votacion in self.ids_votaciones:
            self.votos_globales[id_votacion] = {}
            for opcion in self.opciones[id_votacion]:
                self.votos_globales[id_votacion][opcion] = 0
            self.votos_globales[id_votacion]['Nulo'] = 0
            self.votos_globales[id_votacion]['Blanco'] = 0

        # Inicializamos un registro de suscriptores (dict)
        self.suscriptores = {}

    def recibir_votos(self, sucursal: str, votos: dict) -> None:
        total_votos = 0
        for id_votacion, dict_votos in votos.items():
            if id_votacion in self.votos_globales:
                for opcion in dict_votos:
                    if opcion in self.votos_globales[id_votacion]:
                        valor = dict_votos[opcion]
                        self.votos_globales[id_votacion][opcion] += valor
                        total_votos += valor
        with open(self.log_path, 'a', encoding='utf-8') as archivo:
            archivo.write(
                f'Sucursal {sucursal} ha enviado información: {total_votos}\n'
            )

    def ganador(self, id_votacion: str) -> None:
        tema = self.configuration['temas_votaciones'][id_votacion]
        votos = self.votos_globales[id_votacion]
        opciones_validas = [
            op for op in votos.keys() if op not in ['Nulo', 'Blanco']
            ]
        votos_validos = sum(votos.get(op, 0) for op in opciones_validas)

        if votos_validos == 0 or not opciones_validas:
            resultado = 'No se puede determinar'
        else:
            max_votos = max(votos.get(op, 0) for op in opciones_validas)
            ganadores = [
                op for op in opciones_validas
                if votos.get(op, 0) == max_votos
            ]
            if len(ganadores) == 1:
                resultado = ganadores[0]
            else:
                resultado = 'Empate'

        with open(self.log_path, 'a', encoding='utf-8') as archivo:
            archivo.write(f'Ganador {tema}: {resultado}\n')

    def log(self, id_votacion: str, opcion: str) -> None:
        tema = self.configuration['temas_votaciones'][id_votacion]
        if opcion not in self.votos_globales[id_votacion].keys():
            resultado = 'No existe' 
        else:
            resultado = self.votos_globales[id_votacion][opcion]
        with open(self.log_path, 'a', encoding='utf-8') as archivo:
            archivo.write(f'Votos {tema} ({opcion}): {resultado}\n')

    def new_subscriber(self, subscriptor: str) -> None:
        '''
        Crea un nuevo archivo que representará a un subscriptor.
        El archivo se almacena en un directorio/carpeta llamado subscriptor y
        cuyo nombre debe ser igual al indicado por el argumento subscriptor.

        Si el archivo indicado ya existe, este se debe eliminar y crear
        nuevamente para asegurar que el contenido esté limpio.

        Finalmente, el subscriptor no posee ningún filtro al momento de ser
        creado.
        '''
        archivo_subscriptor = os.path.join(
            'subscriptors', f'{subscriptor}.txt'
            )
        with open(archivo_subscriptor, 'w', encoding='utf-8'):
            pass
        self.suscriptores[subscriptor] = set()

    def subscribe(self, subscriptor: str, sucursal: str, evento: str) -> None:
        '''
        Agrega un nuevo filtro al subscriptor indicado por subscriptor.
        El filtro corresponde al par (sucursal, evento) y determina qué
        eventos se deben notificar al subscriptor.
        '''
        if subscriptor not in self.suscriptores:
            return None
        self.suscriptores[subscriptor].add((sucursal, evento))

    def unsubscribe(
            self,
            subscriptor: str,
            sucursal: str,
            evento: str
            ) -> None:
        '''
        Elimina el filtro correspondiente al par (sucursal, evento) del
        subscriptor indicado por subscriptor.

        Si el subscriptor no existe o el filtro no está registrado, entonces
        no ocurre ningún cambio
        '''
        if subscriptor not in self.suscriptores:
            return None
        if (sucursal, evento) in self.suscriptores[subscriptor]:
            self.suscriptores[subscriptor].remove((sucursal, evento))

    def publish(self, sucursal: str, id: str, evento: str) -> None:
        '''
        Primero, obtiene el nombre del votante a partir de su id.
        Luego, publica el evento (sucursal, id, evento) a los subscriptores que
        concierna con el formato sucursal;nombre_votante;evento
        '''

        # Se obtiene el nombre del votante a partir de su id
        try:
            with open('votantes.csv', 'r', encoding='utf-8') as archivo:
                for linea in archivo:
                    datos = linea.strip().split(',')
                    if len(datos) >= 2 and str(datos[0]) == str(id):
                        votante_nombre = datos[1]
                        break
        # Si no existe en los registros, se declara desconocido
        except FileNotFoundError:
            votante_nombre = 'Desconocido'

        for subscriptor, filtros in self.suscriptores.items():
            coincide = False
            for filtro_sucursal, filtro_evento in filtros:
                sucursal_ok = filtro_sucursal in ('*', sucursal)
                evento_ok = filtro_evento in ('*', evento)
                if sucursal_ok and evento_ok:
                    coincide = True
                    break
            if coincide:
                archivo_subscriptor = os.path.join(
                    'subscriptors',
                    f'{subscriptor}.txt'
                )
                with open(archivo_subscriptor, 'a', encoding='utf-8') as a:
                    a.write(f'{sucursal};{votante_nombre};{evento}\n')

    def get_configuration(self) -> dict:
        return self.configuration


if __name__ == '__main__':
    if len(argv) != 4 or not argv[1].isdigit():
        texto = '''
        El comando debe ser ejecutado con el siguiente formato:
        <COMANDO_PYTHON> main.py <PUERTO> <CONFIGURACION> <LOGS>

        Donde:
         - <COMANDO_PYTHON> es el comando para ejecutar Python en tu sistema operativo.
         - <PUERTO> es el puerto en el que se ejecutará el servidor RPC.
         - <CONFIGURACION> es el nombre de un archivo JSON con la configuración de la votación.
         - <LOGS> es el nombre de un archivo TXT donde se guardarán los logs de la votación.
        '''
        print(texto)
        exit(1)

    PUERTO = int(argv[1])
    CONFIGURACION = argv[2]
    LOGS = argv[3]

    # DEBES dejar IP_TAREA como '127.0.0.1'
    # porque como 'localhost' es un poco más lenta la comunicación
    # para los que tienen sistema Windows
    # Link de interés: https://superuser.com/a/595324
    IP_TAREA = '127.0.0.1'

    servel_votaciones = Servel(CONFIGURACION, LOGS)

    server = SimpleXMLRPCServer((IP_TAREA, PUERTO), allow_none=True)
    server.register_instance(servel_votaciones)

    print(f'Servidor RPC ejecutándose en {IP_TAREA}:{PUERTO}')
    server.serve_forever()
