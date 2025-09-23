from fastapi import APIRouter

#from game.jugadores.endpoints import jugadores_router
from game.partidas.endpoints import partidas_router
#from game.cartas.endpoints import cartas_router

api_router = APIRouter()
#api_router.include_router(jugadores_router, prefix="/jugadores", tags=["tags"])
api_router.include_router(partidas_router, prefix="/partidas", tags=["partidas"])
#api_router.include_router(cartas_router, prefix="/cartas", tags=["cartas"])