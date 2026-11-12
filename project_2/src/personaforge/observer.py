"""
observer.py — a third agent that reads a finished conversation and judges it.
"""

from dataclasses import dataclass
from typing import Optional

from .conversation import Conversation
from .llm import LLM

_OBSERVER_SYSTEM = """You are an observer watching a conversation between characters.
You do not take part. You only read the transcript and judge it.

Answer in exactly this format, with nothing before or after:

SUMMARY: <2-3 sentences about what happened>
ON_TOPIC: <a number from 1 to 5>
IN_CHARACTER: <yes or no>
NOTES: <one sentence>

Rules:
- ON_TOPIC: 1 means they barely talked about the topic, 5 means the topic was the main thing and it got a real answer.
- IN_CHARACTER: say "no" if someone talks like an AI, speaks for the other person, or acts nothing like their persona.
"""

@dataclass
class Review:
    """What the observer thought of one conversation."""

    summary: str
    on_topic: Optional[int]  # 1 to 5, or None if the observer did not give a number
    in_character: Optional[bool]  # True, False, or None if the answer was unclear
    notes: str
    raw: str  # the observer's full answer, kept in case something could not be read


def review_conversation(conversation: Conversation, llm: LLM) -> Review:
    """Send the finished conversation to the observer and return its review."""
    message = f"The topic was: {conversation.topic}\n\n{conversation.transcript()}"
    answer = llm.complete(_OBSERVER_SYSTEM, [{"role": "user", "content": message}], max_tokens=512)
    return parse_review(answer)



def parse_review(answer: str) -> Review:
    """Read the observer's answer. Be generous: the model does not always follow the format exactly."""
    fields = {}
    for line in answer.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip().strip("*").strip().upper()
            fields[key] = value.strip().strip("*").strip()

    # ON_TOPIC: take the first digit from 1 to 5 ("4", "4/5" and "4 out of 5" all work)
    on_topic = None
    for char in fields.get("ON_TOPIC", ""):
        if char in "12345":
            on_topic = int(char)
            break

    # IN_CHARACTER: "yes" -> True, "no" -> False, anything else -> None
    in_character = None
    answer_text = fields.get("IN_CHARACTER", "").lower()
    if answer_text.startswith("yes"):
        in_character = True
    elif answer_text.startswith("no"):
        in_character = False

    return Review(
        summary=fields.get("SUMMARY", ""),
        on_topic=on_topic,
        in_character=in_character,
        notes=fields.get("NOTES", ""),
        raw=answer,
    )



def review_markdown(review: Review) -> str:
    """Turn a review into short markdown, for the screen and for review.md."""
    score = f"{review.on_topic}/5" if review.on_topic is not None else "unknown"
    if review.in_character is True:
        character = "yes"
    elif review.in_character is False:
        character = "no"
    else:
        character = "unknown"

    return (
        "**Observer review**\n\n"
        f"- Summary: {review.summary}\n"
        f"- On topic: {score}\n"
        f"- In character: {character}\n"
        f"- Notes: {review.notes}\n"
    )


def save_review(review: Review, directory, filename: str = "review.md"):
    """Write the review next to the transcript it judged."""
    from pathlib import Path

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    path.write_text(review_markdown(review), encoding="utf-8")
    return path
