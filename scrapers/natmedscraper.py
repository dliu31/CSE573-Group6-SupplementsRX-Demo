# natmed_selenium_scraper.py
import os, re, sys, json, time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, ElementClickInterceptedException, StaleElementReferenceException
)

# ---------- Config ----------
USERNAME = os.getenv("NATMED_EMAIL", "Enter Your email")
PASSWORD = os.getenv("NATMED_PASSWORD", "Enter Your Password")
START_URL = "https://naturalmedicines.therapeuticresearch.com/Home/ND"
OUT_DIR = Path("output")
DEBUG_DIR = OUT_DIR / "debug"
WAIT_SECS = 25
PAUSE = 0.9
UPPER, LOWER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"
# ----------------------------

def pause(s=PAUSE): time.sleep(s)
def log(m): print(m, flush=True)

def accept_cookies(driver, wait):
    try:
        btn = wait.until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler")))
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
        btn.click(); pause(0.25)
        log("✅ Cookies accepted.")
    except TimeoutException:
        pass

def robust_click(driver, wait, locator, retries=3):
    for i in range(retries):
        try:
            accept_cookies(driver, wait)
            el = wait.until(EC.presence_of_element_located(locator))
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
            pause(0.15)
            try:
                wait.until(EC.element_to_be_clickable(locator)).click()
                return
            except ElementClickInterceptedException:
                driver.execute_script("arguments[0].click();", el)
                return
        except Exception:
            if i == retries - 1: raise
            pause(0.4)

def login(driver, wait):
    driver.get(START_URL)
    accept_cookies(driver, wait)
    robust_click(driver, wait, (By.XPATH, "//span[normalize-space()='Login']"))
    wait.until(EC.presence_of_element_located((By.ID, "username"))).send_keys(USERNAME)
    robust_click(driver, wait, (By.ID, "kc-login"))
    wait.until(EC.presence_of_element_located((By.ID, "password"))).send_keys(PASSWORD)
    robust_click(driver, wait, (By.ID, "kc-login"))
    wait.until(EC.url_contains("naturalmedicines"))
    accept_cookies(driver, wait)
    print("✅ Logged in successfully!")

def search_and_open(driver, wait, query):
    box = wait.until(EC.presence_of_element_located((By.ID, "site-search-global")))
    box.clear(); box.send_keys(query); pause(0.2)
    try:
        robust_click(driver, wait, (By.XPATH, "//input[@id='site-search-global']/following::button[.//span[contains(@class,'fa-search')]][1]"))
    except Exception:
        box.send_keys(Keys.ENTER)
    wait.until(EC.presence_of_element_located((By.XPATH, "//h1[contains(.,'Search Results')]")))
    qlow = query.strip().lower()
    heading = (By.XPATH, f"//span[contains(@class,'heading__main')][translate(normalize-space(.),'{UPPER}','{LOWER}')='{qlow}']/ancestor::a[1]")
    try:
        robust_click(driver, wait, heading)
    except Exception:
        robust_click(driver, wait, (By.XPATH, f"//a[contains(translate(normalize-space(.),'{UPPER}','{LOWER}'),'{qlow}')]"))

def expand_all(driver, wait):
    try:
        robust_click(driver, wait, (By.XPATH, "//button[.//span[normalize-space()='Expand All'] or normalize-space()='Expand All']"))
        log("✅ Clicked 'Expand All'.")
        return
    except Exception:
        pass
    toggles = driver.find_elements(By.XPATH, "//button[contains(@class,'accordion-toggle') and (@aria-expanded='false' or contains(@class,'collapsed'))]")
    count = 0
    for t in toggles:
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", t)
            pause(0.1)
            t.click()
            count += 1
            pause(0.15)
        except (StaleElementReferenceException, Exception):
            continue
    if count:
        log(f"Expanded {count} panels.")

