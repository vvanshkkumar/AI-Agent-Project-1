from sqlmodel import SQLModel, Field

def ChatMessagePayload(SQLModel) :
    message : str

def ChatMessage(SQLModel, table=true) :
    id : int | None = Field(default=None, primary_key=true)
    message : str
