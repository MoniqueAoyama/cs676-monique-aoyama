# Project 2: PersonaForge + Observer

Monique Aoyama, CS676

All live runs were done with `claude-haiku-4-5`. The saved runs are in the [`examples/`](examples/) folder.

## 1. What was built and why

The main extension is option 4, the observer. It's a third agent that reads the conversation after it's over and writes a short review: a summary, a score from 1 to 5 for how on-topic it was, whether the characters stayed in character, and a note.

The reason for this choice: in the first offline run, the topic was "the test results", but the characters never talked about any test results. The doctor just asked about symptoms. And nothing in the program noticed that. The observer is there to check if the conversation actually did what it was supposed to do.

It also made sense because it's one new module (easier to do well in the time available), it can be tested for free with `ScriptedLLM`, and it's a good start for the AI judge part of Project 3.

While testing the observer with real conversations, a few other problems showed up, so these were fixed too:
- a failed API call in the middle of a conversation lost everything said so far
- the model kept naming characters "Marcus Chen", and a second persona with the same name overwrote the first one
- conversations got cut off at 6 lines, sometimes before the characters finished

## 2. Design

**When the observer runs.** It runs once, after the conversation loop ends. Running it after every line was an option, but the observer needs the whole conversation to judge it, and running it every turn would mean 6 extra API calls instead of 1.

**Fixed answer format.** The observer has to answer like this:

```
SUMMARY: <2-3 sentences>
ON_TOPIC: <1 to 5>
IN_CHARACTER: <yes or no>
NOTES: <one sentence>
```

A fixed format is needed because the code has to pull the score out of the answer. A free-form paragraph was the other option, but then there'd be no reliable way to get the number. The prompt also explains what 1 and 5 mean, and when to say "no" for in character.

**Reading the answer.** The project README describes a bug where the model left out a `---` line and the parser broke because it was too strict. Following the same idea, the code isn't strict about small stuff:
- if the model writes `**SUMMARY:**` in bold, it still works
- the score takes the first number from 1 to 5, so `4`, `4/5` or `4 out of 5` all give `4`
- yes/no is checked by how the answer starts, so "No, the doctor said he is an AI" still counts as no
- if something is missing it just becomes empty or `None` instead of crashing, and the full answer is kept in `raw` anyway

**Failures.** There are two places where an API call can fail:
- *During the conversation:* the call is inside a `try`/`except`. The conversation stops at that line but keeps every line said before it, saves them, and says what went wrong.
- *During the review:* the conversation is already saved, so the app just says the observer couldn't review it.

**Names.** At first the model chose the name. In almost every run it picked "Marcus Chen" (or something close, like "Dr. Marcus Chen" or "Margaret Chen"). Telling the model which names were already taken was one option, but the model could still ignore it. So now the code picks a random name from a list of 20 first names and 20 last names (skipping names already used), and the model writes everything else about the character. As a safety net, if a name still repeats, the role is added to it (for example "Marcus Chen (support)"), so the second persona doesn't overwrite the first.

**Ending the conversation.** The starter always runs exactly 6 lines. Raising the number would cost more and still cut conversations off at some point. Stopping when the topic is resolved would be the best fix, but it's more work (see section 7). The simple version used here: in the last two lines, the speaker gets a short note, "two lines left: start wrapping up" and then "this is the last line: close the conversation naturally". The note is only sent to the model and isn't saved in the transcript.

**Offline mode.** `DemoLLM` now recognizes the observer prompt and gives back a fixed review, so `--offline` still works end to end without a key.

Files changed:

| File | What changed |
|---|---|
| `src/personaforge/observer.py` | new file: the observer prompt, the `Review` dataclass, and the functions to send, read, show and save the review |
| `src/personaforge/orchestrator.py` | calls the observer after each conversation and saves `temp/review.md`; picks a random name for new personas; renames repeated names; mentions when a conversation stopped early |
| `src/personaforge/conversation.py` | a failed reply stops the conversation but keeps the lines said so far; wrap-up notes for the last two lines |
| `src/personaforge/persona.py` | random name list; `generate_persona` can receive a name; `list_personas` skips `conversation.md` and `review.md` |
| `src/personaforge/llm.py` | `DemoLLM` returns a fake review in offline mode |
| `tests/test_observer.py` | new file, 12 tests |

## 3. Transcripts and comments

