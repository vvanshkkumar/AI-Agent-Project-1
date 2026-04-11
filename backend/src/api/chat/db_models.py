from sqlmodel import SQLModel, Field

class ChatMessagePayload(SQLModel) :
    message : str

class ChatMessage(SQLModel, table=True) :
    id : int | None = Field(default=None, primary_key=True)
    message : str
