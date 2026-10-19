# build_advisor.py
"""
Builds side_hustle_advisor.html (the UK Side Hustle Finder page) from
side_hustles.py and the Gorilla prompts, so the page, the AI prompts and the
backend always show the same knowledge base.

Run: python build_advisor.py
"""

import json
import os

import build_gorilla_prompts
import side_hustles

HERE = os.path.dirname(os.path.abspath(__file__))


def build():
    with open(os.path.join(HERE, "advisor_template.html"), encoding="utf-8") as f:
        html = f.read()
    data = json.dumps(side_hustles.export_json(), ensure_ascii=False).replace("</", "<\\/")
    prompts = json.dumps({c: build_gorilla_prompts.build(c) for c in ("generic_ai", "personalized_ai")},
                         ensure_ascii=False).replace("</", "<\\/")
    html = html.replace("__DATA__", data).replace("__PROMPTS__", prompts)
    out = os.path.join(HERE, "side_hustle_advisor.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    return out


if __name__ == "__main__":
    print(build())
