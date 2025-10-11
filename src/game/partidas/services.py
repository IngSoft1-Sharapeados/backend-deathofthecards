from typing import List, Optional
from fastapi import HTTPException, status
from game.partidas.dtos import PartidaDTO
from game.partidas.models import Partida
from game.jugadores.models import Jugador
from game.jugadores.schemas import JugadorDTO
import random
from game.cartas.services import CartaService
from typing import List, Dict, Any

from datetime import date
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
        if not partida:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No se encontró la partida con el ID proporcionado."
                )
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
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La partida ya tiene el máximo de jugadores."
                )
         
        
    def iniciar(self, id_partida: int, id_jugar_solicitante) -> Partida:
        """
        Inicia una partida por su ID.
        
        Parameters
        ----------
        id_partida: int
            ID de la partida a iniciar
        """
        partida = self._db.query(Partida).filter(Partida.id == id_partida).first()
        if not partida:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No se ha encontrado la partida"
            )
        if partida.anfitrionId != id_jugar_solicitante:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo el anfitrion puede iniciar la partida"
                )
        if partida.iniciada:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La partida ya ha sido iniciada"
                )
        if partida.cantJugadores < partida.minJugadores:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Aun no hay la cantidad suficiente de jugadores"
                )
            
        partida.iniciada = True
        self._db.commit()
        self._db.refresh(partida)
        return partida

    def obtener_turno_actual(self, id_partida) -> int:
        partida = PartidaService(self._db).obtener_por_id(id_partida)
        if not partida:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Partida with id {id_partida} not found."
            )

        return partida.turno_id
    
    def set_turno_actual(self, id_partida: int, id_jugador: int):
        partida = self.obtener_por_id(id_partida)
        partida.turno_id = id_jugador
        self._db.commit()
        self._db.refresh(partida)
        return id_jugador
    
    def avanzar_turno(self, id_partida: int) -> int:
        """
        Avanza al siguiente jugador según el orden de turnos y retorna el nuevo id de turno.
        """
        partida = self.obtener_por_id(id_partida)
        if not partida or not partida.ordenTurnos:
            raise ValueError("No existe orden de turnos para la partida")
        orden = json.loads(partida.ordenTurnos)
        if partida.turno_id not in orden:
            # si no está, setear el primero
            nuevo = orden[0]
            return self.set_turno_actual(id_partida, nuevo)
        idx = orden.index(partida.turno_id)
        nuevo_idx = (idx + 1) % len(orden)
        nuevo = orden[nuevo_idx]
        return self.set_turno_actual(id_partida, nuevo)
    
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

        min_dist = 365
        for jugador in jugadores:
            fecha = jugador.fecha_nacimiento
            f = date(2000, fecha.month, fecha.day)   # normalizo al año 2000
            agatha_birthDay = date(2000, 9, 15)
            dias_distancia = abs((f - agatha_birthDay).days)
            dist_jug = dias_distancia
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
    
    def manejar_accion_recoger(
    self, id_partida: int, id_jugador: int, cartas_draft_ids: List[int]) -> Dict[str, Any]:
        """
        Orchestrates the core game logic for the "pick up" action and
        returns a dictionary with all the necessary data for broadcasting.
        """
        carta_service = CartaService(self._db)

        # Validar el turno
        if self.obtener_turno_actual(id_partida) != id_jugador:
            raise HTTPException(status_code=403, detail="No es tu turno")

        mano_actual = carta_service.obtener_mano_jugador(id_jugador, id_partida)
        if len(mano_actual)+len(cartas_draft_ids) > 6:
            raise HTTPException(
                status_code=403,
                detail="No puedes tener más de 6 cartas en la mano."
            )

        # Tomo las cartas del draft que el jugador ha elegido
        if cartas_draft_ids:
            carta_service.tomar_cartas_draft(id_partida, id_jugador, cartas_draft_ids)
        
        cartas_del_draft_objs = [carta_service.obtener_carta(cid) for cid in cartas_draft_ids]

        # Tomo del deck si es necesario para completar la mano a 6 cartas
        mano_actual = carta_service.obtener_mano_jugador(id_jugador, id_partida)
        cartas_faltantes = max(0, 6 - len(mano_actual))
        cartas_del_mazo_robadas = []
        if cartas_faltantes > 0:
            cartas_del_mazo_robadas = carta_service.robar_cartas(id_partida, id_jugador, cartas_faltantes)
        
        # Actualizo el turno y el draft
        nuevo_turno_id = self.avanzar_turno(id_partida)
        carta_service.actualizar_mazo_draft(id_partida)

        # Obtengo el nuevo draft y la cantidad restante en el mazo
        nuevo_draft = carta_service.obtener_mazo_draft(id_partida)
        cantidad_final_mazo = carta_service.obtener_cantidad_mazo(id_partida)
        
        cartas_del_draft_dicts = [{"id": c.id_carta} for c in cartas_del_draft_objs]
        todas_las_cartas_nuevas = cartas_del_draft_dicts + cartas_del_mazo_robadas

        # Retorno toda la info necesaria
        return {
            "nuevas_cartas": todas_las_cartas_nuevas,
            "nuevo_turno_id": nuevo_turno_id,
            "nuevo_draft": nuevo_draft,
            "cantidad_final_mazo": cantidad_final_mazo,
        }

        cartas_del_draft_dicts = [{"id": c.id_carta} for c in cartas_del_draft_objs]
        todas_las_cartas_nuevas = cartas_del_draft_dicts + cartas_del_mazo_robadas

        # Retorno toda la info necesaria
        return {
            "nuevas_cartas": todas_las_cartas_nuevas,
            "nuevo_turno_id": nuevo_turno_id,
            "nuevo_draft": nuevo_draft,
            "cantidad_final_mazo": cantidad_final_mazo,
        }
