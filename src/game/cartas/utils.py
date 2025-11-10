from game.cartas.constants import cartasDict
from game.cartas.models import Carta 
from game.jugadores.models import Jugador 
from game.jugadores.services import JugadorService
from game.cartas.services import CartaService 
from game.partidas.services import PartidaService
from game.partidas.utils import determinar_desgracia_social

from fastapi import HTTPException, status

def jugar_set_detective(id_partida: int, id_jugador: int,set_destino_id: int, set_cartas: list[int], db) -> list[Carta]:
    """
    Valida y mueve a set_jugado exactamente las cartas seleccionadas por el jugador.
    Importante: cuando hay múltiples copias del mismo id_carta en la mano, se consumen
    sólo tantas copias como se seleccionaron en set_cartas, evitando eliminar extras.
    """

    #verificar que la partida exista --------------------------------------------------
    partida = PartidaService(db).obtener_por_id(id_partida)
    if partida is None:
        raise HTTPException(status_code=404, detail=f"No se encontró la partida con id {id_partida}")
    
    #fin de la verificacion de si la partida existe ---------------------------------

    #---------------------------------------------------------------------------------

    
    #verificar que la partida este iniciada-----------------------------------------

    if(partida.iniciada == False):
        raise HTTPException(status_code=400, detail="La partida no está iniciada")


    #fin de la verificacion de si la partida esta iniciada ---------------------------

    #------------------------------------------------------------------------------------


    #verificar que sea el turno del jugador -----------------------------------------
    id_jugador_en_turno = PartidaService(db).obtener_turno_actual(id_partida)

    if (id_jugador_en_turno != id_jugador):
        raise HTTPException(status_code=400, detail="No es el turno del jugador")



    #fin de la verificacion de si es el turno del jugador ---------------------------

    #---------------------------------------------------------------------------------

    #verificar que el jugador tenga las cartas en la mano ---------------------------- 
    # Debe consumirse exactamente la cantidad seleccionada por id_carta,
    # incluso cuando existan múltiples copias del mismo id_carta en la mano.
    from collections import Counter, defaultdict

    cartas_mano = CartaService(db).obtener_mano_jugador(id_jugador, id_partida)

    # Agrupar cartas de la mano por id_carta -> lista de cartas reales (Cartas)
    cartas_por_id_carta = defaultdict(list)
    for c in cartas_mano:
        cartas_por_id_carta[c.id_carta].append(c)

    # Contar cuántas instancias de cada id_carta se seleccionaron
    seleccion_por_id_carta = Counter(set_cartas)

    # Validar disponibilidad y seleccionar exactamente esa cantidad de IDs reales
    set_id = []  # IDs reales (Carta.id) a mover
    for id_carta, cantidad_seleccionada in seleccion_por_id_carta.items():
        disponibles = cartas_por_id_carta.get(id_carta, [])
        if len(disponibles) < cantidad_seleccionada:
            # Alguna de las cartas seleccionadas no está en mano en cantidad suficiente
            raise HTTPException(status_code=400, detail="Una o más cartas no se encuentran en la mano del jugador")
        # Tomar exactamente la cantidad seleccionada (los primeros N disponibles)
        set_id.extend([carta.id for carta in disponibles[:cantidad_seleccionada]])
    # Nota: NO convertir a set; necesitamos preservar cantidad exacta si hay duplicados
    
    #fin de la verificacion de las cartas que tiene en mano el jugador ------------------

    #---------------------------------------------------------------------------------

    #verificar que sean todos detectives ----------------------------------------------
        # crear un diccionario que mapee id_real -> info_carta
    cartas_por_id = []
    for carta in set_id:
        cartas_por_id.append(CartaService(db).obtener_carta_por_id(carta))

    if not all(carta.tipo == "Detective" for carta in cartas_por_id):
        raise HTTPException(status_code=400, detail="Todas las cartas deben ser del tipo Detective")

    #fin de la verificacion de que sean todos detectives ------------------------------

    desgracia_social = determinar_desgracia_social(id_partida, id_jugador, db)
    if desgracia_social:
        raise HTTPException(status_code=403, detail=f"El jugador {id_jugador} se encuentra en desgracia social")

    #---------------------------------------------------------------------------------

    #verificar que las cartas sean jugables -------------------------------------------
    
    id_comodin = 14
    id_tupence = 13
    id_tommy = 12
    id_miss_marple = 8
    id_hercule_poirot = 7
    id_adriane_oliver = 15

    cantidad = len(set_cartas)
    tipos = set(set_cartas)
    todos_iguales = len(set(set_cartas)) == 1
    tiene_comodin = id_comodin in tipos
    tiene_tup_tom = (id_tupence in tipos) and (id_tommy in tipos)
    tiene_miss_o_poirot = (id_miss_marple in tipos) ^ (id_hercule_poirot in tipos)  # XOR real

    # Regla especial: Adriane Oliver sola
    if id_adriane_oliver in tipos:
        if cantidad != 1:
            raise HTTPException(status_code=400, detail="Adriane Oliver solo puede jugarse sola")
        sets_existentes = CartaService(db).obtener_sets_jugados(id_partida)
        if not sets_existentes:
            raise HTTPException(
                status_code=404,
                detail="No hay sets existentes en la mesa para agregar Ariadne Oliver")
        if not any(set_destino_id in s["cartas_ids"] for s in sets_existentes):
            raise HTTPException(
                status_code=404,
                detail="No se encuentra el set en la mesa para agregar Ariadne Oliver"
            )
        cartas_jugadas = CartaService(db).mover_set(set_id)
    
    
    # Caso 1: dos cartas distintas sin comodín → Tommy y Tuppence
    elif cantidad == 2 and not tiene_comodin and tiene_tup_tom:
        cartas_jugadas = CartaService(db).mover_set(set_id)

    # Caso 2: dos cartas con comodín → cualquier carta + comodín, menos Miss Marple o Poirot
    elif cantidad == 2 and tiene_comodin and not (id_miss_marple in tipos or id_hercule_poirot in tipos):
        cartas_jugadas = CartaService(db).mover_set(set_id)

    # Caso 3: dos cartas iguales → cualquier carta menos Miss Marple, Poirot o comodín
    elif cantidad == 2 and todos_iguales and not (id_miss_marple in tipos or id_hercule_poirot in tipos or id_comodin in tipos):
        cartas_jugadas = CartaService(db).mover_set(set_id)

    # Caso 4: tres cartas iguales → deben ser todas Miss Marple o todas Hercule Poirot
    elif cantidad == 3 and todos_iguales and (id_miss_marple in tipos or id_hercule_poirot in tipos):
        cartas_jugadas = CartaService(db).mover_set(set_id)

    # Caso 5: tres cartas con comodines → al menos una Miss Marple o Poirot (pero no ambos)
    elif cantidad == 3 and tiene_comodin and tiene_miss_o_poirot:
        cartas_jugadas = CartaService(db).mover_set(set_id)

    else:
        raise HTTPException(status_code=400, detail="El set de detectives no es jugable")
    
    return cartas_jugadas


    

    #fin de la verificacion de las cartas jugables --------------------------------------   