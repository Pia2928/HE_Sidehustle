# prompts.py
"""
System prompts for the two AI conditions.

Design (2 x 2, AI cells):
- generic_ai:       tailored to the participant's LOCAL AREA only.
- personalized_ai:  tailored to the same local area PLUS the participant's
                    personal profile (interests, hobbies, skills, age, gender,
                    occupation).

The local-area part is identical in both, so the only manipulated difference
between the two AI conditions is the personal profile. Both prompts share the
same task, tone, output format and length. Edit wording here before piloting,
then freeze it for the preregistration.
"""

import side_hustles
from regions import area_context, match_area_type, match_region

# Fields from the survey. Only PERSONAL_FIELDS differ between the conditions.
AREA_FIELDS = ("region", "area_type", "town")
PERSONAL_FIELDS = ("age", "gender", "occupation", "sector", "years_in_sector", "education",
                   "free_time", "skills", "lose_yourself")
PROFILE_FIELDS = AREA_FIELDS + PERSONAL_FIELDS

PERSONAL_LABELS = {
    "age": "Age",
    "gender": "Gender",
    "occupation": "Job title",
    "sector": "Line of work",
    "years_in_sector": "Years in that line of work",
    "education": "Highest qualification",
    "free_time": "Enjoys doing in free time",
    "skills": "Main skills and strengths in and outside of work",
    "lose_yourself": "Activities or topics they can lose themselves in",
}

SHARED_RULES = """
You are an assistant helping UK residents come up with ideas for a profitable
side business they could run alongside a regular job (roughly 5-15 hours per
week, low start-up costs).

The participant has five minutes to brainstorm 5 ideas for a side business.

Rules:
- When asked for ideas, suggest exactly 5 side-business ideas per reply, as a
  numbered list of short idea phrases (at most 12 words each),
  e.g. "Evening meal-prep delivery for night-shift nurses".
- Do not add explanations unless the participant asks for them.
- Keep each reply under 120 words. Use plain, friendly British English.
- You may vary, combine or adjust ideas when the participant asks.
- Do not ask the participant for personal details such as their name, address,
  employer or contact information.
- Do not tell the participant what you know about them or their area unless
  they ask; just give the ideas.
- Stay on the topic of side-business ideas. If asked about something else,
  politely steer back to the task.

Only suggest side hustles that need no specific training or qualification and
little money to start (up to about £250), like those in the catalogue below.
Build on the catalogue, and make each idea specific (who it is for, what exactly
is offered). Mix different kinds of ideas. If an idea needs a registration or
licence, add it in brackets, e.g. "(register with council)".

Catalogue of low-barrier side hustles (UK rules checked """ + side_hustles.CHECKED_ON + """):
""" + side_hustles.catalogue_text() + "\n"

AREA_BLOCK = """
Local area:
{area}

Best-fitting side hustles from the catalogue for this area: {best_fits}.

Every idea must fit real demand in this local area (use the notes above).
"""

GENERIC_BLOCK = """
Do NOT tailor ideas to the participant's personal interests, hobbies, skills,
job, age, gender or background, even if they mention them. If they share
personal details, acknowledge them briefly and keep suggesting ideas that
would suit most people living in this area.
"""

PERSONAL_BLOCK = """
Participant interest profile:
{profile}

Tailor every idea to this person as well as to the area: each idea must
clearly build on at least one of their interests, hobbies or skills (you may
add the matching interest in brackets after the phrase). You may also build on
their job, line of work and experience. Use age, years of experience and
qualification only to judge what is realistic for them (time, experience,
budget). Never base ideas on gender, age or other stereotypes.
"""

OPENING_MESSAGE = (
    "Hi! I'm here to help you come up with ideas for a profitable side "
    "business. Ask me for ideas whenever you're ready."
)

STARTER_PROMPTS = [
    "Suggest 5 side-business ideas",
    "Ideas I could start with very little money",
    "Ideas that fit around a full-time job",
]


def _clean(profile):
    profile = profile or {}
    return {k: str(profile.get(k, "")).strip() for k in PROFILE_FIELDS}


def personal_profile_text(profile, interests_text=None):
    p = _clean(profile)
    lines = [f"{PERSONAL_LABELS[k]}: {p[k]}" for k in PERSONAL_FIELDS if p[k]]
    if not lines and interests_text:
        lines = [interests_text.strip()]
    return "\n".join(lines) or "(no profile provided)"


def build_system_prompt(condition, profile=None, interests_text=None):
    """
    Return the system prompt for an AI condition.

    profile: dict with any of PROFILE_FIELDS (from the Gorilla survey).
    interests_text: older free-text profile (used by the standalone flow).
    For generic_ai, personal fields are ignored even if they were sent.
    """
    p = _clean(profile)
    best = side_hustles.best_fits_text(match_region(p["region"]), match_area_type(p["area_type"]))
    prompt = SHARED_RULES + AREA_BLOCK.format(area=area_context(p["region"], p["area_type"], p["town"]),
                                              best_fits=best)
    if condition == "personalized_ai":
        return prompt + PERSONAL_BLOCK.format(profile=personal_profile_text(p, interests_text))
    return prompt + GENERIC_BLOCK
