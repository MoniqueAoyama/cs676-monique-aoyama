"""
Tests for the observer: reading its answer, sending it the conversation,
and how the app uses it. Everything runs against ScriptedLLM, so it is free.
"""

from personaforge import Orchestrator, PersonaSpec, list_personas, save_persona
from personaforge.conversation import Conversation, Turn
from personaforge.llm import ScriptedLLM
from personaforge.observer import parse_review, review_conversation

GOOD_ANSWER = """SUMMARY: The doctor asked about symptoms.
ON_TOPIC: 2
IN_CHARACTER: yes
NOTES: The test results were never discussed."""


def small_conversation():
    return Conversation(
        topic="the test results",
        participants=["Alice", "Bob"],
        turns=[Turn("Alice", "How are you?"), Turn("Bob", "My back hurts.")],
    )


def two_personas(directory):
    save_persona(PersonaSpec(name="Alice", role="doctor", summary="", body="A"), directory)
    save_persona(PersonaSpec(name="Bob", role="patient", summary="", body="B"), directory)


# -- reading the observer's answer ------------------------------------------


def test_parse_review_reads_every_field():
    review = parse_review(GOOD_ANSWER)
    assert review.summary == "The doctor asked about symptoms."
    assert review.on_topic == 2
    assert review.in_character is True
    assert review.notes == "The test results were never discussed."


def test_parse_review_accepts_bold_and_score_out_of_five():
    review = parse_review("**SUMMARY:** Short.\n**ON_TOPIC:** 4/5\n**IN_CHARACTER:** No, the doctor said he is an AI")
    assert review.summary == "Short."
    assert review.on_topic == 4
    assert review.in_character is False


def test_parse_review_does_not_crash_on_nonsense():
    review = parse_review("I am not sure what you want.")
    assert review.on_topic is None
    assert review.in_character is None
    assert review.raw == "I am not sure what you want."


# -- sending the conversation to the observer -------------------------------


def test_review_conversation_sends_topic_and_transcript():
    llm = ScriptedLLM(replies=[GOOD_ANSWER])
    review_conversation(small_conversation(), llm)

    sent = llm.calls[0]["messages"][0]["content"]
    assert "the test results" in sent
    assert "My back hurts." in sent
    assert "You are an observer" in llm.calls[0]["system"]


# -- the observer inside the app --------------------------------------------


def test_conversation_in_app_saves_a_review(tmp_path):
    two_personas(tmp_path)
    # 6 dialogue lines, then the observer's answer as the 7th call.
    llm = ScriptedLLM(replies=["a line"] * 6 + [GOOD_ANSWER])
    result = Orchestrator(llm=llm, persona_dir=tmp_path).handle("have them talk about the test results")

    assert "Observer review" in result.reply
    assert "On topic: 2/5" in result.reply
    assert (tmp_path / "review.md").exists()


class BrokenObserverLLM(ScriptedLLM):
    """Answers normally as a character, but fails when asked to be the observer."""

    def complete(self, system, messages, max_tokens=2048):
        if "You are an observer" in system:
            raise RuntimeError("API is down")
        return super().complete(system, messages, max_tokens)


def test_conversation_is_kept_when_observer_fails(tmp_path):
    two_personas(tmp_path)
    result = Orchestrator(llm=BrokenObserverLLM(replies=["a line"]), persona_dir=tmp_path).handle(
        "have them talk about the test results"
    )

    assert result.conversation is not None
    assert (tmp_path / "conversation.md").exists()
    assert "could not review" in result.reply


# -- the "Unnamed" bug -------------------------------------------------------


def test_transcript_and_review_are_not_listed_as_personas(tmp_path):
    two_personas(tmp_path)
    (tmp_path / "conversation.md").write_text("# Conversation: x", encoding="utf-8")
    (tmp_path / "review.md").write_text("**Observer review**", encoding="utf-8")

    names = [spec.name for spec in list_personas(tmp_path)]
    assert names == ["Alice", "Bob"]
