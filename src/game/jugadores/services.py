from game.partidas.dtos import PartidaDTO
from game.jugadores.models import Jugador
from game.cartas.models import Carta

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
    