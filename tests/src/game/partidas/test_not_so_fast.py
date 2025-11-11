import pytest
import os
import json
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
from main import app
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch, AsyncMock
from game.modelos.db import get_db
from game.modelos.db import get_db
from game.partidas.utils import *
from game.partidas.models import Partida
from game.jugadores.models import Jugador
from game.cartas.models import Carta

# -----------------------------------TESTS A NIVEL API------------------------------------------------------

# ----------------------------------------------------------------------
# Test Not So Fast (caso todo ok)
# ----------------------------------------------------------------------

@patch('game.partidas.endpoints.manager')
@patch('game.partidas.endpoints.jugar_not_so_fast')
@patch('game.partidas.endpoints.verif_evento')
def test_API_not_so_fast_ok(
    mock_verif_evento, 
    mock_jugar_not_so_fast, 
    mock_manager, 
    session
):
    """
    Test para jugar Not So Fast con éxito.
    """
    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override

    client = TestClient(app)
    
    ID_PARTIDA = 5
    ID_JUGADOR = 10
    ID_CARTA = 101
    
    # El contexto que devuelve jugar_not_so_fast después de ejecutar la lógica
    accion_context_mock = {"id_accion": 55, "carta_jugada": "Not so Fast"}
    
    # 1. Configurar verif_evento para que retorne True (pasa la validación inicial)
    mock_verif_evento.return_value = True
    
    # 2. Configurar jugar_not_so_fast para que retorne el contexto de acción
    mock_jugar_not_so_fast.return_value = accion_context_mock

    # 3. Configurar manager.broadcast como AsyncMock para evitar el TypeError: object MagicMock can't be used in 'await'
    mock_manager.broadcast = AsyncMock() 

    response = client.put(
        f"/partidas/{ID_PARTIDA}/respuesta/not_so_fast?id_jugador={ID_JUGADOR}&id_carta={ID_CARTA}"
    )

    assert response.status_code == 200
    assert response.json() == {"detail": "Not So Fast jugado."}
    
    mock_verif_evento.assert_called_once_with("Not so fast", ID_CARTA)
    
    mock_jugar_not_so_fast.assert_called_once_with(
        ID_PARTIDA,
        ID_JUGADOR,
        ID_CARTA,
        session
    )
    
    mock_manager.broadcast.assert_awaited_once() 
    
    expected_broadcast_data = json.dumps({
        "evento": "pila-actualizada",
        "data": accion_context_mock,
        "mensaje": f"Jugador {ID_JUGADOR} respondió con 'Not So Fast'!"
    })

    mock_manager.broadcast.assert_called_with(ID_PARTIDA, expected_broadcast_data)
    
    app.dependency_overrides.clear()


# ----------------------------------------------------------------------
# Test Not So Fast (caso carta equivocada)
# ----------------------------------------------------------------------
@patch('game.partidas.endpoints.verif_evento')
@patch('game.partidas.endpoints.jugar_not_so_fast')
def test_API_not_so_fast_carta_incorrecta(
    mock_jugar_not_so_fast, # Este mock no debería ser llamado
    mock_verif_evento, 
    session
):
    """
    Test para jugar Not So Fast fallido: La carta jugada no es Not So Fast.
    Se espera un 400 Bad Request.
    """
    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override

    client = TestClient(app)
    
    ID_PARTIDA = 5
    ID_JUGADOR = 10
    ID_CARTA = 101
    
    mock_verif_evento.return_value = False
    
    response = client.put(
        f"/partidas/{ID_PARTIDA}/respuesta/not_so_fast?id_jugador={ID_JUGADOR}&id_carta={ID_CARTA}"
    )
    
    assert response.status_code == 400
    assert response.json()["detail"] == "La carta no es Not So Fast."
    
    mock_jugar_not_so_fast.assert_not_called()
    
    app.dependency_overrides.clear()


