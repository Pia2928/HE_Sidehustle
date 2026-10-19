# HE Study Backend

Web app for the 2 × 2 study on AI support, personalisation and entrepreneurial action.
It recruits nobody itself: participants come from Prolific, go through the coaching flow here, and are then forwarded to your survey.

## Participant flow

```
Prolific ─► /start ─► Welcome ─► "A bit about you" ─► Task intro ─► [RANDOMISATION] ─► Brainstorm ─► Choose idea ─► SURVEY_URL
                                  (prime)              "Let's develop                     5 min,                         (Gorilla /
                                                        an idea!"                         4 versions                     Qualtrics)
```

| Step | Same in all conditions? | What happens |
|---|---|---|
| Welcome | yes | "Your side hustle starts here" |
| Prime | yes | Three open questions, answered in bullet points: free time, professional skills and strengths, activities they lose themselves in |
| Task intro | yes | "Let's develop an idea!": brainstorm 5 ideas for a profitable side business, any kind welcome, five minutes, short phrases |
| *Randomisation* | | The condition is assigned when the participant clicks "Start brainstorming" |
| Brainstorm | **no: this is the manipulation** | 5-minute timer; participants add short idea phrases to a list (at least 5). Instruction differs by personalisation (build on what you wrote / many people would pay for). AI conditions get the chat panel; the personalised assistant receives the prime answers. Personalised conditions see their prime answers above the task. Continue unlocks when the time is up. |
| Choose idea | yes | Pick one idea from the list and describe it in a few sentences |
| Survey | yes | Redirect to `SURVEY_URL` with the ID, condition and chosen idea |

The optional unpaid part (`/guide`, `/plan`) is unchanged; link to it from the end of your survey, after the Prolific completion code:
`https://<app>/guide?pid=<PROLIFIC_PID>&cond=<cond>` and `https://<app>/plan?pid=<PROLIFIC_PID>&cond=<cond>&idea=<idea>`.

All participant-facing text is in **`content.py`**; the AI instructions are in **`prompts.py`**.

## Randomisation

`randomisation.py` uses **permuted-block randomisation with block sizes 4 and 8** in random order:

- Every block contains each of the four conditions equally often, so groups stay balanced throughout recruitment (at any moment they differ by at most a few participants).
- Varying block sizes make the next assignment unpredictable.
- The whole sequence is generated once from `ALLOCATION_SEED` and stored in the database, so it is reproducible and auditable. Each new participant takes the next free slot; two people arriving at the same moment can never get the same slot.
- A participant who reloads or reopens the link keeps their original condition.
- Randomisation happens at the end of the task intro, not at the start. People who drop out during the welcome, prime or intro are never randomised, so they don't use up slots or unbalance the groups. Report them separately as "dropped out before randomisation" (the `flow` export shows them with an empty condition).

Wording for the preregistration: *"Participants were randomly assigned to one of the four conditions using permuted-block randomisation (block sizes 4 and 8, randomly ordered), with a pre-generated allocation sequence based on a fixed seed."*

Check balance during data collection: `https://<app>/admin/balance?token=<ADMIN_TOKEN>` (randomised / finished brainstorm / finished, per condition, plus the number not yet randomised).

Dropouts after assignment are not replaced automatically; Prolific's "returned" submissions are re-offered to new participants, who get new slots. Expect small differences in the number of completers per condition and recruit a little above 800.

## Settings (environment variables, see `.env.example`)

| Variable | Purpose |
|---|---|
| `ALLOCATION_SEED` | Seed for the allocation sequence. Set once before launch, record it, never change it. |
| `IDEATION_SECONDS` | Brainstorm length, equal for all conditions (default 300 = 5 minutes) |
| `SURVEY_URL` | Your survey link with placeholders `{pid} {cond} {idea} {description} {study_id} {session_id}` |
| `ALLOW_FORCED_CONDITION` | `1` only for testing: lets you open `/start?pid=TEST1&cond=generic_ai` |
| `ADMIN_TOKEN`, `DB_PATH`, AI settings | As before |

## Prolific setup

- Study URL: `https://<app>/start?PROLIFIC_PID={{%PROLIFIC_PID%}}&STUDY_ID={{%STUDY_ID%}}&SESSION_ID={{%SESSION_ID%}}`
  (Prolific fills these in when you choose to record participant IDs via URL parameters.)
- The completion code is shown at the end of your survey, **before** the optional guide and plan.

## Survey setup (Gorilla or Qualtrics)

Your survey must read the URL parameters (`PROLIFIC_PID`, `cond`, `idea`) and store them, so you can merge the data and show the chosen idea above the quality and ownership questions.
In Qualtrics: add them as Embedded Data fields at the top of the Survey Flow. In Gorilla: check its documentation for passing URL parameters into the experiment. In both, verify with a test run that the values arrive.

## AI chat for Gorilla (`/chat`)

