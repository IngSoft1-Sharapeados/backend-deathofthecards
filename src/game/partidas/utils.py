from game.partidas.models import Partida
from game.jugadores.models import Jugador
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

def mostrar_cartas_descarte(id_partida: int, cantidad:  int,  db):

    if PartidaService(db).obtener_por_id(id_partida) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontro la partida con el ID {id_partida}.")
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

    if PartidaService(db).obtener_por_id(id_partida) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontro la partida con el ID {id_partida}.")

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
    
def robar_carta_draft(id_partida: int, id_jugador: int, carta_tomada: int, db):
    """
    Controla la acción de tomar cartas del draft, manejando errores comunes.
    """
    partida = PartidaService(db).obtener_por_id(id_partida)
    if partida is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Partida no encontrada."
        )
    
    jugador = JugadorService(db).obtener_jugador(id_jugador)
    if jugador is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Jugador no encontrado."
        )

    turno_actual = PartidaService(db).obtener_turno_actual(id_partida)
    if turno_actual != id_jugador:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No es tu turno para tomar cartas del draft."
        )

    mazo = CartaService(db).obtener_mazo_draft(id_partida)
    ids_cartas = [carta.id_carta for carta in mazo]
    if carta_tomada not in ids_cartas:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La carta seleccionada no se encuentra en el draft."
        )

    cartas_en_mano = CartaService(db).obtener_mano_jugador(id_jugador, id_partida)
    if len(cartas_en_mano) >= 6:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puedes tener más de 6 cartas en la mano."
        )

    try:   
        CartaService(db).tomar_cartas_draft(id_partida, id_jugador, carta_tomada)

        return {"detail": "Cartas tomadas correctamente."}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al tomar cartas del draft: {e}"
        )
