from datetime import datetime

from pydantic import BaseModel, Field


class GenerateQuestionRequest(BaseModel):
    session_id: str = Field(min_length=3, max_length=64)
    pokemon_name: str = Field(min_length=2, max_length=64)


class GenerateQuestionResponse(BaseModel):
    question_id: int
    session_id: str
    pokemon_name: str
    prompt: str
    created_at: datetime


class SubmitAnswerRequest(BaseModel):
    user_answer: str = Field(min_length=1, max_length=500)


class SubmitAnswerResponse(BaseModel):
    question_id: int
    is_correct: bool
    expected_answer: str
    explanation: str


class SessionHistoryItem(BaseModel):
    id: int
    pokemon_name: str
    prompt: str
    answer: str
    explanation: str
    created_at: datetime


class SessionHistoryResponse(BaseModel):
    session_id: str
    questions: list[SessionHistoryItem]
