from __future__ import annotations

import html
import json
import re
import shutil
import sys
import time
import uuid
from dataclasses import dataclass
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

try:
    from selenium import webdriver
    from selenium.common.exceptions import TimeoutException, WebDriverException
    from selenium.webdriver.chrome.options import Options
except ImportError:
    webdriver = None
    TimeoutException = Exception
    WebDriverException = Exception
    Options = None


APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
HOST = "127.0.0.1"
PORT = 8765

# Session management
class DriverSession:
    def __init__(self):
        self.driver: Optional[Any] = None
        self.created_at = time.time()
    
    def create_driver(self):
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1440,1100")
        
        chrome_binary = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        if chrome_binary.exists():
            options.binary_location = str(chrome_binary)
        elif shutil.which("chromium"):
            options.binary_location = shutil.which("chromium")
        elif shutil.which("google-chrome"):
            options.binary_location = shutil.which("google-chrome")
        
        self.driver = webdriver.Chrome(options=options)
        self.driver.set_page_load_timeout(30)
    
    def navigate(self, url: str):
        if self.driver is None:
            raise RuntimeError("Session not initialized")
        self.driver.get(url)
        time.sleep(1.25)
    
    def fill_field(self, selector: str, value: str):
        if self.driver is None:
            raise RuntimeError("Session not initialized")
        try:
            elem = self.driver.find_element("css selector", selector)
            elem.clear()
            elem.send_keys(value)
        except Exception as e:
            raise RuntimeError(f"Could not fill field '{selector}': {str(e)}")
    
    def click_element(self, selector: str):
        if self.driver is None:
            raise RuntimeError("Session not initialized")
        try:
            elem = self.driver.find_element("css selector", selector)
            elem.click()
            time.sleep(1.5)
        except Exception as e:
            raise RuntimeError(f"Could not click element '{selector}': {str(e)}")
    
    def get_page_info(self) -> dict[str, Any]:
        if self.driver is None:
            raise RuntimeError("Session not initialized")
        return {
            "title": self.driver.title,
            "url": self.driver.current_url,
        }
    
    def scan_elements(self) -> list[dict[str, Any]]:
        if self.driver is None:
            raise RuntimeError("Session not initialized")
        return self.driver.execute_script(SCAN_SCRIPT)
    
    def close(self):
        if self.driver is not None:
            self.driver.quit()
            self.driver = None

# Store active sessions: session_id -> DriverSession
SESSIONS: dict[str, DriverSession] = {}




SCAN_SCRIPT = """
const selectors = [
  'a', 'button', 'input', 'select', 'textarea',
  '[role]', '[aria-label]', '[aria-labelledby]', '[placeholder]',
  '[data-testid]', '[data-test]', '[data-qa]', '[data-cy]',
  '[id]', '[name]', 'summary', '[contenteditable="true"]'
];

function visible(el) {
  const style = window.getComputedStyle(el);
  const rect = el.getBoundingClientRect();
  return style.display !== 'none'
    && style.visibility !== 'hidden'
    && Number(style.opacity) !== 0
    && rect.width > 0
    && rect.height > 0;
}

function directLabel(el) {
  if (el.id) {
    const label = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
    if (label) return label.innerText.trim();
  }
  const parentLabel = el.closest('label');
  if (parentLabel) return parentLabel.innerText.trim();
  return '';
}

function textFor(el) {
  const pieces = [
    el.innerText,
    el.value,
    el.getAttribute('aria-label'),
    el.getAttribute('placeholder'),
    directLabel(el),
    el.getAttribute('title'),
    el.getAttribute('alt')
  ];
  return pieces
    .filter(Boolean)
    .map((value) => String(value).replace(/\\s+/g, ' ').trim())
    .find(Boolean) || '';
}

function uniqueCssPath(el) {
  const parts = [];
  let current = el;
  while (current && current.nodeType === Node.ELEMENT_NODE && current !== document.body) {
    let part = current.tagName.toLowerCase();
    if (current.id) {
      part += `#${CSS.escape(current.id)}`;
      parts.unshift(part);
      break;
    }
    const siblings = Array.from(current.parentElement ? current.parentElement.children : []);
    const sameTag = siblings.filter((sibling) => sibling.tagName === current.tagName);
    if (sameTag.length > 1) {
      part += `:nth-of-type(${sameTag.indexOf(current) + 1})`;
    }
    parts.unshift(part);
    current = current.parentElement;
  }
  return parts.join(' > ');
}

function xpath(el) {
  if (el.id) return `//*[@id="${el.id.replace(/"/g, '\\\\"')}"]`;
  const parts = [];
  let current = el;
  while (current && current.nodeType === Node.ELEMENT_NODE) {
    let index = 1;
    let sibling = current.previousElementSibling;
    while (sibling) {
      if (sibling.tagName === current.tagName) index += 1;
      sibling = sibling.previousElementSibling;
    }
    parts.unshift(`${current.tagName.toLowerCase()}[${index}]`);
    current = current.parentElement;
  }
  return '/' + parts.join('/');
}

const elements = Array.from(document.querySelectorAll(selectors.join(',')))
  .filter((el) => visible(el))
  .slice(0, 500);

return elements.map((el, index) => {
  const attrs = {};
  for (const attr of [
    'id', 'name', 'class', 'type', 'href', 'role', 'aria-label',
    'aria-labelledby', 'placeholder', 'title', 'alt',
    'data-testid', 'data-test', 'data-qa', 'data-cy'
  ]) {
    const value = el.getAttribute(attr);
    if (value) attrs[attr] = value;
  }
  const rect = el.getBoundingClientRect();
  return {
    index,
    tag: el.tagName.toLowerCase(),
    text: textFor(el).slice(0, 120),
    label: directLabel(el).replace(/\\s+/g, ' ').trim().slice(0, 120),
    attrs,
    cssPath: uniqueCssPath(el),
    xpath: xpath(el),
    x: Math.round(rect.x),
    y: Math.round(rect.y)
  };
});
"""


