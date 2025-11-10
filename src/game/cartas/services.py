from game.cartas.constants import cartasDict, secretosDict
from game.cartas.models import Carta, SetJugado
from game.jugadores.models import Jugador
from game.jugadores.services import JugadorService
from game.partidas.utils import *
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

        random.shuffle(mazo_nuevo)
        for i, carta in enumerate(mazo_nuevo):
            carta.orden_mazo = i

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
            raise Exception("Una o mas cartas no se encuentran en la mano del jugador")
        
        # Mantener orden de descarte y dejar visibles las cartas descartadas
        ultimo_orden = (
            self._db.query(func.max(Carta.orden_descarte))
            .filter(Carta.partida_id == jugador.partida_id)
            .scalar() or 0
        )
        
        for carta in cartas_descarte_id:
            carta_descarte = self._db.query(Carta).filter(Carta.id_carta == carta, Carta.jugador_id == id_jugador).first()
            carta_descarte.jugador_id = 0
            carta_descarte.ubicacion = "descarte"


            carta_descarte.bocaArriba = False
            ultimo_orden = ultimo_orden + 1
            carta_descarte.orden_descarte = ultimo_orden

            carta_descarte.orden_mazo = None

            self._db.commit()
            print(f'Se descarto la carta con id {carta_descarte.id} y nombre {carta_descarte.nombre}.')

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

        cartas_a_robar = mazo[:cantidad]

        # Asignar cartas al jugador
        for carta in cartas_a_robar:
            carta.jugador_id = id_jugador
            carta.ubicacion = "mano"
            carta.orden_mazo = None
        self.descartar_eventos(id_partida, id_jugador)

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


    def revelar_secreto(self, id_unico_secreto: int) -> Carta:
        """
        Revela el secreto de un jugador en una partida específica.
        
        Parameters
        ----------
        id_unico_secreto: int
            ID del secreto que debe ser revelado
        
        Returns
        -------
        secreto_revelado: Carta
            diccionario con el id del secreto revelado.
        """
        secreto_a_revelar: Carta
        secreto_a_revelar = self._db.get(Carta, id_unico_secreto)
        
        secreto_a_revelar.bocaArriba = True
        self._db.commit()
        #secreto_revelado = {"id-secreto": secreto_a_revelar.id}

        return secreto_a_revelar


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

    def es_complice(self, id_unico_secreto: int):
        secreto = self._db.get(Carta, id_unico_secreto)
        return (secreto.nombre == "accomplice")

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

    def obtener_asesino_complice(self, id_partida):
        carta_asesino = self._db.query(Carta).filter_by(partida_id=id_partida, tipo="secreto", nombre="murderer").first()
        asesino_id = carta_asesino.jugador_id if carta_asesino else None
        carta_complice = self._db.query(Carta).filter_by(partida_id=id_partida, tipo="secreto", nombre="accomplice").first()
        complice_id = carta_complice.jugador_id if carta_complice else None
        
        return {"asesino-id": asesino_id, "complice-id": complice_id}


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


    def ocultar_secreto(self, id_unico_secreto: int) -> Carta:
        """
        Oculta el secreto de un jugador en una partida específica.
        
        Parameters
        ----------
        id_secreto: int
            ID del secreto que debe ser ocultado
        
        Returns
        -------
        secreto_ocultado: Carta
            Carta que fue ocultada
        """
        secreto_a_ocultar: Carta
        secreto_a_ocultar = self._db.get(Carta, id_unico_secreto)
        
        secreto_a_ocultar.bocaArriba = False
        self._db.commit()

        return secreto_a_ocultar


    def obtener_carta_por_id(self, id_unico_secreto: int) -> Carta:
        """Obtiene una carta dado su ID único"""
        carta = self._db.get(Carta, id_unico_secreto)
        return carta

    def robar_secreto(self, secreto_a_robar: Carta, id_jugador_destino: int):
        secreto_a_robar.bocaArriba = False
        secreto_a_robar.jugador_id = id_jugador_destino
        self._db.commit()
        secreto_robado = {"id-secreto": secreto_a_robar.id}
        return secreto_robado


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
            
    
    def obtener_cartas_jugadas(self, id_partida: int, id_jugador: int, nombre: str, ubicacion: str):
        carta_evento = self._db.query(Carta).filter_by(partida_id=id_partida,
                                                        jugador_id=id_jugador, 
                                                        ubicacion=ubicacion,
                                                        nombre=nombre).first()
        return carta_evento
    
    
    def tomar_into_the_ashes(self, id_partida: int, id_jugador: int, id_carta_objetivo: int):
        
        if id_carta_objetivo == 20:
            carta_objetivo = self._db.query(Carta).filter_by(partida_id=id_partida,
                                                    id_carta=id_carta_objetivo,
                                                    ubicacion="descarte"
                                                    ).order_by(Carta.orden_descarte.desc()).first()
            carta_objetivo.orden_descarte = self.ultimo_orden_descarte(id_partida) + 1
            self._db.commit()
            self._db.refresh(carta_objetivo)
        
            carta_evento_vuelve = self._db.query(Carta).filter_by(partida_id=id_partida,
                                                    id_carta=id_carta_objetivo,
                                                    ubicacion="evento_jugado"
                                                    ).first()

            carta_evento_vuelve.jugador_id = id_jugador
            carta_evento_vuelve.ubicacion = "mano"
            carta_evento_vuelve.bocaArriba = False
            carta_evento_vuelve.orden_descarte = None
            self._db.commit()
            self._db.refresh(carta_evento_vuelve)
        
        else:
            carta_objetivo = self._db.query(Carta).filter_by(partida_id=id_partida,
                                                        id_carta=id_carta_objetivo,
                                                        ubicacion="descarte"
                                                        ).order_by(Carta.orden_descarte.desc()).first()
            
            carta_objetivo.jugador_id = id_jugador
            carta_objetivo.ubicacion = "mano"
            carta_objetivo.bocaArriba = False
            carta_objetivo.orden_descarte = None
            self._db.commit()
            self._db.refresh(carta_objetivo)

    
    def descartar_eventos(self, id_partida: int, id_jugador: int):
        carta_jugada = self._db.query(Carta).filter_by(partida_id=id_partida,
                                                    jugador_id=id_jugador, 
                                                    ubicacion="evento_jugado",
                                                    ).first()
    
        if carta_jugada is None:
            return
        if carta_jugada.nombre == "Delay the murderer's escape!":
            carta_jugada.partida_id = 0
            carta_jugada.ubicacion = "eliminada"
            carta_jugada.jugador_id = 0
            self._db.commit()
        else:
            self.descartar_cartas(id_jugador, [carta_jugada.id_carta])
            

    def jugar_delay_the_murderer_escape(self, id_partida: int, id_jugador: int,cantidad: int):
    
        cartas = self.obtener_cartas_descarte(id_partida, cantidad) 
        min_orden = self._db.query(func.min(Carta.orden_mazo)).filter_by(partida_id=id_partida, ubicacion="mazo_robo").scalar()
        if min_orden is None:
            min_orden = 0

        for i, carta in enumerate(cartas, start=1):
            carta.ubicacion = "mazo_robo"
            carta.bocaArriba = False
            carta.orden_mazo = min_orden - i

        self._db.commit()


    def robar_set(self, id_partida: int, id_jugador: int, id_objetivo: int, id_representacion_carta: int, ids_cartas: list[int]):
        # Convertimos la lista de cartas a CSV para comparar correctamente
        cartas_csv = ",".join(map(str, ids_cartas))
        
        
        set_a_robar = (
        self._db.query(SetJugado)
        .filter_by(
            partida_id=id_partida,
            jugador_id=id_objetivo,
            representacion_id_carta=id_representacion_carta,
            cartas_ids_csv=cartas_csv
        )
        .first()
        )

        if not set_a_robar:
            raise ValueError("El set no existe o los parámetros son incorrectos.")

        set_a_robar.jugador_id = id_jugador
        self._db.commit()

        carta_jugada = self._db.query(Carta).filter_by(partida_id=id_partida,
                                                          jugador_id=id_jugador, 
                                                          ubicacion="evento_jugado",
                                                          nombre="Another Victim").first()

        self.descartar_cartas(id_jugador, [carta_jugada.id_carta])
 

    def eliminar_carta(self, carta: Carta):
        try:
            self._db.delete(carta)
            self._db.commit()
        except Exception as e:
            self._db.rollback()
            raise ValueError(f"Error al eliminar la carta: {str(e)}")
        

    def jugar_early_train_to_paddington(self, id_partida: int, id_jugador: int):
            """
            Mueve las primeras 6 cartas del mazo de robo al de descarte, boca arriba,
            y remueve la carta de evento jugada.
            """
            cartas_a_mover = self._db.query(Carta)\
                .filter_by(partida_id=id_partida, ubicacion="mazo_robo")\
                .order_by(Carta.orden_mazo.desc())\
                .limit(6)\
                .all()

            if cartas_a_mover:
                max_orden_descarte = self._db.query(func.max(Carta.orden_mazo))\
                    .filter_by(partida_id=id_partida, ubicacion="descarte")\
                    .scalar() or 0

                for i, carta in enumerate(cartas_a_mover, start=1):
                    carta.ubicacion = "descarte"
                    carta.bocaArriba = True
                    carta.orden_descarte = max_orden_descarte + i

            carta_evento_jugada = self._db.query(Carta).filter_by(
                partida_id=id_partida,
                jugador_id=id_jugador,
                ubicacion="evento_jugado",
                nombre="Early train to paddington" 
            ).first()

            if carta_evento_jugada:
                carta_evento_jugada.ubicacion = "removida"
            
            self._db.commit()
            
            
    def jugar_carta_instantanea(self, id_partida: int, id_jugador: int, id_carta_tipo: int) -> Carta:
        """
        Mueve una carta de la mano del jugador a "en_la_pila".
        """
        carta = self.obtener_carta_de_mano(id_carta_tipo, id_jugador) 
        if not carta:
             raise ValueError("La carta no se encuentra en la mano del jugador.")
        if carta.partida_id != id_partida:
             raise ValueError("La carta no pertenece a esta partida.")
             
        carta.ubicacion = "en_la_pila"
        carta.bocaArriba = True
        self._db.commit()
        self._db.refresh(carta)
        return carta


    def descartar_cartas_de_pila(self, ids_cartas_db: list[int], id_partida: int):
        """
        Toma una lista de IDs de BBDD (Carta.id) y las mueve a "descarte".
        """
        if not ids_cartas_db:
            return

        ultimo_orden = self.ultimo_orden_descarte(id_partida) 
        cartas = self._db.query(Carta).filter(Carta.id.in_(ids_cartas_db)).all()
        
        for i, carta in enumerate(cartas):
            carta.ubicacion = "descarte" 
            carta.jugador_id = 0
            carta.orden_mazo = None
            carta.bocaArriba = False
            carta.orden_descarte = ultimo_orden + 1 + i
            carta.partida_id = id_partida

        self._db.commit()

    
    def jugar_ariadne_oliver(self, id_partida:int, set_destino_id: int):
        """
        Mueve la carta jugada de ariadne oliver a un set existente de otro jugador
        para que muestre un secreto de su eleccion.
        """
        
        set_destino = (
            self._db.query(SetJugado)
            .filter(
                SetJugado.partida_id == id_partida,
                SetJugado.representacion_id_carta == set_destino_id
            )
            .first()
        )

        ids_actuales = set_destino.cartas_ids_csv.split(",") if set_destino.cartas_ids_csv else []
        ids_actuales.append(str(15))
        set_destino.cartas_ids_csv = ",".join(ids_actuales)

        self._db.add(set_destino)
        self._db.commit()

        return {
            "mensaje": "Ariadne Oliver jugada correctamente",
            "set_actualizado": {
                "id_jugador_dueño": set_destino.jugador_id,
                "cartas_ids": ids_actuales,
            },
            "jugador_revela_secreto": set_destino.jugador_id,
        }   
               
        
    def agregar_carta_a_set(self, id_jugador_set: int, id_tipo_set: int, id_carta_instancia: int):
        """
        Busca el set usando el ID de TIPO (representacion_id_carta) y el ID del JUGADOR,
        porque el frontend no tiene el ID (PK) del set.

        Luego, agrega la carta (por instancia) y la MUEVE fuera de la mano.
        """

        set_jugado = self._db.query(SetJugado).filter(
            SetJugado.jugador_id == id_jugador_set,
            SetJugado.representacion_id_carta == id_tipo_set
        ).first()

        if not set_jugado:
            raise Exception(f"No se encontró el Set para el jugador {id_jugador_set} con tipo {id_tipo_set}")

#Obtener la carta por INSTANCIA
        carta = self.obtener_carta_por_id(id_carta_instancia) 
        if not carta:
            raise Exception(f"No se encontró la Carta con instancia id {id_carta_instancia}")

#Mover la carta (la saca de la mano)
        carta.ubicacion = "set_jugado" 
        self._db.add(carta)

        nuevas_cartas_ids = set_jugado.cartas_ids_csv.split(',') if set_jugado.cartas_ids_csv else []
        nuevas_cartas_ids.append(str(carta.id_carta)) 
        set_jugado.cartas_ids_csv = ",".join(nuevas_cartas_ids)
        self._db.add(set_jugado)

        self._db.commit()

        return set_jugado

    def mover_carta_a_objetivo(self, id_carta, id_objetivo: int):

        carta = self._db.query(Carta).filter(Carta.id == id_carta).first()

        carta.jugador_id = id_objetivo
        self._db.commit()
        self._db.refresh(carta)

        return {
            "mensaje": "carta enviada correctamente",
            "carta_actualizada": {
                "jugador_id": carta.jugador_id
            }
        }   