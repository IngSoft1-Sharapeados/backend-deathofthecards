from typing import List
import logging
from collections import defaultdict
from fastapi import Body
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi import WebSocket, WebSocketException, WebSocketDisconnect
from game.partidas.models import Partida
from game.partidas.schemas import PartidaData, AccionGenericaPayload, PartidaResponse, PartidaOut, PartidaListar, IniciarPartidaData, RecogerCartasPayload, AnotherVictimPayload, OneMorePayload
#from game.partidas.services import PartidaService
from game.jugadores.models import Jugador
from game.cartas.models import Carta
from game.jugadores.schemas import JugadorData, JugadorResponse, JugadorOut
#from game.jugadores.services import JugadorService
#from game.cartas.services import CartaService
from game.modelos.db import get_db
from game.partidas.utils import *
import game.partidas.utils as partidas_utils
from game.cartas.utils import jugar_set_detective
from game.jugadores.services import JugadorService

import json
import traceback
#from game.partidas.utils import *
import logging
from time import sleep
from fastapi import Request

import asyncio


partidas_router = APIRouter()
logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[int, list[WebSocket]] = defaultdict(list)
        self.active_connections_personal: dict[int, list[WebSocket]] = defaultdict(list)

    async def connect(self, websocket: WebSocket, id_partida: int, id_jugador: int):
        await websocket.accept()
        logger.info("WS connect: jugador=%s partida=%s", id_jugador, id_partida)
        
        if websocket not in self.active_connections[id_partida]:
            self.active_connections[id_partida].append(websocket)
        
        if websocket not in self.active_connections_personal[id_jugador]:
            self.active_connections_personal[id_jugador].append(websocket)
    
    def disconnect(self, websocket: WebSocket, id_partida: int, id_jugador: int):
        logger.info("WS disconnect: jugador=%s partida=%s", id_jugador, id_partida)
        if id_partida in self.active_connections and websocket in self.active_connections[id_partida]:
            self.active_connections[id_partida].remove(websocket)
        if id_jugador in self.active_connections_personal:
            if websocket in self.active_connections_personal[id_jugador]:
                self.active_connections_personal[id_jugador].remove(websocket)
                
        if not self.active_connections_personal[id_jugador]:
            del self.active_connections_personal[id_jugador]

    async def broadcast(self, id_partida: int, message: str):
        logger.debug("WS broadcast partida=%s payload=%s", id_partida, message)
        for connection in list(self.active_connections[id_partida]):
            try:
                await connection.send_text(message)
            except WebSocketDisconnect:
                self.active_connections[id_partida].remove(connection)
            except Exception as e:
                logger.exception("WS broadcast error: %s", e)
                continue
    
    async def send_personal_message(self, id_jugador: int, message: str):
        websockets = self.active_connections_personal.get(id_jugador, [])
        for websocket in websockets:
            try:
                logger.debug("WS personal jugador=%s payload=%s", id_jugador, message)
                await websocket.send_text(message)
            except Exception as e:
                logger.warning("Error enviando WS a jugador %s: %s", id_jugador, e)
            
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

        logger.info(
            "DESCARTE: partida=%s jugador=%s cantidad=%s ids=%s",
            id_partida, id_jugador, len(cartas_descarte), cartas_descarte,
        )

        partida = PartidaService(db).obtener_por_id(id_partida)
        if partida is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="No se encontró la partida"
                                )
        if partida.turno_id != id_jugador:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="No es tu turno"
                                )
        desgracia_social = PartidaService(db).desgracia_social(id_partida, id_jugador)
        if desgracia_social and (len(cartas_descarte) != 1):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                    detail="El jugador esta en desgracia social, solo puede descartar una carta."
                    )

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
        logger.exception("DESCARTE ERROR: partida=%s jugador=%s error=%s", id_partida, id_jugador, e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@partidas_router.get(path='/{id_partida}/mazo')
async def obtener_cartas_restantes(id_partida, db=Depends(get_db), manager=Depends(get_manager)):
    cantidad_restante = CartaService(db).obtener_cantidad_mazo(id_partida)
    # evento = {
    #     "evento":"actualizacion-mazo",
    #     "cantidad-restante-mazo": cantidad_restante,
    # }
    # # Enviar como texto JSON por WebSocket
    # await manager.broadcast(id_partida, json.dumps(evento))
    # if cantidad_restante == 0:
    #     # Broadcast fin de partida (payload mínimo)
    #     fin_payload = {
    #         "evento": "fin-partida",
    #         "payload": {"ganadores": [], "asesinoGano": False}
    #     }
    #     await manager.broadcast(id_partida, json.dumps(fin_payload))
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
        logger.info(
            "ROBAR: partida=%s jugador=%s solicitadas=%s faltantes=%s disponibles=%s a_robar=%s",
            id_partida, id_jugador, cantidad, faltantes, disponibles, a_robar,
        )
        if a_robar == 0:
            # Nada que robar, simplemente retornar
            return []

        cartas = CartaService(db).robar_cartas(id_partida=id_partida, id_jugador=id_jugador, cantidad=a_robar)
        logger.info(
            "ROBAR OK: partida=%s jugador=%s robadas=%s detalle=%s",
            id_partida, id_jugador, len(cartas), cartas,
        )
        
        # Notificar actualización del mazo
        cantidad_restante = CartaService(db).obtener_cantidad_mazo(id_partida)
        await manager.broadcast(id_partida, json.dumps({
            "evento": "actualizacion-mazo",
            "cantidad-restante-mazo": cantidad_restante,
        }))
        # Si el mazo queda en 0, emitir fin de partida
        if cantidad_restante == 0:
            fin_payload = {
                "evento": "fin-partida",
                "payload": {"ganadores": [], "asesinoGano": True}
            }
            await manager.broadcast(id_partida, json.dumps(fin_payload))
            eliminarPartida(id_partida, db)

        # Si la mano quedó en 6 tras robar, avanzar turno
        mano_final = CartaService(db).obtener_mano_jugador(id_jugador, id_partida)
        if len(mano_final) >= 6 or cantidad_restante == 0:
            nuevo_turno = PartidaService(db).avanzar_turno(id_partida)
            logger.info(
                "TURNO AVANZA POR ROBAR: partida=%s nuevo_turno=%s",
                id_partida, nuevo_turno,
            )
            await manager.broadcast(id_partida, json.dumps({
                "evento": "turno-actual",
                "turno-actual": nuevo_turno,
            }))
            CartaService(db).actualizar_mazo_draft(id_partida)

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


@partidas_router.get(path="/{id_partida}/sets", status_code=status.HTTP_200_OK)
async def obtener_sets_jugados(id_partida: int, db=Depends(get_db)):
    """Devuelve los sets jugados en la partida agrupados por jugador."""
    from game.cartas.services import CartaService
    try:
        sets = CartaService(db).obtener_sets_jugados(id_partida)
        return sets
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


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
            {"id": carta.id_carta, "nombre": carta.nombre, "id_instancia": carta.id,  "revelada": carta.bocaArriba}
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
        asesino_complice = ids_asesino_complice(db, id_partida)

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
        cartas_descarte = mostrar_cartas_descarte(id_partida, id_jugador, cantidad, db)
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


@partidas_router.patch(path="/{id_partida}/revelacion", status_code=status.HTTP_200_OK)
async def revelar_secreto(id_partida: int, id_jugador_turno: int, id_unico_secreto: int, db=Depends(get_db)):
    """
    Revela el secreto de un jugador de la partida.
    
    Recibe el ID de la partida donde se ejecuta la acción, el ID del jugador del turno que revela
    un secreto de otro jugador, y el ID de la carta a revelar.
    """
    try:
        desgraciaSocial_aux = True
        desgracia_social = PartidaService(db).desgracia_social(id_partida, id_jugador_turno)
        if not desgracia_social:
            desgraciaSocial_aux = False

        secreto_revelado = revelarSecreto(id_partida, id_jugador_turno, id_unico_secreto, db)
        secretoID = secreto_revelado.id
        if not secreto_revelado:
            return None
        
        secretos_actuales = CartaService(db).obtener_secretos_jugador(secreto_revelado.jugador_id, id_partida)
        print(f'secretos del jugador: {[{"id_carta": s.id, "bocaArriba": s.bocaArriba} for s in secretos_actuales]}')
        await manager.broadcast(id_partida, json.dumps({
            "evento": "actualizacion-secreto",
            "jugador-id": secreto_revelado.jugador_id,
            "lista-secretos": [{"revelado": s.bocaArriba} for s in secretos_actuales]
        }))

        esAsesino = CartaService(db).es_asesino(id_unico_secreto)
        if esAsesino:
            await manager.broadcast(id_partida, json.dumps({
            "evento": "fin-partida",
            "jugador-perdedor-id": secreto_revelado.jugador_id,
            "payload": {"ganadores": [], "asesinoGano": False}
            }))
            eliminarPartida(id_partida, db)
        else:
            desgracia_social = PartidaService(db).desgracia_social(id_partida, id_jugador_turno)
            if (not desgraciaSocial_aux) and (desgracia_social):
                print(f"desgracia social: El jugador {id_jugador_turno} entro en desgracia social")
                await manager.broadcast(id_partida, json.dumps({
                    "desgracia_social": True,
                    "Jugador": id_jugador_turno
                }))

        return {"id-secreto": secretoID}
        
    except ValueError as e:
        if ("No se ha encontrado" in str(e)):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        elif ("Solo el jugador del turno puede realizar esta acción" in str(e)):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e)
            )
        elif("no pertenece a" in str(e)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        elif("El secreto ya está revelado!" in str(e)):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Hubo un error al revelar secreto.{str(e)}"
            )