A full-page chat in the style of ChatGPT, embedded in the Gorilla brainstorm screen of the two AI conditions. Replies appear word by word (streaming), lists are formatted, each reply has a **Copy** button, and the conversation is restored if the page reloads. All messages are saved (`messages` export).

### What the assistant knows

| | Local area (region, type of area, town) | Personal profile (age, gender, occupation, hobbies, skills, interests) |
|---|---|---|
| `generic_ai` | yes | **no** (ignored on the server even if sent) |
| `personalized_ai` | yes | yes |

The local-area information is identical in both AI conditions, so the only difference between them is the personal profile. For each of the 12 UK regions, `regions.py` lists typical local demand for low-cost side businesses (plus notes for city / town / rural). **This is a qualitative draft: check it against current sources (ONS regional profiles, Nomis, local authority and tourism data) before the pilot, then freeze it.**

Both assistants also get the same catalogue of everyday side jobs (`COMMON_SIDE_HUSTLES` in `regions.py`: babysitting, dog walking, pet sitting, cleaning, reselling clothes and other products, home baking, tutoring, event help, simple online services, holiday-let services and more) and are told to prefer simple, practical ideas that are quick and cheap to start, noting any check or registration needed (e.g. DBS check, food business registration).

The prompts are in `prompts.py`. Both tell the assistant to give 5 short idea phrases per reply; the personalised one must also build each idea on the person's interests or skills, use age and occupation only to judge what's realistic, and never use gender or age stereotypes.

### Survey questions and Store names

Everyone answers them before randomisation. Save each answer to the Store under the name in the last column.

| Question | Store name |
|---|---|
| How old are you? | `age` |
| Which gender describes you best? | `gender` |
| Which region of the UK do you live in? (dropdown, 12 regions) | `region` |
| Which city or town do you live in? | `town` |
| Which of the following best describes the area you live in? | `area_type` |
| What is your job title? | `occupation` |
| Which of the following best describes your line of work? | `sector` |
| How many years have you worked in this line of work? | `years_in_sector` |
| What is your highest educational or professional qualification? | `education` |
| What do you enjoy doing and care about in your free time? | `free_time` |
| What are your main professional skills and strengths? | `skills` |
| What activities or topics do you lose yourself in? | `lose_yourself` |

The area matching accepts region names, larger UK cities and towns, and counties (e.g. "Leeds" -> Yorkshire and the Humber), so a free-text answer also works. A region dropdown is still the most reliable.

### Embed the chat in the Gorilla brainstorm screen

Add a Markdown Text (or HTML) component and paste the line for the condition. Replace `YOUR-APP` with your app address and check the name of the Store field that holds the Prolific ID.

**generic_ai** (area only):
```html
<iframe src='https://YOUR-APP/chat?pid=${store:PROLIFIC_PID}&cond=generic_ai#region=${store:region}||area_type=${store:area_type}||town=${store:town}' style='width:100%;height:520px;border:0' allow='clipboard-write'></iframe>
```

**personalized_ai** (area + person):
```html
<iframe src='https://YOUR-APP/chat?pid=${store:PROLIFIC_PID}&cond=personalized_ai#region=${store:region}||area_type=${store:area_type}||town=${store:town}||age=${store:age}||gender=${store:gender}||occupation=${store:occupation}||sector=${store:sector}||years_in_sector=${store:years_in_sector}||education=${store:education}||free_time=${store:free_time}||skills=${store:skills}||lose_yourself=${store:lose_yourself}' style='width:100%;height:520px;border:0' allow='clipboard-write'></iframe>
```

Why the `#` and `||`: everything after `#` stays in the browser and isn't cut off by `&` or `#` inside an answer (e.g. "fish & chips"). The page reads the fields and sends them to the server once; the first profile received is kept, so a reload can't change what the assistant knows. Fields left empty are simply skipped.

**Test in Preview** with one run per AI condition: ask for ideas, then check the `participants` export. `profile_json` should contain the survey answers (only area fields matter for `generic_ai`).

### Keep the no-AI conditions parallel

Because both AI conditions now tailor ideas to the participant's area, mention the area in the no-AI instructions too, so the 2 × 2 stays clean:
- generic_noai: "Write down ideas for a profitable side business that people in your area would pay for."
- personalized_noai: "Write down ideas for a profitable side business that build on what you wrote about yourself and suit your area."

## Idea Workspace for the no-AI conditions (`/workspace`)

The brainstorm environment for `generic_noai` and `personalized_noai`. It looks like the AI chat (same frame, size, layout, input box and start buttons), so the four conditions differ only in what you are testing, not in how the screen looks.

Instead of AI replies, participants get **fixed thinking prompts**: 3 start buttons and a "Thinking prompt" button that shows the next of 6 prompts. Their own messages are saved as **notes**. They still write their 5 ideas in the Gorilla fields below, as in the AI conditions.

| | First message | Prompts about |
|---|---|---|
| `generic_noai` | "Think about the people who live in your area and what they need." + their area | Needs of people in their area |
| `personalized_noai` | "Think about your own background: your interests, your skills and your experience." + **their background** (free time, skills, what they lose themselves in, occupation) + their area | How their hobbies, skills and experience could become a business in their area |

