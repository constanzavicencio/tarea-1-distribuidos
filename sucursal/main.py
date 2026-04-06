# Solo puedes importar las siguientes librerías y ninguna otra
from typing import List
from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.client import ServerProxy
from sys import argv


class Sucursal:
    def __init__(self, puerto_servel: str, nombre: str) -> None:
        self.configuration = {}
        self.opciones = {}
        self.registro = {}
        self.puerto_servel = puerto_servel
        self.nombre = nombre
        self.registro = {'Votos': {}, 'Ya Votaron': {}}
        self.estado = 'Abierta'

        # Conectar con el servidor Servel
        self.servel = ServerProxy(
            f'http://{IP_TAREA}:{puerto_servel}', allow_none=True
            )

    def solicitar_información(self) -> None:
        # Actualiza estructura de votos y registro según configuración Servel.
        config = self.servel.get_configuration()
        if not isinstance(config, dict):
            raise TypeError('La configuración recibida no es un diccionario')
        self.configuration = config
        self.ids_votaciones = self.configuration['temas_votaciones']
        self.temas = self.configuration['temas_votaciones']
        self.opciones = self.configuration['opciones_votaciones']
        self.registro['Ya Votaron'] = {id: [] for id in self.ids_votaciones}
        self.reiniciar_votos()

    def reiniciar_votos(self) -> None:
        for id_votacion in self.ids_votaciones:
            self.registro['Votos'][id_votacion] = {}
            for opcion in self.opciones[id_votacion]:
                self.registro['Votos'][id_votacion][opcion] = 0
            self.registro['Votos'][id_votacion]['Nulo'] = 0
            self.registro['Votos'][id_votacion]['Blanco'] = 0

    def cerrar_temporal(self) -> None:
        self.estado = 'Cerrada'

    def reanudar(self) -> None:
        self.estado = 'Abierta'

    def reportar(self) -> None:
        if self.estado == 'Abierta':
            self.servel.recibir_votos(self.nombre, self.registro['Votos'])
            self.reiniciar_votos()

    def votar(
        self,
        id_votante: str,
        id_votacion: str,
        preferencias: List[str],
        estados: List[str],
    ) -> None:

        evento = ''

        # 1. verificar las condiciones que impiden votar
        # 1.a. sucursal está cerrada
        if self.estado != 'Abierta':
            evento = 'Cerrado'
        # 1.b. la votación no existe
        elif id_votacion not in self.configuration['temas_votaciones']:
            evento = 'No existe'
        # 1.d. el votante está indocumentado
        elif 'Indocumentado' in estados:
            if 'Corrupto' not in estados:
                evento = 'Indocumentado'
        # 1.c. el votante no está inscrito en la sucursal para dicha votación
        elif int(id_votante) not in self.configuration[
            'votantes_habilitados_sucursal'
        ][self.nombre][id_votacion]:
            if 'Mov. Reducida' not in estados:
                evento = 'Sucursal incorrecta'
        # 1.e. el votante ya votó en dicha sucursal para la votación indicada
        elif int(id_votante) in self.registro['Ya Votaron'][id_votacion]:
            if 'Corrupto' not in estados:
                evento = 'Repetido'

        # Registrar voto
        if evento == '':
            opciones_validas = self.opciones[id_votacion]

            # Caso negacionista
            if 'Negacionista' in estados:
                preferencias = list(set(opciones_validas) - set(preferencias))

            prefs_validas = []
            for preferencia in preferencias:
                if preferencia in opciones_validas:
                    prefs_validas.append(preferencia)

            if len(prefs_validas) == 1:
                pref_final = prefs_validas[0]
            elif len(prefs_validas) == 0:
                pref_final = 'Blanco'
            elif len(prefs_validas) > 1:
                pref_final = 'Nulo'

            # Caso general
            # Marcamos que el votante ya votó para la votación dada
            self.registro['Ya Votaron'][id_votacion].append(int(id_votante))
            # Anotamos el voto
            self.registro['Votos'][id_votacion][pref_final] += 1

        else:
            self.servel.publish(self.nombre, id_votante, evento)

    def verificar_voto(self):  # -> bool
        pass


if __name__ == '__main__':
    if len(argv) != 4 or not argv[1].isdigit():
        texto = '''
        El comando debe ser ejecutado con el siguiente formato:
        <COMANDO_PYTHON> main.py <PUERTO> <PUERTO_SERVEL> <NOMBRE>

        Donde:
         - <COMANDO_PYTHON> es el comando para ejecutar Python en tu sistema operativo.
         - <PUERTO> es el puerto en el que se ejecutará el servidor RPC.
         - <PUERTO_SERVEL> es el puerto en el que se encuentra el servidor Servel.
         - <NOMBRE> es el nombre de la sucursal.
        '''
        print(texto)
        exit(1)

    PUERTO = int(argv[1])
    PUERTO_SERVEL = int(argv[2])
    NOMBRE = argv[3]

    # DEBES dejar IP_TAREA como '127.0.0.1'
    # porque como 'localhost' es un poco más lenta la comunicación
    # para los que tienen sistema Windows
    # Link de interés: https://superuser.com/a/595324
    IP_TAREA = '127.0.0.1'

    sucursal = Sucursal(str(PUERTO_SERVEL), NOMBRE)

    server = SimpleXMLRPCServer((IP_TAREA, PUERTO), allow_none=True)
    server.register_instance(sucursal)

    print(f'Sucursal {NOMBRE} ejecutándose en {IP_TAREA}:{PUERTO}')
    server.serve_forever()
