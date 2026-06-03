const API_BASE = import.meta.env.VITE_API_BASE ?? "/api/v1";

export type GeneratedQuestion = {
  question_id: number;
  session_id: string;
  pokemon_name: string;
  prompt: string;
  created_at: string;
};

export type AnswerResult = {
  question_id: number;
  is_correct: boolean;
  expected_answer: string;
  explanation: string;
};

export type SessionHistoryItem = {
  id: number;
  pokemon_name: string;
  prompt: string;
  answer: string;
  explanation: string;
  created_at: string;
};

export async function generateQuestion(
  sessionId: string,
  pokemonName: string,
): Promise<GeneratedQuestion> {
  const resp = await fetch(`${API_BASE}/questions/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, pokemon_name: pokemonName }),
  });

  if (!resp.ok) {
    throw new Error(`Generate failed: ${resp.status}`);
  }

  return resp.json();
}

export async function submitAnswer(
  questionId: number,
  userAnswer: string,
): Promise<AnswerResult> {
  const resp = await fetch(`${API_BASE}/questions/${questionId}/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_answer: userAnswer }),
  });

  if (!resp.ok) {
    throw new Error(`Answer submit failed: ${resp.status}`);
  }

  return resp.json();
}

export async function getSessionHistory(
  sessionId: string,
): Promise<SessionHistoryItem[]> {
  const resp = await fetch(`${API_BASE}/questions/sessions/${sessionId}`);

  if (!resp.ok) {
    throw new Error(`Session history failed: ${resp.status}`);
  }

  const payload = await resp.json();
  return payload.questions as SessionHistoryItem[];
}
