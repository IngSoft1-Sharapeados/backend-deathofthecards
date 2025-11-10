from game.partidas.models import Partida, VotacionEvento
from game.jugadores.models import Jugador
from game.cartas.models import Carta, SetJugado
from game.cartas.constants import *
from game.jugadores.schemas import JugadorOut
from game.partidas.schemas import PartidaData, PartidaResponse, IniciarPartidaData, AccionGenericaPayload, Mensaje
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
    
    desgracia_social = determinar_desgracia_social(id_partida, id_jugador, db)
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
    """
    Verifica si un nombre (de carta) se corresponde con la carta dado su ID

    Parameters
    ------------
    evento: str
        String que representa el nombre de una carta

    id_carta: int
        ID de representación de la carta
        (es decir, no el ID único, sino el usado para representar a todas las cartas del mismo tipo)
    """
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


def validar_accion_evento(id_partida: int, id_jugador: int, id_carta: int, db) -> Carta:
    """
    Copia de 'jugar_carta_evento' que SÓLO VALIDA y no modifica la BBDD.
    Retorna el objeto Carta si es válido, o lanza ValueError si no.
    """
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
    
    desgracia_social = determinar_desgracia_social(id_partida, id_jugador, db)
    if desgracia_social:
        raise ValueError(f"El jugador {id_jugador} esta en desgracia social")

    cartas_mano = CartaService(db).obtener_mano_jugador(id_jugador, id_partida)
    
    no_mas_eventos = CartaService(db).evento_jugado_en_turno(id_jugador)
    
    if no_mas_eventos == True:
        raise ValueError(f"Solo se puede jugar una carta de evento por turno.")
           
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
    
    # Si todo es válido, retorna la carta (sin moverla)
    return carta_evento

    
def votacion_activada(id_partida: int, db):
    PartidaService(db).inicia_votacion(id_partida)

    
def jugar_point_your_suspicions(id_partida: int, id_jugador: int, id_votante: int, id_votado: int, db): 
    ps = PartidaService(db)
    js = JugadorService(db)
    cs = CartaService(db)
    
    # Verifico que el evento Point Your Suspicions este efectivamente jugado.
    carta_evento_jugada = cs.obtener_cartas_jugadas(id_partida,
                                                    id_jugador,
                                                    "Point your suspicions",
                                                    "evento_jugado"
                                                    )
    if not carta_evento_jugada:
        raise ValueError(f"No se jugo el evento Point Your Suspicions.")
    
    partida = ps.obtener_por_id(id_partida)
    if partida.votacion_activa == False:
        raise ValueError(f"No hay votacion en proceso actualmente.")
    
    votante = js.obtener_jugador(id_votante)
    votado = js.obtener_jugador(id_votado)
    
    # Chequeo que el jugador votante exista y este dentro de la partida.
    if not votante:
        raise ValueError(f"No se encontro el votante.")
    
    if votante.partida_id != id_partida:
        raise ValueError(f"El jugador votante no pertenece a la partida.")
    
    # Chequeo que el jugador votado exista y este dentro de la partida.
    if not votado:
        raise ValueError(f"No se encontro el votado.")
    
    if votado.partida_id != id_partida:
        raise ValueError(f"El jugador votado no pertenece a la partida.")
    
    ps.registrar_voto(id_partida, id_votante, id_votado)
    total_votos = ps.numero_de_votos(id_partida)
    
    total_jugadores = len(partida.jugadores)
    
    if total_votos == total_jugadores:
        sospechoso = ps.resolver_votacion(id_partida)
        ps.fin_votacion(id_partida)
        ps.borrar_votacion(id_partida)
        return sospechoso

