from sqlalchemy import Column, String
from app.db.database import Base

class ChatBot(Base):
    __tablename__ = "chatbot"

    client_id = Column(String(255), primary_key=True)
    client_secret = Column(String(255), nullable=False)
    user_id = Column(String(255), nullable=False)
    canvas_id = Column(String(32), nullable=False) 
    status = Column(String(20), nullable=False, default="stop")