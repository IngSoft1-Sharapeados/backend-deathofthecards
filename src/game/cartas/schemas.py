from datetime import date
from pydantic import BaseModel
from game.cartas.dtos import CartaDTO

class CartasOut(BaseModel):
    nombre: str
    tipo: enumerate = { "detective", "secreto",
                       "devious", "insta",
                       "evento", "asesino escapo?"   
                    }
    bocaArriba: bool
    ubicacion: enumerate = { "mano", "mazo_robo", 
                          "mazo_descarte"
                        } 
    descripcion: str 
    jugador_id: int
    partida_id: int 
