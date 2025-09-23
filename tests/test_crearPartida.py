import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
#from game.partidas.endpoints import partidas_router
#from game.partidas.services import PartidaService

from main import app

client = TestClient(app)

@pytest.fixture
def partida_service():
    return PartidaService()


@pytest.fixture
def datosPartida_1():
    return {
        "nombre": "partiditaTEST",
        "maxJugadores": 4
    }

@patch('game.partidas.services.PartidaService')
def test_crear_partida_ok(mock_PartidaService, datosPartida_1):

    mock_service = MagicMock()
    mock_service.crear.return_value = {"id_partida": 1}
    mock_PartidaService.return_value = mock_service

    # Act
    response = client.post("/partidas", json=datosPartida_1)

    assert response.status_code == 201
    assert response.json() == {"id_partida": 1}
    #mock_service.crear.assert_called_once_with(datosPartida_1)

@patch('game.partidas.services.PartidaService')
def test_crear_partida_sin_cant_jugadores(mock_PartidaService):

    mock_service = MagicMock()
    mock_PartidaService.return_value = mock_service
    datos_incompletos = {"nombre": "partida sin cantidad"}

    response = client.post("/partidas", json=datos_incompletos)

    assert response.status_code == 422  # Unprocessable Entity

#@patch('game.partidas.services.PartidaService')
#def test_crear_partida_service_error(mock_PartidaService, datosPartida_1):
#    # Arrange
#    mock_service = MagicMock()
#    mock_service.crear.side_effect = Exception("Service error")
#    mock_PartidaService.return_value = mock_service

    # Act
#    response = client.post("/partidas", json=datosPartida_1)

    # Assert
#    assert (response.status_code == 400)
