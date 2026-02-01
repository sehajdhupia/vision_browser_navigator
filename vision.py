import json
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---------------------------------------------------------------------------
# BASE SYSTEM PROMPT — return schema is given dynamically
# ---------------------------------------------------------------------------
BASE_SYSTEM_PROMPT = """
You are an autonomous web navigation agent.

You are given:
- A screenshot of the current webpage
- A user goal
- A short history of previous actions
- A REQUIRED JSON output schema

Your task is to decide the NEXT SINGLE action to take.

You MUST respond with EXACTLY ONE valid JSON object.
DO NOT include explanations, markdown, or extra text.

Valid actions:

CLICK — describe the target in plain text. Do NOT guess pixel coordinates.
{
  "action": "click",
  "target": "<what you want to click>",
  "reason": "<why>"
}

TYPE:
{
  "action": "type",
  "text": "<text to type>",
  "reason": "<why>"
}

ENTER:
{
  "action": "enter"
}

SCROLL DOWN:
{
  "action": "scroll"
}

SCROLL UP:
{
  "action": "scroll_up"
}

SCROLL TO TOP:
{
  "action": "scroll_top"
}


FINISH:
{
  "action": "finish",
  "result": <JSON object matching the required schema>
}

Rules for FINISH:
- The result MUST match the schema EXACTLY.
- All required keys must be present.
- If a value is not visible on the page, use null.
- Do NOT invent data.
- Do NOT add extra keys.

Required Output Schema:
<JSON_SCHEMA>
"""

# ---------------------------------------------------------------------------
# PHASE 2 PROMPT — resolve semantic target -> DOM element index
# ---------------------------------------------------------------------------
RESOLVE_PROMPT = """
You are given a list of clickable elements on a webpage and a target description.
Pick the element that best matches the target.

Respond with EXACTLY ONE valid JSON object:
{
  "index": <int>,
  "reason": "<why this element matches>"
}

If no element matches, respond:
{
  "index": -1,
  "reason": "<why nothing matched>"
}
"""


def extract_first_json(text: str):
    decoder = json.JSONDecoder()
    text = text.strip()
    for i in range(len(text)):
        if text[i] == "{":
            try:
                obj, _ = decoder.raw_decode(text[i:])
                return obj
            except json.JSONDecodeError:
                continue
    raise ValueError(f"No valid JSON object found:\n{text}")


def decide_next_action(image_b64, goal, output_schema, history):
    schema_text = json.dumps(output_schema, indent=2)

    system_prompt = BASE_SYSTEM_PROMPT.replace(
        "<JSON_SCHEMA>",
        schema_text
    )

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": f"Goal: {goal}\nPrevious actions: {history}"
                    },
                    {
                        "type": "input_image",
                        "image_url": f"data:image/png;base64,{image_b64}"
                    }
                ]
            }
        ],
        max_output_tokens=500
    )

    return extract_first_json(response.output_text)


def resolve_click(target_description, clickable_elements):
    elements_text = "\n".join(
        f"[{el['index']}] <{el['tag']}> text=\"{el['text']}\" href={el['href']}"
        for el in clickable_elements
    )

    prompt = (
        f"Target description: {target_description}\n\n"
        f"Clickable elements:\n{elements_text}"
    )

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {
                "role": "system",
                "content": RESOLVE_PROMPT
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        max_output_tokens=200
    )

    return extract_first_json(response.output_text)
