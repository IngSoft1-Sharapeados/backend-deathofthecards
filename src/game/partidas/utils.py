from game.partidas.models import Partida
from game.jugadores.models import Jugador
from game.cartas.models import Carta, SetJugado
from game.cartas.constants import *
from game.jugadores.schemas import JugadorOut
from game.partidas.schemas import PartidaData, PartidaResponse, IniciarPartidaData
from game.partidas.services import PartidaService
from game.partidas.dtos import *
from game.cartas.services import CartaService
from game.jugadores.services import JugadorService
from game.jugadores.services import *
from fastapi import HTTPException, status
from game.modelos.db import get_db
from datetime import date


def listar_jugadores(partida: Partida) -> list[JugadorOut]:
    jugadores_out = []
    for jugador in partida.jugadores:
        jugadores_out.append(
            JugadorOut(
                id_jugador=jugador.id,
                nombre_jugador=jugador.nombre,
                fecha_nacimiento=jugador.fecha_nacimiento
            )
        )
    return jugadores_out


def distancia_fechas(fecha: date) -> int:
    f = date(2000, fecha.month, fecha.day)   # normalizo al año 2000
    agatha_birthDay = date(2000, 9, 15)
    dias_distancia = abs((f - agatha_birthDay).days)
    return dias_distancia


