from game.cartas.constants import cartasDict
from game.cartas.models import Carta
from game.jugadores.models import Jugador
from game.jugadores.services import JugadorService
#from game.partidas.models import Partida
import random
from game.partidas.utils import * 
#from game.partidas.services import PartidaService


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
    
    def obtener_mazo_descarte(self, id_partida: int) -> list[Carta]:
        """
        Obtiene el mazo de descarte de una partida.

        Args:
            id_partida (int)

        Returns:
            list[Carta]
        """
        mazo_descarte = (self._db.query(Carta)
                         .filter_by(partida_id=id_partida, ubicacion="descarte")
                         .order_by(Carta.orden_descarte.desc()).all()
                        )
        
        return mazo_descarte

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
        from sqlalchemy import func
  
        jugador = JugadorService(self._db).obtener_jugador(id_jugador)
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
        
        ultimo_orden = self._db.query(func.max(Carta.orden_descarte)).filter(Carta.partida_id == jugador.partida_id).scalar() or 0
        for carta in cartas_descarte_id:
            carta_descarte = self._db.query(Carta).filter(Carta.id_carta == carta, Carta.jugador_id == id_jugador).first()
            carta_descarte.jugador_id = 0
            carta_descarte.ubicacion = "descarte"
            carta_descarte.bocaArriba = False
            carta_descarte.orden_descarte = ultimo_orden + 1
            
            self._db.commit()
            print(f'Se descarto la carta con id {carta_descarte.id} y nombre {carta_descarte.nombre}.')


    def obtener_cantidad_mazo(self, id_partida):
        partida = PartidaService(self._db).obtener_por_id(id_partida)
        return len(self.obtener_mazo_de_robo(partida.id))

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