@partidas_router.put("/{id_partida}/jugador/{id_jugador}/recoger", status_code=status.HTTP_200_OK)
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
                "evento": "fin-partida", "ganadores": [], "asesinoGano": True
            }))
            eliminarPartida(id_partida, db)
        return nuevas_cartas_para_jugador
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("RECOGER ERROR endpoint: partida=%s jugador=%s error=%s", id_partida, id_jugador, e)
        raise HTTPException(status_code=500, detail=str(e))


@partidas_router.get(path="/{id_partida}/secretosjugador", status_code=status.HTTP_200_OK)
async def obtener_secretos_otro_jugador(id_partida: int, id_jugador: int, db=Depends(get_db)):
    """
    Obtiene los secretos de un jugador específico para una partida.
    """
    try:
        cartas_a_enviar = CartaService(db).obtener_secretos_ajenos(id_jugador, id_partida)
        return cartas_a_enviar
    
    except Exception as e:
        print(f"Error al obtener secretos: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@partidas_router.patch(path="/{id_partida}/ocultamiento", status_code=status.HTTP_200_OK)
async def ocultar_secreto(id_partida: int, id_jugador_turno: int, id_unico_secreto: int,db=Depends(get_db)):
    """
    Oculta el secreto de un jugador de la partida.
    
    Recibe el ID de la partida donde se ejecuta la acción, el ID del jugador del turno que oculta
    un secreto de otro jugador, y el ID de la carta a ocultar.
    """
    try:
        desgraciaSocial_aux = False
        desgracia_social = PartidaService(db).desgracia_social(id_partida, id_jugador_turno)
        if desgracia_social:
            desgraciaSocial_aux = True
        secreto_ocultado = ocultarSecreto(id_partida, id_jugador_turno, id_unico_secreto, db)
        
        if not secreto_ocultado:
            return None
        
        secretos_actuales = CartaService(db).obtener_secretos_jugador(secreto_ocultado.jugador_id, id_partida)
        print(f'secretos del jugador: {[{"id_carta": s.id, "bocaArriba": s.bocaArriba} for s in secretos_actuales]}')
        await manager.broadcast(id_partida, json.dumps({
            "evento": "actualizacion-secreto",
            "jugador-id": secreto_ocultado.jugador_id,
            "lista-secretos": [{"revelado": s.bocaArriba} for s in secretos_actuales]
        }))

        desgracia_social = PartidaService(db).desgracia_social(id_partida, id_jugador_turno)
        if desgraciaSocial_aux and (not desgracia_social):
            print(f"desgracia social: El jugador {id_jugador_turno} salio de desgracia social")
            await manager.broadcast(id_partida, json.dumps({
                "desgracia_social": False,
                "Jugador": {id_jugador_turno}
            }))

        return {"id-secreto": secreto_ocultado.id}
        
    except ValueError as e:
        if ("No se ha encontrado" in str(e)):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        elif ("Solo el jugador del turno puede realizar esta acción" in str(e)):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e)
            )
        elif("no pertenece a" in str(e)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        elif("El secreto ya está oculto!" in str(e)):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Hubo un error al ocultar el secreto."
            )


