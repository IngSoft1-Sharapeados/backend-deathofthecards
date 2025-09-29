from typing import List, Optional

from game.partidas.dtos import PartidaDTO
from game.partidas.models import Partida
from game.jugadores.models import Jugador
from game.jugadores.schemas import JugadorDTO
import random

from datetime import date
from game.partidas.utils import distancia_fechas
import json


class PartidaService:
    def __init__(self, db):
        self._db = db
        #self._JugadorService = JugadorService(db)
    
    def crear(self, partida_dto: PartidaDTO) -> Partida:
        """
        Crea una nueva partida en la base de datos.
        
        Parameters
        ----------
        partida_dto: PartidaDTO
            DTO con la info de la partida a crear
        
        Returns
        -------
        Partida
            La partida creada
        """
        nueva_partida = Partida(
            nombre=partida_dto.nombrePartida,
            cantJugadores=0,
            anfitrionId=0,
            iniciada=False,
            maxJugadores=partida_dto.maxJugadores,
            minJugadores=partida_dto.minJugadores,
            turno_id=1,
        )
        self._db.add(nueva_partida)
        self._db.flush()
        self._db.commit()
        self._db.refresh(nueva_partida)
        return nueva_partida

    def asignar_anfitrion(self, partida: Partida, id_jugador: int):
        partida.anfitrionId = id_jugador
        partida.cantJugadores += 1
        self._db.commit()
        self._db.refresh(partida)

    def obtener_por_id(self, id_partida: int) -> Partida:
        """
        Obtiene una partida por su ID.
        
        Parameters
        ----------
        id_partida: int
            ID de la partida a obtener
        
        Returns
        -------
        Partida
            La partida obtenida
        """
        partida = self._db.query(Partida).filter(Partida.id == id_partida).first()
        # if not partida:
        #     raise Exception("No se encontró la partida con el ID proporcionado.")
        return partida
        
    def listar(self) -> List[Partida]:
        """
        Lista las partidas en la base de datos.

        Returns
        -------
        List[Partidas]
            lista de las partidas
        """
        
        return (self._db.query(Partida)
                .filter(Partida.iniciada == False)
                .all())
    # servicio unir jugador a partida
    def unir_jugador(self, id_partida, jugador_creado: Jugador):
        """
        Une un jugador a una partida.

        Returns
        -------
        Partida
            La partida actualizada con el nuevo jugador
        """
        
        partida = self._db.query(Partida).filter(Partida.id == id_partida).first()
        jugador = self._db.query(Jugador).filter(Jugador.id == jugador_creado.id).first()
        # agregar jugador a la partida
        if partida.cantJugadores < partida.maxJugadores:
            # uso crear jugador del servicio jugador
            self._db.add(jugador)
            partida.cantJugadores += 1
            self._db.commit()
            self._db.refresh(partida)
        else:
            raise Exception("La partida ya está llena.")    
        
    def iniciar(self, id_partida: int, id_jugar_solicitante) -> None:
        """
        Inicia una partida por su ID.
        
        Parameters
        ----------
        id_partida: int
            ID de la partida a iniciar
        """
        partida = self._db.query(Partida).filter(Partida.id == id_partida).first()
        if not partida:
            raise ValueError(f"No se encontró la partida con ID {id_partida}")
        if partida.anfitrionId != id_jugar_solicitante:
            raise ValueError("Solo el anfitrión puede iniciar la partida")
        if partida.iniciada:
            raise ValueError(f"La partida con ID {id_partida} ya está iniciada")
        if partida.cantJugadores < partida.minJugadores:
            raise ValueError(f"No hay suficientes jugadores para iniciar la partida (mínimo {partida.minJugadores})")
            
        partida.iniciada = True
        self._db.commit()
        self._db.refresh(partida)
        return partida

    def obtener_turno_actual(self, id_partida) -> int:
        partida = PartidaService(self._db).obtener_por_id(id_partida)
        return partida.turno_id
    
    def set_turno_actual(self, id_partida: int, id_jugador: int):
        partida = self.obtener_por_id(id_partida)
        partida.turno_id = id_jugador
        self._db.commit()        # usar self._db
        self._db.refresh(partida)
        return id_jugador
    
    def orden_turnos(self, id_partida: int, jugadores: list[Jugador]) -> list[int]:
        """
        Genera un orden de turnos para los jugadores en la partida.

        Parameters
        ----------
        jugadores: list[Jugador]
            Lista de jugadores en la partida

        Returns
        -------
        dict[int, int]
            Diccionario con el orden de turnos (clave: turno, valor: id del jugador)
        """
        partida = self._db.query(Partida).filter(Partida.id == id_partida).first()
        # primer_turno = min(jugadores, key=lambda jugador: distancia_fechas(jugador.fecha_nacimiento))
        min_dist = 365    
        for jugador in jugadores:
            dist_jug = distancia_fechas(jugador.fecha_nacimiento)
            if dist_jug < min_dist:
                min_dist = dist_jug
                jugador_turno_inicial = jugador
            elif dist_jug == min_dist:
                jugador_min = random.choice([jugador_turno_inicial, jugador])
                jugador_turno_inicial = jugador_min
        jugadores_copy = jugadores.copy()
        jugadores_copy.remove(jugador_turno_inicial)
        orden_de_turnos = [jugador_turno_inicial.id] 
        random.shuffle(jugadores_copy)
        for jugador in jugadores_copy:
            orden_de_turnos.append(jugador.id)
        partida.ordenTurnos = json.dumps(orden_de_turnos)
        self._db.commit()
        self._db.refresh(partida)
        return orden_de_turnos