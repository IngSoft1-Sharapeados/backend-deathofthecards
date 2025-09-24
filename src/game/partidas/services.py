from typing import List, Optional

from game.partidas.dtos import PartidaDTO
from game.partidas.models import Partida
from game.jugadores.models import Jugador


class PartidaService:
    def __init__(self, db):
        self._db = db
        #self._JugadorService = JugadorService(db)
    
    def crear(self, partida_dto: PartidaDTO) -> Partida:
        """
        Crea una nueva partida en la base de datos.
        
        Parameters
        ----------
        partida_dto: PartidaDTO
            DTO con la info de la partida a crear
        
        Returns
        -------
        Partida
            La partida creada
        """
        nueva_partida = Partida(
            nombre=partida_dto.nombre,
            nombreAnfitrion="pepito",
            cantJugadores=0,
            iniciada=False,
            maxJugadores=partida_dto.maxJugadores,
        )
        self._db.add(nueva_partida)
        self._db.flush()
        self._db.commit()
        self._db.refresh(nueva_partida)
        return nueva_partida

    def obtener_por_id(self, id_partida: int) -> Partida:
        """
        Obtiene una partida por su ID.
        
        Parameters
        ----------
        id_partida: int
            ID de la partida a obtener
        
        Returns
        -------
        Partida
            La partida obtenida
        """
        partida = self._db.query(Partida).filter(Partida.id == id_partida).first()
        return partida
        