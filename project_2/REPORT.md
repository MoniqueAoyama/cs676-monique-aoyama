# Project 2: PersonaForge + Observer

Monique Aoyama, CS676

The live run was done with `claude-haiku-4-5`. The files from that run are in the [`examples/`](examples/) folder.

## 1. What was built and why

The extension chosen was option 4, the observer. It's a third agent that reads the conversation after it's over and writes a short review: a summary, a score from 1 to 5 for how on-topic it was, whether the characters stayed in character, and a note.

The reason for this choice: in the first offline run, the topic was "the test results", but the characters never talked about any test results. The doctor just asked about symptoms. And nothing in the program noticed that. The observer is there to check if the conversation actually did what it was supposed to do.

It also made sense because it's one new module (easier to do well in the time available), it can be tested for free with `ScriptedLLM`, and it's a good start for the AI judge part of Project 3.

## 2. Design

**When the observer runs.** It runs once, after the conversation loop ends. Running it after every line was an option, but the observer needs the whole conversation to judge it, and running it every turn would mean 6 extra API calls instead of 1.

**Fixed answer format.** The observer has to answer like this:

```
SUMMARY: <2-3 sentences>
ON_TOPIC: <1 to 5>
IN_CHARACTER: <yes or no>
NOTES: <one sentence>
```

A fixed format is needed because the code has to pull the score out of the answer. If the model just wrote a paragraph, there'd be no way to get the number. The prompt also explains what 1 and 5 mean, and when to say "no" for in character.

**Reading the answer.** The project README describes a bug where the model left out a `---` line and the parser broke because it was too strict. Following the same idea, the code isn't strict about small stuff:
- if the model writes `**SUMMARY:**` in bold, it still works
- the score takes the first number from 1 to 5, so `4`, `4/5` or `4 out of 5` all give `4`
- yes/no is checked by how the answer starts, so "No, the doctor said he is an AI" still counts as no
- if something is missing it just becomes empty or `None` instead of crashing, and the full answer is kept in `raw` anyway

**If the observer fails.** The observer call is inside a `try`/`except` in `orchestrator.py`. If the API fails at that point, the conversation is already saved, so it isn't lost. The app just says the observer couldn't review it.

**Offline mode.** `DemoLLM` now recognizes the observer prompt and gives back a fixed review. That way `--offline` still works end to end without a key.

Files changed:

| File | What changed |
|---|---|
| `src/personaforge/observer.py` | new file: the prompt, the `Review` dataclass, and the functions to send, read, show and save the review |
| `src/personaforge/orchestrator.py` | calls the observer after the conversation, shows the review and saves `temp/review.md` |
| `src/personaforge/llm.py` | `DemoLLM` returns a fake review in offline mode |
| `src/personaforge/persona.py` | bug fix (see section 4, #1) |
| `tests/test_observer.py` | new file, 7 tests |

## 3. Transcript and comments

Commands used (live mode):

```
create a persona patient with chronic back pain who distrusts doctors
create a persona doctor who is direct and running forty minutes late
have them talk about the MRI results
```

The transcript is in [`examples/conversation.md`](examples/conversation.md) and the review in [`examples/review.md`](examples/review.md).

The observer gave it **5/5 on topic** and said both stayed in character. Its summary was basically: the doctor explains the MRI (a herniated disc at L4-L5 pressing on a nerve), recommends anti-inflammatories and physical therapy before surgery, and answers the patient's worries about the medicine and about PT not working before.

What worked:
- 5/5 is fair here, they really talked about the MRI the whole time. In the offline run the observer gave 1/5 because the topic never came up. So the score does tell the two cases apart, which was the point.
- The patient stayed skeptical all the way through. He questioned the medicine, said PT failed three times before, and asked when surgery would actually make sense. That fits "distrusts doctors" pretty well.
- The summary was accurate, and it's a lot faster to read than the six turns, which were long.

## 4. What went wrong

**1. The "Unnamed" bug.** In the second conversation run, one of the speakers was called "Unnamed" and the patient wasn't in the conversation anymore. The cause: `list_personas` reads every `.md` file in `temp/`, and that includes `conversation.md` from the run before. So the old transcript was loaded as a character with no name, and since the files are in alphabetical order, it took the patient's spot. The new `review.md` would have caused the same thing. The fix makes `list_personas` skip those two files. This only happens from the second run on, so it's easy to miss. There's a test for it, and the test fails if the fix is taken out (this was checked).

**2. Same name twice.** The model called the patient "Marcus Chen" and the doctor "Dr. Marcus Chen". Each persona is created separately, so the model doesn't know the name is already taken. It makes the transcript confusing, and `find_persona` could grab the wrong one.

**3. Stage directions, and the observer didn't catch them.** The prompt in `agent.py` says no stage directions and no asterisks, but both characters used them anyway (`*glances at the folder*`, `*leans back*`). The observer still said "in character: yes", because its rule for "no" only covers sounding like an AI, speaking for the other person, or acting nothing like the persona. So the observer only catches what it's told to look for.

**4. The doctor wasn't really "running late".** That was part of his persona but it only shows once (`*glances at watch*`). He gives long, calm explanations, which isn't what you'd expect from a doctor 40 minutes behind. The observer didn't mention it. It's good at checking the topic but not at checking details of the persona.

**5. Cost.** That run was about 10 API calls: 2 to make the personas, 6 turns, 1 for the observer, and 1 extra by accident (#6). The answers were long and every turn sends the whole conversation again, so the later turns cost more. The observer only adds 1 call, which is small next to the rest.

**6. A mistyped `/quit` costs a call.** Some keys were typed while the conversation was printing, and after that `/quit` didn't work. The app sent it to the model like a normal message, and the model answered that it didn't have a quit command. Small thing, but it's an extra call for nothing.

**7. One score, one time.** The score comes from just one call. Running the observer again on the same conversation might give a different score, and that wasn't measured. It's also a model grading another model's conversation, so it might be too easy on it (#3 kind of shows that). And in offline mode the review is always the same fake one, so the quality of the reviews can't be tested without the API.

## 5. Tests

All the tests use `ScriptedLLM`, so they run without a key and cost nothing. 48 pass in total: 41 from the starter and 7 new ones.

| Test | What it checks |
|---|---|
| `test_parse_review_reads_every_field` | a normal answer fills all 4 fields |
| `test_parse_review_accepts_bold_and_score_out_of_five` | bold labels and `4/5` still work |
| `test_parse_review_does_not_crash_on_nonsense` | a weird answer gives `None` instead of crashing |
| `test_review_conversation_sends_topic_and_transcript` | the observer actually gets the topic and the dialogue |
| `test_conversation_in_app_saves_a_review` | in the app the review shows up and `review.md` is created |
| `test_conversation_is_kept_when_observer_fails` | if the observer fails, the conversation is still saved |
| `test_transcript_and_review_are_not_listed_as_personas` | the "Unnamed" bug doesn't come back |

What isn't tested is whether a real review is good, because that needs the API (see #7).

## 6. How to run it

```bash
uv sync
uv run pytest                              # 48 tests, no key needed
uv run main.py --offline                   # the whole app, no key needed
uv run main.py --model claude-haiku-4-5    # real run, needs ANTHROPIC_API_KEY in .env
```

After each conversation the review shows up on screen and is saved in `temp/review.md`.

## 7. Next steps

- Add stage directions and persona details to the observer rules, to fix #3 and #4.
- Run the observer a few times on the same conversation and see how much the score changes, kind of like looking at the variance across folds in cross validation.
- Use the review to stop the conversation early once the question is answered (option 3).
- Tell the model which names are already taken when it creates a new persona, so it doesn't repeat them.
