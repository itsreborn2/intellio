from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from common.models.base import Base
from uuid import UUID as PyUUID

class ChatHistory(Base):
    __tablename__ = "chat_history"
    
    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[PyUUID] = mapped_column(UUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False) 