from datetime import date

from pydantic import BaseModel
from game.jugadores.dtos import JugadorDTO

class JugadorData(BaseModel):
    """
    Schema que representa los datos entrantes de un jugador a crear
    """
    nombreJugador: str
    fechaNacimiento: date
    

    def to_dto(self) -> JugadorDTO:
        return JugadorDTO(
            nombreJugador=self.nombreJugador,
            fechaNacimiento=self.fechaNacimiento,
            
        )


class JugadorResponse(BaseModel):
    """
    Clase que representa la response al crear un jugador
    """
    id_jugador: int
