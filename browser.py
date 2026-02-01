import base64
import time
import hashlib

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common import action_chains
from webdriver_manager.chrome import ChromeDriverManager


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

    # ---------- ACTIONS ----------

    def type_text(self, text):
        self.driver.switch_to.active_element.send_keys(text)
        time.sleep(0.4)

    def press_enter(self):
        self.driver.switch_to.active_element.send_keys(Keys.ENTER)
        time.sleep(1.2)

    def click_at(self, x, y):
        """
        Click at absolute viewport coordinates using Selenium's ActionChains.

        Why not JS dispatchEvent?
        GitHub (and most modern SPAs) use React's synthetic event system.
        React attaches a single delegated listener on the root container and
        only fires its handlers when the browser itself dispatches the event
        through its native pipeline. Manually constructed MouseEvents via
        el.dispatchEvent() bypass that pipeline entirely, so React never sees
        them — the click silently does nothing.

        ActionChains.move_to_element_with_offset + click() tells the Chrome
        DevTools Protocol to move the actual mouse pointer and fire a real
        click through the browser engine, which is the only way to reliably
        trigger React (and similar framework) event handlers.

        Two extra safety measures:
        1. We first scroll the element into view so that the coordinates are
           valid (vision models report coordinates relative to the visible
           viewport; if the page scrolled between the screenshot and the click
           the target may be off-screen).
        2. If the element at (x, y) is not itself interactive (e.g. a <span>
           inside an <a>), we walk up the DOM to find the nearest clickable
           ancestor before clicking.
        """
        # Step 1: find the element at the given viewport coordinates and
        # scroll it into view so it stays at roughly the same spot.
        element = self.driver.execute_script(
            """
            const el = document.elementFromPoint(arguments[0], arguments[1]);
            if (el) {
                el.scrollIntoView({ block: 'center', inline: 'center' });
            }
            return el;
            """,
            x, y
        )

        if element is None:
            print(f"⚠️  No element found at ({x}, {y})")
            return

        # Step 2: walk up to the nearest clickable ancestor if the target
        # itself is not interactive (common pattern: <a><span>text</span></a>).
        element = self.driver.execute_script(
            """
            let el = arguments[0];
            const clickableTags = new Set(['A', 'BUTTON', 'INPUT', 'SELECT',
                                           'TEXTAREA', 'LABEL', 'SUMMARY']);
            while (el && el !== document.body) {
                if (clickableTags.has(el.tagName)) return el;
                if (el.getAttribute('role') === 'button') return el;
                if (el.onclick) return el;
                el = el.parentElement;
            }
            // If no clickable ancestor found, return the original element —
            // it might still respond to the click (e.g. a div with a listener).
            return arguments[0];
            """,
            element
        )

        # Step 3: use ActionChains to perform a real browser-level click.
        # move_to_element first ensures the pointer is over the element;
        # click() then fires mousedown → mouseup → click through the engine.
        actions = action_chains.ActionChains(self.driver)
        actions.move_to_element(element).click().perform()

        time.sleep(1.0)  # give the page a moment to react / navigate

    def scroll_down(self):
        self.driver.execute_script("window.scrollBy(0, 900);")
        time.sleep(0.7)

    # ---------- CLEANUP ----------

    def close(self):
        self.driver.quit()