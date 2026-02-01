import argparse
import json
from browser import Browser
from vision import decide_next_action

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
                continue  # typing is fire-and-forget; no need to verify

            elif action == "enter":
                before_url = browser.current_url()
                before_hash = browser.screenshot_hash()

                browser.press_enter()

            elif action == "click":
                before_url = browser.current_url()
                before_hash = browser.screenshot_hash()

                browser.click_at(decision["x"], decision["y"])

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

            # ---------- VERIFY (for click / enter / scroll) ----------
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