@partidas_router.patch(path="/{id_partida}/robo-secreto", status_code=status.HTTP_200_OK)
async def robar_secreto_otro_jugador(id_partida: int, id_jugador_turno: int, id_jugador_destino: int, id_unico_secreto: int, db=Depends(get_db)):
    """
    Roba el secreto de un jugador dado su ID, el ID del jugador del turno, el ID de la carta y el de la partida.
    """
    try:
        secreto_robado = robar_secreto(id_partida, id_jugador_turno, id_jugador_destino, id_unico_secreto, db)

        if not secreto_robado:
            return None
        
        secretos_actuales = CartaService(db).obtener_secretos_jugador(id_jugador_destino, id_partida)
        print(f'secretos del jugador: {[{"id_carta": s.id, "bocaArriba": s.bocaArriba} for s in secretos_actuales]}')
        await manager.broadcast(id_partida, json.dumps({
            "evento": "actualizacion-secreto",
            "jugador-id": id_jugador_destino,
            "lista-secretos": [{"revelado": s.bocaArriba} for s in secretos_actuales]
        }))

        return secreto_robado
        
    except ValueError as e:
        if ("No se ha encontrado" in str(e)):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        elif ("Solo el jugador del turno puede realizar esta acción" in str(e)):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e)
            )
        elif("no pertenece a" in str(e)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        elif("No se puede robar un secreto que está oculto!" in str(e)):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Hubo un error al robar la carta secreto u obtener al jugador."
            )


#Endpoint Jugar set 
@partidas_router.post(path='/{id_partida}/Jugar-set', status_code=status.HTTP_200_OK)
async def jugar_set(id_partida: int, id_jugador: int, set_cartas: list[int], db=Depends(get_db), manager=Depends(get_manager)):
    """ Juega un set de cartas si es el turno del jugador y las cartas son las correctas.
    Parameters ----------
        id_partida: int ID de la partida en la que se intenta jugar el set 
        id_jugador: int ID del jugador que intenta jugar el set 
        set_cartas: list[int] IDs del set cartas que se quiere jugar
    Returns -------
        Status 200 OK si el set se puede jugar correctamente, de lo contrario lanza una excepción HTTP. 
    """ 
     
    cartas_jugadas = jugar_set_detective(id_partida, id_jugador, set_cartas, db)
    # Persist and broadcast the played set
    try:
        from game.cartas.services import CartaService
        cs = CartaService(db)
        registro = cs.registrar_set_jugado(id_partida, id_jugador, cartas_jugadas)
        payload = {
            "evento": "jugar-set",
            "jugador_id": id_jugador,
            "representacion_id": next((c.id_carta for c in cartas_jugadas if c.id_carta != 14), cartas_jugadas[0].id_carta if cartas_jugadas else 1),
            "cartas_ids": [c.id_carta for c in cartas_jugadas],
        }
        await manager.broadcast(id_partida, json.dumps(payload))
    except Exception:
        # do not block on logging/persist issues
        pass
    try:
        resumen = ", ".join([f"{c.id_carta}:{c.nombre}" for c in cartas_jugadas])
        logger = logging.getLogger(__name__)
        logger.info(
            "JUGAR SET: partida=%s jugador=%s set_ids=%s cartas=[%s]",
            id_partida, id_jugador, set_cartas, resumen,
        )
    except Exception:
        # No bloquear por logging
        pass
    return {"detail": "Set jugado correctamente", "cartas_jugadas": [{"id": carta.id_carta, "nombre": carta.nombre} for carta in cartas_jugadas]}


@partidas_router.get(path="/{id_partida}/secretosjugador", status_code=status.HTTP_200_OK)
async def obtener_secretos_otro_jugador(id_partida: int, id_jugador: int, db=Depends(get_db)):
    """
    Obtiene los secretos de un jugador específico para una partida.
    """
    try:
        cartas_a_enviar = CartaService(db).obtener_secretos_ajenos(id_jugador, id_partida)
        return cartas_a_enviar
    
    except Exception as e:
        print(f"Error al obtener secretos: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")



@partidas_router.patch(path="/{id_partida}/ocultamiento", status_code=status.HTTP_200_OK)
async def ocultar_secreto(id_partida: int, id_jugador: int, id_unico_secreto: int,db=Depends(get_db)):
    """
    Oculta el secreto de un jugador dado su ID, el ID de la carta y el de la partida.
    """
    try:
        secreto_ocultado = CartaService(db).ocultar_secreto(id_partida, id_jugador, id_unico_secreto)
        
        if not secreto_ocultado:
            return None
        
        secretos_actuales = CartaService(db).obtener_secretos_jugador(id_jugador, id_partida)
        print(f'secretos del jugador: {[{"id_carta": s.id, "bocaArriba": s.bocaArriba} for s in secretos_actuales]}')
        await manager.broadcast(id_partida, json.dumps({
            "evento": "actualizacion-secreto",
            "jugador-id": id_jugador,
            "lista-secretos": [{"revelado": s.bocaArriba} for s in secretos_actuales]
        }))

        return secreto_ocultado
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Hubo un error al ocultar la carta secreto u obtener al jugador."
        )


