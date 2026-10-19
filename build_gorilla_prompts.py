# build_gorilla_prompts.py
"""
Writes the system prompts for Gorilla's AI Chat Box (Settings > AI), one per
AI task, from the same sources the backend uses (prompts.py, regions.py,
side_hustles.py). Gorilla fills ${store:...} from the survey.

Run: python build_gorilla_prompts.py   ->  gorilla/system_prompt_generic_ai.txt
                                           gorilla/system_prompt_personalized_ai.txt
"""

import os

import prompts
import regions
import side_hustles

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gorilla")

AREA = """
Local area of this participant (from the survey):
- Region: ${store:region}
- City or town: ${store:town}
- Type of area: ${store:area_type}

Every idea must fit real demand in this participant's local area. Use the
notes below for their region and type of area. If the region or type of area
is missing or unclear, use demand that is common across the UK.

Typical local demand by UK region:

{regions}

Notes by type of area:
- City: {city}
- Town or suburb: {town}
- Village or rural area: {rural}

Best-fitting side hustles from the catalogue, by region:
{table}
"""

PERSON = """
Participant interest profile (from the survey):
- Age: ${store:age}
- Gender: ${store:gender}
- Job title: ${store:occupation}
- Line of work: ${store:sector}
- Years in that line of work: ${store:years_in_sector}
- Highest qualification: ${store:education}
- Enjoys doing in free time: ${store:free_time}
- Main skills and strengths in and outside of work: ${store:skills}
- Activities or topics they can lose themselves in: ${store:lose_yourself}

Tailor every idea to this person as well as to the area: each idea must
clearly build on at least one of their interests, hobbies or skills (you may
add the matching interest in brackets after the phrase). You may also build on
their job, line of work and experience. Use age, years of experience and
qualification only to judge what is realistic for them (time, experience,
budget). Never base ideas on gender, age or other stereotypes.
"""


def area_section():
    regions_text = "\n\n".join(f"{name}:\n" + "\n".join(f"- {i}" for i in items)
                               for name, items in regions.REGIONS.items())
    strip = lambda s: s.split(": ", 1)[1] if ": " in s else s
    # str.format would trip over Gorilla's ${store:...}, so fill the slots by hand
    text = AREA
    for key, value in (("{regions}", regions_text), ("{city}", strip(regions.AREA_TYPES["city"])),
                       ("{town}", strip(regions.AREA_TYPES["town"])), ("{rural}", strip(regions.AREA_TYPES["rural"])),
                       ("{table}", side_hustles.gorilla_region_table())):
        text = text.replace(key, value)
    return text


def build(condition):
    text = prompts.SHARED_RULES.strip() + "\n" + area_section()
    text += PERSON if condition == "personalized_ai" else prompts.GENERIC_BLOCK
    return text.strip() + "\n"


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for cond in ("generic_ai", "personalized_ai"):
        path = os.path.join(OUT, f"system_prompt_{cond}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(build(cond))
        print(path, len(build(cond).split()), "words")