def crearPartida(partida_info: PartidaData, db) -> PartidaResponse:
    """
    Metodo para crear una partida
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
        
        return PartidaResponse(id_partida=partida_creada.id, id_jugador=jugador_creado.id, id_Anfitrion=jugador_creado.id)


def iniciarPartida(id_partida: int, data: IniciarPartidaData, db):
    
    partida = PartidaService(db).iniciar(id_partida, data.id_jugador)
    try:
        mazo_partida = CartaService(db).crear_mazo_inicial(id_partida)
        
        CartaService(db).repartir_cartas_iniciales(mazo_partida, partida.jugadores)
        
        CartaService(db).actualizar_mazo_draft(id_partida)
        
        secretos = CartaService(db).crear_secretos(id_partida)
        CartaService(db).repartir_secretos(secretos, partida.jugadores)
        turnos = PartidaService(db).orden_turnos(id_partida, partida.jugadores)
        PartidaService(db).set_turno_actual(id_partida, turnos[0])
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


def unir_a_partida(id_partida: int, jugador_info, db) -> JugadorOut:
    partida = PartidaService(db).obtener_por_id(id_partida)
    if partida is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontro la partida con el ID {id_partida}."
        )

    elif(partida.cantJugadores == partida.maxJugadores):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La partida ya tiene el máximo de jugadores."
        )
    try:
        jugador_creado = JugadorService(db).crear_unir(id_partida, jugador_dto=jugador_info.to_dto())
        PartidaService(db).unir_jugador(id_partida, jugador_creado)
        
        return JugadorOut(
            id_jugador = jugador_creado.id,
        nombre_jugador = jugador_creado.nombre,
        fecha_nacimiento = jugador_creado.fecha_nacimiento
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo completar la solicitud por un error interno"
        )


def mostrar_cartas_descarte(id_partida: int, id_jugador: int, cantidad:  int,  db):

    partida = PartidaService(db).obtener_por_id(id_partida)
    
    if partida is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontro la partida con el ID {id_partida}.")
        
    jugador = JugadorService(db).obtener_jugador(id_jugador)  
    
    if jugador is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontro el jugador {id_jugador}.")
        
    if jugador.partida_id != id_partida:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"El jugador con ID {id_jugador} no pertenece a la partida {id_partida}."
            )
    
    if cantidad not in (5, 1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Solo se mostrara 1 o las 5 ultimas cartas del mazo de descarte"
        )
        
    try:    
        desde_mazo_descarte = CartaService(db).obtener_cartas_descarte(id_partida, cantidad)            
        cartas_de_descarte = [
            {"id": carta.id_carta, "nombre": carta.nombre}
            for carta in desde_mazo_descarte
        ]
        return cartas_de_descarte
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No se pudo obtener las cartas del mazo descarte. Error: {e}"
        )


def mostrar_mazo_draft(id_partida: int, db):
    try:    
        mazo_descarte = CartaService(db).obtener_mazo_draft(id_partida)            
        cartas = [
            {"id": carta.id_carta, "nombre": carta.nombre}
            for carta in mazo_descarte
        ]
        return cartas
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No se pudo obtener el mazo de descarte. Error: {e}"
        )


def ids_asesino_complice(db, id_partida: int):
    """
    Metodo que dado el ID de una partida, devuelve el ID del asesino, y el ID del cómplice
    si es que la partida tiene 5 ó 6 jugadores.
    
    Parameters
        ----------
        db: Dependency
            Base de datos
        
        id_partida: int
            ID de la partida para la cual se obtiene los IDs de asesino y complice
        
        Returns
        -------
        dict[str, int]
            Diccionario con ID de asesino y ID de cómplice en caso de 5 ó 6 jugadores
            {"asesino-id": id_asesino}  / {"asesino-id": id_asesino, "complice-id": id_complice} 
    """
    partida = PartidaService(db).obtener_por_id(id_partida)
    if partida.cantJugadores >=5:
        carta_asesino = db.query(Carta).filter_by(partida_id=id_partida, tipo="secreto", nombre="murderer").first()
        asesino_id = carta_asesino.jugador_id
        carta_complice = db.query(Carta).filter_by(partida_id=id_partida, tipo="secreto", nombre="accomplice").first()
        complice_id = carta_complice.jugador_id
    
        return {"asesino-id": asesino_id, "complice-id": complice_id}
    
    else:
        carta_asesino = db.query(Carta).filter_by(partida_id=id_partida, tipo="secreto", nombre="murderer").first()
        asesino_id = carta_asesino.jugador_id
    
        return {"asesino-id": asesino_id}


def robar_secreto(id_partida: int, id_jugador_turno: int, id_jugador_destino:  int, id_unico_secreto: int, db) -> dict:
    """
    Roba el secreto revelado de un jugador en una partida específica,
    y se lo agrega boca abajo a los secretos propios o de otro jugador.
    
    Parameters
    ----------
    id_jugador_turno: int
        ID del jugador del turno que robará un secreto de otro jugador.
    
    id_jugador_destino: int
        ID del jugador que recibirá el secreto robado.

    id_partida: int
        ID de la partida para la cual se obtiene los secretos.
    
    id_unico_secreto: int
        ID del secreto que debe ser ocultado
    
    Returns
    -------
    secreto_robado: dict
        diccionario con el id del secreto robado. {"id-secreto": secreto.id}
    """
    partida = PartidaService(db).obtener_por_id(id_partida)
    if not partida:
        raise ValueError(f"No se ha encontrado la partida con el ID:{id_partida}")
    jugador_turno = JugadorService(db).obtener_jugador(id_jugador_turno)
    if not jugador_turno:
        raise ValueError(f"No se ha encontrado el jugador con el ID: {id_jugador_turno}")
    jugador_destino = JugadorService(db).obtener_jugador(id_jugador_destino)
    if not jugador_destino:
        raise ValueError(f"No se ha encontrado el jugador con el ID: {id_jugador_destino}")
    if jugador_turno.id != partida.turno_id:
        raise ValueError(f"Solo el jugador del turno puede realizar esta acción")
    #secreto_a_robar: Carta
    #secreto_a_robar = self._db.get(Carta, id_unico_secreto)
    secreto_a_robar = CartaService(db).obtener_carta_por_id(id_unico_secreto)
    if not secreto_a_robar:
        raise ValueError(f"No se ha encontrado el secreto con el ID:{id_unico_secreto}")
    if secreto_a_robar.tipo != "secreto":
        raise ValueError(f"La carta no pertenece a la categoría secreto")
    if secreto_a_robar.partida_id != id_partida:
        raise ValueError(f"El secreto con el ID:{id_unico_secreto} no pertenece a la partida con el ID: {id_partida}")
    if not secreto_a_robar.bocaArriba:
        raise ValueError(f"No se puede robar un secreto que está oculto!")
    secreto_robado = CartaService(db).robar_secreto(secreto_a_robar, id_jugador_destino)

    return secreto_robado


def revelarSecreto(id_partida: int, id_jugador_turno: int, id_unico_secreto: int, db) -> Carta:
    """
    Revela el secreto de un jugador en una partida específica
    
    
    Parameters
    ----------
    id_partida: int
        ID de la partida en la que se revelará un secreto.

    id_jugador_turno: int
        ID del jugador del turno que revelará un secreto de otro jugador.
        
    id_unico_secreto: int
        ID del secreto que debe ser revelado
    
    Returns
    -------
    secreto_revelado: Carta
        Carta secreto revelada.
    """
    partida = PartidaService(db).obtener_por_id(id_partida)
    if not partida:
        raise ValueError(f"No se ha encontrado la partida con el ID:{id_partida}")
    jugador_turno = JugadorService(db).obtener_jugador(id_jugador_turno)
    if not jugador_turno:
        raise ValueError(f"No se ha encontrado el jugador con el ID: {id_jugador_turno}")
    if jugador_turno.id != partida.turno_id:
        raise ValueError(f"Solo el jugador del turno puede realizar esta acción")
    secreto_a_revelar = CartaService(db).obtener_carta_por_id(id_unico_secreto)
    if not secreto_a_revelar:
        raise ValueError(f"No se ha encontrado el secreto con el ID:{id_unico_secreto}")
    if secreto_a_revelar.tipo != "secreto":
        raise ValueError(f"La carta no pertenece a la categoría secreto")
    if secreto_a_revelar.partida_id != id_partida:
        raise ValueError(f"El secreto con el ID:{id_unico_secreto} no pertenece a la partida con el ID: {id_partida}")
    if secreto_a_revelar.bocaArriba:
        raise ValueError(f"El secreto ya está revelado!")
    secreto_revelado = CartaService(db).revelar_secreto(secreto_a_revelar.id)

    return secreto_revelado


def ocultarSecreto(id_partida: int, id_jugador_turno: int, id_unico_secreto: int, db) -> Carta:
    """
    Oculta el secreto de un jugador en una partida específica


    Parameters
    ----------
    id_partida: int
        ID de la partida en la que se ocultará un secreto.

    id_jugador_turno: int
        ID del jugador del turno que ocultará un secreto de otro jugador.
        
    id_unico_secreto: int
        ID del secreto que debe ser ocultado
    
    Returns
    -------
    secreto_ocultado: Carta
        Carta secreto ocultada.
    """
    partida = PartidaService(db).obtener_por_id(id_partida)
    if not partida:
        raise ValueError(f"No se ha encontrado la partida con el ID:{id_partida}")
    jugador_turno = JugadorService(db).obtener_jugador(id_jugador_turno)
    if not jugador_turno:
        raise ValueError(f"No se ha encontrado el jugador con el ID: {id_jugador_turno}")
    if jugador_turno.id != partida.turno_id:
        raise ValueError(f"Solo el jugador del turno puede realizar esta acción")
    secreto_a_ocultar = CartaService(db).obtener_carta_por_id(id_unico_secreto)
    if not secreto_a_ocultar:
        raise ValueError(f"No se ha encontrado el secreto con el ID:{id_unico_secreto}")
    if secreto_a_ocultar.tipo != "secreto":
        raise ValueError(f"La carta no pertenece a la categoría secreto")
    if secreto_a_ocultar.partida_id != id_partida:
        raise ValueError(f"El secreto con el ID:{id_unico_secreto} no pertenece a la partida con el ID: {id_partida}")
    if not secreto_a_ocultar.bocaArriba:
        raise ValueError(f"El secreto ya está oculto!")
    secreto_ocultado = CartaService(db).ocultar_secreto(secreto_a_ocultar.id)

    return secreto_ocultado


def jugar_carta_evento(id_partida: int, id_jugador: int, id_carta: int, db) -> Carta:
    
    partida = PartidaService(db).obtener_por_id(id_partida)
    if partida is None:
        raise ValueError(f"No se ha encontrado la partida con el ID:{id_partida}")
    
    jugador = JugadorService(db).obtener_jugador(id_jugador)
    if jugador is None:
        raise ValueError(f"No se encontro el jugador {id_jugador}.")
    
    if partida.iniciada == False:
        raise ValueError(f"Partida no iniciada")
    
    if partida.turno_id != id_jugador:
        raise ValueError(f"El jugador no esta en turno.")
    
    if jugador.partida_id != id_partida:
        raise ValueError(f"El jugador con ID {id_jugador} no pertenece a la partida {id_partida}.")
    
    
    if partida.iniciada == False:
        raise ValueError(f"Partida no iniciada")
    
    jugador = JugadorService(db).obtener_jugador(id_jugador)
    if jugador is None:
        raise ValueError(f"No se encontro el jugador {id_jugador}.")
    
    if jugador.partida_id != id_partida:
        raise ValueError(f"El jugador con ID {id_jugador} no pertenece a la partida {id_partida}.")
    
    if partida.turno_id != id_jugador:
        raise ValueError(f"El jugador no esta en turno.")
    
    desgracia_social = PartidaService(db).desgracia_social(id_partida, id_jugador)
    if desgracia_social:
        raise ValueError(f"El jugador {id_jugador} esta en desgracia social")

    cartas_mano = CartaService(db).obtener_mano_jugador(id_jugador, id_partida)
    
    no_mas_eventos = CartaService(db).evento_jugado_en_turno(id_jugador)
    
    if no_mas_eventos == True:
        raise ValueError(f"Solo se puede jugar una carta de evento por turno.")
    
    print("Se verifica que no haya otro evento jugado en turno")
    if no_mas_eventos == True:
        raise ValueError(f"Solo se puede jugar una carta de evento por turno.")
    print("Se verifico que no hay eventos jugados en el turno")
            
    en_mano = False
    for c in cartas_mano:
        if c.id_carta == id_carta:
            en_mano = True
    if en_mano == False:
        raise ValueError(f"La carta no se encuentra en la mano del jugador.")
    
    carta_evento = CartaService(db).obtener_carta_de_mano(id_carta, id_jugador)
    
    if carta_evento.partida_id != id_partida:
        raise ValueError(f"La carta seleccionada no pertence a la partida")
    
    if carta_evento.tipo != "Event":
        raise ValueError(f"La carta no es de tipo evento y no puede ser jugada como tal.")
    else:
        carta_evento.ubicacion = "evento_jugado"
        carta_evento.bocaArriba = True
        db.commit()
    db.refresh(carta_evento)
    
    return carta_evento


def verif_evento(evento: str, id_carta: int) -> bool:
    carta = next((v for v in cartasDict.values() if v["id"] == id_carta), None)
    if carta is None:
        return False
    return (evento == carta["carta"])

def verif_jugador_objetivo(id_partida: int, id_jugador: int, id_objetivo: int, db):
    jugador_objetivo = JugadorService(db).obtener_jugador(id_objetivo)
    if jugador_objetivo is None:
        raise ValueError(f"No se encontro el objetivo {id_objetivo}.")
    if id_objetivo == id_jugador:
        raise ValueError(f"El efecto de evento no puede aplicar sobre el jugador que tiro la carta.")
    if id_partida != jugador_objetivo.partida_id:
        raise ValueError(f"El jugador al que se quiere aplicar el evento no pertence a la partida.")
    

def jugar_look_into_ashes(id_partida: int, id_jugador: int, id_carta_objetivo: int, db):

    carta_evento_jugada = CartaService(db).obtener_cartas_jugadas(id_partida,
                                                        id_jugador,
                                                        "Look into the ashes",
                                                        "evento_jugado"
                                                        )
    
    if not carta_evento_jugada:
        raise ValueError(f"No se jugo el evento Look Into The Ashes.")
    
    # carta_evento_jugada = carta_evento_jugada[0]
    # if id_carta_objetivo == 20:
    #     CartaService(db).anular_look_into(id_jugador, carta_evento_jugada.id)
    #     return True
            
    ultimas_5 = CartaService(db).obtener_cartas_descarte(id_partida, 5)
    entre_top5 = False
    for c in ultimas_5:
        if id_carta_objetivo == c.id_carta:
            entre_top5 = True
    if entre_top5 == False:
        raise ValueError(f"La carta a robar no esta entre las top 5 cartas del mazo descarte")
    else:
        CartaService(db).tomar_into_the_ashes(id_partida, id_jugador, id_carta_objetivo)


def revelarSecretoPropio(id_partida: int, id_jugador: int, id_unico_secreto: int, db) -> Carta:
    """
    Revela el secreto de un jugador en una partida específica
    
    
    Parameters
    ----------
    id_partida: int
        ID de la partida en la que se revelará un secreto.

    id_jugador: int
        ID del jugador del turno que revelará un secreto propio.
        
    id_unico_secreto: int
        ID del secreto que debe ser revelado
    
    Returns
    -------
    secreto_revelado: Carta
        Carta secreto revelada.
    """
    partida = PartidaService(db).obtener_por_id(id_partida)
    if not partida:
        raise ValueError(f"No se ha encontrado la partida con el ID:{id_partida}")
    jugador = JugadorService(db).obtener_jugador(id_jugador)
    if not jugador:
        raise ValueError(f"No se ha encontrado el jugador con el ID: {id_jugador}")
    if jugador.partida_id != partida.id:
        raise ValueError(f"El jugador no pertenece a la partida indicada")
    secreto_a_revelar = CartaService(db).obtener_carta_por_id(id_unico_secreto)
    if not secreto_a_revelar:
        raise ValueError(f"No se ha encontrado el secreto con el ID:{id_unico_secreto}")
    if secreto_a_revelar.tipo != "secreto":
        raise ValueError(f"La carta no pertenece a la categoría secreto")
    if secreto_a_revelar.partida_id != id_partida:
        raise ValueError(f"El secreto con el ID:{id_unico_secreto} no pertenece a la partida con el ID: {id_partida}")
    if secreto_a_revelar.bocaArriba:
        raise ValueError(f"El secreto ya está revelado!")
    secreto_revelado = CartaService(db).revelar_secreto(secreto_a_revelar.id)

    return secreto_revelado


def abandonarPartida(id_partida: int, id_jugador: int, db) -> dict:
    """
    Se elimina el jugador de una partida dado su ID y el ID de la partida.
     Si el jugador es el anfitrión, se elimina la partida y todos sus jugadores.
    
    
    Parameters
    ----------
    id_partida: int
        ID de la partida que abandonará el jugador
    
    id_jugador: int
        ID del jugador que abandonará la partida

    Returns
    -------
    diccionario: dict
        Diccionario que contiene datos según si el que abandona es el anfitrion o un invitado.
            En caso que sea el anfitrion:
                {"rol":"anfitrion"}
            En caso que sea un invitado: 
                {"rol":"invitado",
                    "id_jugador": int,
                    "nombre_jugador": str,
                    "jugadoresRestantes": int
                }
    """

    partida = PartidaService(db).obtener_por_id(id_partida)
    if not partida:
        raise ValueError(f"No se ha encontrado la partida con el ID:{id_partida}")
    if partida.iniciada:
        raise ValueError("No se puede abandonar la partida una vez iniciada!")
    jugador = JugadorService(db).obtener_jugador(id_jugador)
    if not jugador:
        raise ValueError(f"No se ha encontrado el jugador con el ID: {id_jugador}")
    if jugador.partida_id != partida.id:
        raise ValueError(f"El jugador no pertenece a la partida indicada")
    
    jugadorID = jugador.id
    jugadorNombre = jugador.nombre

    try:
        # Si el jugador es anfitrión, eliminar la partida y todos los jugadores
        if jugador.id == partida.anfitrionId:
            # Eliminar a todos los jugadores
            for jugador in partida.jugadores:
                JugadorService(db).eliminar_jugador(jugador)

            # Eliminar la partida
            PartidaService(db).eliminar_partida(partida)

            return {"rol":"anfitrion"}

        # El jugador no es el anfitrión
        else:
            JugadorService(db).eliminar_jugador(jugador)
            cantJugadores = PartidaService(db).actualizar_cant_jugadores(id_partida)

            return {"rol":"invitado",
                    "id_jugador": jugadorID,
                    "nombre_jugador": jugadorNombre,
                    "jugadoresRestantes": cantJugadores,
                    }

    except Exception as e:
        raise ValueError(f"Hubo un error al abandonar la partida: {str(e)}")


def eliminarPartida(id_partida: int, db):
    partida = PartidaService(db).obtener_por_id(id_partida)
    db.query(SetJugado).filter(SetJugado.partida_id == id_partida).delete()
    for jugador in partida.jugadores:
        JugadorService(db).eliminar_jugador(jugador)
    for carta in partida.cartas:
        CartaService(db).eliminar_carta(carta)
    PartidaService(db).eliminar_partida(partida)

def verif_cantidad(id_partida: int, cantidad: int, db):
    if cantidad < 1 or cantidad > 5:
        raise ValueError("La cantidad debe estar entre 1 y 5 cartas.")
    cantidad_cartas_descarte = CartaService(db).obtener_cartas_descarte(id_partida, cantidad)
    if len(cantidad_cartas_descarte) < cantidad:
        raise ValueError("No hay suficientes cartas en el mazo de descarte.")

def enviar_carta(id_partida: int, id_carta: int, id_objetivo: int, db):

    partida = PartidaService(db).obtener_por_id(id_partida)

    carta_a_enviar = CartaService(db).obtener_carta(id_carta)

    CartaService(db).mover_carta_a_objetivo(partida, carta_a_enviar, id_objetivo)





def verif_send_card(id_partida: int, id_carta: int, id_jugador: int, id_objetivo: int, db) -> bool:

    se_puede_enviar = False
    
    partida = PartidaService(db).obtener_por_id(id_partida)
    if partida is None:
        raise ValueError(f"No se ha encontrado la partida con el ID:{id_partida}")
    
    jugador = JugadorService(db).obtener_jugador(id_jugador)
    if jugador is None:
        raise ValueError(f"No se encontro el jugador {id_jugador}.")
    
    jugador_objetivo = JugadorService(db).obtener_jugador(id_objetivo)
    if jugador_objetivo is None:
        raise ValueError(f"No se encontro el jugador objetivo {id_objetivo}.")
    
    if partida.iniciada == False:
        raise ValueError(f"Partida no iniciada")
    
    if jugador.partida_id != id_partida:
        raise ValueError(f"El jugador con ID {id_jugador} no pertenece a la partida {id_partida}.")
    
    if jugador_objetivo.partida_id != id_partida:
        raise ValueError(f"El jugador con ID {id_objetivo} no pertenece a la partida {id_partida}.")
    
    desgracia_social = PartidaService(db).desgracia_social(id_partida, id_jugador)
    if desgracia_social:
        raise ValueError(f"El jugador {id_jugador} esta en desgracia social")
    
    desgracia_social = PartidaService(db).desgracia_social(id_partida, id_objetivo)
    if desgracia_social:
        raise ValueError(f"El jugador objetivo {id_objetivo} esta en desgracia social")

    cartas_mano = CartaService(db).obtener_mano_jugador(id_jugador, id_partida)
    en_mano = False
    
    for c in cartas_mano:
        if c.id_carta == id_carta:
            en_mano = True
    if en_mano == False:
        raise ValueError(f"La carta no se encuentra en la mano del jugador.")
    
    else:
        se_puede_enviar = True

    return se_puede_enviar