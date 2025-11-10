from game.partidas.dtos import PartidaDTO
from game.jugadores.models import Jugador
from game.cartas.models import Carta
from game.partidas.models import Partida
#from game.cartas.models import Carta
from game.jugadores.dtos import JugadorDTO

from typing import List, Optional
#from game.partidas.services import PartidaService

class JugadorService:
    def __init__(self,db):
        self._db = db

    def crear(self, id: int, jugador_dto: PartidaDTO) -> Jugador:
        """
        Crea un nuevo jugador en la base de datos.
        
        Parameters
        ----------
        jugador_dto: JugadorDTO
            DTO con la info del jugador a crear
        
        Returns
        -------
        Jugador
            El jugador creado
        """
        nuevo_jugador = Jugador(
            nombre = jugador_dto.nombreJugador,
            fecha_nacimiento = jugador_dto.fechaNacimiento,
            partida_id = id,
        )
        self._db.add(nuevo_jugador)
        self._db.flush()
        self._db.commit()
        self._db.refresh(nuevo_jugador)
        return nuevo_jugador
    
    
    def crear_unir(self, id_partida: int, jugador_dto: JugadorDTO) -> Jugador:
        """
        Crea un nuevo jugador y lo une a una partida existente.
        
        Parameters
        ----------
        id_partida: int
            ID de la partida a la que se unirá el jugador
        jugador_dto: JugadorDTO
            DTO con la info del jugador a crear
        
        Returns
        -------
        Jugador
            El jugador creado y unido a la partida
        """

        nuevo_jugador = Jugador(
            nombre = jugador_dto.nombre,
            fecha_nacimiento = jugador_dto.fecha_nacimiento,
            partida_id = id_partida,
        )
        self._db.add(nuevo_jugador)
        self._db.flush()
        self._db.commit()
        self._db.refresh(nuevo_jugador)
        return nuevo_jugador
    

    def obtener_jugador(self, id_jugador: int) -> Optional[Jugador]:
        """
        Obtiene un jugador por su ID .
        
        Parameters
        ----------
        id_jugador: int
            ID del jugador
        
        Returns
        -------
        Optional[Jugador]
            El jugador si se encuentra, o None si no existe.
        """
        jugador = self._db.query(Jugador).filter(Jugador.id == id_jugador).first()
        return jugador


    def eliminar_jugador(self, jugador: Jugador):
        """
        Método para eliminar un jugador de la base de datos.

        Parameters
        ----------
            jugador: Jugador
                Objeto Jugador de la base de datos 
        
        """
        try:
            self._db.delete(jugador)
            self._db.commit()
        except Exception as e:
            self._db.rollback()
            raise ValueError(f"Error al eliminar el jugador: {str(e)}")
        
    def obtener_jugador_id_carta(self, partida: Partida, carta: Carta) -> int:
        jugador = self._db.query(Jugador).filter(Jugador.partida_id == partida.id,
                                                  Jugador.id == carta.jugador_id).first()
        return jugador.id