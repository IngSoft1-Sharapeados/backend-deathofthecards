from game.partidas.models import Partida
from game.jugadores.models import Jugador
from game.cartas.models import Carta
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
    
    
def jugar_carta_evento(id_partida: int, id_jugador: int, id_carta: int, db) -> Carta:
    
    partida = PartidaService(db).obtener_por_id(id_partida)
    if partida is None:
        raise ValueError(f"No se ha encontrado la partida con el ID:{id_partida}")
    
    if partida.iniciada == False:
        raise ValueError(f"Partida no iniciada")
    
    jugador = JugadorService(db).obtener_jugador(id_jugador)
    if jugador is None:
        raise ValueError(f"No se encontro el jugador {id_jugador}.")
    
    if jugador.partida_id != id_partida:
        raise ValueError(f"El jugador con ID {id_jugador} no pertenece a la partida {id_partida}.")
    
    if partida.turno_id != id_jugador:
        raise ValueError(f"El jugador no esta en turno.")
    
    cartas_mano = CartaService(db).obtener_mano_jugador(id_jugador, id_partida)
    
    no_mas_eventos = CartaService(db).evento_jugado_en_turno(id_jugador)
    
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
    
    if carta_evento.tipo != "Event":
        raise ValueError(f"La carta no es de tipo evento y no puede ser jugada como tal.")
    else:
        carta_evento.ubicacion = "evento_jugado"
        db.commit()
    db.refresh(carta_evento)
    
    return carta_evento
    

def jugar_carta_evento(id_partida: int, id_jugador: int, id_carta: int, db) -> Carta:
    
    partida = PartidaService(db).obtener_por_id(id_partida)
    if partida is None:
        raise ValueError(f"No se ha encontro la partida con el ID:{id_partida}")
    
    if partida.iniciada == False:
        raise ValueError(f"Partida no iniciada")
    
    jugador = JugadorService(db).obtener_jugador(id_jugador)
    if jugador is None:
        raise ValueError(f"No se encontro el jugador {id_jugador}.")
    
    if jugador.partida_id != id_partida:
        raise ValueError(f"El jugador con ID {id_jugador} no pertenece a la partida {id_partida}.")
    
    if partida.turno_id != id_jugador:
        raise ValueError(f"El jugador no esta en turno.")
    
    cartas_mano = CartaService(db).obtener_mano_jugador(id_jugador, id_partida)
    
    no_mas_eventos = CartaService(db).evento_jugado_en_turno(id_jugador)
    
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

    carta_evento_jugada = CartaService(db).obtener_evento_jugado(id_partida,
                                                        id_jugador,
                                                        "Look into the ashes")
    print(carta_evento_jugada)
    if not carta_evento_jugada:
        raise ValueError(f"No se jugo el evento Look Into The Ashes.")
            
    ultimas_5 = mostrar_cartas_descarte(id_partida, id_jugador, 5, db)
    entre_top5 = False
    for c in ultimas_5:
        if id_carta_objetivo == c["id"]:
            entre_top5 = True
    if entre_top5 == False:
        raise ValueError(f"La carta a robar no esta entre las top 5 cartas del mazo descarte")
    else:
        CartaService(db).tomar_into_the_ashes(id_jugador, id_carta_objetivo)