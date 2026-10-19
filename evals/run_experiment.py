#!/usr/bin/env python3
"""Run the published pokemon-trivia-generator suite against the real agent.

Suite:       suite_23704bea-5f16-438b-9f0d-62fda3dfc21a @ v3 (pulled, never modified)
Evaluators:  the three stored evaluators published for that suite, fetched by id from the
             control plane and verified (not rewritten) by EvaluatorsClient.ensure.
Agent:       backend/app/services/claude_client.generate_question_from_context, called
             through the app's own Agent Observability client so generations are recorded.

Credentials come from the untracked .env / environment, never from this file:
  AGENTO11Y_ENDPOINT, AGENTO11Y_AUTH_TENANT_ID, AGENTO11Y_AUTH_TOKEN, AGENTO11Y_INGEST_ACTOR,
  AGENTO11Y_SERVICE_ACCOUNT_TOKEN + GRAFANA_URL (control plane: suite + evaluator reads),
  ANTHROPIC_API_KEY (agent).

    cd backend && .venv/bin/python ../evals/run_experiment.py [--limit N]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from agento11y.experiments import (  # noqa: E402
    AgentOutput,
    Candidate,
    Check,
    EvaluationPlan,
    EvaluatorsClient,
    StoredEvaluator,
    TestSuitesClient,
    run_evals,
)

from app.core import observability  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.services import claude_client  # noqa: E402

SUITE_ID = "suite_23704bea-5f16-438b-9f0d-62fda3dfc21a"
SUITE_VERSION = "v3"
_PREFIX = "grafana.starter.suite_23704bea_5f16_438b_9f0d_62fda3dfc21a."
EVALUATOR_IDS = {
    "meets_expectations": _PREFIX + "meets_expectations",
    "stays_in_scope": _PREFIX + "stays_in_scope",
    "no_secret_leaks": _PREFIX + "no_secret_leaks",
}


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def _stored(control: EvaluatorsClient, evaluator_id: str) -> StoredEvaluator:
    d = control.get(evaluator_id)
    return StoredEvaluator(
        evaluator_id=evaluator_id,
        version=d["version"],
        config=d["config"],
        output_keys=d["output_keys"],
        kind=d["kind"],
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="smoke run: only the first N cases")
    args = ap.parse_args()

    # Client built from AGENTO11Y_* env, same constructor the app uses at startup.
    observability._setup_agento11y()
    o11y = observability.get_agento11y_client()
    if o11y is None:
        sys.exit("Agent Observability client not configured: check AGENTO11Y_* in .env")

    suites = TestSuitesClient(grafana_url=os.environ.get("GRAFANA_URL", ""))
    suite = suites.pull_suite(SUITE_ID, SUITE_VERSION, require_published=True)
    if args.limit:
        suite.test_cases = suite.test_cases[: args.limit]

    control = EvaluatorsClient(control=suites)
    plan = EvaluationPlan([Check(name, _stored(control, eid)) for name, eid in EVALUATOR_IDS.items()])

    def target(prompt: str) -> AgentOutput:
        # Case input is a free-text prompt, so use the agent's subject-only path.
        conversation_id = f"eval-{int(time.time() * 1000)}"
        result = asyncio.run(
            claude_client.generate_question_from_context(
                {"name": prompt}, is_subject_only=True, conversation_id=conversation_id
            )
        )
        return AgentOutput(text=json.dumps(result), conversation_id=conversation_id, flush=o11y.flush)

    candidate = Candidate(
        agent_name=claude_client.AGENT_NAME,
        agent_version=claude_client.AGENT_VERSION,
        model_provider="anthropic",
        model_name=settings.anthropic_model,
        git_sha=_git("rev-parse", "HEAD"),
    )

    try:
        run = run_evals(
            suite,
            target,
            name=f"{claude_client.AGENT_NAME} {SUITE_VERSION}",
            candidate=candidate,
            plan=plan,
            tags=["published-suite"],
            metadata={"git_dirty": bool(_git("status", "--porcelain"))},
        )
    finally:
        observability.shutdown()
    print(f"experiment: {run.url}")


if __name__ == "__main__":
    main()
