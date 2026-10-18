#!/usr/bin/env bash
# Generate N Pokemon questions against the API, each in its own session/conversation.
# Usage: scripts/load.sh [count] (default 10)
# Env:   API_BASE (default http://localhost:8000/api/v1)
set -euo pipefail

COUNT="${1:-10}"
API_BASE="${API_BASE:-http://localhost:8000/api/v1}"
POKEMON=(pikachu charizard bulbasaur squirtle eevee snorlax mewtwo gengar jigglypuff machamp)
RUN="load-$(date +%s)"

ok=0
for ((i = 0; i < COUNT; i++)); do
  name="${POKEMON[i % ${#POKEMON[@]}]}"
  session="$RUN-$((i + 1))" # one session (= one conversation) per request
  code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$API_BASE/questions/generate" \
    -H 'Content-Type: application/json' \
    -d "{\"session_id\": \"$session\", \"pokemon_name\": \"$name\"}")
  echo "[$((i + 1))/$COUNT] $name -> HTTP $code"
  [[ "$code" == 200 ]] && ok=$((ok + 1))
done

echo "done: $ok/$COUNT succeeded (run $RUN)"
[[ "$ok" -eq "$COUNT" ]]
