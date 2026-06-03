import { FormEvent, useMemo, useState } from "react";
import {
  generateQuestion,
  getSessionHistory,
  submitAnswer,
  type AnswerResult,
  type GeneratedQuestion,
  type SessionHistoryItem,
} from "../api/client";

const seededSessionId = `talk-${Math.random().toString(36).slice(2, 10)}`;

export function App() {
  const [sessionId, setSessionId] = useState(seededSessionId);
  const [pokemonName, setPokemonName] = useState("pikachu");
  const [question, setQuestion] = useState<GeneratedQuestion | null>(null);
  const [answer, setAnswer] = useState("");
  const [result, setResult] = useState<AnswerResult | null>(null);
  const [history, setHistory] = useState<SessionHistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmitAnswer = useMemo(
    () => !!question && answer.trim().length > 0,
    [question, answer],
  );

  async function onGenerate(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);
    setLoading(true);

    try {
      const generated = await generateQuestion(sessionId, pokemonName);
      setQuestion(generated);
      setAnswer("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  async function onSubmitAnswer(e: FormEvent) {
    e.preventDefault();
    if (!question) {
      return;
    }

    setError(null);
    setLoading(true);

    try {
      const answerResult = await submitAnswer(question.question_id, answer);
      setResult(answerResult);
      const sessionHistory = await getSessionHistory(sessionId);
      setHistory(sessionHistory);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="shell">
      <header>
        <h1>Pokemon Q&A App</h1>
        <p>
          Ask Claude-powered Pokemon questions with PokeAPI-grounded context.
        </p>
      </header>

      <section className="panel">
        <form onSubmit={onGenerate}>
          <label>Session ID</label>
          <input
            value={sessionId}
            onChange={(e) => setSessionId(e.target.value)}
          />
          <label>Pokemon Name</label>
          <input
            value={pokemonName}
            onChange={(e) => setPokemonName(e.target.value)}
            placeholder="e.g. mew"
          />
          <button type="submit" disabled={loading}>
            Generate Question
          </button>
        </form>
      </section>

      {question && (
        <section className="panel">
          <h2>Question</h2>
          <p>{question.prompt}</p>
          <form onSubmit={onSubmitAnswer}>
            <label>Your answer</label>
            <input value={answer} onChange={(e) => setAnswer(e.target.value)} />
            <button type="submit" disabled={!canSubmitAnswer || loading}>
              Submit Answer
            </button>
          </form>
        </section>
      )}

      {result && (
        <section className="panel">
          <h2>Result</h2>
          <p>{result.is_correct ? "Correct" : "Not quite"}</p>
          <p>Expected: {result.expected_answer}</p>
          <p>{result.explanation}</p>
        </section>
      )}

      <section className="panel">
        <h2>Session History</h2>
        <button
          type="button"
          onClick={async () => {
            try {
              const sessionHistory = await getSessionHistory(sessionId);
              setHistory(sessionHistory);
            } catch (err) {
              setError(err instanceof Error ? err.message : "Unknown error");
            }
          }}
        >
          Refresh History
        </button>
        <ul>
          {history.map((item) => (
            <li key={item.id}>
              <strong>{item.pokemon_name}</strong>: {item.prompt}
            </li>
          ))}
        </ul>
      </section>

      {error && <p className="error">{error}</p>}
    </main>
  );
}
