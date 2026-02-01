import argparse
import json
from browser import Browser
from vision import decide_next_action, resolve_click

MAX_STEPS = 25


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--prompt", required=True)
    args = parser.parse_args()

    browser = Browser(args.url)
    history = []

    try:
        for step in range(MAX_STEPS):
            screenshot = browser.screenshot_base64()

            # Phase 1: vision model decides what to do
            decision = decide_next_action(
                image_b64=screenshot,
                goal=args.prompt,
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
                # Phase 2: resolve the text description to a real DOM element
                target_desc = decision.get("target", "")
                clickable_elements = browser.get_clickable_elements()

                print(f"   Resolving target: \"{target_desc}\" against {len(clickable_elements)} elements...")

                resolution = resolve_click(target_desc, clickable_elements)
                chosen_index = resolution.get("index", -1)
                print(f"   Resolved → index={chosen_index} reason=\"{resolution.get('reason', '')}\"")

                if chosen_index == -1 or chosen_index >= len(clickable_elements):
                    print("⚠️  Could not resolve click target — replanning")
                    history.append({
                        "failed_action": decision,
                        "reason": f"resolve_click returned index={chosen_index}"
                    })
                    continue

                # Capture state before click for change detection
                before_url = browser.current_url()
                before_hash = browser.screenshot_hash()

                # Click the actual DOM element by index
                success = browser.click_element_by_index(chosen_index)
                if not success:
                    history.append({
                        "failed_action": decision,
                        "reason": "click_element_by_index returned False"
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
                print(f"⚠️  Unknown action: {action}")
                history.append({"error": "unknown_action", "decision": decision})
                continue

            # ---------- VERIFY (click / enter / scroll) ----------
            after_url = browser.current_url()
            after_hash = browser.screenshot_hash()

            url_changed = (after_url != before_url)
            visual_changed = (after_hash != before_hash)

            if not url_changed and not visual_changed:
                print("⚠️  Action caused no visible change — replanning")
                history.append({
                    "failed_action": decision,
                    "reason": "no_visible_change"
                })
                continue

            history.append(decision)

        print("❌ Max steps reached without finishing.")

    finally:
        browser.close()


if __name__ == "__main__":
    main()