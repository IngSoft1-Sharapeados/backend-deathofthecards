from typing import List, Optional

from pydantic import BaseModel
from game.partidas.dtos import PartidaDTO

class PartidaData(BaseModel):
    """
    Schema que representa los datos entrantes de una partida a crear
    """
    nombre: str
    maxJugadores: int

    def to_dto(self) -> PartidaDTO:
        return PartidaDTO(
            nombre=self.nombre,
            maxJugadores=self.maxJugadores
        )


class PartidaResponse(BaseModel):
    """
    Clase que representa la response al crear partida
    """
    id_partida: int

class PartidaOut(BaseModel):
    """
    Clase que representa los datos salientes de una partida
    """
    nombre_partida: str
    iniciada: bool
    maxJugadores: int

class PartidaListar(BaseModel):
    """
    Clase que representa la response al listar las partidas
    """
    id: int
    nombre: str
    iniciada: bool
    cantJugadores: int
    minJugadores: int
    maxJugadores: int


