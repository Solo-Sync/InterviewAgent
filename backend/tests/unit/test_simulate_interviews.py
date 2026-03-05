from scripts.simulate_interviews import (
    CandidateAccount,
    PERSONAS,
    extract_json_object,
    render_transcript_markdown,
    slugify,
)


def test_extract_json_object_supports_embedded_payload() -> None:
    payload = extract_json_object('prefix {"answer":"ok","should_stop":false} suffix')

    assert payload["answer"] == "ok"
    assert payload["should_stop"] is False


def test_slugify_normalizes_mixed_input() -> None:
    assert slugify("LLM Sim Run #1") == "llm-sim-run-1"


def test_render_transcript_markdown_contains_session_and_messages() -> None:
    markdown = render_transcript_markdown(
        session_id="sess_123",
        persona=PERSONAS["structured"],
        candidate=CandidateAccount(
            email="alice@example.com",
            candidate_id="candidate_alice",
            display_name="Alice",
            invite_token="invite-alice-001",
        ),
        conversation=[
            {"speaker": "Interviewer", "text": "How would you estimate demand?"},
            {"speaker": "Candidate", "text": "I would start by defining the population."},
        ],
    )

    assert "# Session sess_123" in markdown
    assert "Structured Problem Solver" in markdown
    assert "How would you estimate demand?" in markdown
    assert "I would start by defining the population." in markdown
