from typing import List
from collections import defaultdict
from fastapi import Body
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi import WebSocket, WebSocketException, WebSocketDisconnect
from game.partidas.models import Partida
from game.partidas.schemas import PartidaData, PartidaResponse, PartidaOut, PartidaListar, IniciarPartidaData
from game.partidas.services import PartidaService
from game.jugadores.models import Jugador
from game.jugadores.schemas import JugadorData, JugadorResponse, JugadorOut
from game.jugadores.services import JugadorService
from game.cartas.services import CartaService
from game.modelos.db import get_db
from game.partidas.utils import listar_jugadores
import json
import traceback


partidas_router = APIRouter()


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
    
    def disconnect(self, websocket: WebSocket, id_partida: int, id_jugador: int):
        print(f"Jugador {id_jugador} se ha desconectado de la partida {id_partida}.")
        if id_partida in self.active_connections and websocket in self.active_connections[id_partida]:
            self.active_connections[id_partida].remove(websocket)
        if id_jugador in self.active_connections_personal:
            self.active_connections_personal.pop(id_jugador)

    async def broadcast(self, id_partida: int, message: str):
        print(f"Enviando mensaje a la partida {id_partida}: {message}")
        for connection in list(self.active_connections[id_partida]):
            try:
                await connection.send_text(message)
            except WebSocketDisconnect:
                self.active_connections[id_partida].remove(connection)
            except Exception as e:
                print(f"Error enviando mensaje: {e}")
                continue
    
    async def send_personal_message(self, id_jugador: int, message:str):
        print(f"Enviando mensaje personal al jugador {id_jugador}: {message}")
        await self.active_connections_personal[id_jugador].send_text(message)

manager = ConnectionManager()
    
def get_manager():
    return manager


# Endpoint crear partida
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
        print(f'conexion nueva partida. {manager.active_connections[partida_creada.id]}')
        return PartidaResponse(id_partida=partida_creada.id, id_jugador=jugador_creado.id, id_Anfitrion=jugador_creado.id)


# Endpoint Obtener datos de una partida dado el ID
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


# Endpoint listar partidas
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


# Endpoint unir jugador a partida dado el ID
@partidas_router.post(path="/{id_partida}", status_code=status.HTTP_200_OK)
async def unir_jugador_a_partida(id_partida: int, jugador_info: JugadorData, db=Depends(get_db), manager=Depends(get_manager)
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
        
            await manager.broadcast(id_partida, json.dumps({
                    "evento": "union-jugador", 
                    "id_jugador": jugador_creado.id, 
                    "nombre_jugador": jugador_creado.nombre
                }))
            
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


# Endpoint iniciar partida
@partidas_router.put(path="/{id_partida}", status_code=status.HTTP_200_OK)
async def iniciar_partida(id_partida: int, data: IniciarPartidaData, db=Depends(get_db)):
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
        print("partida iniciando")
        partida = PartidaService(db).iniciar(id_partida, data.id_jugador)
        mazo_partida = CartaService(db).crear_mazo_inicial(id_partida)
        CartaService(db).repartir_cartas_iniciales(mazo_partida, partida.jugadores)
        print("cartas repartidas")
        turnos = PartidaService(db).orden_turnos(id_partida, partida.jugadores)
        print(f"turnos generados: {turnos}")
        PartidaService(db).set_turno_actual(id_partida, turnos[0])
        print(f"turno actual seteado: {turnos[0]}")
        await manager.broadcast(id_partida, json.dumps({"evento": "iniciar-partida"}))
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
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(f'No se encontro la partida con el ID {id_partida}.')
        )
    except Exception as e:
        print("ERROR en iniciar_partida:")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado: {e}"
        )

# Endpoint obtener orden de turnos
@partidas_router.get(path="/{id_partida}/turnos", status_code=status.HTTP_200_OK)
async def obtener_orden_turnos(id_partida: int, db=Depends(get_db)) -> List[int]:
    """
    Obtiene el orden de turnos de los jugadores en una partida.
    
    Parameters
    ----------
    id_partida: int
        ID de la partida
    
    Returns
    -------
    List[int]
        Lista con el orden de turnos (IDs de jugadores)
    """
    try:
        partida = PartidaService(db).obtener_por_id(id_partida)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=("No existe la partida con el ID proporcionado.")
        )
    if not partida.ordenTurnos:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se ha generado el orden de turnos para la partida con ID {id_partida}."
        )
    orden = json.loads(partida.ordenTurnos)
    return orden

