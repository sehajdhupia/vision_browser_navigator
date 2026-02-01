import base64
import time
import hashlib

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager


# ---------------------------------------------------------------------
# How execute_script works:
#   Selenium wraps whatever string you pass into:
#       function anonymous(/* ...args */) { <YOUR CODE HERE> }
#   and then calls it, passing any extra Python arguments as the
#   `arguments` object.
#
#   That means:
#     - A bare `return x;` sends x back to Python.  Good.
#     - An IIFE like `(function(){ return x; })()` returns x from the
#       *inner* function.  The outer anonymous function never sees it,
#       so Selenium gets `undefined` (None in Python).  Bad.
#     - `arguments[0]` refers to Selenium's first extra arg -- but only
#       at the top level.  Inside an IIFE `arguments` is the IIFE's own
#       (empty) argument list.
#
#   Both JS blocks below are written as plain top-level statements for
#   exactly these reasons.
# ---------------------------------------------------------------------

_EXTRACT_CLICKABLES_JS = r"""
    const results = [];
    const seen = new Set();

    const candidates = document.querySelectorAll(
        "a, button, [role='button'], [role='link'], "
        + "input[type='submit'], input[type='button'], "
        + "select, textarea, input:not([type='hidden']), "
        + "[tabindex='0'], summary"
    );

    candidates.forEach(function(el) {
        if (seen.has(el)) return;
        seen.add(el);

        var rect = el.getBoundingClientRect();

        if (rect.width < 1 || rect.height < 1) return;
        if (rect.top > window.innerHeight || rect.bottom < 0) return;
        if (rect.left > window.innerWidth || rect.right < 0) return;

        var text = (el.innerText || el.textContent || "").replace(/\s+/g, " ").trim();
        if (text.length === 0 && el.tagName !== "INPUT") return;

        results.push({
            index: results.length,
            tag: el.tagName.toLowerCase(),
            text: text.substring(0, 120),
            href: el.getAttribute("href") || null,
            rect: {
                x: Math.round(rect.x),
                y: Math.round(rect.y),
                w: Math.round(rect.width),
                h: Math.round(rect.height)
            }
        });
    });

    // Mirror the same filtering in the clickable map so indices match.
    window.__clickable_map__ = [];
    var idx = 0;
    candidates.forEach(function(el) {
        if (!seen.has(el)) return;
        var rect = el.getBoundingClientRect();
        if (rect.width < 1 || rect.height < 1) return;
        if (rect.top > window.innerHeight || rect.bottom < 0) return;
        if (rect.left > window.innerWidth || rect.right < 0) return;
        var text = (el.innerText || el.textContent || "").replace(/\s+/g, " ").trim();
        if (text.length === 0 && el.tagName !== "INPUT") return;
        window.__clickable_map__[idx] = el;
        idx++;
    });

    return results;
"""

# arguments[0] here is the index Selenium passes as the second arg to
# execute_script().  It works because this code runs at the top level
# of the wrapper function, not inside an IIFE.
_CLICK_BY_INDEX_JS = """
    var idx = arguments[0];
    var el = window.__clickable_map__ && window.__clickable_map__[idx];
    if (!el) {
        return { ok: false, reason: "Element index " + idx + " not found in clickable map" };
    }

    el.scrollIntoView({ block: "center", inline: "center" });

    return {
        ok: true,
        tag: el.tagName.toLowerCase(),
        text: (el.innerText || "").substring(0, 80),
        href: el.getAttribute("href") || null
    };
"""


class Browser:
    def __init__(self, url):
        options = webdriver.ChromeOptions()
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-extensions")
        options.add_argument("--start-maximized")

        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )

        self.driver.get(url)
        time.sleep(2)

    # ---------- STATE ----------

    def current_url(self):
        return self.driver.current_url

    def screenshot_hash(self):
        png = self.driver.get_screenshot_as_png()
        return hashlib.md5(png).hexdigest()

    # ---------- PERCEPTION ----------

    def screenshot_base64(self):
        png = self.driver.get_screenshot_as_png()
        return base64.b64encode(png).decode("utf-8")

    def get_clickable_elements(self):
        """
        Extract all visible, interactive elements from the current page.
        Returns a list of dicts with: index, tag, text, href, rect.
        Also populates window.__clickable_map__ so we can click by index.
        """
        result = self.driver.execute_script(_EXTRACT_CLICKABLES_JS)
        # Safety: if Chrome somehow returns None, hand back an empty list
        # so callers don't have to null-check.
        return result if result is not None else []

    # ---------- ACTIONS ----------

    def type_text(self, text):
        self.driver.switch_to.active_element.send_keys(text)
        time.sleep(0.4)

    def press_enter(self):
        self.driver.switch_to.active_element.send_keys(Keys.ENTER)
        time.sleep(1.2)

    def click_element_by_index(self, index):
        """
        Click a specific element from the list returned by get_clickable_elements().
        """
        # Step 1: scroll into view and validate the element still exists
        info = self.driver.execute_script(_CLICK_BY_INDEX_JS, index)
        if not info.get("ok"):
            print(f"  click_element_by_index failed: {info.get('reason')}")
            return False

        print(f"   -> Clicking [{index}] <{info['tag']}> \"{info['text']}\" href={info['href']}")

        # Step 2: get the actual DOM element reference
        element = self.driver.execute_script(
            "return window.__clickable_map__[arguments[0]];",
            index
        )

        # Step 3: ActionChains click -- real browser event
        ActionChains(self.driver).move_to_element(element).click().perform()
        time.sleep(1.2)
        return True

    def click_at(self, x, y):
        """
        Fallback: click at raw viewport coordinates.
        Uses ActionChains (not dispatchEvent) so React sees the event.
        """
        element = self.driver.execute_script(
            """
            var el = document.elementFromPoint(arguments[0], arguments[1]);
            if (el) el.scrollIntoView({ block: 'center', inline: 'center' });
            return el;
            """,
            x, y
        )
        if element is None:
            print(f"  No element at ({x}, {y})")
            return

        # Walk up to nearest clickable ancestor
        element = self.driver.execute_script(
            """
            var el = arguments[0];
            var tags = ['A','BUTTON','INPUT','SELECT','TEXTAREA','LABEL','SUMMARY'];
            while (el && el !== document.body) {
                if (tags.indexOf(el.tagName) !== -1 || el.getAttribute('role') === 'button') return el;
                el = el.parentElement;
            }
            return arguments[0];
            """,
            element
        )

        ActionChains(self.driver).move_to_element(element).click().perform()
        time.sleep(1.0)

    def scroll_down(self):
        self.driver.execute_script("window.scrollBy(0, 900);")
        time.sleep(0.7)

    def scroll_up(self):
        self.driver.execute_script("window.scrollBy(0, -900);")
        time.sleep(0.7)

    def scroll_to_top(self):
        self.driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.7)

    # ---------- CLEANUP ----------

    def close(self):
        self.driver.quit()