@dataclass
class Locator:
    by: str
    value: str
    confidence: int
    reason: str


def clean_text(value: Any, limit: int = 120) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()[:limit]


def css_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def xpath_string(value: str) -> str:
    if '"' not in value:
        return f'"{value}"'
    if "'" not in value:
        return f"'{value}'"
    parts = value.split('"')
    return "concat(" + ', "\\"", '.join(f'"{part}"' for part in parts) + ")"


def java_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def looks_generated(value: str) -> bool:
    value = value.strip()
    generated_patterns = [
        r"^[a-f0-9]{8,}$",
        r"^ember\d+$",
        r"^react-select-\d+",
        r"^mui-\d+",
        r"^\d+$",
        r".*__[a-z0-9]{5,}$",
    ]
    return any(re.match(pattern, value, re.I) for pattern in generated_patterns)


def stable_attr_candidates(attrs: dict[str, str]) -> list[Locator]:
    locators: list[Locator] = []
    for attr in ("data-testid", "data-test", "data-qa", "data-cy"):
        value = attrs.get(attr)
        if value:
            locators.append(
                Locator(
                    "By.cssSelector",
                    f"[{attr}={css_string(value)}]",
                    96,
                    f"Stable test attribute `{attr}`.",
                )
            )
    return locators


def build_locators(item: dict[str, Any]) -> list[Locator]:
    attrs = {str(k): clean_text(v, 240) for k, v in item.get("attrs", {}).items()}
    tag = clean_text(item.get("tag"))
    text = clean_text(item.get("text"))
    label = clean_text(item.get("label"))
    locators: list[Locator] = []

    element_id = attrs.get("id")
    if element_id:
        confidence = 95 if not looks_generated(element_id) else 68
        reason = "Unique-looking id." if confidence >= 90 else "Id exists, but it may be generated."
        locators.append(Locator("By.id", element_id, confidence, reason))

    name = attrs.get("name")
    if name:
        locators.append(Locator("By.name", name, 90, "Name attribute is usually stable for forms."))

    locators.extend(stable_attr_candidates(attrs))

    aria = attrs.get("aria-label")
    if aria:
        locators.append(
            Locator(
                "By.cssSelector",
                f'{tag}[aria-label={css_string(aria)}]',
                86,
                "Accessible label is descriptive and readable.",
            )
        )

    placeholder = attrs.get("placeholder")
    if placeholder and tag in {"input", "textarea"}:
        locators.append(
            Locator(
                "By.cssSelector",
                f'{tag}[placeholder={css_string(placeholder)}]',
                82,
                "Placeholder identifies the field.",
            )
        )

    input_type = attrs.get("type")
    if input_type and tag == "input":
        selector = f'input[type={css_string(input_type)}]'
        if name:
            selector += f'[name={css_string(name)}]'
        locators.append(Locator("By.cssSelector", selector, 78, "Input type plus stable attribute fallback."))

    href = attrs.get("href")
    if tag == "a" and text:
        locators.append(Locator("By.linkText", text, 80, "Readable link text."))
        if href:
            locators.append(Locator("By.cssSelector", f'a[href={css_string(href)}]', 76, "Link href fallback."))

    if text and tag in {"button", "summary"}:
        locators.append(
            Locator(
                "By.xpath",
                f"//{tag}[normalize-space(.)={xpath_string(text)}]",
                74,
                "Visible text fallback for clickable element.",
            )
        )

    classes = attrs.get("class", "")
    class_names = [part for part in classes.split() if part and not looks_generated(part)]
    if class_names:
        selector = tag + "".join(f".{re.sub(r'([^a-zA-Z0-9_-])', r'\\\\\\1', part)}" for part in class_names[:2])
        locators.append(Locator("By.cssSelector", selector, 58, "Class-based fallback; verify it is stable."))

    css_path = clean_text(item.get("cssPath"), 260)
    if css_path:
        locators.append(Locator("By.cssSelector", css_path, 44, "DOM path fallback; can break when layout changes."))

    xpath = clean_text(item.get("xpath"), 260)
    if xpath:
        locators.append(Locator("By.xpath", xpath, 40, "Absolute XPath fallback; least stable."))

    unique: list[Locator] = []
    seen: set[tuple[str, str]] = set()
    for locator in sorted(locators, key=lambda loc: loc.confidence, reverse=True):
        key = (locator.by, locator.value)
        if key not in seen:
            seen.add(key)
            unique.append(locator)
    return unique