# -----------------------------------TESTS A NIVEL LOGICA NEGOCIOS------------------------------------------
# ----------------------------------------------------------------------
# Test Not So Fast (caso todo ok)
# ----------------------------------------------------------------------
@patch('game.partidas.utils.CartaService')
@patch('game.partidas.utils.JugadorService')
@patch('game.partidas.utils.PartidaService')
def test_jugar_not_so_fast_ok(
    MockPartidaService,
    MockJugadorService,
    MockCartaService,
    session # No se usa
):
    """
    Verifica que jugar_not_so_fast() ejecuta la lógica de juego y 
    devuelve el contexto de acción correcto.
    """
    ID_PARTIDA = 1
    ID_JUGADOR = 5
    ID_CARTA = 16
    
    # Mocks para simular el estado de la partida/jugador
    jugador_mock = MagicMock(id=ID_JUGADOR, partida_id = ID_PARTIDA)
    partida_mock = MagicMock(id=ID_PARTIDA)
    carta_en_mano = MagicMock(id=1, partida_id=ID_PARTIDA,id_carta=ID_CARTA, jugador_id = ID_JUGADOR, tipo="Not so Fast")
    
    # 1. Mockear PartidaService y JugadorService (para la obtención inicial)
    partida_service_instance = MockPartidaService.return_value
    partida_service_instance.obtener_por_id.return_value = partida_mock
    
    jugador_service_instance = MockJugadorService.return_value
    jugador_service_instance.obtener_jugador.return_value = jugador_mock
    
    # 2. Mockear CartaService (simulando la lógica de juego)
    carta_service_instance = MockCartaService.return_value
    carta_service_instance.obtener_mano_jugador.return_value = [
        carta_en_mano, 
        MagicMock(id_carta=99, tipo="otro")
    ]

    # Simular el retorno de la lógica interna de juego
    contexto_accion_esperado = {"id_accion": 123, "tipo": "respuesta"}
    partida_service_instance.obtener_accion_en_progreso.return_value = contexto_accion_esperado
    carta_service_instance.jugar_carta_instantanea.return_value = carta_en_mano
    
    # --- Ejecución ---
    from game.partidas.utils import jugar_not_so_fast
    
    resultado = jugar_not_so_fast(ID_PARTIDA, ID_JUGADOR, ID_CARTA, session)
    
    # Verifica el resultado
    assert resultado == contexto_accion_esperado
    
    # Llamadas a los services
    partida_service_instance.obtener_por_id.assert_called_once_with(ID_PARTIDA)
    jugador_service_instance.obtener_jugador.assert_called_once_with(ID_JUGADOR)
    
    # Verifica la llamada principal a la lógica de juego
    carta_service_instance.jugar_carta_instantanea.assert_called_once_with(
        ID_PARTIDA, ID_JUGADOR, ID_CARTA
    )


# ----------------------------------------------------------------------
# Test Not So Fast partida inexistente
# ----------------------------------------------------------------------
@patch('game.partidas.utils.CartaService')
@patch('game.partidas.utils.JugadorService')
@patch('game.partidas.utils.PartidaService')
def test_jugar_not_so_fast_fail_partida_no_existe(
    MockPartidaService,
    MockJugadorService,
    session
):
    """
    Verifica que se lanza ValueError si la partida no se encuentra.
    """
    ID_PARTIDA = 99
    
    partida_service_instance = MockPartidaService.return_value
    partida_service_instance.obtener_por_id.return_value = None
    
    from game.partidas.utils import jugar_not_so_fast
    
    with pytest.raises(ValueError, match=f"No se ha encontrado la partida con el ID:{ID_PARTIDA}"):
        jugar_not_so_fast(ID_PARTIDA, 1, 1, session)

    partida_service_instance.obtener_por_id.assert_called_once()
    
    MockJugadorService.return_value.obtener_jugador.assert_not_called()


#------------------------------------------TEST INTEGRACION-------------------------------------------------

def test_integracion_jugar_not_so_fast_ok(session, partida1, jugador1, carta_nsf):
    """
    Verifica la ejecución completa de jugar_not_fast con la DB de testing (RAM),
    asegurando que la carta se mueva a la pila y que la acción se registre.
    """
    
    ID_PARTIDA = 1
    ID_JUGADOR_1 = 5
    ID_UNICO_NSF = 101
    ID_TIPO_CARTA_NSF = 16

    session.add_all([partida1, jugador1, carta_nsf])
    session.commit() 
    
    from game.partidas.utils import jugar_not_so_fast
    
    resultado_contexto = jugar_not_so_fast(ID_PARTIDA, ID_JUGADOR_1, ID_TIPO_CARTA_NSF, session) 
        
    # Verificar la ubicación de la carta después de jugarse
    carta_despues = session.query(Carta).filter(Carta.id == ID_UNICO_NSF).first()
    
    assert carta_despues.ubicacion == "en_la_pila"
    assert carta_despues.jugador_id == 5 # Sigue siendo del jugador, se descarta una vez que termina el flujo de NSF
    
    # Verificar que la función devolvió el contexto de acción
    assert isinstance(resultado_contexto, dict)
    assert len(resultado_contexto["pila_respuestas"]) > 1
    
    # Verificar el cambio en el campo JSON 'accion_en_progreso' de la partida
    partida_actualizada = session.query(Partida).filter(Partida.id == ID_PARTIDA).first()
    assert partida_actualizada.accion_en_progreso == resultado_contexto
    
    session.rollback()