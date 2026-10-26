from sqlmodel import SQLModel, Field, Relationship
from typing import List, Optional
import datetime

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    ip_address: str
    first_seen: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    conversations: List["Conversation"] = Relationship(back_populates="user")


class Conversation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    user_message: str
    ai_response: str
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    user: Optional[User] = Relationship(back_populates="conversations")
