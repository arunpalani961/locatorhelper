# Selenium Locator Scanner

A small local web app that opens a target URL with Selenium, inspects useful page elements, and recommends stable Selenium locators in a table.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python server.py
```

Then open:

```text
http://127.0.0.1:8765
```

## Notes

- Requires Google Chrome or Chromium. Selenium Manager will try to find or install the matching driver automatically.
- Scans public pages best. Login-only pages, CAPTCHA, bot protection, and very strict CSP/browser checks can limit results.
- Locator ranking favors stable Selenium locators first: `By.id`, `By.name`, stable CSS attributes, link text, then XPath fallback.
