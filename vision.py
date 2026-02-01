import json
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---------------------------------------------------------------------------
# PHASE 1 PROMPT — vision model looks at screenshot, decides WHAT to do.
# For clicks it outputs a text description, NOT coordinates.
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """
You are an autonomous web navigation agent.

You are given:
- A screenshot of the current webpage
- A user goal
- A short history of previous actions

Your task is to decide the NEXT SINGLE action to take.

You MUST respond with EXACTLY ONE valid JSON object.
DO NOT include explanations, markdown, or extra text.

Valid actions:

CLICK — describe the target in plain text. Do NOT guess pixel coordinates.
{
  "action": "click",
  "target": "<describe exactly what you want to click, e.g. 'the openclaw/openclaw repository link'>",
  "reason": "<why>"
}

TYPE:
{
  "action": "type",
  "text": "<text to type>",
  "reason": "<short reason>"
}

ENTER:
{
  "action": "enter"
}

SCROLL:
{
  "action": "scroll"
}

FINISH:
{
  "action": "finish",
  "result": {
    "repository": "<repo name>",
    "latest_release": {
      "version": "<version>",
      "tag": "<tag>",
      "author": "<author>"
    }
  }
}
"""

# ---------------------------------------------------------------------------
# PHASE 2 PROMPT — no vision needed. Pure text matching: given a list of
# clickable elements from the DOM and a target description, pick the index.
# ---------------------------------------------------------------------------
RESOLVE_PROMPT = """
You are given a list of clickable elements on a webpage and a target description.
Pick the element that best matches the target.

Respond with EXACTLY ONE valid JSON object, nothing else:
{
  "index": <int>,
  "reason": "<why this element matches>"
}

If no element is a reasonable match, respond:
{
  "index": -1,
  "reason": "<why nothing matched>"
}
"""


def extract_first_json(text: str):
    """Extract the first valid JSON object from a string."""
    decoder = json.JSONDecoder()
    text = text.strip()
    for i in range(len(text)):
        if text[i] == "{":
            try:
                obj, _ = decoder.raw_decode(text[i:])
                return obj
            except json.JSONDecodeError:
                continue
    raise ValueError(f"No valid JSON object found in model output:\n{text}")


def decide_next_action(image_b64, goal, history):
    """
    Phase 1: look at the screenshot and decide what action to take.
    For clicks, this returns a 'target' description — not coordinates.
    """
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
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
        max_output_tokens=400
    )

    return extract_first_json(response.output_text)


def resolve_click(target_description, clickable_elements):
    """
    Phase 2: given the vision model's target description and the real list
    of clickable DOM elements (from browser.get_clickable_elements()),
    use a text-only LLM call to pick the correct element index.

    This is the key step that makes clicking deterministic — we match against
    actual DOM nodes, not pixel coordinates.
    """
    # Format the element list for the prompt
    elements_text = "\n".join(
        f"[{el['index']}] <{el['tag']}> text=\"{el['text']}\" href={el['href']}"
        for el in clickable_elements
    )

    prompt = (
        f"Target description: {target_description}\n\n"
        f"Clickable elements on the page:\n{elements_text}"
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

    result = extract_first_json(response.output_text)
    return result  # { "index": <int>, "reason": "<str>" }