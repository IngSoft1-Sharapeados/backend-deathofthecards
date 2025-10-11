from typing import List
from collections import defaultdict
from fastapi import Body
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi import WebSocket, WebSocketException, WebSocketDisconnect
from game.partidas.models import Partida
from game.partidas.schemas import PartidaData, PartidaResponse, PartidaOut, PartidaListar, IniciarPartidaData, RecogerCartasPayload
#from game.partidas.services import PartidaService
from game.jugadores.models import Jugador
from game.jugadores.schemas import JugadorData, JugadorResponse, JugadorOut
#from game.jugadores.services import JugadorService
#from game.cartas.services import CartaService
from game.modelos.db import get_db
from game.partidas.utils import *
import json
import traceback
#from game.partidas.utils import *


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
@partidas_router.post(path="", status_code=status.HTTP_201_CREATED)
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
    
    response = crearPartida(partida_info, db)
    manager.active_connections.update({response.id_partida: []})
    return response


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
        Datos de la partida actualizada con el jugador unido
    """
    try:
        jugador_unido = unir_a_partida(id_partida, jugador_info, db)
        await manager.broadcast(id_partida, json.dumps({
                    "evento": "union-jugador", 
                    "id_jugador": jugador_unido.id_jugador, 
                    "nombre_jugador": jugador_unido.nombre_jugador
                }))
        return jugador_unido

    except HTTPException as e:
        raise e
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# Endpoint iniciar partida
@partidas_router.put(path="/{id_partida}")
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
        iniciarPartida(id_partida, data, db)
        await manager.broadcast(id_partida, json.dumps({"evento": "iniciar-partida"}))
        return {"detail": "Partida iniciada correctamente."}
    
    except Exception as e:  
        raise e


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


@partidas_router.put(path='/{id_partida}/descarte')
async def descarte_cartas(id_partida: int, id_jugador: int, cartas_descarte: list[int]= Body(...), db=Depends(get_db), manager=Depends(get_manager)):
    try:
        partida = PartidaService(db).obtener_por_id(id_partida)
        if partida is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="No se encontró la partida"
                                )
        if partida.turno_id != id_jugador:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="No es tu turno"
                                )
        CartaService(db).descartar_cartas(id_jugador, cartas_descarte)
        # Emitimos actualización del mazo (por si alguna lógica futura mueve entre mazos)
        cantidad_restante = CartaService(db).obtener_cantidad_mazo(id_partida)
        evento = {
            "evento": "actualizacion-mazo",
            "cantidad-restante-mazo": cantidad_restante,
        }
        evento2= {
            "evento": "carta-descartada", 
            "payload": {
                        "discardted":
                        cartas_descarte
                    } 
        }
        
        await manager.broadcast(id_partida, json.dumps(evento))
        await manager.broadcast(id_partida, json.dumps(evento2))

        return {"detail": "Descarte exitoso"}
    
    except HTTPException:
        raise
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
    if cantidad_restante == 0:
        # Broadcast fin de partida (payload mínimo)
        fin_payload = {
            "evento": "fin-partida",
            "payload": {"ganadores": [], "asesinoGano": False}
        }
        await manager.broadcast(id_partida, json.dumps(fin_payload))
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


# Endpoint robar/reponer cartas
@partidas_router.post(path='/{id_partida}/robar', status_code=status.HTTP_200_OK)
async def robar_cartas(id_partida: int, id_jugador: int, cantidad: int = 1, db=Depends(get_db), manager=Depends(get_manager)):
    try:
        # Validar turno actual
        turno_actual = PartidaService(db).obtener_turno_actual(id_partida)
        if turno_actual != id_jugador:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No es tu turno")

        # Calcular cuántas cartas faltan para llegar a 6
        mano = CartaService(db).obtener_mano_jugador(id_jugador, id_partida)
        faltantes = max(0, 6 - len(mano))
        # Capear por faltantes y por cartas disponibles en el mazo
        disponibles = CartaService(db).obtener_cantidad_mazo(id_partida)
        a_robar = min(cantidad, faltantes, disponibles) if faltantes > 0 else 0
        if a_robar == 0:
            # Nada que robar, simplemente retornar
            return []

        cartas = CartaService(db).robar_cartas(id_partida=id_partida, id_jugador=id_jugador, cantidad=a_robar)

        # Notificar actualización del mazo
        cantidad_restante = CartaService(db).obtener_cantidad_mazo(id_partida)
        await manager.broadcast(id_partida, json.dumps({
            "evento": "actualizacion-mazo",
            "cantidad-restante-mazo": cantidad_restante,
        }))
        if cantidad_restante == 0:
            fin_payload = {
                "evento": "fin-partida",
                "payload": {"ganadores": [], "asesinoGano": False}
            }
            await manager.broadcast(id_partida, json.dumps(fin_payload))

        # Si la mano quedó en 6 tras robar, avanzar turno
        mano_final = CartaService(db).obtener_mano_jugador(id_jugador, id_partida)
        if len(mano_final) >= 6 or cantidad_restante == 0:
            nuevo_turno = PartidaService(db).avanzar_turno(id_partida)
            await manager.broadcast(id_partida, json.dumps({
                "evento": "turno-actual",
                "turno-actual": nuevo_turno,
            }))
            CartaService(db).actualizar_mazo_draft(id_partida)

        # Si el mazo queda en 0, emitir fin de partida
        if cantidad_restante == 0:
            fin_payload = {
                "evento": "fin-partida",
                "payload": {"ganadores": [], "asesinoGano": False}
            }
            await manager.broadcast(id_partida, json.dumps(fin_payload))

        return cartas
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@partidas_router.get(path= '/{id_partida}/draft')
async def mazo_draft(id_partida: int, db=Depends(get_db)):
    """ 
    Se muestra el mazo de draft
    
    Returns
    -------
    Devuelve una lista de cartas que componen el mazo de draft.
    """
    try:
        mazo_draft = mostrar_mazo_draft(id_partida, db)
        return mazo_draft
    
    except Exception as e:
        raise e

@partidas_router.put(path="/{id_partida}/draft")
async def tomar_cartas_draft(id_partida: int,id_jugador: int,
                        carta_tomada: int = Body(...),
                        db=Depends(get_db),
                        manager=Depends(get_manager)):
    """
    El jugador toma 1 carta del draft.
    """
    try:
        robar_carta_draft(id_partida, id_jugador, carta_tomada, db)
        mano = CartaService(db).obtener_mano_jugador(id_jugador, id_partida)
        faltan = max(0, 6 - len(mano))
        await robar_cartas(id_partida, id_jugador, faltan, db, manager)
        evento = {
            "evento": "actualizacion-draft",
            "id_jugador": id_jugador,
            "carta_tomada": carta_tomada,
        }

        await manager.broadcast(id_partida, json.dumps(evento))
        return {"detail": "Carta tomada correctamente."}

    except Exception as e:
        raise e

@partidas_router.get(path="/{id_partida}/secretos", status_code=status.HTTP_200_OK)
async def obtener_secretos(id_partida: int, id_jugador: int, db=Depends(get_db)):
    """
    Obtiene los secretos de un jugador específico para una partida.
    """
    try:
        secretos_jugador = CartaService(db).obtener_secretos_jugador(id_jugador, id_partida)

        if not secretos_jugador:
            return []

        cartas_a_enviar = [
            {"id": carta.id_carta, "nombre": carta.nombre}
            for carta in secretos_jugador
        ]
        
        return cartas_a_enviar

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se pudo obtener los secretos para el jugador {id_jugador} en la partida {id_partida}. Error: {e}"
        )


@partidas_router.get(path="/{id_partida}/roles", status_code=status.HTTP_200_OK)
async def obtener_asesino_complice(id_partida: int, db=Depends(get_db)):
    """
    Obtiene los IDs del asesino y el cómplice de una partida específica.
    """
    try:
        asesino_complice = CartaService(db).obtener_asesino_complice(id_partida)

        if not asesino_complice:
            return []

        return asesino_complice
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Hubo un error al obtener los IDs del asesino y el cómplice"
        )
    
@partidas_router.get(path= '/{id_partida}/descarte')
async def mazo_descarte(id_partida: int, id_jugador: int, cantidad: int = 1, db=Depends(get_db)):
    """ 
    Se muestra el mazo de descarte
    
    devuelve lista de cartas que componen el mazo de desarte.
    """
    try:
        cartas_descarte = mostrar_cartas_descarte(id_partida, cantidad, db)
        carta_top = cartas_descarte[0] if cartas_descarte else None
        
        if cantidad == 1:
            await manager.broadcast(id_partida, json.dumps({
                "evento": "mazo-descarte-top",
                "carta": carta_top
            }))
        elif cantidad == 5:
            await manager.send_personal_message(id_jugador, json.dumps({
                "evento": "mazo-descarte-top5",
                "carta": cartas_descarte
            }))
        return cartas_descarte
    
    except Exception as e:
        raise e
        


@partidas_router.put(
    "/{id_partida}/jugador/{id_jugador}/recoger",
    status_code=status.HTTP_200_OK
)
async def accion_recoger_cartas(
    id_partida: int,
    id_jugador: int,
    payload: RecogerCartasPayload,
    db= Depends(get_db),
    manager: Depends = Depends(get_manager)
):
    try:
        # Llamar al servicio para manejar la acción de recoger cartas
        resultado = PartidaService(db).manejar_accion_recoger(
            id_partida, id_jugador, payload.cartas_draft
        )

        # Extraer datos del resultado
        nuevas_cartas_para_jugador = resultado["nuevas_cartas"]
        nuevo_turno_id = resultado["nuevo_turno_id"]
        nuevo_draft = resultado["nuevo_draft"]
        cantidad_final_mazo = resultado["cantidad_final_mazo"]

        # Emitir eventos por WebSocket
        await manager.broadcast(id_partida, json.dumps({
            "evento": "nuevo-draft",
            "mazo-draft": [{"id": c.id_carta, "nombre": c.nombre} for c in nuevo_draft]
        }))
        await manager.broadcast(id_partida, json.dumps({
            "evento": "actualizacion-mazo",
            "cantidad-restante-mazo": cantidad_final_mazo
        }))
        await manager.broadcast(id_partida, json.dumps({
            "evento": "turno-actual",
            "turno-actual": nuevo_turno_id
        }))
        if cantidad_final_mazo == 0:
            await manager.broadcast(id_partida, json.dumps({
                "evento": "fin-partida", "ganadores": [], "asesino_gano": False
            }))

        return nuevas_cartas_para_jugador
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in accion_recoger_cartas endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))