import os
from unittest.mock import patch, MagicMock
import pytest
from narrator import _build_queries, generate_game_story, FALLBACK_STORY


# --- _build_queries (pure function, no mocks needed) ---

def test_build_queries_normal_win():
    archetype_q, climax_q = _build_queries(
        history=[50, 25, 37, 43],
        secret=43,
        status="won",
        difficulty="Normal",
        low=1,
        high=100,
        attempt_limit=8,
    )
    assert "won" in archetype_q
    assert "Normal" in archetype_q
    assert "50" in archetype_q  # first guess appears
    assert "43" in climax_q     # secret appears
    assert "won" in climax_q


def test_build_queries_loss_includes_distance():
    _, climax_q = _build_queries(
        history=[50, 75, 90, 95, 98],
        secret=65,
        status="lost",
        difficulty="Hard",
        low=1,
        high=200,
        attempt_limit=5,
    )
    assert "lost" in climax_q
    assert "33" in climax_q  # abs(98 - 65) = 33


def test_build_queries_empty_history_returns_none():
    archetype_q, climax_q = _build_queries(
        history=[], secret=50, status="lost",
        difficulty="Normal", low=1, high=100, attempt_limit=8,
    )
    assert archetype_q is None
    assert climax_q is None


def test_build_queries_first_pct_computed():
    archetype_q, _ = _build_queries(
        history=[75],
        secret=75,
        status="won",
        difficulty="Normal",
        low=1,
        high=100,
        attempt_limit=8,
    )
    assert "75%" in archetype_q  # (75-1)/(100-1)*100 = 74.74 → rounds to 75


# --- generate_game_story (mocked rag_engine + Gemini) ---

def _mock_rag_and_gemini(mock_retrieve_archetypes, mock_retrieve_genre, mock_genai_client):
    mock_retrieve_archetypes.return_value = [
        {"text": "The player opened boldly.", "id": "archetype_high_opener", "score": 0.82}
    ]
    mock_retrieve_genre.return_value = ["Write in detective noir style."]

    mock_response = MagicMock()
    mock_response.text = "The detective opened at 75, too high for the secret hiding at 43."
    mock_genai_client.return_value.models.generate_content.return_value = mock_response


@patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
@patch("narrator.genai.Client")
@patch("narrator.rag_engine.retrieve_genre")
@patch("narrator.rag_engine.retrieve_archetypes")
def test_generate_story_returns_string(mock_archetypes, mock_genre, mock_client):
    _mock_rag_and_gemini(mock_archetypes, mock_genre, mock_client)

    story, score = generate_game_story(
        history=[75, 50, 43], secret=43, status="won",
        difficulty="Normal", score=70, genre="Detective",
        low=1, high=100, attempt_limit=8,
    )

    assert isinstance(story, str)
    assert len(story) > 0
    assert score == pytest.approx(0.82)


@patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
@patch("narrator.genai.Client")
@patch("narrator.rag_engine.retrieve_genre")
@patch("narrator.rag_engine.retrieve_archetypes")
def test_generate_story_calls_gemini_once(mock_archetypes, mock_genre, mock_client):
    _mock_rag_and_gemini(mock_archetypes, mock_genre, mock_client)

    generate_game_story(
        history=[50, 25, 13], secret=13, status="won",
        difficulty="Normal", score=80, genre="Sports",
        low=1, high=100, attempt_limit=8,
    )

    mock_client.return_value.models.generate_content.assert_called_once()


@patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
@patch("narrator.genai.Client")
@patch("narrator.rag_engine.retrieve_genre")
@patch("narrator.rag_engine.retrieve_archetypes")
def test_single_guess_below_threshold_returns_fallback(mock_archetypes, mock_genre, mock_client):
    mock_archetypes.return_value = [
        {"text": "Some archetype.", "id": "archetype_lucky_strike", "score": 0.28}
    ]
    mock_genre.return_value = ["Genre style."]

    story, score = generate_game_story(
        history=[50], secret=50, status="won",
        difficulty="Easy", score=90, genre="Fantasy",
        low=1, high=20, attempt_limit=6,
    )

    assert story == FALLBACK_STORY
    assert score == pytest.approx(0.28)
    mock_client.return_value.models.generate_content.assert_not_called()


@patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
@patch("narrator.genai.Client")
@patch("narrator.rag_engine.retrieve_genre")
@patch("narrator.rag_engine.retrieve_archetypes")
def test_empty_history_returns_fallback(mock_archetypes, mock_genre, mock_client):
    story, score = generate_game_story(
        history=[], secret=50, status="lost",
        difficulty="Normal", score=0, genre="Detective",
        low=1, high=100, attempt_limit=8,
    )

    assert story == FALLBACK_STORY
    assert score == 0.0
    mock_client.return_value.models.generate_content.assert_not_called()


@patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
@patch("narrator.genai.Client")
@patch("narrator.rag_engine.retrieve_genre")
@patch("narrator.rag_engine.retrieve_archetypes")
def test_game_data_injected_into_prompt(mock_archetypes, mock_genre, mock_client):
    _mock_rag_and_gemini(mock_archetypes, mock_genre, mock_client)

    generate_game_story(
        history=[100, 50, 75, 62, 68, 65], secret=65, status="won",
        difficulty="Hard", score=40, genre="Detective",
        low=1, high=200, attempt_limit=5,
    )

    call_args = mock_client.return_value.models.generate_content.call_args
    prompt_text = call_args[1]["contents"]
    assert "65" in prompt_text      # secret
    assert "Hard" in prompt_text    # difficulty
    assert "100" in prompt_text     # first guess
    assert "won" in prompt_text     # outcome


@patch.dict(os.environ, {}, clear=True)
@patch("narrator.genai.Client")
@patch("narrator.rag_engine.retrieve_genre")
@patch("narrator.rag_engine.retrieve_archetypes")
def test_missing_api_key_returns_friendly_error(mock_archetypes, mock_genre, mock_client):
    _mock_rag_and_gemini(mock_archetypes, mock_genre, mock_client)

    story, _ = generate_game_story(
        history=[50, 25, 13], secret=13, status="won",
        difficulty="Normal", score=80, genre="Detective",
        low=1, high=100, attempt_limit=8,
    )

    assert "GEMINI_API_KEY" in story
    mock_client.assert_not_called()
