# content.py
"""
All participant-facing text for the main flow, in one place.

Edit wording here (not in the templates). Freeze it before the pilot and
include it in the preregistration materials.

Order: welcome -> prime -> task intro -> [randomisation] -> ideation -> choose idea

Design rules followed:
- Everything before ideation is identical for all participants, because the
  condition is only assigned after the task intro.
- Ideation instructions have the same structure and length; they differ only
  in where ideas should come from (own background vs. broad appeal) and in
  whether an AI assistant is available.
- No screen mentions "ownership", "personalisation" or the hypotheses.
"""

WELCOME = {
    "title": "Your side hustle starts here",
    "body": [
        "In this short coaching session, you’ll develop a profitable idea for a side business. "
        "Many people want to earn extra income alongside their job but don’t know where to start. "
        "This session gives you a simple way to get there.",
        "You have 15 minutes. There are no right or wrong answers.",
    ],
    "button": "Let’s get started",
}

# The prime: answered by everyone, before randomisation. The personalised
# conditions later build on these answers (and the personalised assistant
# receives them); the generic conditions do not.
PRIME_ABOUT_YOU = {
    "title": "A bit about you",
    "intro": "Let’s talk a little about your skills and interests. "
             "Please answer each question with a few short bullet points. (1-2 min)",
    "questions": [
        {"key": "free_time", "text": "What do you enjoy doing in your free time?",
         "placeholder": "e.g.\n• hiking\n• cooking for friends\n• following football"},
        {"key": "skills", "text": "What are your main skills and strengths in and outside of work?",
         "placeholder": "e.g.\n• organising projects\n• explaining things clearly\n• Excel"},
        {"key": "lose_yourself", "text": "What activities or topics can you lose yourself in?",
         "placeholder": "e.g.\n• interior design\n• fixing old bikes\n• history podcasts"},
    ],
    "button": "Continue",
}

# Task intro: same for everyone, shown right before randomisation.
TASK_INTRO = {
    "title": "Let’s develop an idea!",
    "body": [
        "Your task is to brainstorm 5 ideas for a profitable side business. "
        "Any kind of business is welcome. There are no wrong ideas.",
        "You have five minutes. Write each idea as a short phrase.",
    ],
    "button": "Start brainstorming",
}

IDEATION_SECONDS_DEFAULT = 300   # 5 minutes, same for all conditions (env IDEATION_SECONDS overrides)
MIN_IDEAS = 5                    # needed before continuing (matches "brainstorm 5 ideas")
MAX_IDEAS = 50
MIN_IDEA_CHARS = 3
MAX_IDEA_CHARS = 200

# Shown on the ideation page under the condition-specific instruction.
IDEATION_REMINDER = "Add 5 ideas as short phrases."

IDEATION = {
    "generic_noai": {
        "title": "Brainstorm your ideas",
        "body": "Write down ideas for a profitable side business that many people would pay for.",
    },
    "personalized_noai": {
        "title": "Brainstorm your ideas",
        "body": "Write down ideas for a profitable side business that build on what you wrote about yourself.",
    },
    "generic_ai": {
        "title": "Brainstorm your ideas",
        "body": "Use the assistant to brainstorm ideas for a profitable side business that many people would pay "
                "for. Write down every idea you want to keep in your list.",
    },
    "personalized_ai": {
        "title": "Brainstorm your ideas",
        "body": "Use the assistant to brainstorm ideas for a profitable side business that build on what you wrote "
                "about yourself. The assistant knows your answers. Write down every idea you want to keep in your list.",
    },
}

SHOW_PRIME_ANSWERS_IN = {"personalized_noai", "personalized_ai"}

SELECT = {
    "title": "Choose your idea",
    "body": "Which of your ideas would you most like to develop further? Choose one.",
    "describe": "Describe this idea in a few sentences: what would you offer, and to whom?",
    "button": "Continue",
}

DONE = {
    "title": "Thank you!",
    "body": "Your idea has been saved. Please continue with the next part of the study.",
    "button": "Continue",
}


# ---------------------------------------------------------------------------
# Idea Workspace (/workspace): the no-AI brainstorm environment for Gorilla.
# Same look and size as the AI chat, but replies are fixed thinking prompts.
# Both versions have the same structure: 3 starter questions + 3 more prompts,
# similar length. Generic = people in your area; personalised = your
# background + your area (mirrors what the two AI assistants use).
# ---------------------------------------------------------------------------

WORKSPACE = {
    "title": "What side business could you start?",
    "subtitle": "Use this space to think and jot down ideas. Pick a thinking prompt whenever you need inspiration.",
    "placeholder": "Jot down a thought or idea…",
    "prompt_button": "Thinking prompt",
    "generic_noai": {
        "intro": "Think about the people who live in your area and what they need.",
        "starters": [
            "What do people around me need?",
            "What could I sell?",
            "What service is missing locally?",
        ],
        "prompts": [
            "What do busy people in your area struggle to find time for? Which task could you take off their hands?",
            "What do people in your area often buy, or would buy if it were easier to get? Could you sell it?",
            "Which everyday service is hard to find or too expensive where you live?",
            "Think of one group in your area, such as parents, pet owners, students or older people. What do they need?",
            "What could you offer in the evenings or at weekends, alongside a job?",
            "Take an idea you already have. How could you make it simpler, cheaper or more local?",
        ],
    },
    "personalized_noai": {
        "intro": "Think about your own background: your interests, your skills and your experience.",
        "starters": [
            "How could my hobbies help others?",
            "Which of my skills would people pay for?",
            "What could I offer in my area?",
        ],
        "prompts": [
            "Look at what you enjoy in your free time. How could one of these activities help other people?",
            "Which of your skills, in or outside of work, would someone pay for?",
            "What do you know a lot about that others find hard? Could you teach it, do it for them or sell it?",
            "Think of the people in your area. Which of your interests or skills could solve a problem for them?",
            "What could you offer in the evenings or at weekends that builds on your experience?",
            "Take an idea you already have. How could you make it fit you even better?",
        ],
    },
}

BACKGROUND_LABELS = {
    "free_time": "Free time",
    "skills": "Skills and strengths",
    "lose_yourself": "What you lose yourself in",
    "occupation": "Job",
    "sector": "Line of work",
}
