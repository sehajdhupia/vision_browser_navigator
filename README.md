# Vision Browser Navigator

An autonomous, vision-guided web navigation agent that can browse arbitrary websites, interact with real DOM elements, and extract structured information into a user-defined JSON format.

The system combines:
- Visual perception (screenshots)
- LLM-based reasoning
- Deterministic browser control via Selenium
- Schema-driven structured output

It is designed to work across **any website** and **any extraction goal**, not just GitHub.

---

## What This Tool Does

Given:
- a starting URL
- a natural-language goal
- a desired JSON output format

The agent will:
1. Open a real browser
2. Observe the page visually
3. Decide the next action (click, type, scroll, etc.)
4. Execute the action on real DOM elements
5. Repeat until it can produce the requested structured output
6. Return a JSON object matching the user-provided schema

Example use cases:
- Extract latest releases from package repositories
- Summarize what a project does from its homepage
- Pull pricing, changelogs, or metadata from unfamiliar sites
- Perform general-purpose website exploration with structured results

---

## High-Level Architecture

The system is intentionally split into three layers.

### 1. Navigation Loop (`navigate.py`)

The control loop that:
- Captures screenshots
- Calls the LLM to decide the next action
- Executes browser actions
- Verifies whether actions caused a visible change
- Stops when the LLM emits a `finish` action

This loop enforces:
- One action per step
- Bounded execution
- Deterministic browser control

---

### 2. Browser Control (`browser.py`)

This layer wraps Selenium and exposes high-level browser actions:
- `type_text`
- `press_enter`
- `click_element_by_index`
- `scroll`, `scroll_up`, `scroll_top`
- `get_clickable_elements`
- Screenshot capture and hashing

The LLM never clicks raw pixels.  
All clicks are resolved against real DOM elements.

---

### 3. LLM Reasoning (`vision.py`)

This layer uses the OpenAI API in two phases.

#### Phase 1 — Visual Reasoning
- Input: screenshot, goal, action history
- Output: next action in strict JSON

#### Phase 2 — Click Resolution
- Input: textual target description + clickable DOM elements
- Output: index of the best-matching DOM element

Separating intent from execution makes navigation deterministic and layout-independent.

---

## Installation & Setup

### 1. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```
### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Install Google Chrome
The agent uses Chrome via Selenium.
Ensure Chrome is installed locally.

### 4. Set your OpenAI API key

Create a .env file:
```env
OPENAI_API_KEY=...
```

---

## Usage

Basic command format:

```bash
python3 navigate.py \
  --url "<starting_url>" \
  --prompt "<goal>" \
  --format '<json_schema>'
```

Example:

```bash
python3 navigate.py \
  --url "https://github.com" \
  --prompt "search for openclaw and get the current release and related tags" \
  --format '{
    "latest_release": {
      "version": "string",
      "tag": "string",
      "date": "string",
      "author": "string"
    }
  }'
```