def _normalize(txt: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", (txt or "").strip())

def get_mechanism_text(driver, wait):
    """
    Extract 'Mechanism of Action' text with 3 strategies. Logs each attempt and returns normalized text.
    """
    accept_cookies(driver, wait)
    expand_all(driver, wait)

    # Strategy 1 — exact <h2>/<h3> then collect following siblings until next heading
    try:
        h = WebDriverWait(driver, 8).until(EC.presence_of_element_located(
            (By.XPATH, "//*[self::h2 or self::h3][contains(normalize-space(.), 'Mechanism of Action') or normalize-space(.)='Mechanism of Action' or contains(normalize-space(.), 'Mechanism')]")))
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", h)
        pause(0.2)
        js_following = """
        const h = arguments[0];
        const parts = [];
        let n = h.nextElementSibling;
        while (n && !/^H[23]$/.test(n.tagName)) {
          const t = (n.innerText || '').trim();
          if (t) parts.push(t);
          n = n.nextElementSibling;
        }
        return parts.join('\\n');
        """
        text1 = driver.execute_script(js_following, h) or ""
        text1 = _normalize(text1)
        if len(text1) >= 60:
            log(f"Mechanism text via heading-siblings ({len(text1)} chars).")
            return text1
        else:
            log(f" Heading-siblings text too short ({len(text1)} chars), trying container sweep…")
    except TimeoutException:
        log("No direct heading found, trying container sweep…")

    # Strategy 2 — container sweep near the heading (cards/sections)
    try:
        js_container = """
        const labels = ['Mechanism of Action','Mechanism'];
        function findHeading(){
          const hs = Array.from(document.querySelectorAll('h2,h3'));
          for (const h of hs){
            const t = (h.innerText||'').trim();
            if (labels.some(l => t===l || t.includes(l))) return h;
          }
          return null;
        }
        const h = findHeading();
        if (!h) return '';
        // Try nearest section/card container that includes the heading
        let cont = h.closest('section,div.card,div.panel,div.accordion,div');
        if (!cont) cont = h.parentElement;
        const text = (cont.innerText||'').trim();
        return text;
        """
        text2 = driver.execute_script(js_container) or ""
        # Remove the heading label itself if it’s at the start
        text2 = re.sub(r"^\s*Mechanism of Action\s*", "", text2, flags=re.I).strip()
        text2 = _normalize(text2)
        if len(text2) >= 60:
            log(f"✅ Mechanism text via container sweep ({len(text2)} chars).")
            return text2
        else:
            log(f"ℹ️ Container sweep too short ({len(text2)} chars), trying page sweep…")
    except Exception:
        pass

    # Strategy 3 — last-resort page-wide sweep
    try:
        js_page = """
        const labels = ['Mechanism of Action','Mechanism'];
        const nodes = Array.from(document.querySelectorAll('*'));
        // prefer elements that look like section headers
        const heads = nodes.filter(el => {
          const t = (el.textContent||'').trim();
          return t && labels.some(l => t===l || t.includes(l)) && /^(H2|H3|BUTTON)$/i.test(el.tagName);
        });
        function collectFrom(el){
          // if it’s a button with aria-controls/data-bs-target
          const a = el.getAttribute && el.getAttribute('aria-controls');
          const b = el.getAttribute && el.getAttribute('data-bs-target');
          if (a && document.getElementById(a)) return document.getElementById(a).innerText||'';
          if (b && b.startsWith('#') && document.querySelector(b)) return document.querySelector(b).innerText||'';
          // else take siblings until next heading/toggle
          let n = el.nextElementSibling, parts=[];
          while (n && !/^H[23]$/.test(n.tagName) && !(n.matches && n.matches('button.accordion-toggle'))){
            parts.push((n.innerText||'').trim());
            n = n.nextElementSibling;
          }
          return parts.filter(Boolean).join('\\n');
        }
        for (const h of heads){
          const txt = collectFrom(h).trim();
          if (txt) return txt;
        }
        return '';
        """
        text3 = driver.execute_script(js_page) or ""
        text3 = _normalize(text3)
        if len(text3) >= 60:
            log(f" Mechanism text via page sweep ({len(text3)} chars).")
            return text3
    except Exception:
        pass

    return ""

def dump_debug(driver, tag):
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    driver.save_screenshot(str(DEBUG_DIR / f"{tag}.png"))
    with open(DEBUG_DIR / f"{tag}.html", "w", encoding="utf-8") as f:
        f.write(driver.page_source)

def main():
    query = " ".join(sys.argv[1:]).strip() if len(sys.argv) > 1 else input("Supplement: ").strip()
    if not query:
        log(" No supplement provided."); return
    if USERNAME == "YOUR_EMAIL" or PASSWORD == "YOUR_PASSWORD":
        log("  Set NATMED_EMAIL and NATMED_PASSWORD env vars or edit the script."); return

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    driver = webdriver.Chrome()  # chromedriver must be on PATH
    driver.maximize_window()
    wait = WebDriverWait(driver, WAIT_SECS)

    try:
        login(driver, wait)
        search_and_open(driver, wait, query)
        text = get_mechanism_text(driver, wait)

        if not text:
            log(" Mechanism text empty — saving debug artifacts.")
            tag = f"{re.sub(r'\\W+','_', query.lower())}_mechanism_missing"
            dump_debug(driver, tag)

        data = {
            "query": query,
            "url": driver.current_url,
            "title": driver.title,
            "mechanism_of_action": text
        }

        out = OUT_DIR / (re.sub(r"\W+", "_", query.lower()) + "_mechanism.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  Saved → {out}")

    except Exception as e:
        print(" Error:", e)
    finally:
        pause(1.2)
        driver.quit()

if __name__ == "__main__":
    main()
