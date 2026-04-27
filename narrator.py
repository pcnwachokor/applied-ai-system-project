import os
import logging
from google import genai
import rag_engine

logger = logging.getLogger(__name__)

MIN_QUERY_LENGTH = 20
FALLBACK_STORY = (
    "The game ended in a flash — a single moment, over before a proper tale could take shape. "
    "Sometimes the story is shorter than the telling of it."
)


def _build_queries(history, secret, status, difficulty, low, high, attempt_limit):
    """Build archetype and climax query strings from game state. Pure function."""
    if not history:
        return None, None

    first_guess = history[0]
    range_size = high - low
    first_pct = round((first_guess - low) / range_size * 100) if range_size > 0 else 50
    n = len(history)
    guesses_str = ", ".join(str(g) for g in history)
    outcome_word = "won" if status == "won" else "lost"

    archetype_query = (
        f"Player {outcome_word} a {difficulty} game in {n} attempts. "
        f"Guesses: {guesses_str}. Secret was {secret}. "
        f"First guess was {first_guess}, which is {first_pct}% of the range {low}-{high}."
    )

    last_guess = history[-1]
    if status == "won":
        climax_query = (
            f"Player won in {n} out of {attempt_limit} allowed attempts. "
            f"Final guess {last_guess} matched secret {secret}."
        )
    else:
        distance = abs(last_guess - secret)
        climax_query = (
            f"Player lost after {n} attempts, limit was {attempt_limit}. "
            f"Last guess {last_guess} was {distance} away from secret {secret}."
        )

    return archetype_query, climax_query


def generate_game_story(
    history: list,
    secret: int,
    status: str,
    difficulty: str,
    score: int,
    genre: str,
    low: int,
    high: int,
    attempt_limit: int,
) -> tuple[str, float]:
    """
    Generate a narrative story for a completed game using RAG + Claude.

    Returns (story_text, top_similarity_score).
    Falls back to a safe default story when the query is too short or
    similarity is below threshold (single-guess edge case).
    """
    archetype_query, climax_query = _build_queries(
        history, secret, status, difficulty, low, high, attempt_limit
    )

    if not archetype_query or len(archetype_query) < MIN_QUERY_LENGTH:
        logger.warning("[narrator] query too short — using fallback story")
        return FALLBACK_STORY, 0.0

    logger.info("[narrator] archetype query: %s", archetype_query)
    logger.info("[narrator] climax query: %s", climax_query)

    archetype_results = rag_engine.retrieve_archetypes(archetype_query, k=1)
    climax_results = rag_engine.retrieve_archetypes(climax_query, k=1) if climax_query else []
    genre_chunks = rag_engine.retrieve_genre(genre)

    top_score = archetype_results[0]["score"] if archetype_results else 0.0

    if top_score < rag_engine.MIN_SCORE and len(history) <= 1:
        logger.warning("[narrator] similarity %.2f below threshold — using fallback story", top_score)
        return FALLBACK_STORY, top_score

    archetype_text = "\n\n".join(r["text"] for r in archetype_results + climax_results)
    genre_text = genre_chunks[0] if genre_chunks else ""
    guesses_str = ", ".join(str(g) for g in history)

    prompt = (
        "You are a dramatic narrator for a number guessing game.\n"
        "Use the following narrative style templates to write a 3-4 sentence story about this game session.\n"
        "Incorporate the exact guess numbers and the final outcome. Stay in character with the genre style.\n"
        "Do NOT invent details not present in the game data below.\n\n"
        f"[NARRATIVE TEMPLATES]\n{archetype_text}\n\n"
        f"[GENRE STYLE]\n{genre_text}\n\n"
        f"[GAME DATA]\n"
        f"Secret number: {secret} | Difficulty: {difficulty} | Range: {low}-{high}\n"
        f"Guesses made: {guesses_str} | Result: {status} | Score: {score}\n\n"
        "Write the story now."
    )

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        logger.warning("[narrator] no GEMINI_API_KEY set")
        return (
            "⚠️ Story generation is unavailable: the GEMINI_API_KEY environment "
            "variable is not set. Set it in your shell and restart the app.",
            top_score,
        )

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
    except Exception as e:
        logger.exception("[narrator] Gemini API call failed")
        return (
            f"⚠️ Story generation failed: {type(e).__name__}: {e}",
            top_score,
        )

    story = (response.text or "").strip()
    logger.info("[narrator] response: %d chars, top_score=%.2f", len(story), top_score)

    return story, top_score
