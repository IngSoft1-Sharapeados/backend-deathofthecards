from typing import List, Optional

from pydantic import BaseModel, Field
from game.partidas.dtos import PartidaDTO
from datetime import date
from game.jugadores.schemas import JugadorOut
from typing import Any

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

class RecogerCartasPayload(BaseModel):
    cartas_draft: List[int]

class AnotherVictimPayload(BaseModel):
    id_objetivo: int
    id_representacion_carta: int
    ids_cartas: list[int]

class OneMorePayload(BaseModel):
    """
    Payload para el evento 'And then there was one more...'
    - id_fuente: jugador desde el cual se roba el secreto (debe tenerlo revelado)
    - id_destino: jugador que recibirá el secreto (se agrega oculto)
    - id_unico_secreto: ID único del secreto a trasladar
    """
    id_fuente: int
    id_destino: int
    id_unico_secreto: int
    
class AccionGenericaPayload(BaseModel):
    """
    Un payload genérico que el frontend construye para CUALQUIER acción
    que pueda ser cancelada (Eventos, Sets, etc.).
    """
    
    tipo_accion: str
    """
    Un string único para que el frontend sepa qué endpoint original llamar.
    Ej: "evento_another_victim", "jugar_set_detective"
    """
    
    cartas_db_ids: List[int]
    """
    El frontend debe enviar la lista de IDs de BBDD
    (los 'Carta.id' únicos) de las cartas que se están jugando.
    - Para AnotherVictim (ID BBDD 245): [245]
    - Para un Set (IDs BBDD 101, 102, 110): [101, 102, 110]
    """
    
    nombre_accion: str
    """
    El nombre bonito de la acción para el broadcast.
    Ej: "Another Victim", "Set de Detectives"
    """
    
    payload_original: Any = None
    """
    El payload que el endpoint original necesitará si la acción se ejecuta.
    - Para AnotherVictim: { "id_objetivo": 2, ... }
    - Para JugarSet: { "set_cartas": [7, 7, 14] } (IDs de representación de carta)
    """
    id_carta_tipo_original: int = 0


class Mensaje(BaseModel):
    nombreJugador: str
    texto: str