@partidas_router.put(path='/{id_partida}/evento/CardsTable', status_code=status.HTTP_200_OK)
async def cards_off_the_table(id_partida: int, id_jugador: int, id_objetivo: int, id_carta: int, db=Depends(get_db)):
    """
    Se juega el evento Cards off the table (descarta los 'Not so fast' de la mano de un jugador)
    """
    try:
        if not verif_evento("Cards off the table", id_carta):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La carta no corresponde al evento Cards Off The Table"
            )

        # Verificaciones básicas
        verif_jugador_objetivo(id_partida, id_jugador, id_objetivo, db)
        jugar_carta_evento(id_partida, id_jugador, id_carta, db)

        # Aplicar el efecto en la base
        CartaService(db).jugar_cards_off_the_table(id_partida, id_jugador, id_objetivo)

        # Avisar a todos que se jugó el evento
        await manager.broadcast(id_partida, json.dumps({
            "evento": "se-jugo-cards-off-the-table",
            "jugador_id": id_jugador,
            "objetivo_id": id_objetivo
        }))
        
        
        evento= {
        "evento": "carta-descartada", 
        "payload": {
                    "discardted":
                    [id_carta]
                } 
        }
        await manager.broadcast(id_partida, json.dumps(evento))

        for jugador in [id_jugador, id_objetivo]:
            mano_jugador = CartaService(db).obtener_mano_jugador(jugador, id_partida)
            cartas_a_enviar = [{"id": carta.id_carta, "nombre": carta.nombre} for carta in mano_jugador]
            
            await manager.send_personal_message(
                jugador,
                json.dumps({
                    "evento": "actualizacion-mano",
                    "data": cartas_a_enviar
                })
            )

        return {"detail": "Evento jugado correctamente"}

    except ValueError as e:
        msg = str(e)
        print(f"Error de validación: {msg}")

        if "aplicar el efecto." in msg:
            raise HTTPException(status_code=400, detail=msg)
        elif "No se ha encontrado la partida" in msg:
            raise HTTPException(status_code=404, detail=msg)
        elif "objetivo" in msg.lower() and "no se encontro" in msg.lower():
            raise HTTPException(status_code=404, detail=msg)
        elif "jugador" in msg.lower() and "no se encontro" in msg.lower():
            raise HTTPException(status_code=404, detail=msg)
        elif "Partida no iniciada" in msg:
            raise HTTPException(status_code=403, detail=msg)
        elif "no esta en turno" in msg.lower():
            raise HTTPException(status_code=403, detail=msg)
        elif "no pertenece a la partida" in msg.lower():
            raise HTTPException(status_code=403, detail=msg)
        elif "desgracia social" in msg:
            raise HTTPException(status_code=403, detail=msg)
        elif "Solo se puede jugar una carta de evento" in msg:
            raise HTTPException(status_code=400, detail=msg)
        elif "no se encuentra en la mano" in msg.lower():
            raise HTTPException(status_code=400, detail=msg)
        elif "no es de tipo evento" in msg.lower():
            raise HTTPException(status_code=400, detail=msg)
        else:
            raise HTTPException(status_code=400, detail=f"Error de validación: {msg}")

    except HTTPException:
        raise

    except Exception as e:
        print(f"Error inesperado al jugar carta de evento Cards off the table: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")    


@partidas_router.put(path='/{id_partida}/evento/OneMore', status_code=status.HTTP_200_OK)
async def one_more(id_partida: int, id_jugador: int, id_carta: int,
                   payload: OneMorePayload,
                   db=Depends(get_db)):
    """
    Juega el evento "And then there was one more..." (id 22):
    - El jugador en turno elige un jugador fuente que tenga al menos un secreto revelado.
    - Selecciona uno de esos secretos revelados (id_unico_secreto) y lo mueve a un jugador destino.
    - El secreto pasa a estar oculto en el destino.
    """
    try:
        # Validar que la carta sea la correcta (nombre exacto en constants)
        if not verif_evento("And then there was one more...", id_carta):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="La carta no corresponde al evento And then there was one more...")

        # Validaciones de jugadores y turno
        # Para OneMore permitimos que la fuente sea el mismo jugador en turno (mover su propio secreto).
        # Sólo validamos existencia y que destino sea distinto a fuente.
        # Validar primero el jugador destino (tests esperan este mensaje prioritario)
        jugador_destino = partidas_utils.JugadorService(db).obtener_jugador(payload.id_destino)
        if jugador_destino is None:
            raise ValueError(f"No se encontró el jugador destino {payload.id_destino}.")

        jugador_fuente = partidas_utils.JugadorService(db).obtener_jugador(payload.id_fuente)
        if jugador_fuente is None:
            raise ValueError(f"No se encontró el jugador fuente {payload.id_fuente}.")

        # Ambos jugadores deben pertenecer a la partida
        if jugador_fuente.partida_id != id_partida or jugador_destino.partida_id != id_partida:
            raise ValueError("Los jugadores seleccionados no pertenecen a la partida indicada.")

        # Se permite mover el secreto al mismo jugador (queda oculto en destino)
        
        # jugar carta de evento (marca evento_jugado y valida turno/mano)
        jugar_carta_evento(id_partida, id_jugador, id_carta, db)

        # Verificar secreto y moverlo al destino oculto
        from game.cartas.services import CartaService
        cs = CartaService(db)
        secreto = cs.obtener_carta_por_id(payload.id_unico_secreto)
        if secreto is None:
            raise HTTPException(status_code=404, detail="Secreto no encontrado")
        if secreto.partida_id != id_partida or secreto.tipo != "secreto":
            raise HTTPException(status_code=400, detail="Secreto inválido para esta partida")
        if not secreto.bocaArriba:
            raise HTTPException(status_code=400, detail="El secreto seleccionado no está revelado")
        if secreto.jugador_id != payload.id_fuente:
            raise HTTPException(status_code=400, detail="El secreto no pertenece al jugador fuente")

        cs.robar_secreto(secreto, payload.id_destino)

        # Descartar la carta de evento jugada y avisar
        carta_jugada = db.query(Carta).filter_by(partida_id=id_partida,
                                                 jugador_id=id_jugador,
                                                 ubicacion="evento_jugado",
                                                 nombre="And then there was one more...").first()
        if carta_jugada:
            cs.descartar_cartas(id_jugador, [carta_jugada.id_carta])

        await manager.broadcast(id_partida, json.dumps({
            "evento": "se-jugo-one-more",
            "jugador_id": id_jugador,
            "objetivo_id": payload.id_fuente,
            "destino_id": payload.id_destino
        }))

        # Actualizar contadores de secretos para fuente y destino
        secretos_fuente = cs.obtener_secretos_jugador(payload.id_fuente, id_partida)
        await manager.broadcast(id_partida, json.dumps({
            "evento": "actualizacion-secreto",
            "jugador-id": payload.id_fuente,
            "lista-secretos": [{"revelado": s.bocaArriba} for s in secretos_fuente]
        }))
        secretos_destino = cs.obtener_secretos_jugador(payload.id_destino, id_partida)
        await manager.broadcast(id_partida, json.dumps({
            "evento": "actualizacion-secreto",
            "jugador-id": payload.id_destino,
            "lista-secretos": [{"revelado": s.bocaArriba} for s in secretos_destino]
        }))

        evento = {
            "evento": "carta-descartada",
            "payload": {"discardted": [id_carta]}
        }
        await manager.broadcast(id_partida, json.dumps(evento))

        return {"detail": "Evento jugado correctamente"}
    except ValueError as e:
        msg = str(e)
        if "aplicar el efecto." in msg:
            raise HTTPException(status_code=400, detail=msg)
        elif "No se ha encontrado la partida" in msg:
            raise HTTPException(status_code=404, detail=msg)
        elif "Partida no iniciada" in msg:
            raise HTTPException(status_code=403, detail=msg)
        elif "no esta en turno" in msg.lower():
            raise HTTPException(status_code=403, detail=msg)
        elif "no pertenece a la partida" in msg.lower():
            raise HTTPException(status_code=403, detail=msg)
        elif "Solo se puede jugar una carta de evento" in msg:
            raise HTTPException(status_code=400, detail=msg)
        elif "no se encuentra en la mano" in msg.lower():
            raise HTTPException(status_code=400, detail=msg)
        elif "no es de tipo evento" in msg.lower():
            raise HTTPException(status_code=400, detail=msg)
        elif "sobre el jugador que tiro la carta" in msg:
            raise HTTPException(status_code=409, detail=msg)
        elif "jugador" in msg and "no pertence a la partida" in msg:
            raise HTTPException(status_code=403, detail=msg)
        else:
            raise HTTPException(status_code=400, detail=f"Error de validación: {msg}")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error al jugar carta de evento One More: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@partidas_router.put(path='/{id_partida}/evento/AnotherVictim', status_code=status.HTTP_200_OK)