def iniciar_accion_cancelable(id_partida: int, id_jugador: int, accion: AccionGenericaPayload, db):
    """
    Método encargado de guardar el estado de contexto de la partida,
    abriendo paso a la ventana de respuesta de una potencial Not So Fast

    Parameters
    -----------
    id_partida: int
        ID de la partida donde se iniciará la acción (set, evento)

    id_jugador: int
        ID del jugador que jugará el set o evento
    
    accion: AccionGenericaPayload
        Un payload genérico que el frontend construye para cualquier acción
        que pueda ser cancelada (Eventos, Sets, etc.).

    Returns
    ----------
    (accion_context, mensaje): tuple
        -accion_context- es un diccionario que contiene mayor detalle sobre
        el contexto de la partida: tipo y nombre de accion jugada, lista de IDs de cartas jugadas,
        jugador que ejecutó la acción, el payload necesario que el endpoint original necesitará
        si la acción se ejecuta, la pila de respuestas (pila de cartas NSF, en principio vacía),
        y el id de representación de esa carta.
         -mensaje- es un string que informa que un jugador ejecutó determinada acción, y en caso de
         haberlo hecho sobre otro jugador, sobre qué otro jugador

    """
    partida = PartidaService(db).obtener_por_id(id_partida)
    
    if partida is None:
        raise ValueError(f"No se ha encontrado la partida con el ID:{id_partida}") 
    
    if partida.iniciada == False:
        raise ValueError(f"Partida no iniciada") 
    
    if partida.accion_en_progreso:
        raise ValueError("Ya hay una acción en progreso.") 
    
    jugador = JugadorService(db).obtener_jugador(id_jugador)
    if jugador is None:
        raise ValueError(f"No se ha encontrado el jugador {id_jugador}.") 

    if jugador.partida_id != id_partida:
        raise ValueError(f"El jugador con ID {id_jugador} no pertenece a la partida {id_partida}.") 
    
    if partida.turno_id != id_jugador:
        raise ValueError(f"El jugador no esta en turno.") 

    # 1. Empaquetar la acción (confiando en los datos del frontend)
    accion_context = {
        "tipo_accion": accion.tipo_accion,
        "cartas_originales_db_ids": accion.cartas_db_ids, # Confiamos en esta lista
        "id_jugador_original": id_jugador,
        "nombre_accion": accion.nombre_accion,
        "payload_original": accion.payload_original,
        "pila_respuestas": [],    
        "id_carta_tipo_original": accion.id_carta_tipo_original
    }
    
    # 2. Iniciar la "pausa" en la BBDD y establecer la accion que se quiere realizar
    PartidaService(db).iniciar_accion(id_partida, accion_context)

    # 3. Construir y enviar el Broadcast (con nombres)
    jugador_nombre = jugador.nombre if jugador else f"Jugador {id_jugador}"
    
    mensaje = f"{jugador_nombre} jugó '{accion.nombre_accion}'"
    
    # Chequeamos si la acción que se quiere realizar involucra un jugador objetivo (por ej. al robar un secreto, jugar another victim)
    id_objetivo = None
    if isinstance(accion.payload_original, dict):
        id_objetivo = accion.payload_original.get('id_objetivo')
    
    if id_objetivo:
        objetivo = JugadorService(db).obtener_jugador(id_objetivo)
        
        if objetivo is None:
            raise ValueError(f"No se ha encontrado el jugador {id_objetivo}.") 
        
        if objetivo.partida_id != id_partida:
            raise ValueError(f"El jugador con ID {id_objetivo} no pertenece a la partida {id_partida}.") 
        
        objetivo_nombre = objetivo.nombre if objetivo else f"Jugador {id_objetivo}"
        mensaje += f" sobre {objetivo_nombre}"
    
    return accion_context, mensaje


def jugar_not_so_fast(id_partida: int, id_jugador: int, id_carta: int, db) -> dict:
    """
    Se encarga de jugar la carta Not So Fast.

    Parameters
    ----------
    id_partida: int
        ID de la partida donde se juega la carta NSF

    id_jugador: int
        ID del jugador que jugará la carta NSF

    id_carta: int
        ID de representación de la carta Not So Fast
        (es decir, no el ID único, sino el usado para representar a todas las cartas del mismo tipo)
    
    Return
    ---------
    accion_context: dict
        diccionario con el contexto de acción de la partida. Lo más importante es la pila de cartas NSF
    """
    
    partida = PartidaService(db).obtener_por_id(id_partida)
    
    if partida is None:
        raise ValueError(f"No se ha encontrado la partida con el ID:{id_partida}")
    
    if partida.iniciada == False:
        raise ValueError(f"Partida no iniciada")
    
    jugador = JugadorService(db).obtener_jugador(id_jugador)
    if jugador is None:
        raise ValueError(f"No se ha encontrado el jugador {id_jugador}.")

    if jugador.partida_id != id_partida:
        raise ValueError(f"El jugador con ID {id_jugador} no pertenece a la partida {id_partida}.")
    
    cartas_mano = CartaService(db).obtener_mano_jugador(id_jugador, id_partida)
    
    en_mano = False
    for c in cartas_mano:
        if c.id_carta == id_carta:
            en_mano = True
    if en_mano == False:
        raise ValueError(f"La carta no pertenece al jugador.")

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
    return accion_context


