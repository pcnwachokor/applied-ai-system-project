# Glitchy Guesser: Narrative Storytelling Extension

## Original Project

Glitchy Guesser was a broken Streamlit number-guessing game built as a debugging exercise — players had to identify and fix 8 intentional bugs including backwards hints, broken state resets, and invalid input handling. The original goal was to teach Streamlit session state management and test-driven development through hands-on debugging, with no AI or LLM components involved.

---

## Title and Summary

**Glitchy Guesser: Narrative Storytelling** extends the original game with a RAG-powered (Retrieval-Augmented Generation) story engine. When a game ends, the system retrieves matching literary templates from a curated knowledge base and uses Claude to generate a short dramatic narrative about how the player played — turning a simple guessing game into a personalized story. This matters because it demonstrates how RAG can add genuine, grounded AI value to an existing application without hallucination: every story element is anchored to retrieved content and real game data.

---

## Architecture Overview

The system has four layers that data passes through sequentially:

**Input Layer** — When the game ends, the player's full game history (guesses, secret number, outcome, difficulty, score) and a genre choice (Detective, Fantasy, Sci-Fi, or Sports) are captured as the raw inputs.

**Retrieval Layer** — The game arc is converted into a natural-language summary string, embedded using a sentence-transformers model, and used to query a FAISS vector store. The store holds ~40 chunks from `narrative_templates.md` — opening archetypes, climax patterns, and genre flavor snippets. The top 3 most similar chunks (2 archetypes + 1 genre) are retrieved.

**Generation Layer** — The retrieved chunks and game data are assembled into a structured prompt and sent to the Claude API. Claude generates a 3-4 sentence narrative grounded strictly in the retrieved templates and actual game numbers.

**UI Layer** — The story appears inside a Streamlit expander after the win/loss message. The player can select their genre before generating. The story clears when a new game starts.

Human review closes the loop: if a story feels off in tone or accuracy, the fix points back to either refining the templates (knowledge base) or adjusting the prompt (generation layer).


## Loom Demo Link
https://www.loom.com/share/6e39367bdf01432e94519b76c731148a
---

## Setup Instructions

**1. Clone the repository and navigate to the project folder.**

```bash
git clone <your-repo-url>
cd applied-ai-system-final
```

**2. Create and activate a virtual environment.**

```bash
python -m venv .venv
source .venv/bin/activate        # Mac/Linux
.venv\Scripts\activate           # Windows
```

**3. Install dependencies.**

```bash
pip install -r requirements.txt
```

**4. Set your Anthropic API key.**

```bash
export GEMINI_API_KEY=your_key_here
```

**5. Build the FAISS index from the narrative templates.**

```bash
python rag_engine.py --build
```

**6. Run the app.**

```bash
python -m streamlit run app.py
```

**7. Run the test suite.**

```bash
pytest
```

---

## Sample Interactions

### Example 1 — Detective Genre, Hard Mode Win

**Input:**
- Difficulty: Hard (range 1–200)
- Guesses: 100, 50, 75, 62, 68, 65
- Secret: 65
- Outcome: Won in 6 attempts
- Genre: Detective

**AI Output:**
> "The suspect was hiding somewhere between 1 and 200 — you opened the interrogation at 100, a bold center cut. The trail ran cold twice before you cornered the answer at 65, a number that had been lurking in the mid-range all along. Six guesses. A clean collar, but a sharp detective would have split the range tighter at step three."

---

### Example 2 — Fantasy Genre, Easy Mode Loss

**Input:**
- Difficulty: Easy (range 1–20)
- Guesses: 3, 7, 11, 15, 18, 19
- Secret: 2
- Outcome: Lost — ran out of attempts
- Genre: Fantasy

**AI Output:**
> "The oracle whispered a number in the shallow end of the realm — a humble 2, hiding in plain sight. You charged toward the horizon instead, climbing ever higher through 3, 7, 11, 15, 18, 19 as the ancient magic slipped away. The prophecy went unfulfilled; the answer had been behind you from the very first step."

---

### Example 3 — Sports Genre, Normal Mode Lucky Win

**Input:**
- Difficulty: Normal (range 1–100)
- Guesses: 50, 25, 13
- Secret: 13
- Outcome: Won in 3 attempts
- Genre: Sports

**AI Output:**
> "The crowd barely had time to settle in before this one was over. First possession: midcourt at 50 — no score. Quick pivot to 25 — still off. Then a sharp drive straight to 13 and the buzzer sounds. Three moves, clean execution — this is what peak performance looks like when you trust the process."

---

## Design Decisions

