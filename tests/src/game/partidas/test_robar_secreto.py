import pytest
import os
import json
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
from main import app
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch, AsyncMock
from game.modelos.db import get_db
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from game.modelos.db import Base, get_db, get_session_local
from game.partidas.utils import *


# ---------- FIXTURE DE DB ----------
@pytest.fixture(name="session")
def dbTesting_fixture():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSessionLocal = get_session_local(engine)
    Base.metadata.create_all(bind=engine)
    with TestingSessionLocal() as session:
        yield session


@patch('game.partidas.endpoints.manager') # 1. Mock para el manager de WebSocket (evita error de serialización)
@patch('game.partidas.endpoints.robar_secreto') # 2. Mock para la función robar_secreto (evita el error 401)
@patch('game.partidas.endpoints.CartaService') # 3. Mock Clase CartaService en endpoints (CLAVE para el AttributeError)
@patch('game.partidas.utils.CartaService')      # 4. Mock Clase CartaService en utils
@patch('game.partidas.utils.JugadorService')
@patch('game.partidas.utils.PartidaService')
def test_robar_secreto_otro_jugador_ok(
    mock_PartidaService,
    mock_JugadorService,
    mock_CartaService_utils,
    mock_CartaService_endpoints, # Argumento para el mock de la Clase CartaService en el endpoint
    mock_robar_secreto, 
    mock_manager, 
    session
):
    """
    Test robar secreto en caso de éxito.
    """
    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override

    client = TestClient(app)
    
    # --- 1. Definición de Mocks ---
    
    partida_mock = MagicMock(id=1, turno_id=1)
    jugador_turno = MagicMock(id=1)
    jugador_destino = MagicMock(id=2)
    id_jugador_victima = 3 # El dueño original del secreto

    # Carta robada antes de la acción
    carta_a_robar_mock = MagicMock(id=1, bocaArriba=True, jugador_id=id_jugador_victima, partida_id=1, tipo="secreto")

    # Mocks de cartas para la lista de secretos (deben tener .bocaArriba)
    secreto_mock_oculto = MagicMock(bocaArriba=False)
    secreto_mock_robado = MagicMock(bocaArriba=False)

    # Listas de secretos después del robo (side_effect)
    secretos_destino_post_robo = [secreto_mock_robado, secreto_mock_oculto]
    secretos_victima_post_robo = []

    # --- 2. Configuración de Retornos ---
    
    # Función robar_secreto
    mock_robar_secreto.return_value = {"id-secreto": carta_a_robar_mock.id}
    
    # Instancia de CartaService
    carta_service_instance = MagicMock()
    carta_service_instance.obtener_carta_por_id.return_value = carta_a_robar_mock
    
    carta_service_instance.obtener_secretos_jugador.side_effect = (
        lambda id_jugador, id_partida:
        secretos_destino_post_robo
        if id_jugador == jugador_destino.id
        else secretos_victima_post_robo
        if id_jugador == id_jugador_victima
        else []
    )

    
    # CLAVE: Configurar ambos mocks de CLASE para devolver la misma INSTANCIA
    mock_CartaService_utils.return_value = carta_service_instance 
    mock_CartaService_endpoints.return_value = carta_service_instance 

    # JugadorService
    jugador_service_instance = MagicMock()
    jugador_service_instance.obtener_jugador.side_effect = lambda id: \
        jugador_turno if id == 1 else jugador_destino if id == 2 else MagicMock(id=3)
    mock_JugadorService.return_value = jugador_service_instance

    # PartidaService
    partida_service_instance = MagicMock()
    partida_service_instance.obtener_por_id.return_value = partida_mock
    mock_PartidaService.return_value = partida_service_instance

    # Manager
    mock_manager.broadcast = AsyncMock(return_value=None)
    mock_manager.clean_connections = AsyncMock(return_value=None)
    
    # --- 3. EJECUCIÓN ---
    response = client.patch(
        f"/partidas/{partida_mock.id}/robo-secreto?id_jugador_turno={jugador_turno.id}&id_jugador_destino={jugador_destino.id}&id_unico_secreto={carta_a_robar_mock.id}"
    )

    # --- 4. ASSERTIONS ---
    
    # Éxito
    assert response.status_code == 200
    assert response.json() == {"id-secreto": carta_a_robar_mock.id}
    
    # Llamada a robar_secreto
    mock_robar_secreto.assert_called_once_with(
        partida_mock.id,
        jugador_turno.id,
        jugador_destino.id,
        carta_a_robar_mock.id,
        session
    )
    
    # Broadcasts
    assert mock_manager.broadcast.call_count == 3
    
    # Primer broadcast (Jugador Destino)
    broadcast_destino_data = json.loads(mock_manager.broadcast.call_args_list[0].args[1])
    assert broadcast_destino_data["jugador-id"] == jugador_destino.id
    
    # Segundo broadcast (Jugador Víctima)
    broadcast_victima_data = json.loads(mock_manager.broadcast.call_args_list[1].args[1])
    assert broadcast_victima_data["jugador-id"] == id_jugador_victima
    
    app.dependency_overrides.clear()


@patch('game.partidas.endpoints.CartaService')
@patch('game.partidas.endpoints.robar_secreto')
@patch('game.partidas.utils.CartaService')
@patch('game.partidas.utils.JugadorService')
@patch('game.partidas.utils.PartidaService')
def test_robar_secreto_oculto(mock_partida_service, mock_jugador_service, mock_carta_service, mock_robar_secreto, session):
    """Test fallo al querer robar un secreto que está oculto"""
    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override

    client = TestClient(app)

    partida_mock = MagicMock()
    partida_mock.id = 1
    partida_mock.turno_id = 1

    jugador_turno = MagicMock()
    jugador_turno.id = 1

    jugador_destino = MagicMock()
    jugador_destino.id = 2

    carta_secreta = MagicMock()
    carta_secreta.id = 1
    carta_secreta.jugador_id = 1
    carta_secreta.bocaArriba = False  # Oculto
    carta_secreta.partida_id = 1

    mock_partida_service.return_value.obtener_por_id.return_value = partida_mock
    mock_jugador_service.return_value.obtener_jugador.side_effect = lambda id: jugador_turno if id == 1 else jugador_destino
    mock_carta_service.return_value.obtener_carta_por_id.return_value = carta_secreta

    mock_robar_secreto.side_effect = ValueError("No se puede robar un secreto que está oculto!")

    response = client.patch("/partidas/1/robo-secreto?id_jugador_turno=1&id_jugador_destino=2&id_unico_secreto=1")

    assert response.status_code == 401
    assert "No se puede robar un secreto que está oculto" in response.json()["detail"]

    app.dependency_overrides.clear()