async def another_victim(id_partida: int, id_jugador: int, id_carta: int, 
                             payload: AnotherVictimPayload, 
                             db=Depends(get_db)):
    """
    juega el evento Another Victim (el jugador que juega la carta roba un set a eleccion)
    parameters:
    ----------  
        id_partida: int ID de la partida en la que se intenta jugar el evento
        id_jugador: int ID del jugador que quiere robar el set
        id_objetivo: int ID del jugador a quien le roban el set
        id_represetacion_carta: int ID del detective que representa al set
        ids_cartas: list[int] IDs de las cartas que estan en el set
        id_carta: int ID de la carta de evento que se juega
    Returns:
    ----------
        Status 200 OK si el evento se puede jugar correctamente, de lo contrario lanza una excepción HTTP. 
    """
    try:
        if verif_evento("Another Victim", id_carta):
            verif_jugador_objetivo(id_partida, id_jugador, payload.id_objetivo, db)
            jugar_carta_evento(id_partida, id_jugador, id_carta, db)
            
            CartaService(db).robar_set(id_partida, id_jugador, payload.id_objetivo, payload.id_representacion_carta, payload.ids_cartas)
            
            # await manager.broadcast(id_partida, json.dumps({
            #     "evento": "se-jugo-another-victim",
            #     "jugador_id": id_jugador,
            #     "objetivo_id": payload.id_objetivo
            # }))
            evento= {
            "evento": "carta-descartada", 
            "payload": {
                        "discardted":
                        [id_carta]
                    } 
            }
            await manager.broadcast(id_partida, json.dumps(evento))
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La carta no corresponde al evento Another victim"
                )
    except ValueError as e:
        msg = str(e)

        if "aplicar el efecto." in msg:
            raise HTTPException(status_code=400, detail=msg)
        elif "No se ha encontrado la partida" in msg:
            raise HTTPException(status_code=404, detail=msg)
        elif "objetivo" in msg and "no se encontro" in msg.lower():
            raise HTTPException(status_code=404, detail=msg)
        elif "jugador" in msg and "no se encontro" in msg.lower():
            raise HTTPException(status_code=404, detail=msg)
        elif "Partida no iniciada" in msg:
            raise HTTPException(status_code=403, detail=msg)
        elif "no esta en turno" in msg.lower():
            raise HTTPException(status_code=403, detail=msg)
        elif "no pertenece a la partida" in msg.lower():
            raise HTTPException(status_code=403, detail=msg)
        elif "desgracia_social" in msg:
            raise HTTPException(status_code=403, detail=msg)
        elif "Solo se puede jugar una carta de evento" in msg:
            raise HTTPException(status_code=400, detail=msg)
        elif "no se encuentra en la mano" in msg.lower():
            raise HTTPException(status_code=400, detail=msg)
        elif "no es de tipo evento" in msg.lower():
            raise HTTPException(status_code=400, detail=msg)
        else:
            raise HTTPException(status_code=400, detail=f"Error de validación: {msg}")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error al jugar carta de evento Another victim: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor") 

@partidas_router.patch(path="/{id_partida}/revelacion-propia", status_code=status.HTTP_200_OK)
async def revelar_secreto_propio(id_partida: int, id_jugador: int, id_unico_secreto: int, db=Depends(get_db)):
    """
    Revela el secreto de un jugador de la partida.
    
    Recibe el ID de la partida donde se ejecuta la acción, el ID del jugador que revela
    un secreto propio, y el ID de la carta a revelar.
    """
    try:
        secreto_revelado = revelarSecretoPropio(id_partida, id_jugador, id_unico_secreto, db)
        secretoID = secreto_revelado.id
        if not secreto_revelado:
            return None
        
        secretos_actuales = CartaService(db).obtener_secretos_jugador(secreto_revelado.jugador_id, id_partida)
        print(f'secretos del jugador: {[{"id_carta": s.id, "bocaArriba": s.bocaArriba} for s in secretos_actuales]}')
        await manager.broadcast(id_partida, json.dumps({
            "evento": "actualizacion-secreto",
            "jugador-id": secreto_revelado.jugador_id,
            "lista-secretos": [{"revelado": s.bocaArriba} for s in secretos_actuales]
        }))

        esAsesino = CartaService(db).es_asesino(id_unico_secreto)
        if esAsesino:
            await manager.broadcast(id_partida, json.dumps({
            "evento": "fin-partida",
            "jugador-perdedor-id": secreto_revelado.jugador_id,
            "payload": {"ganadores": [], "asesinoGano": False}
            }))
            eliminarPartida(id_partida, db)

        return {"id-secreto": secretoID}
        
    except ValueError as e:
        if ("No se ha encontrado" in str(e)):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        elif ("Solo el jugador del turno puede realizar esta acción" in str(e)):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e)
            )
        elif("no pertenece a" in str(e)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        elif("El secreto ya está revelado!" in str(e)):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Hubo un error al revelar secreto."
            )

