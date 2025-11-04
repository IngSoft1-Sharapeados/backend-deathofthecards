"""Modelo Partida"""
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.orm import relationship, Mapped, mapped_column
from typing import List
from game.modelos.db import Base
 
class Partida(Base):
    __tablename__ = "partidas"
 
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String, nullable=False)
    anfitrionId: Mapped[int] = mapped_column(Integer, nullable=False)
    cantJugadores: Mapped[int] = mapped_column(Integer, nullable=False)
    iniciada: Mapped[bool] = mapped_column(Boolean, default=False)
    maxJugadores: Mapped[int] = mapped_column(Integer, nullable=True)
    minJugadores: Mapped[int] = mapped_column(Integer, nullable=True)
    turno_id: Mapped[int] = mapped_column(Integer,nullable=True)
    
    ordenTurnos: Mapped[str] = mapped_column(String, nullable=True)  # Almacena el orden de turnos como una cadena separada por comas
    turno_id: Mapped[int] = mapped_column(Integer, nullable=True)  # ID del jugador cuyo turno es actualmente
    

    # Relación de 1 a muchos con Jugador
    jugadores: Mapped[List["Jugador"]] = relationship("Jugador", back_populates="partida")

    cartas: Mapped[List["Carta"]] = relationship("Carta", back_populates="partida")
        
    # Relación de 1 a muchos con VotacionEvento
    votaciones_evento: Mapped[List["VotacionEvento"]] = relationship(
                                                        "VotacionEvento",
                                                        back_populates="partida",
                                                        cascade="all, delete-orphan"
                                                                    )
    
class VotacionEvento(Base):
    __tablename__ = "votaciones_evento"

    partida_id: Mapped[int] = mapped_column(ForeignKey("partidas.id"), nullable=False)
    id_jugador: Mapped[int] = mapped_column(ForeignKey("jugadores.id"), nullable=False)
    id_votado: Mapped[int] = mapped_column(ForeignKey("jugadores.id"), nullable=False)

    partida: Mapped["Partida"] = relationship("Partida", back_populates="votaciones_evento")

    __table_args__ = (
        PrimaryKeyConstraint('partida_id', 'id_jugador', name='pk_votacion_evento'),
    )