def resolver_accion_turno(id_partida: int, db):
    """
    Resuelve la acción (o no) llevada a cabo en el turno en una partida específica
    
    Parameters
    ----------
    id_partida: int
        ID de la partida donde se resuelve si la acción se ejecuta o no (set o evento jugado)
    
    Return
    ---------
    mensaje: str
        string que avisa que la acción fue ejecutada
    
    diccionario: dict
        Diccionario que contiene el contexto de accion de la partida, y el ID de la carta
        que queda en el tope del mazo de descarte.
    """
    # Obtener la acción pendiente (con bloqueo)
    partida = PartidaService(db).obtener_por_id(id_partida)
    if partida is None:
        raise ValueError(f"No se ha encontrado la partida con el ID:{id_partida}")
    
    if partida.iniciada == False:
        raise ValueError(f"Partida no iniciada")
        
    accion_context = PartidaService(db).obtener_accion_en_progreso(id_partida)    
    
    # Junta los IDs de las cartas NSF de la pila
    cartas_nsf_db_ids = [nsf["id_carta_db"] for nsf in accion_context["pila_respuestas"]]
    
    # Limpiar la pila 
    PartidaService(db).limpiar_accion_en_progreso(id_partida)

    cantidad_nsf = len(cartas_nsf_db_ids)
    
    if cantidad_nsf % 2 == 0:
        # Cantidad par de NSF: La acción original se realiza
        # Descartar solo las cartas NSF (de "en_la_pila" a "descarte")
        CartaService(db).descartar_cartas_de_pila(cartas_nsf_db_ids, id_partida)
        
        return "Acción ejecutada"

    else:
        # Cantidad impar de NSF: La acción original no se realiza
        # Descartar las cartas NSF
        CartaService(db).descartar_cartas_de_pila(cartas_nsf_db_ids, id_partida)

        # Obtener los datos de la acción original
        jugador_id_original = accion_context["id_jugador_original"]
        cartas_db_ids_originales = accion_context["cartas_originales_db_ids"]
        
        # Buscar los ID de representación (id_carta) correspondientes a los ID únicos
        cartas_a_descartar_query = (
            CartaService(db)._db.query(Carta.id_carta)
            .filter(Carta.id.in_(cartas_db_ids_originales))
        )
        lista_de_tipo_ids = [c[0] for c in cartas_a_descartar_query.all()]

        # Descartamos las cartas
        if lista_de_tipo_ids:
            CartaService(db).descartar_cartas(jugador_id_original, lista_de_tipo_ids)
            
        nueva_carta_tope = CartaService(db).obtener_cartas_descarte(id_partida, 1)
        id_carta_tope_descarte: int = nueva_carta_tope[0].id_carta if nueva_carta_tope else None

        return {"accion_context": accion_context, "tope_descarte": id_carta_tope_descarte}


def determinar_desgracia_social(id_partida: int, id_jugador: int, db) -> bool:
    """
    Recorre los secretos de un jugador y lo saca de estado de desgracia social o lo 
    agrega al mismo.
    
    Parameters
    ----------
    id_jugado: int
        ID del jugador al cual se pondra o sacara del estado desgracia social.

    id_partida: int
        ID de la partida para la cual se obtiene los secretos.
    
    Returns
    -------
    bool
        devuelve True en caso de que este en desgracia social o False en caso contrario.
    """
    PartidaService(db).obtener_por_id(id_partida)
    jugador = JugadorService(db).obtener_jugador(id_jugador)
    if jugador is None:
        raise ValueError(f"No se ha encontrado al jugador con id:{id_jugador}")
    secretos = CartaService(db).obtener_secretos_jugador(id_jugador, id_partida)
    if secretos is None:
        raise ValueError(f"No se ha encontrado los secretos del jugador{id_jugador} y la partida:{id_partida}")
    desgracia_social = PartidaService(db).desgracia_social(jugador, secretos)
    return desgracia_social