@partidas_router.post(path="/{id_partida}/solicitar-revelacion", status_code=status.HTTP_200_OK)
async def solicitar_revelacion(
    id_partida: int,
    id_jugador_solicitante: int,
    id_jugador_objetivo: int,
    motivo: str = "lady-brent",
    db=Depends(get_db),
    manager=Depends(get_manager),
):
    """Solicita a un jugador que revele uno de sus secretos mediante un mensaje personal por WebSocket.

    Usado por efectos como Lady Eileen "Bundle" Brent, donde el objetivo elige el secreto a revelar.
    """
    try:
        partida = PartidaService(db).obtener_por_id(id_partida)
        if partida is None:
            raise HTTPException(status_code=404, detail="Partida no encontrada")

        jugador_obj = JugadorService(db).obtener_jugador(id_jugador_objetivo)
        if jugador_obj is None or jugador_obj.partida_id != id_partida:
            raise HTTPException(status_code=404, detail="Jugador objetivo no válido para esta partida")

        payload = {
            "evento": "solicitar-revelacion-secreto",
            "motivo": motivo,  # valores posibles: 'lady-brent', 'beresford'
            "solicitante-id": id_jugador_solicitante,
            "partida-id": id_partida,
        }
        await manager.send_personal_message(id_jugador_objetivo, json.dumps(payload))
        return {"detail": "Solicitud enviada"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@partidas_router.put(path='/{id_partida}/evento/DelayMurderer', status_code=status.HTTP_200_OK)
async def delay_the_murderer_escape(id_partida: int, id_jugador: int, id_carta: int, cantidad: int, db=Depends(get_db)):
    """
    Se juega el evento delay_the_murderer_escape(agrega hasta 5 cartas del mazo de descarte al de robo)
    """
    try:
        if verif_evento("Delay the murderer's escape!", id_carta):
            verif_cantidad(id_partida, cantidad, db)
            jugar_carta_evento(id_partida, id_jugador, id_carta, db)
            await manager.broadcast(id_partida, json.dumps({
                "evento": "se-jugo-delay-escape"
            }, default=str))
            CartaService(db).jugar_delay_the_murderer_escape(id_partida, id_jugador, cantidad)
            cantidad_restante = CartaService(db).obtener_cantidad_mazo(id_partida)
            await manager.broadcast(id_partida, json.dumps({
                "evento": "actualizacion-mazo",
                "cantidad-restante-mazo": cantidad_restante
            }, default=str))
            nueva_carta_tope = CartaService(db).obtener_cartas_descarte(id_partida, 1)
            await manager.broadcast(id_partida, json.dumps({
                "evento": "carta-descartada", 
                "payload": [{"id": c.id_carta} for c in nueva_carta_tope]
            }, default=str))
            return {"detail": "Evento jugado correctamente"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La carta no corresponde al evento Delay the murderer's escape!"
                )
    except ValueError as e:
        msg = str(e)
        if "1 y 5" in msg:
            raise HTTPException(status_code=400, detail=msg)
        elif "mazo de descarte" in msg:
            raise HTTPException(status_code=400, detail=msg)
        elif "No se ha encontrado la partida" in msg:
            raise HTTPException(status_code=404, detail=msg)
        elif "jugador" in msg and "no se encontro" in msg.lower():
            raise HTTPException(status_code=404, detail=msg)
        elif "Partida no iniciada" in msg:
            raise HTTPException(status_code=403, detail=msg)
        elif "no esta en turno" in msg.lower():
            raise HTTPException(status_code=403, detail=msg)
        elif "no pertenece a la partida" in msg.lower():
            raise HTTPException(status_code=403, detail=msg)
        elif "desgracia social" in msg:
            raise HTTPException(status_code=403, detail=msg)
        elif "Solo se puede jugar una carta de evento" in msg:
            raise HTTPException(status_code=400, detail=msg)
        elif "no se encuentra en la mano" in msg.lower():
            raise HTTPException(status_code=400, detail=msg)
        elif "no es de tipo evento" in msg.lower():
            raise HTTPException(status_code=400, detail=msg)
        else:
            raise HTTPException(status_code=400, detail=f"Error de validación: {msg}")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error al jugar carta de evento Delay the murderer's escape!: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")    


@partidas_router.put(path='/{id_partida}/evento/LookIntoTheAshes', status_code=status.HTTP_200_OK)
async def look_into_the_ashes(id_partida: int, id_jugador: int, db=Depends(get_db), id_carta: int = None, id_carta_objetivo: int = None):
    """
    Se juega el evento Look Into The Ashes.
    """
    if id_carta != None and id_carta_objetivo == None:
        try:
            if verif_evento("Look into the ashes", id_carta):
                carta_evento = jugar_carta_evento(id_partida, id_jugador, id_carta, db)
                await manager.broadcast(id_partida, json.dumps({
                    "evento": "se-jugo-look-into-the-ashes",
                    "jugador_id": id_jugador
                }))
                await asyncio.sleep(3)
        
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="La carta no corresponde al evento Look Into The Ashes."
            )
        except ValueError as e:
            msg = str(e)
            
            if "no se encontro" in msg:
                raise HTTPException(status_code=404, detail=msg)
            elif "Partida no iniciada" in msg:
                raise HTTPException(status_code=403, detail=msg)
            elif "no pertenece a la partida" in msg:
                raise HTTPException(status_code=403, detail=msg)
            elif "no esta en turno" in msg:
                raise HTTPException(status_code=403, detail=msg)
            elif "una carta de evento por turno" in msg:
                raise HTTPException(status_code=400, detail=msg)
            elif "La carta no se encuentra en la mano del jugador" in msg:
                raise HTTPException(status_code=400, detail=msg)
            elif "no es de tipo evento" in msg:
                raise HTTPException(status_code=400, detail=msg)
            else:
                raise HTTPException(status_code=500, detail="Error inesperado.")
            
    elif id_carta == None and id_carta_objetivo != None:
        try:
            jugar_look_into_ashes(id_partida, id_jugador, id_carta_objetivo, db)
            evento2= {
            "evento": "carta-descartada", 
            "payload": {
                        "discardted":
                        [20]
                    } 
                }
            await manager.broadcast(id_partida, json.dumps(evento2))
        except Exception as e:
            msg = str(e)
        
            if "No se jugo el evento Look Into The Ashes" in msg:
                raise HTTPException(status_code=400, detail=msg)
            elif "La carta a robar no esta entre las top 5 cartas del mazo descarte" in msg:
                raise HTTPException(status_code=403, detail=msg)
                 
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error de validacion"
        )
    
    
