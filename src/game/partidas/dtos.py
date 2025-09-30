""""Data transfer objects para partida"""

from dataclasses import dataclass
from dataclasses import field as dataclass_field

from typing import List

@dataclass
class PartidaDTO:
    nombrePartida: str
    maxJugadores: int
    minJugadores: int
    nombreJugador: str
    fechaNacimiento: str
    
    #jugadores: List["Jugador"] = dataclass_field(default_factory=list)