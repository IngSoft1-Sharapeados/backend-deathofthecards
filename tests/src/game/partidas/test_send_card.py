# tests/test_send_card.py
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, ANY
from main import app
from game.modelos.db import get_db
import json

@patch("game.partidas.endpoints.manager.send_personal_message")
@patch("game.partidas.endpoints.enviar_carta")
@patch("game.partidas.endpoints.verif_send_card", return_value=True)
def test_send_card_behavior(mock_verif_send_card, mock_enviar_carta, mock_send_message):
    """
    Test unitario del endpoint send_card
    """

    # --- Dependencia de DB en memoria ---
    def get_db_override():
        yield MagicMock()
    app.dependency_overrides[get_db] = get_db_override

    client = TestClient(app)

    # --- Llamada al endpoint ---
    response = client.post("/partidas/1/evento/sendCard?id_jugador=1&id_objetivo=2&id_carta=10")

    print("Response JSON:", response.json())

    # --- Limpieza ---
    app.dependency_overrides.clear()

    # --- Aserciones básicas ---
    assert response.status_code == 200
    assert "detail" in response.json()
    assert response.json()["detail"] == "Carta enviada correctamente"

    # --- Verificaciones de llamadas ---
    mock_verif_send_card.assert_called_once_with(1, 10, 1, 2, ANY)
    mock_enviar_carta.assert_called_once_with(10, 2, ANY)
    mock_send_message.assert_called_once()
    called_args = mock_send_message.call_args[0]
    assert called_args[0] == 2  # id_objetivo
    data = json.loads(called_args[1])
    assert data["evento"] == "actualizacion-mano"

@patch("game.partidas.endpoints.manager.send_personal_message")
@patch("game.partidas.endpoints.enviar_carta")
@patch("game.partidas.endpoints.verif_send_card", return_value=False)  # Validación falla
def test_send_card_fail_carta_no_en_mano(
    mock_verif_send_card,
    mock_enviar_carta,
    mock_send_message
):
    """
    Test cuando la carta no está en la mano del jugador.
    Debe devolver un error 500 (según la lógica del endpoint).
    """

    # --- Mock de DB ---
    def get_db_override():
        yield MagicMock()
    app.dependency_overrides[get_db] = get_db_override

    client = TestClient(app)

    # --- Llamada al endpoint ---
    response = client.post("/partidas/1/evento/sendCard?id_jugador=1&id_objetivo=2&id_carta=10")

    # --- Limpieza ---
    app.dependency_overrides.clear()

    # --- Aserciones ---
    assert response.status_code == 500
    assert "detail" in response.json()
    assert response.json()["detail"] == "Error al enviar la carta"

    # --- Verificaciones de llamadas ---
    mock_verif_send_card.assert_called_once_with(1, 10, 1, 2, ANY)
    mock_enviar_carta.assert_not_called()
    mock_send_message.assert_not_called()


@patch("game.partidas.endpoints.manager.send_personal_message")
@patch("game.partidas.endpoints.enviar_carta")
@patch("game.partidas.endpoints.verif_send_card")
def test_send_card_fail_partida_no_iniciada(
    mock_verif_send_card,
    mock_enviar_carta,
    mock_send_message
):
    """
    Test cuando la partida no está iniciada.
    Debe devolver un error 403 (Partida no iniciada).
    """

    # --- Mock de verif_send_card para simular ValueError ---
    def verif_side_effect(id_partida, id_carta, id_jugador, id_objetivo, db):
        raise ValueError("Partida no iniciada")
    
    mock_verif_send_card.side_effect = verif_side_effect

    # --- Mock de DB ---
    def get_db_override():
        yield MagicMock()
    app.dependency_overrides[get_db] = get_db_override

    client = TestClient(app)

    # --- Llamada al endpoint ---
    response = client.post("/partidas/1/evento/sendCard?id_jugador=1&id_objetivo=2&id_carta=10")

    # --- Limpieza ---
    app.dependency_overrides.clear()

    # --- Aserciones ---
    assert response.status_code == 403
    assert "detail" in response.json()
    assert response.json()["detail"] == "Partida no iniciada"

    # --- Verificaciones de llamadas ---
    mock_verif_send_card.assert_called_once_with(1, 10, 1, 2, ANY)
    mock_enviar_carta.assert_not_called()
    mock_send_message.assert_not_called()
