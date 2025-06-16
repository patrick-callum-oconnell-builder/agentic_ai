from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class ChatRequest(BaseModel):
    messages: list[dict]

@app.post("/api/chat")
async def chat(request: ChatRequest):
    try:
        # Convert Pydantic Message objects to dicts
        messages = [m.dict() for m in request.messages]
        response = await agent.process_messages(messages)
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 