# Endpoint abandonar partida
@partidas_router.post(path="/{id_partida}/abandonar", status_code=status.HTTP_200_OK)
async def abandonar_partida(id_partida: int, id_jugador: int, db=Depends(get_db), manager=Depends(get_manager)):

    """
    Elimina a un jugador de la partida dado su ID y el ID de la partida.
     Si el jugador es el host, elimina la partida y todos los jugadores de la misma.
    
    Parameters
    ----------
    id_partida: int
        ID de la partida que abandonará el jugador
    
    id_jugador: int
        ID del jugador que abandonará la partida
    
    """
    try:
        jugador_abandona = abandonarPartida(id_partida, id_jugador, db)
        if jugador_abandona["rol"] == "invitado":
            await manager.broadcast(id_partida, json.dumps({
                        "evento": "abandono-jugador", 
                        "id-jugador": jugador_abandona["id_jugador"], 
                        "nombre-jugador": jugador_abandona["nombre_jugador"],
                        "jugadores-restantes": jugador_abandona["jugadoresRestantes"],
                    }))
            return jugador_abandona
        
        else:
            await manager.broadcast(id_partida, json.dumps({
                        "evento": "partida-cancelada", 
                        "id-partida": id_partida,
                    }))
            return jugador_abandona

    except ValueError as e:
        if "No se ha encontrado" in str(e):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        elif "No se puede abandonar" in str(e):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e)
            )
        elif "no pertenece a" in str(e):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        elif "Hubo un error" in str(e):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )
            
@partidas_router.put(path='/{id_partida}/evento/EarlyTrain', status_code=status.HTTP_200_OK)
async def early_train_to_paddington(id_partida: int, id_jugador: int, id_carta: int, db=Depends(get_db)):
    """
    Se juega o descarta el evento Early Train To Paddington.
    Mueve 6 cartas del mazo de robo al descarte.
    """
    try:
        if verif_evento("Early train to paddington", id_carta):
            jugar_carta_evento(id_partida, id_jugador, id_carta, db)
            CartaService(db).jugar_early_train_to_paddington(id_partida, id_jugador)

            await manager.broadcast(id_partida, json.dumps({
                "evento": "se-jugo-early-train"
            }))

            cantidad_mazo_robo = CartaService(db).obtener_cantidad_mazo(id_partida)
            await manager.broadcast(id_partida, json.dumps({
                "evento": "actualizacion-mazo",
                "cantidad-restante-mazo": cantidad_mazo_robo
            }))
            cantidad_restante = CartaService(db).obtener_cantidad_mazo(id_partida)

            if cantidad_restante == 0:
                fin_payload = {
                    "evento": "fin-partida",
                    "payload": {"ganadores": [], "asesinoGano": True}
                }
                await manager.broadcast(id_partida, json.dumps(fin_payload))

            nuevas_cartas_descarte = CartaService(db).obtener_cartas_descarte(id_partida, 5)
            await manager.broadcast(id_partida, json.dumps({
                "evento": "actualizacion-descarte",
                "payload": [{"id": c.id_carta} for c in nuevas_cartas_descarte]
            }))

            return {"detail": "Evento jugado correctamente"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La carta no corresponde al evento Early Train To Paddington"
            )
    except ValueError as e:
        msg = str(e)
        if "1 y 5" in msg:
            raise HTTPException(status_code=400, detail=msg)
        elif "mazo de descarte" in msg:
            raise HTTPException(status_code=400, detail=msg)
        elif "No se ha encontrado la partida" in msg:
            raise HTTPException(status_code=404, detail=msg)
        elif "jugador" in msg and "no se encontro" in msg.lower():
            raise HTTPException(status_code=404, detail=msg)
        elif "Partida no iniciada" in msg:
            raise HTTPException(status_code=403, detail=msg)
        elif "no esta en turno" in msg.lower():
            raise HTTPException(status_code=403, detail=msg)
        elif "no pertenece a la partida" in msg.lower():
            raise HTTPException(status_code=403, detail=msg)
        elif "desgracia social" in msg:
            raise HTTPException(status_code=403, detail=msg)
        elif "Solo se puede jugar una carta de evento" in msg:
            raise HTTPException(status_code=400, detail=msg)
        elif "no se encuentra en la mano" in msg.lower():
            raise HTTPException(status_code=400, detail=msg)
        elif "no es de tipo evento" in msg.lower():
            raise HTTPException(status_code=400, detail=msg)
        else:
            raise HTTPException(status_code=400, detail=f"Error de validación: {msg}")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error al jugar carta de evento Early Train: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@partidas_router.post(path='/{id_partida}/iniciar-accion', status_code=status.HTTP_200_OK)
