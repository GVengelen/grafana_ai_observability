from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import QuestionRecord, SessionRecord
from app.schemas.questions import (
    GenerateQuestionRequest,
    GenerateQuestionResponse,
    SessionHistoryItem,
    SessionHistoryResponse,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
)
from app.services.claude_client import generate_question_from_context
from app.services.pokeapi_client import fetch_pokemon_context

router = APIRouter(prefix="/questions", tags=["questions"])


@router.post("/generate", response_model=GenerateQuestionResponse)
async def generate_question(payload: GenerateQuestionRequest, db: Session = Depends(get_db)):
    session = db.get(SessionRecord, payload.session_id)
    if session is None:
        session = SessionRecord(id=payload.session_id)
        db.add(session)
        db.flush()

    try:
        pokemon_context = await fetch_pokemon_context(payload.pokemon_name)
        is_subject_only = False
    except Exception:
        pokemon_context = {"name": payload.pokemon_name}
        is_subject_only = True

    try:
        question_payload = await generate_question_from_context(
            pokemon_context, conversation_id=payload.session_id, is_subject_only=is_subject_only
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Question generation failed: {exc}") from exc

    record = QuestionRecord(
        session_id=session.id,
        pokemon_name=pokemon_context["name"],
        prompt=question_payload["prompt"],
        answer=question_payload["answer"],
        explanation=question_payload["explanation"],
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return GenerateQuestionResponse(
        question_id=record.id,
        session_id=record.session_id,
        pokemon_name=record.pokemon_name,
        prompt=record.prompt,
        created_at=record.created_at,
    )


@router.post("/{question_id}/answer", response_model=SubmitAnswerResponse)
def submit_answer(question_id: int, payload: SubmitAnswerRequest, db: Session = Depends(get_db)):
    question = db.get(QuestionRecord, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    normalized_user = payload.user_answer.strip().lower()
    normalized_expected = question.answer.strip().lower()

    return SubmitAnswerResponse(
        question_id=question_id,
        is_correct=normalized_user == normalized_expected,
        expected_answer=question.answer,
        explanation=question.explanation,
    )


@router.get("/sessions/{session_id}", response_model=SessionHistoryResponse)
def get_session_history(session_id: str, db: Session = Depends(get_db)):
    session = db.get(SessionRecord, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    rows = db.scalars(
        select(QuestionRecord)
        .where(QuestionRecord.session_id == session_id)
        .order_by(QuestionRecord.created_at.desc())
    ).all()

    return SessionHistoryResponse(
        session_id=session_id,
        questions=[
            SessionHistoryItem(
                id=row.id,
                pokemon_name=row.pokemon_name,
                prompt=row.prompt,
                answer=row.answer,
                explanation=row.explanation,
                created_at=row.created_at,
            )
            for row in rows
        ],
    )