| Folder | Scenario | On topic | What happened |
|---|---|---|---|
| [`examples/`](examples/) | patient and doctor, MRI results | 5/5 | good conversation, but both characters were named Marcus Chen |
| [`examples/run_2`](examples/run_2) | math teacher and student, last exam | 5/5 | the student's first line was out of character; the observer didn't notice |
| [`examples/run_3`](examples/run_3) | customer and internet support | 4/5 | ran after the name fix; cut off before the problem was solved |
| [`examples/run_4`](examples/run_4) | two friends planning the weekend | 5/5 | random names; they agreed on a day, time and place |
| [`examples/run_5`](examples/run_5) | two roommates splitting chores | 5/5 | ended on an open question ("Does that work?") |
| [`examples/run_6`](examples/run_6) | same roommates scenario | 5/5 | after the wrap-up change; ended with a clear agreement |

**A conversation that went well: the MRI results.** The doctor explained the MRI (a herniated disc at L4-L5 pressing on a nerve), recommended anti-inflammatories and physical therapy before surgery, and answered the patient's worries. The patient stayed skeptical the whole time: he questioned the medicine, said PT failed three times before, and asked when surgery would make sense. That fits "distrusts doctors". The observer's 5/5 is fair, and its summary is a lot faster to read than the six long turns. In comparison, the offline run where nobody talked about the topic got 1/5, so the score does tell the two cases apart.

**A conversation that went badly in one specific way: the teacher and the student.** Most of it was good. The student sounded like an anxious teenager and the teacher was tired but patient, which is what was asked. But the student's very first line was: *"I'm ready to help with your roleplay, but I need clarification about what you mean by 'the last exam.'"* That's the model talking as an assistant, not as a student. The teacher even answered "I'm Margaret Chen, not Marcus". The likely reason is how the conversation starts: the first speaker only gets a line like `Scene: the last exam`, with no other context, so the model asked for clarification. After that one line the conversation went back to normal. The observer still said "in character: yes" and "stayed in character throughout". It seems to judge the conversation as a whole and miss a single bad line. The same thing happened at the start of the customer/support run.

**Before and after the wrap-up change: the roommates.** The same scenario was run twice. Before the change, the last line was a question: *"Does that work? ... I think I can actually live with that."* After the change, the fifth line started closing (*"Let's give it a week and see how it goes"*) and the sixth line ended it (*"We're gonna be good, man... I promise."*). The observer said they "reached a concrete agreement".

**The customer and support agent.** This scenario first failed completely: the model named both characters "Marcus Chen", the second file overwrote the first, and the app said it needed two personas. After the name fix it ran. The observer gave 4/5 and pointed out on its own that the conversation was "cut short before the support agent provides actual diagnostic information", which is the 6-line limit.

## 4. What went wrong

**1. The "Unnamed" bug (fixed).** In the second conversation run, one of the speakers was called "Unnamed" and the patient wasn't in the conversation anymore. The cause: `list_personas` reads every `.md` file in `temp/`, and that includes `conversation.md` from the run before. So the old transcript was loaded as a character with no name, and since the files are in alphabetical order, it took the patient's spot. The new `review.md` would have caused the same thing. The fix makes `list_personas` skip those two files. This only happens from the second run on, so it's easy to miss. There's a test for it, and the test fails if the fix is taken out (this was checked).

**2. The same name every time (fixed).** The model used "Marcus Chen" or something very close in four different runs, for patients, doctors, students and customers. Each persona is created separately, so the model doesn't know the name is already taken. It made transcripts confusing, and in the customer/support run the second persona overwrote the first and the conversation couldn't start. Now the code picks the name (see section 2). In the runs after the fix the names were Jamal Dubois, Priya Brennan, Carla Fischer, Isabel Moreau, Ana Kowalski and Luis Rossi.

**3. A failed reply lost the whole conversation (fixed).** In the starter, if the API failed on line 4, lines 1 to 3 were lost too. Now they're kept and saved. This wasn't seen in a live run; it's covered by a test that makes the fake model fail on the third call.

**4. Stage directions, and the observer doesn't catch them.** The prompt in `agent.py` says no stage directions and no asterisks, but the characters used them in most runs (`*glances at the folder*`, `*leans back*`). The observer still said "in character: yes", because its rule for "no" only covers sounding like an AI, speaking for the other person, or acting nothing like the persona. The observer only catches what it's told to look for.

**5. One out-of-character line is missed.** See the teacher/student run in section 3: the student opened like an AI assistant and the observer said everything stayed in character. It happened twice (teacher/student and customer/support).

**6. Persona details don't always show up.** In the MRI run the doctor was supposed to be "running forty minutes late", but that only shows once (`*glances at watch*`). He gives long, calm explanations. The observer didn't mention it. It's good at checking the topic but not at checking details of the persona.

