from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.api.dependencies import CurrentUser
from app.db.session import SessionLocal
from app.core.config import settings
from app.schemas.conversation import ChatRequest
from app.services.chat_service import ChatService
router=APIRouter(prefix="/chat",tags=["Chat"])
@router.post("/stream")
async def stream(data:ChatRequest,user:CurrentUser):
 if len(data.message)>settings.max_chat_message_length:from fastapi import HTTPException;raise HTTPException(422,"Message is too long")
 async def body():
  async with SessionLocal() as db:
   async for chunk in ChatService(db).stream(user,data):yield chunk
 return StreamingResponse(body(),media_type="text/event-stream",headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})
