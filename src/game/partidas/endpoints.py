from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from game.partidas.models import Partida
from game.partidas.schemas import PartidaData, PartidaResponse
from game.partidas.services import PartidaService
from game.jugadores.models import Jugador
from game.jugadores.schemas import JugadorData, JugadorResponse
from game.jugadores.services import JugadorService
from game.modelos.db import get_db


partidas_router = APIRouter()

@partidas_router.post(path="", status_code= status.HTTP_201_CREATED)
async def crear_partida(partida_info: PartidaData, db=Depends(get_db)
) -> PartidaResponse:

    """
    Crea una nueva partida en la base de datos.
    
    Parameters
    ----------
    partida_info: PartidaData
        Info de la partida a crear
    
    Returns
    -------
    PartidaResponse
        Respuesta con los datos de la partida creada
    """
    if (partida_info.maxJugadores > 6):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El máximo de jugadores por partida es 6."
        )
    elif (partida_info.maxJugadores < 2 or partida_info.minJugadores >= 2):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El mínimo de jugadores por partida es 2."
        )
    elif (partida_info.minJugadores > partida_info.maxJugadores):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El mínimo de jugadores no puede ser mayor al máximo."
        )
    else:
        try:
            partida_creada = PartidaService(db).crear(partida_dto=partida_info.to_dto())
            jugador_creado = JugadorService(db).crear(partida_creada.id, jugador_dto=partida_info.to_dto())
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        return PartidaResponse(id_partida=partida_creada.id, id_jugador=jugador_creado.id)


# endpoint post /partidas crear (devuelve id_partida) faltan unittest
# endpoint get /partidas listar (devuelve lista de partidas con nombre partida, cantJugadores, lista jugadores)
# endpoint get /partida/{id} info de la partida (devuelve nombre partida, etc)
# endpoint post /jugadores crear jugador (nombre. fecha nacimiento) devuelve id_jugador
# endpoint get /jugadores/{id} info del jugador (devuelve nombre, fecha nac, id_jugador)
# endpoint put /partidas/{id_partida}/{id_jugador}

