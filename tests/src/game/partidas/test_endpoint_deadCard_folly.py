from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, ANY
from types import SimpleNamespace
from main import app
from game.modelos.db import get_db

# --- Test exitoso Dead Card Folly ---
@patch("game.partidas.endpoints.obtener_turnos", return_value=[1, 2, 3])
@patch("game.partidas.endpoints.jugar_carta_evento")
@patch("game.cartas.utils.PartidaService")
@patch("game.cartas.utils.JugadorService")
@patch("game.cartas.services.CartaService")
@patch("game.partidas.endpoints.verif_evento", return_value=True)
def test_dead_card_folly_success(
    mock_verif_evento,
    mock_CartaService_services,
    mock_JugadorService,
    mock_PartidaService,
    mock_jugar_carta_evento,
    mock_obtener_turnos
):
    """
    Test exitoso para el evento Dead Card Folly.
    """

    # --- Override de get_db ---
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
    carta_service.obtener_mano_jugador.return_value = [
        SimpleNamespace(
            id=19,
            id_carta=19,
            nombre="Dead Card Folly",
            tipo="Event",
            ubicacion="mano",
            partida_id=1
        )
    ]
    mock_CartaService_services.return_value = carta_service

    # --- Mock de jugar_carta_evento ---
    mock_jugar_carta_evento.return_value = None

    # --- Llamada al endpoint ---
    response = client.post(
        "/partidas/1/evento/DeadCardFolly?id_jugador=1&id_carta=19&direccion=derecha"
    )
    print("Response JSON:", response.json())

    # --- Limpieza ---
    app.dependency_overrides.clear()

    # --- Aserciones ---
    assert response.status_code == 200
    assert "detail" in response.json()
    assert response.json()["detail"] == "Evento jugado correctamente"

    # --- Verificamos que se llamó a verif_evento ---
    mock_verif_evento.assert_called_once_with("Dead card folly", ANY)

# --- Test fallo Dead Card Folly: carta no corresponde al evento ---
@patch("game.partidas.endpoints.obtener_turnos", return_value=[1, 2, 3])
@patch("game.partidas.endpoints.jugar_carta_evento")
@patch("game.cartas.utils.PartidaService")
@patch("game.cartas.utils.JugadorService")
@patch("game.cartas.services.CartaService")
@patch("game.partidas.endpoints.verif_evento", return_value=False)  # <- verif_evento devuelve False
def test_dead_card_folly_fail_carta_no_valida(
    mock_verif_evento,
    mock_CartaService_services,
    mock_JugadorService,
    mock_PartidaService,
    mock_jugar_carta_evento,
    mock_obtener_turnos
):
    """
    Test de fallo para Dead Card Folly: la carta no corresponde al evento.
    """

    # --- Override de get_db ---
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
    carta_service.obtener_mano_jugador.return_value = [
        SimpleNamespace(
            id=19,
            id_carta=19,
            nombre="Carta Random",
            tipo="Event",
            ubicacion="mano",
            partida_id=1
        )
    ]
    mock_CartaService_services.return_value = carta_service

    # --- Mock de jugar_carta_evento ---
    mock_jugar_carta_evento.return_value = None

    # --- Llamada al endpoint ---
    response = client.post(
        "/partidas/1/evento/DeadCardFolly?id_jugador=1&id_carta=19&direccion=derecha"
    )
    print("Response JSON:", response.json())

    # --- Limpieza ---
    app.dependency_overrides.clear()

    # --- Aserciones ---
    assert response.status_code == 400
    assert "detail" in response.json()
    assert response.json()["detail"] == "La carta no corresponde al evento Dead Card Folly"