**7. The 6-line limit (partly fixed).** Conversations always have 6 lines, whether the topic is solved or not. The wrap-up notes help the characters finish in time (roommates before vs after), but the limit is still fixed. A conversation that needs 10 lines still gets 6.

**8. Cost.** All the live runs on Nov 12 and 13 cost **$0.12** in total (from the Anthropic console). That's about 7 conversations, plus creating the personas and a few extra or failed calls, so one conversation costs around 1 to 2 cents with Haiku. Each conversation is about 9 calls: 2 to create personas, 6 lines and 1 for the observer. The observer is only 1 of those 9. The answers are long, and every line sends the whole conversation again, so later lines cost more than earlier ones. The default model in the starter is Opus, which would cost much more.

**9. Commands typed at the wrong time go to the model.** Some keys were typed while a conversation was printing, and after that `/quit` didn't work. The app sent the text to the model like a normal message and the model answered that it didn't have a quit command. Terminal commands typed inside the app by mistake went to the model too. Small thing, but each one is an extra call for nothing.

**10. Natural instructions only partly work.** The orchestrator from the starter still uses regular expressions. A sentence like "have the doctor and the nurse discuss the schedule" starts a conversation, but without the word "about" the topic becomes "an initial consultation", and without "between" it just takes the first two personas in alphabetical order. Replacing this with tool use (option 1) wasn't part of this project.

**11. One score, one time.** The score comes from just one call. Running the observer again on the same conversation might give a different score, and that wasn't measured. It's also a model grading another model's conversation, so it might be too easy on it (#4 and #5 kind of show that). Almost every live run got 5/5. In offline mode the review is always the same fake one, so the quality of the reviews can't be tested without the API.

**Platform notes (macOS).** `uv` wasn't installed at first; it was installed with the official script from the README. The API key from Project 1 no longer worked (error 401, "invalid x-api-key"), so a new key was created. When the Project 1 virtual environment is still active in the terminal, `uv` prints a warning about `VIRTUAL_ENV`, but it still uses the right environment.

## 5. Tests

All the tests use `ScriptedLLM`, so they run without a key and cost nothing. 53 pass in total: 41 from the starter and 12 new ones in `tests/test_observer.py`.

| Test | What it checks |
|---|---|
| `test_parse_review_reads_every_field` | a normal answer fills all 4 fields |
| `test_parse_review_accepts_bold_and_score_out_of_five` | bold labels and `4/5` still work |
| `test_parse_review_does_not_crash_on_nonsense` | a weird answer gives `None` instead of crashing |
| `test_review_conversation_sends_topic_and_transcript` | the observer actually gets the topic and the dialogue |
| `test_conversation_in_app_saves_a_review` | in the app the review shows up and `review.md` is created |
| `test_conversation_is_kept_when_observer_fails` | if the observer fails, the conversation is still saved |
| `test_transcript_and_review_are_not_listed_as_personas` | the "Unnamed" bug doesn't come back |
| `test_failed_turn_keeps_the_lines_said_so_far` | if a reply fails mid-conversation, the earlier lines are kept and saved |
| `test_repeated_name_does_not_overwrite_the_first_persona` | two personas with the same name both stay |
| `test_random_name_skips_names_already_used` | a random name is never one that's already taken |
| `test_new_persona_is_asked_to_use_a_given_name` | the model is told which name to use |
| `test_last_two_speakers_are_told_to_wrap_up` | the wrap-up notes are sent on lines 5 and 6 only, and aren't saved in the transcript |

What isn't tested: whether a real review is good, whether the model actually uses the given name, and whether the characters actually wrap up. Those depend on the real model, so they were checked with the live runs in section 3 instead.

## 6. How to run it

```bash
uv sync
uv run pytest                              # 53 tests, no key needed
uv run main.py --offline                   # the whole app, no key needed
uv run main.py --model claude-haiku-4-5    # real run, needs ANTHROPIC_API_KEY in .env
```

Example session:

```
create a persona roommate who is very organized and likes a clean kitchen
create a persona roommate who is relaxed and always forgets to do the dishes
have them talk about splitting the house chores
```

After each conversation the review shows up on screen and is saved in `temp/review.md`, next to `temp/conversation.md`.

## 7. Next steps

- Add stage directions and persona details to the observer rules, and ask it to check each line, not just the whole conversation, to fix #4, #5 and #6.
- Give the first speaker a real opening scene instead of the one-line `Scene:` turn, so nobody starts by asking for clarification.
- Stop the conversation when the topic is resolved instead of after a fixed 6 lines. The observer could check after each line whether the question was answered.
- Run the observer a few times on the same conversation and see how much the score changes, kind of like looking at the variance across folds in cross validation.
