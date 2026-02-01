import json
import os
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from .env
load_dotenv()

# Initialize OpenAI client
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

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

CLICK:
{
  "action": "click",
  "x": <int>,
  "y": <int>,
  "reason": "<short reason>"
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

def extract_first_json(text: str):
    """
    Extracts the first valid JSON object from a string.
    This guards against extra text, multiple JSON blobs, or markdown.
    """
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

    # Get raw text output from the model
    text = response.output_text

    # Extract and return the first valid JSON object
    return extract_first_json(text)
