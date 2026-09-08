# models.py
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    team = Column(String, nullable=True, default="")

class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True)
    player_a_id = Column(Integer, ForeignKey("players.id"))
    player_b_id = Column(Integer, ForeignKey("players.id"))
    
    set1 = Column(String, default="-")
    set2 = Column(String, default="-")
    set3 = Column(String, default="-")
    set4 = Column(String, default="-")
    set5 = Column(String, default="-")
    
    score_sets = Column(String, default="0 - 0")
    winner_name = Column(String, default="")

    player_a = relationship("Player", foreign_keys=[player_a_id])
    player_b = relationship("Player", foreign_keys=[player_b_id])