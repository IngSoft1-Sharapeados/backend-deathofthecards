
from game.cartas.constants import cartasDict
from game.cartas.models import Carta
from game.jugadores.models import Jugador
from game.partidas.models import Partida
import random


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
                    nombre=carta["nombre"],
                    tipo=carta["tipo"],
                    bocaArriba=False,
                    ubicacion="mazo",
                    partida_id=id_partida
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
                if carta.nombre.lower() == "not so fast" and carta.jugador_id is None:
                    carta.jugador_id = jugador.id
                    carta.ubicacion = "mano"
                    self._db.refresh(carta)
                    break  # pasamos al siguiente jugador

        # Luego, repartir hasta 6 cartas por jugador
        for jugador in jugadores_en_partida:
            while len([c for c in jugador.cartas if c.ubicacion == "mano"]) <= 6:
                for carta in mazo:
                    if carta.jugador_id is None:
                        carta.jugador_id = jugador.id
                        carta.ubicacion = "mano"
                        self._db.refresh(carta)
                        break
        self._db.commit()
                    
    def mazo_de_robo(self, id_partida: int) -> list[Carta]:
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

    def descarte(self, id_partida: int, jugador:Jugador, carta: Carta):
        """
        Efecto sobre una carta a la hora de descartarla.
        
        Parameters
        ----------
        id_partida: int
            ID de la partida para la cual se obtiene el mazo de robo.    
        """
        if jugador.en_turno == False:
            raise Exception("No es el turno de este jugador.")
        else:

            carta.jugador_id = None
            self._db.commit()
            self._db.refresh(carta)


