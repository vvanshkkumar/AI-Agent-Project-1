from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from api.ai.schemas import EmailMessageSchema
from api.ai.services import generate_email
from .db_models import ChatMessage, ChatMessagePayload
from db import get_session
from settings import ConfigurationError

router = APIRouter()


# curl http://localhost:8000/api/health/
@router.get("/health/")
def chat_health():
    return {"status":"ok"}


# curl http://localhost:8000/api/recents/
@router.get("/recents/")
def chat_list_messages(session : Session = Depends(get_session)):

    query = select(ChatMessage).order_by(ChatMessage.id.desc()).limit(10) # sql -> query
    results = session.exec(query).all()
    return results


# curl -X POST -d '{"message" : "got fired from job without any reason"}' -H"Content-Type: application/json" http://localhost:8000/api/create/
@router.post("/create/", response_model=EmailMessageSchema)
def chat_create_message(payload:ChatMessagePayload,
                        session: Session = Depends(get_session)) :
    try:
        response = generate_email(payload.message)
    except ConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Email generation failed: {exc}") from exc

    data = payload.model_dump()    # convert the obj to dict
    obj = ChatMessage.model_validate(data) # validate if no component is missing
    session.add(obj)
    session.commit()
    
    return response
