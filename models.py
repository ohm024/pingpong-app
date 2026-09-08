from sqlalchemy import Column, Integer, String, ForeignKey
from database import Base

class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    club = Column(String)
    workspace_id = Column(String, index=True, default="default")

class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True)
    player1_id = Column(Integer, ForeignKey("players.id"))
    player2_id = Column(Integer, ForeignKey("players.id"))
    p1_score = Column(Integer)
    p2_score = Column(Integer)
    winner_id = Column(Integer, ForeignKey("players.id"))
    workspace_id = Column(String, index=True, default="default")