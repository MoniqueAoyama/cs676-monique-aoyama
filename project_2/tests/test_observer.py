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



# -- an API failure in the middle of a conversation --------------------------


class FailsOnThirdCallLLM(ScriptedLLM):
    """Works for two replies, then fails like an API that went down."""

    def complete(self, system, messages, max_tokens=2048):
        if len(self.calls) == 2:
            raise RuntimeError("API is down")
        return super().complete(system, messages, max_tokens)


def test_failed_turn_keeps_the_lines_said_so_far(tmp_path):
    two_personas(tmp_path)
    result = Orchestrator(llm=FailsOnThirdCallLLM(replies=["a line"]), persona_dir=tmp_path).handle(
        "have them talk about the test results"
    )

    assert len(result.conversation.turns) == 2
    assert "stopped early" in result.reply
    saved = (tmp_path / "conversation.md").read_text(encoding="utf-8")
    assert saved.count("a line") == 2
    assert "stopped early" in saved



# -- two personas with the same name -------------------------------------------

SAME_NAME_PERSONA = """---
name: Marcus Chen
role: {role}
summary: s
---

# Marcus Chen
Body.
"""


def test_repeated_name_does_not_overwrite_the_first_persona(tmp_path):
    llm = ScriptedLLM(replies=[SAME_NAME_PERSONA.format(role="customer"), SAME_NAME_PERSONA.format(role="support")])
    orch = Orchestrator(llm=llm, persona_dir=tmp_path)
    orch.handle("create a persona customer whose internet is down")
    orch.handle("create a persona support agent")

    names = sorted(spec.name for spec in list_personas(tmp_path))
    assert names == ["Marcus Chen", "Marcus Chen (support)"]



# -- random names ---------------------------------------------------------------


def test_random_name_skips_names_already_used():
    from personaforge.persona import random_name

    for _ in range(50):
        assert random_name(["Ana Silva"]) != "Ana Silva"


def test_new_persona_is_asked_to_use_a_given_name(tmp_path):
    llm = ScriptedLLM(replies=[SAME_NAME_PERSONA.format(role="customer")])
    Orchestrator(llm=llm, persona_dir=tmp_path).handle("create a persona customer")

    request = llm.calls[0]["messages"][0]["content"]
    assert "Use this name for the character:" in request



# -- wrapping up at the end ------------------------------------------------------


def test_last_two_speakers_are_told_to_wrap_up(tmp_path):
    two_personas(tmp_path)
    llm = ScriptedLLM(replies=["a line"])
    result = Orchestrator(llm=llm, persona_dir=tmp_path).handle("have them talk about the test results")

    # calls 0-5 are the six dialogue lines, call 6 is the observer
    assert "start wrapping up" in llm.calls[4]["messages"][-1]["content"]
    assert "last line" in llm.calls[5]["messages"][-1]["content"]
    assert "wrapping up" not in llm.calls[3]["messages"][-1]["content"]
    # the notes are not part of the saved conversation
    assert "wrapping up" not in result.conversation.transcript()