@partidas_router.websocket("/ws/{id_partida}/{id_jugador}")
async def websocket_endpoint(websocket: WebSocket, id_partida: int, id_jugador: int, db=Depends(get_db)):
    await manager.connect(websocket, id_partida, id_jugador)
    
    try:
        while True:
            data = await websocket.receive_text()
            print(f"Mensaje recibido del jugador {id_jugador} en la partida {id_partida}: {data}")
            pass

    except WebSocketDisconnect:
        partida_service = PartidaService(db)
        jugador_service = JugadorService(db)
        
        jugador = jugador_service.obtener_jugador(id_jugador) 
        partida = partida_service.obtener_por_id(id_partida)

        if partida and jugador and not partida.iniciada:
            partida.cantJugadores -= 1
            db.delete(jugador)
            db.commit()
            
            await manager.broadcast(id_partida, json.dumps({
                "evento": "desconexion-jugador",
                "id_jugador": id_jugador,
                "nombre_jugador": jugador.nombre
            }))

        manager.disconnect(websocket, id_partida, id_jugador)
    
@partidas_router.get(path="/{id_partida}/mano", status_code=status.HTTP_200_OK)
async def obtener_mano(id_partida: int, id_jugador: int, db=Depends(get_db)):
    """
    Obtiene la mano inicial de un jugador específico para una partida.
    """
    try:
        mano_jugador = CartaService(db).obtener_mano_jugador(id_jugador, id_partida)

        if not mano_jugador:
            return []

        cartas_a_enviar = [
            {"id": carta.id_carta, "nombre": carta.nombre}
            for carta in mano_jugador
        ]
        
        return cartas_a_enviar

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se pudo obtener la mano para el jugador {id_jugador} en la partida {id_partida}. Error: {e}"
        )
        




# DONE endpoint descartar carta/s . front manda lista de IDs para ubicar en el diccionario, sacar relacion.devolver 200 OK

# endpoint reponer cartas (id_partida, id_jugador) metodo en service obtener_cartas_restantes
# if cartas_restantes > cartas_a_reponer then devovler lista de cartas para reponer
# else broadcast TERIMNAR PARTIDA


# DONE endpoint get remaining cards devuelve INT el numero de cartas restantes del mazo

# DONE endpoint obtener_turno_actual (partida_id) return INT ID del jugador que tiene el turno actual

# endpoint terminar turno ???????????????????????????????????????



@partidas_router.put(path='/descarte/{id_partida}')
def descarte_cartas(id_partida, id_jugador: int, cartas_descarte: list[int]= Body(...), db=Depends(get_db), manager=Depends(get_manager)):
    try:
        CartaService(db).descartar_cartas(id_jugador, cartas_descarte)
        # Emitimos actualización del mazo (por si alguna lógica futura mueve entre mazos)
        cantidad_restante = CartaService(db).obtener_cantidad_mazo(id_partida)
        evento = {
            "evento": "actualizacion-mazo",
            "cantidad-restante-mazo": cantidad_restante,
        }
        # broadcast espera texto
        import json as _json
        # Enviamos como texto JSON a todos en la partida
        import asyncio
        async def _broadcast():
            await manager.broadcast(id_partida, _json.dumps(evento))
        try:
            asyncio.get_event_loop().create_task(_broadcast())
        except RuntimeError:
            # En contexto sin loop (por ejemplo, pruebas), ignoramos
            pass
        return {"detail": "Descarte exitoso"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@partidas_router.get(path='/{id_partida}/mazo')
async def obtener_cartas_restantes(id_partida, db=Depends(get_db), manager=Depends(get_manager)):
    cantidad_restante = CartaService(db).obtener_cantidad_mazo(id_partida)
    evento = {
        "evento":"actualizacion-mazo",
        "cantidad-restante-mazo": cantidad_restante,
    }
    # Enviar como texto JSON por WebSocket
    await manager.broadcast(id_partida, json.dumps(evento))
    return cantidad_restante


@partidas_router.get(path='/{id_partida}/turno')
async def obtener_turno_actual(id_partida, db=Depends(get_db), manager=Depends(get_manager)):
    turno = PartidaService(db).obtener_turno_actual(id_partida)
    evento = {
        "evento": "turno-actual",
        "turno-actual": turno
    }
    await manager.broadcast(id_partida, json.dumps(evento))
    return turno

