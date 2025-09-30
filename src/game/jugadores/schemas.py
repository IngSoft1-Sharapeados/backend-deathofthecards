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
            nombre=self.nombreJugador,
            fecha_nacimiento=self.fechaNacimiento,
            
        )

class JugadorOut(BaseModel):
    """
    Clase que representa los datos salientes de un jugador
    """
    id_jugador: int
    nombre_jugador: str
    fecha_nacimiento: date

class JugadorResponse(BaseModel):
    """
    Clase que representa la response al crear un jugador
    """
    id_jugador: int
