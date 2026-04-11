from fastapi import APIRouter, Depends
from sqlmodel import Sesssion
from .db_models import ChatMessage, ChatMessagePayload
from backend.src.db import get_session

router = APIRouter()

@router.get("/")
def chat_health():
    return {"status":"ok"}

@router.get("/",response_model=ChatMessage)
def chat_create_message(payload:ChatMessagePayload,
                        session: Session:Depends(get_session) :
    data = payload.model_dump()    # convert the obj to dict
    obj = ChatMessage.model_validate(data) # validate if no component is missing
    session.add(obj)
    session.commit()
    session.refresh(obj) # ensures that the data is successfully inserted/added                    
    
    return obj