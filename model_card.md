# Model Card: Glitchy Guesser Narrative Storytelling System

## System Overview

This system uses Retrieval-Augmented Generation (RAG) to produce short dramatic narratives about a player's completed number-guessing game. It retrieves matching style templates from a curated knowledge base and passes them alongside real game data to Gemini 2.5 Flash, which generates a 3–4 sentence story grounded in what actually happened.

---

## Limitations and Biases

**Knowledge base is hand-authored and narrow.** The 26 template chunks were written by one person in one sitting. They reflect a limited set of narrative archetypes — mostly Western storytelling conventions — and do not cover playing styles outside that frame. A player whose strategy doesn't map cleanly to any archetype will get a story shaped by the closest match, which may feel generic or slightly off.

**Retrieval breaks down on short games.** When a game ends in one guess, the query string is too sparse for the embedding model to find a confident match. The system detects this (similarity score below 0.4) and falls back to a safe default story, but that means one-guess games never get personalized narratives.

**Genre representation is uneven.** The five genre options (Detective, Fantasy, Sci-Fi, Sports, Neutral) each have only two template chunks. Rare combinations — such as a one-attempt Hard mode win in Sports genre — may produce outputs that don't feel fully in-character because the retriever had few distinct options to choose from.

**The embedding model has no domain knowledge of games.** `all-MiniLM-L6-v2` was trained on general text, not game design language. Words like "attempt," "range," and "secret" carry specialized meaning here that the model treats as ordinary vocabulary, which can reduce retrieval precision for edge-case queries.

---

## Potential Misuse and Prevention

This system is low-stakes — it narrates a guessing game, not consequential decisions. However, two misuse patterns are worth noting:

**Prompt injection via game history.** A malicious user could craft guess values that, when assembled into a query string, try to manipulate the LLM into producing off-topic or harmful output. The current prompt structure mitigates this by keeping game data in a clearly labeled `[GAME DATA]` block and instructing the model to use only retrieved templates for narrative style. For higher-stakes deployments, input sanitization on the history list would be the next layer of defense.

**API cost abuse.** Each "Generate Story" click makes a live Gemini API call. Without rate limiting, a user could spam the button and run up API costs. A simple fix — disabling the button for 10 seconds after each generation, or storing a session flag that blocks re-generation until a new game starts — would prevent this.

---

## What Surprised Me During Testing

The most surprising finding was how much retrieval quality depended on query construction, not on the embedding model or the LLM. Early tests used a short query like `"player won Hard in 6 guesses"` — retrieval scores were low and the wrong archetypes came back. Switching to a longer, more descriptive query that included the full guess list, percentage of range, and outcome description pushed average scores from around 0.45 to 0.74 without changing anything else. The embedding model was capable all along; it just needed more signal.

The second surprise was how often the genre flavor chunks were irrelevant to the story quality. In manual review, the two stories rated best were both Neutral genre — where there was no stylistic constraint, Claude defaulted to a direct, specific retelling of the game data. The most stylized outputs (Detective, Fantasy) were sometimes the least grounded.

---

## Collaboration with AI During This Project

Claude Code was used throughout — for planning the RAG architecture, writing the initial implementations of `rag_engine.py`, `narrator.py`, and the test suite, and for iterating on bugs as they surfaced during live testing.

**One instance where the AI gave a helpful suggestion:**
When the story expander wasn't appearing immediately after a game ended, Claude identified the root cause without being prompted: the win/loss status change happened inside the submit block mid-script, but the status-check block that renders the expander had already been skipped at the top of that same script run. The fix — triggering `st.rerun()` after setting status, and routing balloons through a one-shot session flag — was clean and correct on the first attempt, and accurately diagnosed a subtle Streamlit execution model behavior that's easy to get wrong.

**One instance where the AI's suggestion was flawed:**
When suggesting the initial model identifier for the Anthropic API integration, Claude used `claude-sonnet-4-6` — an ID that turned out to be inaccessible on the account in use, causing a `BadRequestError` with no useful error message in the UI. The error handling in place at the time also swallowed the specific API response, making it hard to diagnose. The fix required both switching to a known-stable model ID (`claude-sonnet-4-5`) and improving the error message to surface the raw exception text. The lesson: AI-suggested API configurations should be verified against the actual account's model access before relying on them in a running system.
