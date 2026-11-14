from datetime import date
from pydantic import BaseModel, Field

class LoginRequest(BaseModel):
    password: str
class LoginResponse(BaseModel):
    token: str
    role: str = "admin"
class CorrectionRequest(BaseModel):
    vehicle_number: str
    status_date: date
    corrected_status: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=3, max_length=1000)
class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[dict] = []
