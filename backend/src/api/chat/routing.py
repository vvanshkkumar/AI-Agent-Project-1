from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from .db_models import ChatMessage, ChatMessagePayload
from db import get_session

router = APIRouter()


# curl http://localhost:8000/api/health/
@router.get("/health/")
def chat_health():
    return {"status":"ok"}


# curl http://localhost:8000/api/recents/
@router.get("/recents/")
def chat_list_messages(session : Session = Depends(get_session)):

    query = select(ChatMessage) # sql -> query
    results = session.exec(query).fetchall()[:10]
    return results


# curl -X POST -d '{"message" : "checking only"}' -H"Content-Type: application/json" http://localhost:8000/api/create/
@router.post("/create/",response_model=ChatMessage)
def chat_create_message(payload:ChatMessagePayload,
                        session: Session = Depends(get_session)) :
    data = payload.model_dump()    # convert the obj to dict
    obj = ChatMessage.model_validate(data) # validate if no component is missing
    session.add(obj)
    session.commit()
    session.refresh(obj) # ensures that the data is successfully inserted/added                    
    
    return obj