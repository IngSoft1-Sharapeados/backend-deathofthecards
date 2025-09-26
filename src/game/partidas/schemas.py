from typing import List, Optional

from pydantic import BaseModel, Field
from game.partidas.dtos import PartidaDTO
from datetime import date
from game.jugadores.schemas import JugadorOut

class PartidaData(BaseModel):
    """
    Schema que representa los datos entrantes de una partida a crear
    """
    nombrePartida: str = Field(..., alias="nombre-partida")
    maxJugadores: int = Field(..., alias="max-jugadores")
    minJugadores: int = Field(..., alias="min-jugadores")
    nombreJugador: str = Field(..., alias="nombre-jugador")
    fechaNacimiento: date = Field(..., alias="dia-nacimiento")

    def to_dto(self) -> PartidaDTO:
        return PartidaDTO(
            nombrePartida=self.nombrePartida,
            maxJugadores=self.maxJugadores,
            minJugadores=self.minJugadores,
            nombreJugador=self.nombreJugador,
            fechaNacimiento=self.fechaNacimiento,
        )


class PartidaResponse(BaseModel):
    """
    Clase que representa la response al crear partida
    """
    id_partida: int
    id_jugador: int
    id_Anfitrion: int

class PartidaOut(BaseModel):
    """
    Clase que representa los datos salientes de una partida
    """
    nombre_partida: str
    iniciada: bool
    maxJugadores: int
    minJugadores: int
    listaJugadores: List[JugadorOut]
    cantidad_jugadores: int
    id_anfitrion: int

class IniciarPartidaData(BaseModel):
    """
    Schema para los datos de la petición de iniciar partida
    """
    id_jugador: int

class PartidaListar(BaseModel):
    """
    Clase que representa la response al listar las partidas
    """
    id: int
    nombre: str
    iniciada: bool
    maxJugadores: int
    minJugadores: int
    cantJugadores: int


