from game.cartas.constants import cartasDict, secretosDict
from game.cartas.models import Carta, SetJugado
from game.jugadores.models import Jugador
from game.jugadores.services import JugadorService
import random
from typing import List
from collections import Counter
import logging
from sqlalchemy import func

logger = logging.getLogger(__name__)

class CartaService:
    def __init__(self, db):
        self._db = db

    def crear_mazo_inicial(self, id_partida: int) -> list[Carta]:
        """
        Crea el mazo inicial de cartas para una partida.
        
        Parameters
        ----------
        id_partida: int
            ID de la partida para la cual se crea el mazo.
        
        Returns
        -------
        List[Carta]
            Lista de objetos Carta que representan el mazo incicial.
        """
        mazo_nuevo = []
        for carta in cartasDict.values():
            cantidad = carta["cantidad"]
            while cantidad > 0:
                cartita = Carta(
                    nombre=carta["carta"],
                    tipo=carta["tipo"],
                    bocaArriba=carta["bocaArriba"],
                    ubicacion=carta["ubicacion"],
                    jugador_id=0,
                    partida_id=id_partida,
                    id_carta=carta["id"]
                )
                cantidad -= 1
                mazo_nuevo.append(cartita)

        self._db.add_all(mazo_nuevo)
        self._db.commit()

        return mazo_nuevo
    
    def obtener_cartas_descarte(self, id_partida: int, cantidad: int) -> list[Carta]:
        """
        Obtiene las ultimas 'cantidad' cartas del mazo de descarte de una partida.

        Args:
            id_partida (int), cantidad (int)

        Returns:
            list[Carta]
        """
    
        cartas_descarte = (self._db.query(Carta)
                        .filter_by(partida_id=id_partida, ubicacion="descarte")
                        .order_by(Carta.orden_descarte.desc()).limit(cantidad).all()
                        )
        return cartas_descarte

    def repartir_cartas_iniciales(self, mazo: list[Carta], jugadores_en_partida: list[Jugador]):
        """
        Reparte las cartas iniciales a los jugadores en una partida.
        
        Parameters
        ----------
        mazo: list[Carta]
            Lista de objetos Carta que representan el mazo incicial.

        jugadores_en_partida: list[Jugador]
            Lista de jugadores en un
        """
        random.shuffle(mazo)
        # Una carta "Not so fast" por jugador
        for jugador in jugadores_en_partida:
            for carta in mazo:
                if carta.nombre.lower() == "not so fast" and carta.jugador_id == 0:
                    carta.jugador_id = jugador.id
                    carta.ubicacion = "mano"
                    break  # pasamos al siguiente jugador
        # Luego, repartir hasta 6 cartas por jugador
        for jugador in jugadores_en_partida:
            cartas_jugador = 0
            for carta in mazo:
                if carta.jugador_id == 0:
                    carta.jugador_id = jugador.id
                    carta.ubicacion = "mano"
                    cartas_jugador += 1
                    if cartas_jugador == 5:
                        break  # pasamos al siguiente jugador
        self._db.commit()
        # refrescar última carta tocada si existe (defensivo)
        try:
            self._db.refresh(carta)  # type: ignore[name-defined]
        except Exception:
            pass
        logger.info("REPARTO INICIAL: se repartieron cartas iniciales a jugadores")

    def obtener_mazo_de_robo(self, id_partida: int) -> list[Carta]:
        """
        Obtiene el mazo de robo para una partida específica.
        
        Parameters
        ----------
        id_partida: int
            ID de la partida para la cual se obtiene el mazo de robo.
        
        Returns
        -------
        List[Carta]
            Lista de objetos Carta que representan el mazo de robo.
        """
        mazo_robo = self._db.query(Carta).filter_by(partida_id=id_partida, ubicacion="mazo_robo").all()
        return mazo_robo

    def obtener_mano_jugador(self, id_jugador: int, id_partida: int) -> list[Carta]:
        """
        Obtiene la mano de cartas de un jugador en una partida específica.
        
        Parameters
        ----------
        id_jugador: int
            ID del jugador para el cual se obtiene la mano de cartas.
        
        id_partida: int
            ID de la partida para la cual se obtiene la mano de cartas.
        
        Returns
        -------
        List[Carta]
            Lista de objetos Carta que representan la mano del jugador.
        """
        mano_jugador = self._db.query(Carta).filter_by(partida_id=id_partida, jugador_id=id_jugador, ubicacion="mano").all()
        return mano_jugador


    def ultimo_orden_descarte(self, id_partida: int) -> int:
        
        from sqlalchemy import func
        ultimo_orden_descarte = (self._db.query(func.max(Carta.orden_descarte)).
                                 filter(Carta.partida_id == id_partida).
                                 scalar() or 0)
        
        return ultimo_orden_descarte
    

    def descartar_cartas(self, id_jugador, cartas_descarte_id):

        """Descarta cartas de la mano del jugador registrando auditoría en logs."""
        logger.info(
            "DESCARTE: jugador=%s cantidad=%s ids=%s",
            id_jugador, len(cartas_descarte_id), cartas_descarte_id,
        )
        """
        DOC
        """
        jugador = JugadorService(self._db).obtener_jugador(id_jugador)

        tiene_cartas = True
        cartas_mano = jugador.cartas
        for carta_id in cartas_descarte_id:
            enMano = False
            for carta in cartas_mano:
                if (carta_id == carta.id_carta):
                    enMano = enMano or True
            tiene_cartas = tiene_cartas and enMano

        if not tiene_cartas:
            logger.error(
                "DESCARTE ERROR: jugador=%s intenta descartar ids=%s pero no están en mano",
                id_jugador, cartas_descarte_id,
            )
            raise Exception("Una o mas cartas no se encuentran en la mano del jugador")

        
        ultimo_orden = self._db.query(func.max(Carta.orden_descarte)).filter(Carta.partida_id == jugador.partida_id).scalar() or 0
        for carta in cartas_descarte_id:
            carta_descarte = self._db.query(Carta).filter(Carta.id_carta == carta, Carta.jugador_id == id_jugador).first()
            print(f"[DEBUG] Intentando descartar id={carta} (jugador {id_jugador}) → encontrado: {carta_descarte}")
            carta_descarte.jugador_id = 0
            carta_descarte.ubicacion = "descarte"
            carta_descarte.bocaArriba = True
            ultimo_orden = ultimo_orden + 1
            carta_descarte.orden_descarte = ultimo_orden
            self._db.commit()


            # nombres = []
            # for carta_id in cartas_descarte_id:
            #     carta_descarte = self._db.query(Carta).filter(Carta.id_carta == carta_id, Carta.jugador_id == id_jugador).first()
            #     if carta_descarte:
            #         carta_descarte.jugador_id = 0
            #         carta_descarte.ubicacion = "descarte"
            #         carta_descarte.bocaArriba = False
            #         nombres.append(carta_descarte.nombre)
            #         self._db.commit()
            # logger.info(
            #     "DESCARTE HECHO: jugador=%s cantidad=%s ids=%s nombres=%s",
            #     id_jugador, len(cartas_descarte_id), cartas_descarte_id, nombres,
            # )

    def obtener_cantidad_mazo(self, id_partida: int) -> int:
        """
        Calcula la cantidad de cartas restantes en el mazo de robo.
        """
        mazo_robo = self.obtener_mazo_de_robo(id_partida)
        return len(mazo_robo)


    def robar_cartas(self, id_partida: int, id_jugador: int, cantidad: int = 1):
        if cantidad <= 0:
            raise ValueError("La cantidad a robar debe ser mayor a 0")

        # Obtener mazo de robo
        mazo = self.obtener_mazo_de_robo(id_partida)
        # Si no hay suficientes, robar tantas como haya
        if len(mazo) == 0:
            return []
        if len(mazo) < cantidad:
            cantidad = len(mazo)

        # Mezclar para simular robo aleatorio y tomar 'cantidad'
        random.shuffle(mazo)
        cartas_a_robar = mazo[:cantidad]

        # Asignar cartas al jugador
        for carta in cartas_a_robar:
            carta.jugador_id = id_jugador
            carta.ubicacion = "mano"

        self._db.commit()

        resultado = [
            {"id": carta.id_carta, "nombre": carta.nombre}
            for carta in cartas_a_robar
        ]
        logger.info(
            "ROBAR SERVICIO: partida=%s jugador=%s cantidad=%s detalle=%s",
            id_partida, id_jugador, len(resultado), resultado,
        )
        # Retornar información mínima al frontend
        return resultado

    def actualizar_mazo_draft(self, id_partida: int):
        """
        Actualiza el mazo de draft de una partida.

        Parameters
        ----------
            id_partida (int)

        """
        mazo_draft = (
            self._db.query(Carta)
            .filter(Carta.partida_id == id_partida, Carta.ubicacion == "draft")
            .all()
        )

        cartas_draft = len(mazo_draft)
        if cartas_draft <= 2:
            mazo_robo = self.obtener_mazo_de_robo(id_partida)
            random.shuffle(mazo_robo)
            for carta in mazo_robo:
                carta.ubicacion = "draft"
                cartas_draft += 1
                if cartas_draft == 3:
                    break
            
            self._db.commit()


    def obtener_mazo_draft(self, id_partida: int) -> list[Carta]:
        """
        Obtiene el mazo de draft de una partida.

        Parameters
        ----------
            id_partida (int)

        Returns
        --------
            list[Carta]
        """
        mazo_draft = (self._db.query(Carta)
                      .filter(Carta.partida_id == id_partida, Carta.ubicacion == "draft")
                      .all())
        
        return mazo_draft

    def tomar_cartas_draft(self, id_partida: int, id_jugador: int, cartas_tomadas_ids: List[int]):
        """
        Permite al jugador tomar una o más cartas del draft.
        """
        if not cartas_tomadas_ids:
            return

        mazo = self.obtener_mazo_draft(id_partida)
        ids_cartas = [carta.id_carta for carta in mazo]
        if not all(id in ids_cartas for id in cartas_tomadas_ids):
            raise Exception("Una o más cartas seleccionadas no se encuentran en el draft.")

        original_ids = list(cartas_tomadas_ids)
        tomados_nombres = []
        for carta in mazo:
            if carta.id_carta in cartas_tomadas_ids:
                carta.jugador_id = id_jugador
                carta.ubicacion = "mano"
                cartas_tomadas_ids.remove(carta.id_carta)
                tomados_nombres.append(carta.nombre)

        self._db.commit()
        logger.info(
            "DRAFT TOMAR: partida=%s jugador=%s ids=%s nombres=%s",
            id_partida, id_jugador, original_ids, tomados_nombres,
        )

    def crear_secretos(self, id_partida):
        """
        Crea las cartas secreto para una partida. Todas las cartas creadas son secretos comunes,
        en el reparto se asigna la del asesino y cómplice (si aplica).
        
        Parameters
        ----------
        id_partida: int
            ID de la partida para la cual se crean los secretos.
        
        Returns
        -------
        List[Carta]
            Lista de objetos Carta que representan los secretos.
        """

        secretos = []
        for _ in range (18):
            secret = Carta(
                nombre="secreto_comun",
                tipo="secreto",
                bocaArriba=False,
                ubicacion="mesa",
                jugador_id=0,
                partida_id=id_partida,
                id_carta=6
                )
            secretos.append(secret)

        self._db.add_all(secretos)
        self._db.commit()

        return secretos

    
    def repartir_secretos(self, secretos: list[Carta], jugadores_en_partida: list[Jugador]):
        """
        Reparte las cartas secreto a los jugadores en una partida.
        
        Parameters
        ----------
        mazo: list[Carta]
            Lista de objetos Carta que son los secretos.

        jugadores_en_partida: list[Jugador]
            Lista de jugadores en un
        """
   
        # Se elige un jugador al azar para que sea el asesino
        index_murderer = random.randrange(len(jugadores_en_partida))
        id_asesino = jugadores_en_partida[index_murderer].id
        
        id_complice = None
        # Si es una partida de 5 o 6 jugadores debe haber un cómplice
        if (len(jugadores_en_partida) >= 5):
            accomplice_found = False
            while not accomplice_found:
                index_accomplice = random.randrange(len(jugadores_en_partida))
                if index_accomplice != index_murderer:
                    accomplice_found = True
                    id_complice = jugadores_en_partida[index_accomplice].id
        
        secret_index = 0
        for jugador in jugadores_en_partida:
            # Si es el asesino o el cómplice, elijo una ubicacion al azar para esa carta y le doy las 2 comunes
            if jugador.id == id_asesino:
                ubicacionRandom = random.randrange(3)
                for i in range(3):
                    if i == ubicacionRandom:
                        secretos[secret_index].nombre="murderer"
                        secretos[secret_index].jugador_id=jugador.id
                        secretos[secret_index].id_carta=3
                        secret_index+=1
                    else:
                        secretos[secret_index].jugador_id=jugador.id
                        secret_index+=1
            elif (id_complice is not None and jugador.id == id_complice):
                ubicacionRandom = random.randrange(3)
                for i in range(3):
                    if i == ubicacionRandom:
                        secretos[secret_index].nombre="accomplice"
                        secretos[secret_index].jugador_id=jugador.id
                        secretos[secret_index].id_carta=4
                        secret_index+=1
                    else:
                        secretos[secret_index].jugador_id=jugador.id
                        secret_index+=1
            # Si no es asesino o cómplice, le doy los 3 secretos
            else:
                for _ in range(3):
                    secretos[secret_index].jugador_id = jugador.id
                    secret_index+=1
        
        self._db.commit()
            
        print("se repartieron los secretos")



    def obtener_carta(self, id_carta: int) -> Carta:
        """
        Obtiene un objeto Carta específico por su id_carta.
        """
        carta = self._db.query(Carta).filter(Carta.id_carta == id_carta).first()
        if not carta:
            raise ValueError(f"No se encontró una carta con id_carta {id_carta}")
        return carta

    def obtener_secretos_jugador(self, id_jugador: int, id_partida: int) -> list[Carta]:
        """
        Obtiene los secretos de un jugador en una partida específica.
        
        Parameters
        ----------
        id_jugador: int
            ID del jugador para el cual se obtiene los secretos.
        
        id_partida: int
            ID de la partida para la cual se obtiene los secretos.
        
        Returns
        -------
        List[Carta]
            Lista de objetos Carta secreto del jugador.
        """
        secretos_jugador = self._db.query(Carta).filter_by(partida_id=id_partida, jugador_id=id_jugador, ubicacion="mesa").all()
        return secretos_jugador

    def revelar_secreto(self, id_partida: int, id_jugador: int, id_unico_secreto: int) -> dict:
        """
        Revela el secreto de un jugador en una partida específica.
        
        Parameters
        ----------
        id_jugador: int
            ID del jugador para el cual se obtiene los secretos.
        
        id_partida: int
            ID de la partida para la cual se obtiene los secretos.
        
        id_secreto: int
            ID del secreto que debe ser revelado
        
        Returns
        -------
        secreto_revelado: dict
            diccionario con el id del secreto revelado.
        """
        secreto_a_revelar: Carta
        secreto_a_revelar = self._db.get(Carta, id_unico_secreto)
        
        secreto_a_revelar.bocaArriba = True
        self._db.commit()
        secreto_revelado = {"id-secreto": secreto_a_revelar.id}

        return secreto_revelado

    def obtener_secretos_ajenos(self, id_jugador: int, id_partida: int):
        secretos_ajenos = self.obtener_secretos_jugador(id_jugador, id_partida)
        # Si no hay secretos, devolver lista vacía
        if not secretos_ajenos:
            return []
        
        #Crear lista de cartas a enviar
        secretos_a_enviar = []
        for carta in secretos_ajenos:
            if carta.bocaArriba:
                secretos_a_enviar.append({
                    "id": carta.id,
                    "carta_id": carta.id_carta,
                    "nombre": carta.nombre,
                    "bocaArriba": carta.bocaArriba
                })
            else:
                secretos_a_enviar.append({
                    "id": carta.id,
                    "bocaArriba": carta.bocaArriba
                })
        return secretos_a_enviar

    def es_asesino(self, id_unico_secreto: int):
        secreto = self._db.get(Carta, id_unico_secreto)
        return (secreto.nombre == "murderer")


    def obtener_asesino_complice(self, id_partida):
        carta_asesino = self._db.query(Carta).filter_by(partida_id=id_partida, tipo="secreto", nombre="murderer").first()
        asesino_id = carta_asesino.jugador_id if carta_asesino else None
        carta_complice = self._db.query(Carta).filter_by(partida_id=id_partida, tipo="secreto", nombre="accomplice").first()
        complice_id = carta_complice.jugador_id if carta_complice else None
        
        return {"asesino-id": asesino_id, "complice-id": complice_id}

    def obtener_carta_por_id(self, id_carta: int) -> Carta:
        carta = self._db.query(Carta).filter(Carta.id == id_carta).first()
        if not carta:
            raise ValueError(f"No se encontró la carta con id {id_carta}")
        return carta

    def mover_set(self, set_cartas: list[int]) -> list[Carta]:
        set_jugado = []
        for carta_id in set_cartas:
            carta = self.obtener_carta_por_id(carta_id)
            carta.ubicacion = "set_jugado"
            set_jugado.append(carta)
            self._db.add(carta)
        self._db.commit()
        return set_jugado

    def registrar_set_jugado(self, id_partida: int, id_jugador: int, cartas: list[Carta]):
        # Representación del set: NUNCA usar comodín (Harley Quin, id=14)
        # Elegir la primera carta no comodín; si por algún motivo no hay, usar la primera
        WILDCARD_ID = 14
        representacion_id = 1
        if cartas:
            no_wildcards = [c for c in cartas if c.id_carta != WILDCARD_ID]
            representacion_id = (no_wildcards[0].id_carta if no_wildcards else cartas[0].id_carta)
        ids_csv = ",".join(str(c.id_carta) for c in cartas)
        registro = SetJugado(
            partida_id=id_partida,
            jugador_id=id_jugador,
            representacion_id_carta=representacion_id,
            cartas_ids_csv=ids_csv,
        )
        self._db.add(registro)
        self._db.commit()
        return registro

    def obtener_sets_jugados(self, id_partida: int):
        """Devuelve [{ jugador_id, representacion_id_carta, cartas_ids: [int,int...] }]"""
        registros = self._db.query(SetJugado).filter(SetJugado.partida_id == id_partida).all()
        WILDCARD_ID = 14
        salida = []
        for r in registros:
            ids = [int(x) for x in r.cartas_ids_csv.split(",") if x]
            rep = r.representacion_id_carta
            # Corrección retroactiva: si por error quedó comodín como representación, usar primer no comodín
            if rep == WILDCARD_ID:
                rep_candidates = [i for i in ids if i != WILDCARD_ID]
                if rep_candidates:
                    rep = rep_candidates[0]
            salida.append({
                "jugador_id": r.jugador_id,
                "representacion_id_carta": rep,
                "cartas_ids": ids,
            })
        return salida


    def ocultar_secreto(self, id_partida: int, id_jugador:  int, id_unico_secreto: int) -> dict:
        """
        Oculta el secreto de un jugador en una partida específica.
        
        Parameters
        ----------
        id_jugador: int
            ID del jugador para el cual se ocultará un secreto.
        
        id_partida: int
            ID de la partida para la cual se obtiene los secretos.
        
        id_secreto: int
            ID del secreto que debe ser ocultado
        
        Returns
        -------
        secreto_ocultado: dict
            diccionario con el id del secreto ocultado. {"id-secreto": secreto.id}
        """
        secreto_a_ocultar: Carta
        secreto_a_ocultar = self._db.get(Carta, id_unico_secreto)
        
        secreto_a_ocultar.bocaArriba = False
        self._db.commit()
        secreto_ocultado = {"id-secreto": secreto_a_ocultar.id}

        return secreto_ocultado
    
    
    def obtener_carta_de_mano(self, id_carta: int, id_jugador: int) -> Carta:
    
        carta = (self._db.query(Carta).
                 filter(Carta.id_carta == id_carta, Carta.jugador_id == id_jugador, Carta.ubicacion == "mano").
                 first())
        return carta
    
    
    def evento_jugado_en_turno(self, id_jugador: int) -> bool:
        no_mas_eventos = False
        evento_ya_jugado = (self._db.query(Carta).
                 filter(Carta.jugador_id == id_jugador, Carta.ubicacion == "evento_jugado").
                 first())
        if evento_ya_jugado is not None:
            no_mas_eventos = True
            
        return no_mas_eventos

    
    def obtener_carta_de_mano(self, id_carta: int, id_jugador: int) -> Carta:
    
        carta = (self._db.query(Carta).
                 filter(Carta.id_carta == id_carta, Carta.jugador_id == id_jugador, Carta.ubicacion == "mano").
                 first())
        return carta
    
    
    def evento_jugado_en_turno(self, id_jugador: int) -> bool:
        no_mas_eventos = False
        evento_ya_jugado = (self._db.query(Carta).
                 filter(Carta.jugador_id == id_jugador, Carta.ubicacion == "evento_jugado").
                 first())
        if evento_ya_jugado is not None:
            no_mas_eventos = True
            
        return no_mas_eventos

    def jugar_cards_off_the_table(self, id_partida: int, id_jugador: int, id_objetivo: int):
        cartas_jugador = self._db.query(Carta).filter_by(partida_id=id_partida,
                                                          jugador_id=id_objetivo, 
                                                          ubicacion="mano",
                                                          nombre="Not so fast").all()
        if cartas_jugador:
            id_cartas_jugador = [carta.id_carta for carta in cartas_jugador]
            self.descartar_cartas(id_objetivo, id_cartas_jugador)
            
            
    def descartar_eventos(self, id_partida: int, id_jugador: int):
        carta_jugada = self._db.query(Carta).filter_by(partida_id=id_partida,
                                                    jugador_id=id_jugador, 
                                                    ubicacion="evento_jugado",
                                                    ).first()
        if carta_jugada:
            self.descartar_cartas(id_jugador, [carta_jugada.id_carta])
            
    def obtener_cartas_jugadas(self, id_partida: int, id_jugador: int, nombre: str, ubicacion: str):
        carta_evento = self._db.query(Carta).filter_by(partida_id=id_partida,
                                                        jugador_id=id_jugador, 
                                                        ubicacion=ubicacion,
                                                        nombre=nombre).all()
        return carta_evento
        
    def tomar_into_the_ashes(self, id_jugador, id_carta_objetivo):
        carta_objetivo = self.obtener_carta_por_id(id_carta_objetivo)
        
        carta_objetivo.jugador_id = id_jugador
        carta_objetivo.ubicacion = "mano"
        carta_objetivo.bocaArriba = False
        self._db.commit()