from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from game.partidas.models import Partida
from game.partidas.schemas import PartidaData, PartidaResponse, PartidaOut, PartidaListar
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
    if (partida_info.minJugadores > partida_info.maxJugadores):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El mínimo de jugadores no puede ser mayor al máximo."
        )
    elif (partida_info.maxJugadores > 6):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El máximo de jugadores por partida es 6."
        )
    elif (partida_info.maxJugadores < 2 or partida_info.minJugadores > 6 or partida_info.minJugadores < 2):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El mínimo de jugadores por partida es 2."
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
        return PartidaResponse(id_partida=partida_creada.id, id_jugador=jugador_creado.id, id_Anfitreon=jugador_creado.id)

#quiero hacer el endpoint obtener partida.
@partidas_router.get(path="/{id_partida}", status_code=status.HTTP_200_OK)
async def obtener_datos_partida(id_partida: int, db=Depends(get_db)) -> PartidaOut:
    """
    Obtiene los datos de una partida por su ID.
    
    Parameters
    ----------
    id_partida: int
        ID de la partida a obtener
    
    Returns
    -------
    PartidaOut
        Datos de la partida obtenida
    """
    
    partida_obtenida = PartidaService(db).obtener_por_id(id_partida)

    if partida_obtenida is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró la partida con ID {id_partida}"
        )
    else:
        return PartidaOut(
            nombre_partida=partida_obtenida.nombre,
            iniciada=partida_obtenida.iniciada,
            maxJugadores=partida_obtenida.maxJugadores
        )

@partidas_router.get(path="", status_code = status.HTTP_200_OK)
async def listar_partidas(db=Depends(get_db)) -> List[PartidaListar]:

    """
    Lista las partidas no iniciadas de la base de datos.
    
    Returns
    -------
    List[PartidaListar]
        Respuesta con la lista de las partidas.
    """

    partidas_listadas = PartidaService(db).listar()
    return [
        PartidaListar(
            id=p.id,
            nombre=p.nombre,
            iniciada=p.iniciada,
            maxJugadores=p.maxJugadores
        )
        for p in partidas_listadas
    ]


#endpoint iniciar partida
@partidas_router.put(path="", status_code=status.HTTP_200_OK)
async def iniciar_partida(id_partida: int, db=Depends(get_db)) -> None:
    """
    Inicia una partida si el jugador es el anfitrión y se cumplen las condiciones.
    
    Parameters
    ----------
    id_partida: int
        ID de la partida a iniciar
    id_jugador: int
        ID del jugador que intenta iniciar la partida
    
    Returns
    -------
    None
        No retorna nada, solo cambia el estado de la partida a iniciada
    """
    partida_a_iniciar = PartidaService(db).obtener_por_id(id_partida)

    if partida_a_iniciar is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró la partida con ID {id_partida}"
        )
    
    if partida_a_iniciar.iniciada:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La partida ya ha sido iniciada."
        )

    if (partida_a_iniciar.cantJugadores < partida_a_iniciar.minJugadores):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede iniciar la partida. No se ha alcanzado el mínimo de jugadores."
        )

    try:
        PartidaService(db).iniciar_partida(id_partida)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    return None


# endpoint post /partidas crear (devuelve id_partida) faltan unittest
# endpoint get /partidas listar (devuelve lista de partidas con nombre partida, cantJugadores, lista jugadores)
# endpoint get /partida/{id} info de la partida (devuelve nombre partida, etc)
# endpoint post /jugadores crear jugador (nombre. fecha nacimiento) devuelve id_jugador
# endpoint get /jugadores/{id} info del jugador (devuelve nombre, fecha nac, id_jugador)
# endpoint put /partidas/{id_partida}/{id_jugador}

