from fastapi import APIRouter, HTTPException
from schemas.models import AskRequest, AskResponse
from agent.agent import EngineeringAgent

router = APIRouter()
agent = EngineeringAgent()

@router.post("/ask", response_model=AskResponse)
async def ask_agent(request: AskRequest):
    try:
        response = agent.ask(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
