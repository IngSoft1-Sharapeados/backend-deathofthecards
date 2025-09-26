from typing import List
from collections import defaultdict

from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi import WebSocket, WebSocketException, WebSocketDisconnect
from game.partidas.models import Partida
from game.partidas.schemas import PartidaData, PartidaResponse, PartidaOut, PartidaListar, IniciarPartidaData
from game.partidas.services import PartidaService
from game.jugadores.models import Jugador
from game.jugadores.schemas import JugadorData, JugadorResponse, JugadorOut
from game.jugadores.services import JugadorService
from game.modelos.db import get_db
from game.partidas.utils import listar_jugadores
import json



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
            PartidaService(db).asignar_anfitrion(partida_creada, jugador_creado.id)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        manager.active_connections.update({partida_creada.id: []})
        return PartidaResponse(id_partida=partida_creada.id, id_jugador=jugador_creado.id, id_Anfitrion=jugador_creado.id)

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
    try:
        partida_obtenida = PartidaService(db).obtener_por_id(id_partida)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=("No existe la partida con el ID proporcionado.")
        )
    if partida_obtenida is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró la partida con ID {id_partida}"
        )
    else:
        listaJ = listar_jugadores(partida_obtenida)

        return PartidaOut(
            nombre_partida=partida_obtenida.nombre,
            iniciada=partida_obtenida.iniciada,
            maxJugadores=partida_obtenida.maxJugadores,
            minJugadores=partida_obtenida.minJugadores,
            listaJugadores=listaJ,
            cantidad_jugadores=partida_obtenida.cantJugadores,
            id_anfitrion = partida_obtenida.anfitrionId,
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
            maxJugadores=p.maxJugadores,
            minJugadores=p.minJugadores,
            cantJugadores=p.cantJugadores
        )
        for p in partidas_listadas
    ]

# endpoint post unir jugador a partida
@partidas_router.post(path="/{id_partida}", status_code=status.HTTP_200_OK)
async def unir_jugador_a_partida(id_partida: int, jugador_info: JugadorData, db=Depends(get_db)
) -> JugadorOut:

    """
    Une un jugador a una partida existente.
    
    Parameters
    ----------
    id_partida: int
        ID de la partida a la que se unirá el jugador
    
    Returns
    -------
    PartidaOut
        Datos de la partida actualizada con el jugador creado
    """
    try:
        partida = PartidaService(db).obtener_por_id(id_partida)
        print(f'cantidad de jugadores en la partida con el ID: {id_partida} = {partida.cantJugadores}')
    
        if(partida.cantJugadores == partida.maxJugadores):
            print("ac'a entro al if que esta llena la partida")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La partida ya tiene el máximo de jugadores."
            )
        try:
            jugador_creado = JugadorService(db).crear_unir(id_partida, jugador_dto=jugador_info.to_dto())
            PartidaService(db).unir_jugador(id_partida, jugador_creado)
        
            await manager.broadcast(id_partida, f"Jugador {jugador_creado.id} se ha conectado.")
            return JugadorOut(
                id_jugador = jugador_creado.id,
            nombre_jugador = jugador_creado.nombre,
            fecha_nacimiento = jugador_creado.fecha_nacimiento
            )
    
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(f'No se encontro la partida con el ID {id_partida}.')
        )
# # endpoint post unir jugador a partida
# @partidas_router.post(path="/{id_partida}", status_code=status.HTTP_200_OK)
# async def unir_jugador_a_partida(id_partida: int, jugador_info: JugadorData, db=Depends(get_db)) -> JugadorOut                                                                                                                              :

#     """
#     Une un jugador a una partida existente.
    
#     Parameters
#     ----------
#     id_partida: int
#         ID de la partida a la que se unirá el jugador
    
#     Returns
#     -------
#     PartidaOut
#         Datos de la partida actualizada con el jugador creado
#     """
    
#     try:
#         jugador_creado = JugadorService(db).crear(id_partida, jugador_dto=jugador_info.to_dto())
#         PartidaService(db).unir_jugador(id_partida, id_jugador=jugador_creado.id)
#     except ValueError as e:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail=str(e)
#         )
    
#     return JugadorOut(
#         id_jugador=jugador_creado.id,
#         nombre_jugador=jugador_creado.nombre,
#         fecha_nacimiento=jugador_creado.fecha_nacimiento
#     )




#endpoint iniciar partida
@partidas_router.put(path="/{id_partida}", status_code=status.HTTP_200_OK)
async def iniciar_partida(id_partida: int, data: IniciarPartidaData, db=Depends(get_db)) -> None:
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
    Status 200 OK si la partida se inicia correctamente, de lo contrario lanza una excepción HTTP.
    """
    try:
        partida = PartidaService(db).iniciar(id_partida, data.id_jugador)
        await manager.broadcast(id_partida, f"PARITDA INICIADA.")
        return {"detail": "Partida iniciada correctamente."}
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )




class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[int, list[WebSocket]] = defaultdict(list)
        self.active_connections_personal: dict = dict()

    async def connect(self, websocket: WebSocket, id_partida: int, id_jugador: int):
        await websocket.accept()
        print(f"Jugador {id_jugador} se ha conectado a la partida {id_partida}.")
        if websocket not in self.active_connections[id_partida]:
            self.active_connections[id_partida].append(websocket)
        self.active_connections_personal[id_jugador] = websocket
        jugador = PartidaService(get_db()).ultimo_jugador(id_partida)
        if jugador is not None:
            evento = {
                "evento": "union-jugador",
                "nombre_jugador" : jugador.nombre,
                #probablemente tenga que mandar todo el jugador???
            }
            await self.broadcast(id_partida, json.dumps(evento))
    
    def disconnect(self, websocket, id_partida: int,id_jugador: int):
        print(f"Jugador {id_jugador} se ha desconectado de la partida {id_partida}.")
        if id_partida in self.active_connections:
            if websocket in self.active_connections[id_partida]:
                self.active_connections[id_partida].remove(websocket)
            
        self.active_connections_personal.pop(id_jugador)

    async def send_personal_message(self, message: str, id_jugador: int):
        await self.active_connections_personal[id_jugador].send_text(message)

    async def broadcast(self, id_partida: int,message: str):
        print(f"Enviando mensaje a la partida {id_partida}: {message}")
        for connection in self.active_connections[id_partida]:
            try:
                await connection.send_text(message)
            except Exception:
                continue

manager = ConnectionManager()


#websocket endpoint
@partidas_router.websocket("/ws/{id_partida}/{id_jugador}")
async def websocket_endpoint(websocket: WebSocket, id_partida: int, id_jugador: int):
    await manager.connect(websocket, id_partida, id_jugador)
    db = get_db()
    partida_service = PartidaService(db)
    jugador_service = JugadorService(db)
    try:
        while True:
            data = await websocket.receive_text()
            print(f"Mensaje recibido del jugador {id_jugador}: {data}")
            pass

    except WebSocketDisconnect:
        partida = partida_service.obtener_por_id(id_partida)
        jugador = jugador_service.obtener_jugador(id_jugador)

        if partida and jugador and not partida.iniciada:
            #eliminamos al jugador de la partida
            partida.cantJugadores -= 1
            #eliminamos al jugador de la base de datos
            db.delete(jugador)
            db.commit()
            db.refresh(partida)

        manager.disconnect(websocket, id_partida, id_jugador)
        await manager.broadcast(id_partida, f"Jugador {id_jugador} se ha desconectado.")