async def iniciar_accion_generica(id_partida: int, id_jugador: int, 
                                  accion: AccionGenericaPayload, 
                                  request: Request,
                                  db=Depends(get_db)):
    """
    (Fase 1) GENÉRICO: Propone una acción cancelable (Evento O Set).
    ¡¡CONFÍA 100% EN EL FRONTEND!! No valida NADA.
    Solo guarda el estado y abre la ventana de respuesta.
    """
    try:
                # --- LOG: What was sent ---
        raw_body = await request.body()
        print("\n--- DEBUG /iniciar-accion ---")
        print(f"Query param id_partida={id_partida}, id_jugador={id_jugador}")
        print("Raw body (as received):", raw_body.decode("utf-8"))
        print("Parsed AccionGenericaPayload:")
        print("  tipo_accion:", accion.tipo_accion)
        print("  cartas_db_ids:", accion.cartas_db_ids)
        print("  nombre_accion:", accion.nombre_accion)
        print("  payload_original:", accion.payload_original)
        print("------------------------------\n")
        # -----------------------------

        ps = PartidaService(db)
        js = JugadorService(db)

        partida = ps.obtener_por_id(id_partida)
        if partida.accion_en_progreso:
            raise HTTPException(status_code=409, detail="Ya hay una acción en progreso.")

        # --- ¡SIN VALIDACIÓN! ---
        # Confiamos en que el frontend envió los datos correctos.
        # El frontend es responsable de enviar los IDs de BBDD
        # de las cartas que se están jugando.
        
        # 1. Empaquetar la acción (confiando en los datos del frontend)
        accion_context = {
            "tipo_accion": accion.tipo_accion,
            "cartas_originales_db_ids": accion.cartas_db_ids, # Confiamos en esta lista
            "id_jugador_original": id_jugador,
            "nombre_accion": accion.nombre_accion,
            "payload_original": accion.payload_original,
            "pila_respuestas": []      
        }
        
        # 2. Iniciar la "pausa" en la BBDD
        ps.iniciar_accion(id_partida, accion_context)

        # 3. Construir y enviar el Broadcast (con nombres)
        actor = js.obtener_jugador(id_jugador)
        actor_nombre = actor.nombre if actor else f"Jugador {id_jugador}"
        
        mensaje = f"{actor_nombre} jugó '{accion.nombre_accion}'"
        
        id_objetivo = None
        if isinstance(accion.payload_original, dict):
            id_objetivo = accion.payload_original.get('id_objetivo')
        
        if id_objetivo:
            objetivo = js.obtener_jugador(id_objetivo)
            objetivo_nombre = objetivo.nombre if objetivo else f"Jugador {id_objetivo}"
            mensaje += f" sobre {objetivo_nombre}"

        await manager.broadcast(id_partida, json.dumps({
            "evento": "accion-en-progreso",
            "data": accion_context,
            "mensaje": mensaje
        }))
        
        return {"detail": "Acción propuesta, ventana de respuesta abierta."}

    except ValueError as e: # Solo atrapa el "accion_en_progreso"
        msg = str(e)
        raise HTTPException(status_code=400, detail=f"Error de validación: {msg}")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Error interno al iniciar acción.")
    

@partidas_router.put(path='/{id_partida}/respuesta/not_so_fast', status_code=status.HTTP_200_OK)
async def not_so_fast(id_partida: int, id_jugador: int, id_carta: int, db=Depends(get_db)):
    """
    (Fase 2) Juega una carta "Not So Fast" en respuesta a una acción en progreso.
    """
    try:
        if not verif_evento("Not so fast", id_carta):
             raise HTTPException(status_code=400, detail="La carta no es Not So Fast.")
             
        # 1. Jugar la carta (valida que está en mano, la quita y la pone "en_la_pila")
        carta_nsf = CartaService(db).jugar_carta_instantanea(id_partida, id_jugador, id_carta)
        
        # 2. Prepara el objeto de respuesta
        carta_respuesta = {
            "id_jugador": id_jugador,
            "id_carta_db": carta_nsf.id,
            "id_carta_tipo": carta_nsf.id_carta,
            "nombre": carta_nsf.nombre
        }
        
        # 3. Añade la respuesta a la pila (bloquea y guarda)
        PartidaService(db).actualizar_pila_de_respuesta(id_partida, carta_respuesta)
        
        accion_context = PartidaService(db).obtener_accion_en_progreso(id_partida)

        # 4. Notifica al frontend que REINICIE el timer
        await manager.broadcast(id_partida, json.dumps({
            "evento": "pila-actualizada",
            "data": accion_context,
            "mensaje": f"Jugador {id_jugador} respondió con 'Not So Fast'!"
        }))
        return {"detail": "Not So Fast jugado."}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@partidas_router.post(path='/{id_partida}/resolver-accion', status_code=status.HTTP_200_OK)
async def resolver_accion(id_partida: int, db=Depends(get_db)):
    """
    (Fase 3) El frontend llama a esto cuando se acaba el timer.
    Responde si la acción se ejecuta o se cancela, y limpia la pila.
    """
    try:
        # 1. Obtiene la acción pendiente (con bloqueo)
        accion_context = PartidaService(db).obtener_accion_en_progreso(id_partida)
        cs = CartaService(db)
        
        # 2. Recolecta IDs de BBDD de las cartas NSF
        cartas_nsf_db_ids = [nsf["id_carta_db"] for nsf in accion_context["pila_respuestas"]]
        
        # 3. Limpia la pila ANTES de decidir
        PartidaService(db).limpiar_accion_en_progreso(id_partida)

        # 4. Decide el resultado
        cantidad_nsf = len(cartas_nsf_db_ids)
        
        if cantidad_nsf % 2 == 0:
            # --- PAR: La acción original SE EJECUTA ---
            
            # Descarta solo las cartas NSF (de "en_la_pila" a "descarte")
            cs.descartar_cartas_de_pila(cartas_nsf_db_ids, id_partida)
            
            # Avisa al frontend que EJECUTE el endpoint original
            mensaje = "Acción aprobada. Ejecutando..."
            await manager.broadcast(id_partida, json.dumps({
                "evento": "accion-resuelta-exitosa", 
                "detail": mensaje
            }))
            return {"decision": "ejecutar"}
            
        else:
            # --- IMPAR: La acción original SE CANCELA ---
            
            # Descarta las cartas NSF
            cs.descartar_cartas_de_pila(cartas_nsf_db_ids, id_partida)
            
            # Descarta la CARTA ORIGINAL (que sigue en la mano del jugador)
            carta_original = accion_context["carta_original"]
            cs.descartar_cartas(carta_original["id_jugador"], [carta_original["id_carta_tipo"]])
            
            # Avisa al frontend que NO ejecute nada
            mensaje = f"La acción '{carta_original['nombre']}' fue cancelada."
            await manager.broadcast(id_partida, json.dumps({
                "evento": "accion-resuelta-cancelada", 
                "detail": mensaje
            }))
            return {"decision": "cancelar"}

    except ValueError as e:
        # (Si no hay acción, puede que otro ya la haya resuelto. No es un error fatal)
        if "No hay ninguna acción" in str(e):
            return {"decision": "ignorar", "detail": "La acción ya fue resuelta."}
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Error interno al resolver la acción.")