def ganar_por_desgracia_social(id_partida: int, db) -> bool:
    """
    Recorre todos los secretos de todos los jugadores vindo el estado de bocaArriba para
    determinar el resultado.
    
    Parameters

    id_partida: int
        ID de la partida para la cual se obtiene los secretos.
    
    Returns
    -------
    bool
        devuelve True en caso de que el asesino haya ganado y False en caso contrario.
    """
    partida = PartidaService(db).obtener_por_id(id_partida)
    resultado = PartidaService(db).ganar_desgracia_social(partida) 
    return resultado


def obtener_jugador_por_id_carta(id_partida: int, id_carta: int, db) -> int:
    """
    Determina el id de un jugador mediante una carta dada.
    
    Parameters

    id_partida: int
        ID de la partida para buscar al jugador.
    
    id_carta: int
        Id de la carta para buscar al jugador.
    
    Returns
    -------
    bool
        devuelve True en caso de que el asesino haya ganado y False en caso contrario.
    """
    partida = PartidaService(db).obtener_por_id(id_partida)
    if not partida:
        raise ValueError(f"No se ha encontrado la partida con el ID:{id_partida}")
    carta = CartaService(db).obtener_carta_por_id(id_carta)
    if not carta:
        raise ValueError(f"No se ha encontrado la carta con el ID:{id_carta}")
    jugador = JugadorService(db).obtener_jugador_id_carta(partida, carta)
    return jugador


def enviar_mensaje(id_partida: int, id_jugador: int, mensaje: Mensaje, db):
    # try/except porque el servicio levanta una excepcion HTTP
    # y si lo cambio fallan tests
    try:
        partida = PartidaService(db).obtener_por_id(id_partida)
    except Exception as e:
        if "No se encontró" in str(e.detail):
            raise ValueError(f"No se ha encontrado la partida con el ID:{id_partida}")
    if partida is None:
        raise ValueError(f"No se ha encontrado la partida con el ID:{id_partida}")
    
    if partida.iniciada == False:
        raise ValueError(f"Partida no iniciada")
    
    jugador = JugadorService(db).obtener_jugador(id_jugador)
    if jugador is None:
        raise ValueError(f"No se ha encontrado el jugador {id_jugador}.")

    if jugador.partida_id != id_partida:
        raise ValueError(f"El jugador con ID {id_jugador} no pertenece a la partida {id_partida}.")
    
    if len(mensaje.texto)>200:
        raise ValueError(f"Mensaje demasiado largo. No puede tener más de 200 caracteres")
    
    if mensaje.nombreJugador != jugador.nombre:
        raise ValueError("El nombre del jugador no coincide con el nombre del mensaje")
    
    return True
def enviar_carta(id_carta: int, id_objetivo: int, db):
    """
    funcion que llama al servicio para mover la carta
    
    parametros:
        id_carta: int (id de la carta que se quiere mover)
        id_objetivo: int (id del jugador a donde se quiere mover la carta)

    """

    CartaService(db).mover_carta_a_objetivo(id_carta, id_objetivo)





def verif_send_card(id_partida: int, id_carta: int, id_jugador: int, id_objetivo: int, db) -> bool:
    """
    funcion que se encarga de verificar si la carta se puede enviar

    parametros:

        id_partida: int (id de la partida donde se quiere enviar la carta)
        id_carta: int (id de la carta que se quiere enviar)
        id_jugador: int (id del jugador que quiere enviar)
        id_objetivo: int (id del jugador al que se le quiere enviar la carta)


    """


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
        if c.id == id_carta:
            en_mano = True
    if en_mano == False:
        raise ValueError(f"La carta no se encuentra en la mano del jugador.")
    
    else:
       
        se_puede_enviar = True

    return se_puede_enviar

def obtener_id_de_tipo(id_unico: int, db) -> int:
    """
    funcion que obtiene el id de tipo de la carta a travez del id unico

    parametros: 
        id_unico: int  (id unico de la carta en la base de datos)

    return:
        carta.id_carta: int  (id del tipo de carta, por ej 16 osea "not so fast")
    
    """
    carta = CartaService(db).obtener_carta_por_id(id_unico)

    return carta.id_carta