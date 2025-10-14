from game.partidas.models import Partida
from game.jugadores.models import Jugador
from game.jugadores.schemas import JugadorOut

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