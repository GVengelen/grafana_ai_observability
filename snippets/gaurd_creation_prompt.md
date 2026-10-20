## Task: Enable Grafana Agent Observability guards (preflight hooks) in my Python backend

Context: FastAPI app in `backend/`. It uses `agento11y==0.21.0` and `agento11y-anthropic==0.21.0`, and already sends generations to Grafana Agent Observability. In Grafana I created a guard evaluator `block_promp_injection` (preflight phase, blocks prompt injection).

### Verified facts about the SDK (0.21.0). Re-check quickly with grep, but don't assume otherwise.

- `agento11y.ClientConfig` is a dataclass with `hooks: HooksConfig`.
- `HooksConfig(enabled=False, phases=["preflight"], timeout_seconds=15.0, fail_open=True)`.
  - The timeout is in SECONDS, not ms.
  - There is no endpoint field. The URL comes from `AGENTO11Y_ENDPOINT`.
- The SDK reads NO env vars for hooks/guards. The app must read its own settings.
- `agento11y-anthropic` does NOT call hooks. `messages.create_async` ignores `hooks.enabled`.
  - The only primitive is the blocking `Client.evaluate_hook(HookEvaluateRequest) -> HookEvaluateResponse`.
  - It returns an allow immediately if hooks are disabled.
  - The app must call `evaluate_hook` itself before the LLM call.
- Relevant exports from `agento11y`: `HookContext`, `HookEvaluateRequest`, `HookInput`, `HookModel`, `HookPhase`, `HookEvaluateResponse` (`.action`, `.rule_id`, `.reason`, `.transformed_input`), `hook_denied_from_response`, `HookDeniedError(.rule_id, .reason)`, `HookTransportError` (raised only when `fail_open=False`), `Message`, `MessageRole`, `Part`, `PartKind`.
- No generation ID exists before the call, so log `conversation_id` instead.

### Implement

1. `app/core/config.py` (pydantic Settings):
   - `agento11y_guards_enabled: bool = True`
   - `agento11y_guards_fail_open: bool = True`
   - `agento11y_guards_timeout_ms: int = 5000`
   - Comment: production can set `AGENTO11Y_GUARDS_FAIL_OPEN=false` (strict mode).
2. `app/core/observability.py`:
   - Pass `settings` into `_setup_agento11y`.
   - Build `Client(ClientConfig(hooks=HooksConfig(enabled=..., phases=["preflight"], timeout_seconds=ms/1000, fail_open=...)))`.
   - Comment on fail_open semantics.
3. `app/services/claude_client.py`:
   - Add `BLOCKED_MESSAGE = "This request was blocked by a safety policy."` and `GuardBlockedError(rule_id, conversation_id)`.
   - Add `async _run_preflight_guard(client, request, conversation_id, tags)`:
     - Build `HookEvaluateRequest(phase="preflight")`.
     - Context: `HookModel("anthropic", model)`, stable `AGENT_NAME`/`AGENT_VERSION` (same as the LLM call), `tags`, `conversation_id`.
     - Input: the user message and the system prompt.
     - Call `evaluate_hook` via `asyncio.to_thread`.
     - On deny (`hook_denied_from_response`): `logger.warning` with rule_id, conversation_id and agent_name only. NEVER log the prompt or `reason`. Then raise `GuardBlockedError`.
     - If `transformed_input` has text, replace `request["messages"][0]["content"]` with it.
   - Call it before the LLM call whenever the agento11y client exists.
4. `app/api/questions.py`:
   - `GuardBlockedError` -> HTTP 403 with `BLOCKED_MESSAGE`.
   - `HookTransportError` -> HTTP 503 "Safety check unavailable. Please try again later." plus a log line with the conversation_id.
   - Both `except` clauses go before the generic `except Exception`.
   - Add `logger`.
5. `.env.example`: add `AGENTO11Y_GUARDS_ENABLED=true`, `AGENTO11Y_GUARDS_FAIL_OPEN=true` (with a comment that prod = false), `AGENTO11Y_GUARDS_TIMEOUT_MS=5000`.
6. Cover every Anthropic call path. Currently there is only the non-streaming `messages.create_async`. If a streaming path exists, add the same guard call there.

### Tests (`backend/tests/`, pytest + pytest-asyncio)

- The existing happy-path test needs a fake client with `evaluate_hook` returning allow.
- Deny: mock `evaluate_hook` -> `HookEvaluateResponse(action="deny", rule_id="block_promp_injection", reason="secret-reason")`.
  - Assert `GuardBlockedError` with the safe message and rule_id.
  - Assert neither the wrapped call nor the Anthropic `create` ran.
  - Assert the hook request has `agent_name` and `phase == "preflight"`.
  - Assert caplog contains the rule_id and conversation_id, but NOT the prompt text or the reason.
- `transformed_input` replaces the user content sent to the model.
- `HookTransportError` propagates in strict mode.
- Keep the existing agent_version assertion in sync with `AGENT_VERSION`.

### Verify

- Run pytest (install pytest==8.3.3 and pytest-asyncio==0.24.0 in `backend/.venv` if missing).
- Check that the built config reports `HooksConfig(enabled=True, phases=['preflight'], timeout_seconds=5.0, fail_open=True)`.
- Rebuild and redeploy the image (`make build-images load-images restart`), since the app runs in kind.
- In the final summary, state which SDK assumptions turned out to be wrong.
