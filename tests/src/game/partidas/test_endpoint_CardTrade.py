from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, ANY
from types import SimpleNamespace
from main import app
from game.modelos.db import get_db


@patch("game.partidas.endpoints.jugar_carta_evento")
@patch("game.cartas.utils.PartidaService")
@patch("game.cartas.utils.JugadorService")
@patch("game.cartas.services.CartaService")
@patch("game.partidas.endpoints.verif_evento", return_value=True)
def test_evento_card_trade_behavior(
    mock_verif_evento,
    mock_CartaService_services,
    mock_JugadorService,
    mock_PartidaService,
    mock_jugar_carta_evento
):
    """
    Test de comportamiento para el evento Card Trade.
    """

    def get_db_override():
        yield MagicMock()
    app.dependency_overrides[get_db] = get_db_override

    client = TestClient(app)

    # --- Mock de PartidaService ---
    partida_service = MagicMock()
    partida_service.obtener_por_id.return_value = SimpleNamespace(
        id=1, iniciada=True, turno_id=1
    )
    partida_service.desgracia_social.return_value = False
    mock_PartidaService.return_value = partida_service

    # --- Mock de JugadorService ---
    jugador_service = MagicMock()
    jugador_service.obtener_jugador.return_value = SimpleNamespace(id=1, partida_id=1)
    mock_JugadorService.return_value = jugador_service

    # --- Mock de CartaService ---
    carta_service = MagicMock()
    mock_CartaService_services.return_value = carta_service

    carta_en_mano = SimpleNamespace(
        id=10,
        id_carta=21,
        nombre="Card Trade",
        tipo="Event",
        ubicacion="mano",
        partida_id=1,
        bocaArriba=False
    )

    carta_service.obtener_mano_jugador.return_value = [carta_en_mano]
    carta_service.obtener_carta_de_mano.return_value = carta_en_mano
    carta_service.evento_jugado_en_turno.return_value = False
    carta_service.jugar_card_trade.return_value = {
        "mensaje": "Card Trade jugada correctamente",
        "intercambio_realizado": True,
        "jugador_origen": 1,
        "jugador_destino": 2
    }

    # --- Mock de jugar_carta_evento ---
    mock_jugar_carta_evento.return_value = None

    # --- Ejecución del endpoint ---
    response = client.post("/partidas/1/evento/CardTrade?id_jugador=1&id_carta=10&id_objetivo=2")
    print("Response JSON:", response.json())

    # --- Limpieza ---
    app.dependency_overrides.clear()

    # --- Aserciones ---
    assert response.status_code == 200
    assert "detail" in response.json()
    assert response.json()["detail"] == "Evento jugado correctamente"

    # --- Verificamos que se llamó a verif_evento ---
    mock_verif_evento.assert_called_once_with("Card trade", ANY)


# --- Test: jugador no en turno ---
@patch("game.partidas.endpoints.jugar_carta_evento")
@patch("game.cartas.utils.PartidaService")
@patch("game.cartas.utils.JugadorService")
@patch("game.cartas.services.CartaService")
def test_card_trade_fail_jugador_no_turno(
    mock_CartaService_services,
    mock_JugadorService,
    mock_PartidaService,
    mock_jugar_carta_evento
):
    """
    Caso de fallo: el jugador no está en turno.
    Debe devolver HTTP 403.
    """

    def get_db_override():
        yield MagicMock()
    app.dependency_overrides[get_db] = get_db_override

    client = TestClient(app)

    # --- Mock de PartidaService ---
    partida_service = MagicMock()
    # turno de otro jugador
    partida_service.obtener_por_id.return_value = SimpleNamespace(
        id=1, iniciada=True, turno_id=2
    )
    partida_service.desgracia_social.return_value = False
    mock_PartidaService.return_value = partida_service

    # --- Mock de JugadorService ---
    jugador_service = MagicMock()
    jugador_service.obtener_jugador.return_value = SimpleNamespace(id=1, partida_id=1)
    mock_JugadorService.return_value = jugador_service

    # --- Mock de CartaService ---
    carta_service = MagicMock()
    carta_service.obtener_mano_jugador.return_value = [
        SimpleNamespace(
            id=10, id_carta=21, nombre="Card Trade", tipo="Event",
            ubicacion="mano", partida_id=1, bocaArriba=False
        )
    ]
    mock_CartaService_services.return_value = carta_service

    response = client.post("/partidas/1/evento/CardTrade?id_jugador=1&id_carta=10&id_objetivo=2")

    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "detail" in response.json()


# --- Test: carta no está en la mano ---
@patch("game.partidas.endpoints.jugar_carta_evento")
@patch("game.cartas.utils.PartidaService")
@patch("game.cartas.utils.JugadorService")
@patch("game.cartas.services.CartaService")
def test_card_trade_fail_carta_no_mano(
    mock_CartaService_services,
    mock_JugadorService,
    mock_PartidaService,
    mock_jugar_carta_evento
):
    """
    Caso de fallo: la carta no está en la mano del jugador.
    Debe devolver HTTP 500.
    """

    def get_db_override():
        yield MagicMock()
    app.dependency_overrides[get_db] = get_db_override

    client = TestClient(app)

    # --- Mock de PartidaService ---
    partida_service = MagicMock()
    partida_service.obtener_por_id.return_value = SimpleNamespace(
        id=1, iniciada=True, turno_id=1
    )
    partida_service.desgracia_social.return_value = False
    mock_PartidaService.return_value = partida_service

    # --- Mock de JugadorService ---
    jugador_service = MagicMock()
    jugador_service.obtener_jugador.return_value = SimpleNamespace(id=1, partida_id=1)
    mock_JugadorService.return_value = jugador_service

    # --- Mock de CartaService ---
    carta_service = MagicMock()
    # simulamos que la mano del jugador está vacía
    carta_service.obtener_mano_jugador.return_value = []
    mock_CartaService_services.return_value = carta_service

    response = client.post("/partidas/1/evento/CardTrade?id_jugador=1&id_carta=10&id_objetivo=2")

    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "detail" in response.json()