This mirrors the AI conditions: generic = area, personalised = area + person. All texts are in `content.py` (`WORKSPACE`). Both versions have the same number of prompts and similar prompt lengths (checked in `test_chat.py`).

Embed it in the Gorilla brainstorm screen of each no-AI condition, like the chat:

**generic_noai**:
```html
<iframe src='https://YOUR-APP/workspace?pid=${store:PROLIFIC_PID}&cond=generic_noai#region=${store:region}||area_type=${store:area_type}||town=${store:town}' style='width:100%;height:520px;border:0'></iframe>
```

**personalized_noai**:
```html
<iframe src='https://YOUR-APP/workspace?pid=${store:PROLIFIC_PID}&cond=personalized_noai#region=${store:region}||area_type=${store:area_type}||town=${store:town}||occupation=${store:occupation}||free_time=${store:free_time}||skills=${store:skills}||lose_yourself=${store:lose_yourself}' style='width:100%;height:520px;border:0'></iframe>
```

Data: notes and the prompts each person opened are in the `messages` export (`role` = `note` or `prompt`); the `summary` export has `n_notes`, `n_prompts_viewed` and `workspace_active_s`.


## Using an Anthropic (Claude) API key

Set `ANTHROPIC_API_KEY` and the chat uses Claude; it takes priority over the OpenAI settings. Optional: `MODEL` (default `claude-sonnet-5-5`; `claude-haiku-5-5` is cheaper and faster). Pin the model ID you use and record it in the preregistration. `/health` shows `"llm": "anthropic"` and the model when it's set up.

PythonAnywhere WSGI file example:

```python
import os, sys
sys.path.insert(0, "/home/YOURNAME/he-study-backend")
os.environ["ANTHROPIC_API_KEY"] = "sk-ant-..."
os.environ["MODEL"] = "claude-sonnet-5-5"
os.environ["ADMIN_TOKEN"] = "a-long-random-password"
os.environ["DB_PATH"] = "/home/YOURNAME/he-study-backend/study.db"
from app import app as application
```

## Data exports

`https://<app>/admin/export/<name>.csv?token=<ADMIN_TOKEN>`

| File | Contents |
|---|---|
| `summary` | One row per randomised participant: condition, allocation slot, stage reached, brainstorm seconds, chosen idea, chat messages, active time on chat/guide/plan, plan words, etc. |
| `flow` | Everyone who started (including drop-outs before randomisation): prime answers, all brainstormed ideas, chosen idea and description, timestamps per step, Prolific study and session IDs. Number of ideas = the fluency measure. |
| `allocation` | Slot, block and condition for every assigned participant (audit trail for the randomisation) |
| `messages` | Every chat turn |
| `plans`, `page_time`, `events`, `participants` | As before |

## Run locally

```bash
pip install -r requirements.txt
export ADMIN_TOKEN=dev ALLOW_FORCED_CONDITION=1
python app.py
```

Set `IDEATION_SECONDS=20` while testing so you don't wait 5 minutes. Then open, for example:
- `http://127.0.0.1:5000/start?PROLIFIC_PID=TEST1` (random condition)
- `http://127.0.0.1:5000/start?PROLIFIC_PID=TEST2&cond=personalized_ai` (forced, test mode only)
- `http://127.0.0.1:5000/admin/balance?token=dev`

Without an API key the assistant gives mock replies. Tests: `python test_app.py` and `python test_flow.py`.

## Deploy (Azure App Service, UK South)

1. Create an Azure OpenAI resource in **UK South** (or an EU region), deploy a model, and note the endpoint, key and deployment name.
2. Create a Linux App Service (Python 3.12) in the same region and deploy this folder.
3. Set the environment variables from `.env.example`. Use `DB_PATH=/home/data/study.db`, a long random `ADMIN_TOKEN`, your `ALLOCATION_SEED` and `SURVEY_URL`, and **`ALLOW_FORCED_CONDITION=0`**.
4. Startup command: `gunicorn -k gthread -w 2 --threads 8 --timeout 120 -b 0.0.0.0:8000 app:app`
   (threads are needed so streaming chat replies don't block other participants)
5. Open `/health`; it should report `"llm": "azure"`.
6. Keep a single instance (no scale-out) and back up `/home/data/study.db` daily.

## Before the pilot

- Freeze `content.py`, `prompts.py` and `templates/guide.html` and add them to the preregistration materials.
- Record `ALLOCATION_SEED` in the preregistration.
- Use a dated model deployment so the model doesn't change mid-study.
- Decide and preregister the idle threshold (60 s) and the primary time DV (`active` vs `visible`).
- Delete the pilot database (or use a separate seed) before the main study, and turn off `ALLOW_FORCED_CONDITION`.
- If you ran an earlier version of the app locally, delete the old `study.db`; the database layout has changed.
- Consent form: say that chat, answers and plans are recorded (UK GDPR).
