import argparse
import json
from browser import Browser
from vision import decide_next_action, resolve_click

MAX_STEPS = 25


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument(
        "--format",
        required=True,
        help="JSON schema describing the required final output"
    )
    args = parser.parse_args()

    # Parse output schema once
    try:
        output_schema = json.loads(args.format)
    except json.JSONDecodeError as e:
        raise ValueError(f"--format must be valid JSON: {e}")

    browser = Browser(args.url)
    history = []

    try:
        for step in range(MAX_STEPS):
            screenshot = browser.screenshot_base64()

            # Phase 1: vision model decides next action
            decision = decide_next_action(
                image_b64=screenshot,
                goal=args.prompt,
                output_schema=output_schema,
                history=history
            )

            print(f"\nSTEP {step + 1}: {decision}")

            action = decision["action"]

            # ---------- EXECUTE ACTION ----------
            if action == "type":
                browser.type_text(decision["text"])
                history.append(decision)
                continue

            elif action == "click":
                target_desc = decision.get("target", "")
                clickable_elements = browser.get_clickable_elements()

                print(
                    f'   Resolving target "{target_desc}" '
                    f"against {len(clickable_elements)} elements..."
                )

                resolution = resolve_click(target_desc, clickable_elements)
                chosen_index = resolution.get("index", -1)

                print(
                    f"   Resolved -> index={chosen_index} "
                    f'reason="{resolution.get("reason", "")}"'
                )

                if chosen_index == -1 or chosen_index >= len(clickable_elements):
                    print("!! Could not resolve click target — replanning")
                    history.append({
                        "failed_action": decision,
                        "reason": "resolve_click_failed"
                    })
                    continue

                before_url = browser.current_url()
                before_hash = browser.screenshot_hash()

                success = browser.click_element_by_index(chosen_index)
                if not success:
                    history.append({
                        "failed_action": decision,
                        "reason": "click_execution_failed"
                    })
                    continue

            elif action == "enter":
                before_url = browser.current_url()
                before_hash = browser.screenshot_hash()
                browser.press_enter()

            elif action == "scroll":
                before_url = browser.current_url()
                before_hash = browser.screenshot_hash()
                browser.scroll_down()

            elif action == "finish":
                print("\nFINAL RESULT:")
                print(json.dumps(decision["result"], indent=2))
                with open("sample_output.json", "w") as f:
                    json.dump(decision["result"], f, indent=2)
                return

            else:
                print(f"!! Unknown action: {action}")
                history.append({"error": "unknown_action", "decision": decision})
                continue

            # ---------- VERIFY ----------
            after_url = browser.current_url()
            after_hash = browser.screenshot_hash()

            if after_url == before_url and after_hash == before_hash:
                print("!! Action caused no visible change — replanning")
                history.append({
                    "failed_action": decision,
                    "reason": "no_visible_change"
                })
                continue

            history.append(decision)

        print("!!! Max steps reached without finishing.")

    finally:
        browser.close()


if __name__ == "__main__":
    main()