def classify(item: dict[str, Any]) -> str:
    tag = clean_text(item.get("tag"))
    attrs = item.get("attrs", {})
    role = clean_text(attrs.get("role"))
    input_type = clean_text(attrs.get("type"))
    if role:
        return role
    if tag == "input":
        return f"input:{input_type or 'text'}"
    return tag


def scan_url(url: str) -> dict[str, Any]:
    if webdriver is None or Options is None:
        raise RuntimeError("Selenium is not installed. Run `python -m pip install -r requirements.txt`.")

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Enter a full URL starting with http:// or https://.")

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1440,1100")

    chrome_binary = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    if chrome_binary.exists():
        options.binary_location = str(chrome_binary)
    elif shutil.which("chromium"):
        options.binary_location = shutil.which("chromium")
    elif shutil.which("google-chrome"):
        options.binary_location = shutil.which("google-chrome")

    driver = None
    started_at = time.time()
    try:
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(30)
        driver.get(url)
        time.sleep(1.25)
        raw_items = driver.execute_script(SCAN_SCRIPT)
        title = driver.title
        current_url = driver.current_url
    except TimeoutException:
        raise RuntimeError("The page took too long to load. Try again or use a lighter page.")
    except WebDriverException as exc:
        raise RuntimeError(f"Selenium could not scan the page: {exc.msg}")
    finally:
        if driver is not None:
            driver.quit()

    rows = []
    for item in raw_items:
        locators = build_locators(item)
        if not locators:
            continue
        best = locators[0]
        visible_text = clean_text(item.get("text")) or clean_text(item.get("label"))
        rows.append(
            {
                "element": classify(item),
                "tag": clean_text(item.get("tag")),
                "text": visible_text,
                "bestBy": best.by,
                "bestValue": best.value,
                "confidence": best.confidence,
                "reason": best.reason,
                "java": f'driver.findElement({best.by}("{java_string(best.value)}"));',
                "alternatives": [
                    {
                        "by": locator.by,
                        "value": locator.value,
                        "confidence": locator.confidence,
                        "reason": locator.reason,
                        "java": f'driver.findElement({locator.by}("{java_string(locator.value)}"));',
                    }
                    for locator in locators[1:4]
                ],
            }
        )

    rows.sort(key=lambda row: row["confidence"], reverse=True)
    return {
        "url": current_url,
        "title": title,
        "durationMs": round((time.time() - started_at) * 1000),
        "count": len(rows),
        "rows": rows,
    }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def do_POST(self) -> None:
        if self.path == "/api/scan":
            self._handle_scan()
        elif self.path == "/api/session/start":
            self._handle_session_start()
        elif self.path == "/api/session/navigate":
            self._handle_session_navigate()
        elif self.path == "/api/session/fill":
            self._handle_session_fill()
        elif self.path == "/api/session/click":
            self._handle_session_click()
        elif self.path == "/api/session/scan":
            self._handle_session_scan()
        elif self.path == "/api/session/info":
            self._handle_session_info()
        elif self.path == "/api/session/end":
            self._handle_session_end()
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
    
    def _get_json(self) -> dict[str, Any]:
        length = int(self.headers.get("content-length", "0"))
        return json.loads(self.rfile.read(length) or b"{}")
    
    def _handle_scan(self) -> None:
        try:
            payload = self._get_json()
            url = clean_text(payload.get("url"), 2048)
            result = scan_url(url)
            self.send_json(HTTPStatus.OK, result)
        except Exception as exc:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": html.escape(str(exc))})
    
    def _handle_session_start(self) -> None:
        try:
            if webdriver is None:
                raise RuntimeError("Selenium is not installed.")
            session_id = str(uuid.uuid4())
            session = DriverSession()
            session.create_driver()
            SESSIONS[session_id] = session
            self.send_json(HTTPStatus.OK, {"session_id": session_id, "status": "started"})
        except Exception as exc:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": html.escape(str(exc))})
    
    def _handle_session_navigate(self) -> None:
        try:
            payload = self._get_json()
            session_id = payload.get("session_id")
            session = SESSIONS.get(session_id)
            if not session:
                return self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid session ID"})
            
            url = clean_text(payload.get("url"), 2048)
            session.navigate(url)
            info = session.get_page_info()
            self.send_json(HTTPStatus.OK, {"status": "navigated", **info})
        except Exception as exc:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": html.escape(str(exc))})
    
    def _handle_session_fill(self) -> None:
        try:
            payload = self._get_json()
            session_id = payload.get("session_id")
            session = SESSIONS.get(session_id)
            if not session:
                return self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid session ID"})
            
            selector = payload.get("selector")
            value = payload.get("value")
            session.fill_field(selector, value)
            self.send_json(HTTPStatus.OK, {"status": "field_filled"})
        except Exception as exc:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": html.escape(str(exc))})
    
    def _handle_session_click(self) -> None:
        try:
            payload = self._get_json()
            session_id = payload.get("session_id")
            session = SESSIONS.get(session_id)
            if not session:
                return self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid session ID"})
            
            selector = payload.get("selector")
            session.click_element(selector)
            info = session.get_page_info()
            self.send_json(HTTPStatus.OK, {"status": "clicked", **info})
        except Exception as exc:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": html.escape(str(exc))})
    
    def _handle_session_scan(self) -> None:
        try:
            payload = self._get_json()
            session_id = payload.get("session_id")
            session = SESSIONS.get(session_id)
            if not session:
                return self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid session ID"})
            
            raw_items = session.scan_elements()
            info = session.get_page_info()
            
            rows = []
            for item in raw_items:
                locators = build_locators(item)
                if not locators:
                    continue
                best = locators[0]
                visible_text = clean_text(item.get("text")) or clean_text(item.get("label"))
                rows.append({
                    "element": classify(item),
                    "tag": clean_text(item.get("tag")),
                    "text": visible_text,
                    "bestBy": best.by,
                    "bestValue": best.value,
                    "confidence": best.confidence,
                    "reason": best.reason,
                    "java": f'driver.findElement({best.by}("{java_string(best.value)}"));',
                    "alternatives": [
                        {
                            "by": locator.by,
                            "value": locator.value,
                            "confidence": locator.confidence,
                            "reason": locator.reason,
                            "java": f'driver.findElement({locator.by}("{java_string(locator.value)}"));',
                        }
                        for locator in locators[1:4]
                    ],
                })
            
            rows.sort(key=lambda row: row["confidence"], reverse=True)
            result = {
                "url": info["url"],
                "title": info["title"],
                "count": len(rows),
                "rows": rows,
            }
            self.send_json(HTTPStatus.OK, result)
        except Exception as exc:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": html.escape(str(exc))})
    
    def _handle_session_info(self) -> None:
        try:
            payload = self._get_json()
            session_id = payload.get("session_id")
            session = SESSIONS.get(session_id)
            if not session:
                return self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid session ID"})
            
            info = session.get_page_info()
            self.send_json(HTTPStatus.OK, info)
        except Exception as exc:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": html.escape(str(exc))})
    
    def _handle_session_end(self) -> None:
        try:
            payload = self._get_json()
            session_id = payload.get("session_id")
            session = SESSIONS.get(session_id)
            if session:
                session.close()
                del SESSIONS[session_id]
            self.send_json(HTTPStatus.OK, {"status": "ended"})
        except Exception as exc:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": html.escape(str(exc))})

    def send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write("[locator-scanner] " + format % args + "\n")


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Selenium Locator Scanner running at http://{HOST}:{PORT}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")


if __name__ == "__main__":
    main()