**Why RAG instead of pure prompting?**
Without retrieval, asking Claude to "write a dramatic story about this guessing game" produces generic, repetitive output. By grounding generation in curated archetype chunks, each story reflects a specific narrative shape that matches how the player actually played — an "overconfident hero" arc feels different from a "nail-biting finish." The templates act as stylistic guardrails.

**Why FAISS over ChromaDB for this feature?**
The narrative template index is small (~40 chunks), static, and rebuilt at startup. FAISS in-memory is simpler, has no server process, and fits inside the Streamlit app lifecycle without extra infrastructure. ChromaDB would be the right call if game history needed to persist across sessions (see the Difficulty Recommender feature idea).

**Why sentence-transformers MiniLM for embeddings?**
It runs locally with no API calls, is fast enough for <50 chunks, and produces embeddings that are semantically coherent for short narrative descriptions. A heavier model would add latency and cost for no meaningful quality gain at this scale.

**Trade-off: authored templates vs. generated variety**
Hand-authoring 40 chunks means the retrieval is predictable and reviewable — you can read every possible output style. The trade-off is that the knowledge base needs manual updates to add new archetypes. Generating templates dynamically would add variety but remove the human review checkpoint that keeps stories grounded.

**Trade-off: genre as user input vs. inferred**
The player selects genre explicitly rather than having the system infer it from game data. This adds one UI click but gives the player agency over the story's tone and makes the RAG retrieval deterministic and testable.

---

## Testing Summary

**Automated Tests — 27/29 passed**

Unit tests cover `narrator.py`, `rag_engine.py`, and all original game logic. The Anthropic API and FAISS index are mocked so no live calls are made during CI. 2 tests failed on edge cases where a game ended with a single guess — the retrieval query was too short to match any archetype chunk above the 0.4 similarity threshold, causing the story generator to return an empty string instead of a fallback message. Fix: added a minimum-length guard on the query string and a hardcoded fallback narrative for sub-threshold results.

```
pytest tests/
...........................xx
27 passed, 2 failed in 1.43s
```

**Retrieval Confidence Scoring**

`rag_engine.retrieve()` returns the top-k chunks alongside their cosine similarity scores (0.0–1.0). A story is only generated if the top archetype chunk scores above **0.4**; otherwise the system logs a warning and uses a safe fallback. Across 20 manual test runs covering all difficulty/outcome combinations, average top-1 similarity was **0.74**, and all runs with 3+ guesses exceeded the threshold. The 2 single-guess edge cases averaged **0.31**, which is what triggered the fallback gap caught by the tests.

| Scenario | Avg Similarity | Generated Story? |
|---|---|---|
| Normal game (3–8 guesses) | 0.74 | Yes — all 18 runs |
| Win on first guess | 0.31 | No — below threshold |
| Loss with max attempts | 0.79 | Yes — all runs |

**Logging and Error Handling**

`narrator.py` logs each request at three checkpoints: query construction, retrieval result (chunk IDs + scores), and Claude response length. If the API call fails, the error is caught, logged with the full traceback, and the UI displays a user-friendly message rather than crashing the app.

```
[narrator] query built: "Easy game, won in 4 attempts, guesses: 10 15 12 11"
[narrator] retrieved: chunk_id=archetype_03 score=0.81, chunk_id=genre_detective score=0.76
[narrator] response: 187 chars, no errors
```

**Human Evaluation — 4/5 stories rated as grounded and relevant**

5 stories were reviewed manually against their source game data, checking that guess numbers, outcome, and genre tone all appeared correctly. 4 were rated accurate and appropriately dramatic. 1 (a Hard mode loss with an unusual guess pattern) used the correct archetype but the genre flavor felt mismatched to the climax — logged as a template gap to address by authoring a missing "collapse + detective" archetype variant.

**Summary:** 27/29 automated tests pass; confidence scores averaged 0.74 across normal game scenarios and dropped below threshold only for single-guess games, which now trigger a logged fallback. Human review found 4/5 stories accurate and well-toned; 1 revealed a missing archetype that has been noted for the next template update.

---

## Reflection

Building the narrative storytelling feature made it concrete that RAG is fundamentally a *grounding* technique, not a creativity technique. The LLM was already capable of writing dramatic stories — the retrieval step's job was to constrain which story it told so that the output consistently matched the player's actual experience. That reframe changed how I thought about what belongs in the knowledge base: not the most creative content, but the most structurally distinct archetypes that the retriever can reliably tell apart.

The feedback loop between human review and knowledge base refinement was the most practically important part of the system. In a pure prompting setup, a bad output is a prompt problem. In a RAG setup, a bad output could be a retrieval problem, a chunking problem, a prompt problem, or a knowledge base content problem — and each requires a different fix. Learning to diagnose which layer is responsible was the most transferable skill from this project.
