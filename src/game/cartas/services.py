from game.cartas.constants import cartasDict, secretosDict
from game.cartas.models import Carta
from game.jugadores.models import Jugador
from game.jugadores.services import JugadorService
#from game.partidas.models import Partida
import random
from game.partidas.utils import * 
from typing import List
from collections import Counter


class CartaService:
    def __init__(self,db):
        self._db = db
        
    
    def crear_mazo_inicial(self, id_partida: int) -> list[Carta]:
        """
        Crea el mazo inicial de cartas para una partida.
        
        Parameters
        ----------
        id_partida: int
            ID de la partida para la cual se crea el mazo.
        
        Returns
        -------
        List[Carta]
            Lista de objetos Carta que representan el mazo incicial.
        """  

        

        mazo_nuevo = []
        for carta in cartasDict.values():
            cantidad = carta["cantidad"]
            while cantidad > 0:
                cartita = Carta(
                    nombre=carta["carta"],
                    tipo=carta["tipo"],
                    bocaArriba=carta["bocaArriba"],
                    ubicacion=carta["ubicacion"],
                    jugador_id=0,
                    partida_id=id_partida,
                    id_carta=carta["id"]
                    )
                cantidad -= 1
                mazo_nuevo.append(cartita)

        self._db.add_all(mazo_nuevo)
        self._db.commit()

        return mazo_nuevo

    def repartir_cartas_iniciales(self, mazo: list[Carta], jugadores_en_partida: list[Jugador]):
        """
        Reparte las cartas iniciales a los jugadores en una partida.
        
        Parameters
        ----------
        mazo: list[Carta]
            Lista de objetos Carta que representan el mazo incicial.

        jugadores_en_partida: list[Jugador]
            Lista de jugadores en un
        """
        random.shuffle(mazo)
        # Una carta "Not so fast" por jugador
        for jugador in jugadores_en_partida:
            for carta in mazo:
                if carta.nombre.lower() == "not so fast" and carta.jugador_id == 0:
                    carta.jugador_id = jugador.id
                    carta.ubicacion = "mano"
                    break  # pasamos al siguiente jugador
        # Luego, repartir hasta 6 cartas por jugador
        for jugador in jugadores_en_partida:
            cartas_jugador = 0
            for carta in mazo:
                if carta.jugador_id == 0:
                    carta.jugador_id = jugador.id
                    carta.ubicacion = "mano"
                    cartas_jugador += 1
                    if cartas_jugador == 5:
                        break  # pasamos al siguiente jugador
        self._db.commit()
        self._db.refresh(carta)
            
        print("se repartieron las cartas hasta 6")
       
                    
    def obtener_mazo_de_robo(self, id_partida: int) -> list[Carta]:
        """
        Obtiene el mazo de robo para una partida específica.
        
        Parameters
        ----------
        id_partida: int
            ID de la partida para la cual se obtiene el mazo de robo.
        
        Returns
        -------
        List[Carta]
            Lista de objetos Carta que representan el mazo de robo.
        """
        mazo_robo = self._db.query(Carta).filter_by(partida_id=id_partida, ubicacion="mazo_robo").all()
        return mazo_robo
    
    def obtener_mano_jugador(self, id_jugador:  int, id_partida: int) -> list[Carta]:
        """
        Obtiene la mano de cartas de un jugador en una partida específica.
        
        Parameters
        ----------
        id_jugador: int
            ID del jugador para el cual se obtiene la mano de cartas.
        
        id_partida: int
            ID de la partida para la cual se obtiene la mano de cartas.
        
        Returns
        -------
        List[Carta]
            Lista de objetos Carta que representan la mano del jugador.
        """
        mano_jugador = self._db.query(Carta).filter_by(partida_id=id_partida, jugador_id=id_jugador, ubicacion="mano").all()
        return mano_jugador


    def descartar_cartas(self, id_jugador, cartas_descarte_id):
        """
        DOC
        """
        print("ACA POR AGARRAR EL JUGADOR")
        jugador = JugadorService(self._db).obtener_jugador(id_jugador)
        print("YA AGARRE EL JUGADOR")


        tiene_cartas = True
        cartas_mano = jugador.cartas
        for carta_id in cartas_descarte_id:
            enMano = False
            for carta in cartas_mano:
                if (carta_id == carta.id_carta):
                    enMano = enMano or True 
            tiene_cartas = tiene_cartas and enMano

        if not tiene_cartas:
            raise Exception("Una o mas cartas no se encuentran en la mano del jugador")
        
        
        for carta in cartas_descarte_id:
            carta_descarte = self._db.query(Carta).filter(Carta.id_carta == carta, Carta.jugador_id == id_jugador).first()
            carta_descarte.jugador_id = 0
            carta_descarte.ubicacion = "descarte"
            carta_descarte.bocaArriba = False
            self._db.commit()
            print(f'Se descarto la carta con id {carta_descarte.id} y nombre {carta_descarte.nombre}.')


    def obtener_cantidad_mazo(self, id_partida: int) -> int:
        """
        Calcula la cantidad de cartas restantes en el mazo de robo.
        """
        mazo_robo = self.obtener_mazo_de_robo(id_partida)
        return len(mazo_robo)

    def robar_cartas(self, id_partida: int, id_jugador: int, cantidad: int = 1):
        if cantidad <= 0:
            raise ValueError("La cantidad a robar debe ser mayor a 0")

        # Obtener mazo de robo
        mazo = self.obtener_mazo_de_robo(id_partida)
        # Si no hay suficientes, robar tantas como haya
        if len(mazo) == 0:
            return []
        if len(mazo) < cantidad:
            cantidad = len(mazo)

        # Mezclar para simular robo aleatorio y tomar 'cantidad'
        random.shuffle(mazo)
        cartas_a_robar = mazo[:cantidad]

        # Asignar cartas al jugador
        for carta in cartas_a_robar:
            carta.jugador_id = id_jugador
            carta.ubicacion = "mano"

        self._db.commit()

        # Retornar información mínima al frontend
        return [
            {"id": carta.id_carta, "nombre": carta.nombre}
            for carta in cartas_a_robar
        ]

    def actualizar_mazo_draft(self, id_partida: int):
        """
        Actualiza el mazo de draft de una partida.

        Parameters
        ----------
            id_partida (int)

        """
        mazo_draft = (
        self._db.query(Carta)
        .filter(Carta.partida_id == id_partida, Carta.ubicacion == "draft")
        .all())

        cartas_draft = len(mazo_draft)
        if cartas_draft <= 2:
            mazo_robo = self.obtener_mazo_de_robo(id_partida)
            random.shuffle(mazo_robo)
            for cartas in mazo_robo:
                cartas.ubicacion = "draft"
                cartas_draft += 1
                if cartas_draft == 3:
                    break
            
            self._db.commit()

    def obtener_mazo_draft(self, id_partida: int) -> list[Carta]:
        """
        Obtiene el mazo de draft de una partida.

        Parameters
        ----------
            id_partida (int)

        Returns
        --------
            list[Carta]
        """
        mazo_draft = (self._db.query(Carta)
                        .filter(Carta.partida_id == id_partida, Carta.ubicacion == "draft")
                        .all())
                
        return mazo_draft
    
    def tomar_cartas_draft(self, id_partida: int, id_jugador: int, cartas_tomadas_ids: List[int]):
        """
        Permite al jugador tomar una o más cartas del draft.
        """
        if not cartas_tomadas_ids:
            return

        mazo = self.obtener_mazo_draft(id_partida)
        ids_cartas = [carta.id_carta for carta in mazo]
        if not all(id in ids_cartas for id in cartas_tomadas_ids):
            raise Exception("Una o más cartas seleccionadas no se encuentran en el draft.")


        for carta in mazo:
            if carta.id_carta in cartas_tomadas_ids:  
                carta.jugador_id = id_jugador
                carta.ubicacion = "mano"
                cartas_tomadas_ids.remove(carta.id_carta)
        
        self._db.commit()

    
    def crear_secretos(self, id_partida):
        """
        Crea las cartas secreto para una partida.
        
        Parameters
        ----------
        id_partida: int
            ID de la partida para la cual se crean los secretos.
        
        Returns
        -------
        List[Carta]
            Lista de objetos Carta que representan los secretos.
        """

        secretos = []
        for carta in secretosDict.values():
            cantidad = carta["cantidad"]
            while cantidad > 0:
                secret = Carta(
                    nombre=carta["carta"],
                    tipo=carta["tipo"],
                    bocaArriba=carta["bocaArriba"],
                    ubicacion=carta["ubicacion"],
                    jugador_id=0,
                    partida_id=id_partida,
                    id_carta=carta["id"]
                    )
                cantidad -= 1
                secretos.append(secret)

        self._db.add_all(secretos)
        self._db.commit()

        return secretos
    
    def repartir_secretos(self, secretos: list[Carta], jugadores_en_partida: list[Jugador]):
        """
        Reparte las cartas secreto a los jugadores en una partida.
        
        Parameters
        ----------
        mazo: list[Carta]
            Lista de objetos Carta que son los secretos.

        jugadores_en_partida: list[Jugador]
            Lista de jugadores en un
        """

        # Lista de IDs de los jugadores en la partida
        jugadores_ids = [jugador.id for jugador in jugadores_en_partida]
        
        # Se elige un jugador al azar para que sea el asesino
        index_murderer = random.randrange(len(jugadores_en_partida))
        
        # Le asigno la carta de asesino
        secretos[0].jugador_id = jugadores_en_partida[index_murderer].id

        # Saco el id del asesino de la lista de IDs
        jugadores_ids.remove(jugadores_en_partida[index_murderer].id)

        # Si es una partida de 5 o 6 jugadores debe haber un cómplice
        if (len(jugadores_en_partida) >= 5):
            accomplice_found = False
            while not accomplice_found:
                index_accomplice = random.randrange(len(jugadores_en_partida))
                if index_accomplice != index_murderer:
                    secretos[1].jugador_id = jugadores_en_partida[index_accomplice].id
                    accomplice_found = True
            
            # Saco el id del cómplice de la lista de IDs 
            jugadores_ids.remove(jugadores_en_partida[index_accomplice].id)
        
        comunes = 2
        for jugador in jugadores_en_partida:
            # Arrancamos del 3er secreto en adelante (es decir los comunes)
            # Si no es asesino o cómplice, le doy 3 secretos
            if jugador.id in jugadores_ids:
                for _ in range(3):
                    secretos[comunes].jugador_id = jugador.id
                    comunes+=1
            # Si es asesino o cómplice, le doy los 2 secretos que le faltan
            else:
                for _ in range(2):
                    secretos[comunes].jugador_id = jugador.id
                    comunes+=1
        
        self._db.commit()
        #self._db.refresh(secretos)
            
        print("se repartieron los secretos")
        
    def obtener_carta(self, id_carta: int) -> Carta:
        """
        Obtiene un objeto Carta específico por su id_carta.
        """
        carta = self._db.query(Carta).filter(Carta.id_carta == id_carta).first()
        if not carta:
            raise ValueError(f"No se encontró una carta con id_carta {id_carta}")
        return carta

    
    def obtener_secretos_jugador(self, id_jugador:  int, id_partida: int) -> list[Carta]:
        """
        Obtiene los secretos de un jugador en una partida específica.
        
        Parameters
        ----------
        id_jugador: int
            ID del jugador para el cual se obtiene los secretos.
        
        id_partida: int
            ID de la partida para la cual se obtiene los secretos.
        
        Returns
        -------
        List[Carta]
            Lista de objetos Carta secreto del jugador.
        """
        secretos_jugador = self._db.query(Carta).filter_by(partida_id=id_partida, jugador_id=id_jugador, ubicacion="mesa").all()
        return secretos_jugador
    
    def obtener_asesino_complice(self, id_partida):
        print("OBTENIENDO CARTAS ASESINO Y COMPLICE")
        carta_asesino = self._db.query(Carta).filter_by(partida_id=id_partida, tipo="secreto", nombre="murderer").first()
        print(f"la carta del asesino es la carta con el ID: {carta_asesino.id}")
        asesino_id = carta_asesino.jugador_id
        carta_complice = self._db.query(Carta).filter_by(partida_id=id_partida, tipo="secreto", nombre="accomplice").first()
        print(f"la carta del cómplice es la carta con el ID: {carta_complice.id}")
        complice_id = carta_complice.jugador_id
        
        return {"asesino-id": asesino_id, "complice-id": complice_id}
