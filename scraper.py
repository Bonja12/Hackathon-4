"""Haalt ALLE modules/minoren van kiesopmaat.nl op met een echte browser (Playwright)
en slaat ze op in minors.json.

Eenmalig installeren:
    pip install playwright beautifulsoup4
    python -m playwright install chromium

Gebruik:
    python scraper.py                      # alles (~150 pagina's, een paar minuten)
    python scraper.py "<URL met filter>"   # optioneel: alleen een gefilterd aanbod
"""
import json, re, sys, time
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, urljoin
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

BASE = "https://www.kiesopmaat.nl"
START_URL = sys.argv[1] if len(sys.argv) > 1 else f"{BASE}/modules/"
MAX_PAGES = 300          # veiligheidslimiet
ONLY_MINOR = False       # True = alleen titels die met "Minor" beginnen
HEADLESS = True          # zet op False als de site headless blokkeert

def page_url(url, n):
    if n == 1:
        return url
    p = urlparse(url)
    q = parse_qs(p.query)
    q["page"] = [str(n)]
    return urlunparse(p._replace(query=urlencode(q, doseq=True)))

def parse(html):
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for li in soup.select("li"):
        a = li.find("a", href=re.compile(r"/modules/"))
        if not a or "page=" in a["href"]:
            continue
        text = li.get_text("\n", strip=True)
        ec = re.search(r"([\d.,]+)\s*EC", text)
        if not ec:
            continue
        titel = a.get_text(strip=True)
        lines = [l for l in text.split("\n") if l and l != titel and not re.fullmatch(r"[\d.,]+\s*EC", l)]
        periodes = [l for l in lines if " t/m " in l]
        beschrijving = max((l for l in lines if l not in periodes), key=len, default="")
        items.append({"titel": titel, "ec": ec.group(1), "beschrijving": beschrijving,
                      "periodes": periodes, "url": urljoin(BASE, a["href"])})
    return items

def main():
    minors, seen = [], set()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=HEADLESS)
        page = browser.new_context(locale="nl-NL").new_page()
        for n in range(1, MAX_PAGES + 1):
            url = page_url(START_URL, n)
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            try:  # de site toont eerst een "Verifying your browser"-check (Anubis); wacht tot die klaar is
                page.wait_for_function("!document.title.includes('Verifying')", timeout=60000)
                page.wait_for_load_state("domcontentloaded")
            except Exception:
                print("Browsercheck is niet geslaagd. Zet HEADLESS = False en probeer opnieuw.")
                break
            page.wait_for_timeout(1000)
            items = parse(page.content())
            new = [i for i in items if i["url"] not in seen]
            print(f"pagina {n}: {len(items)} modules ({len(new)} nieuw)")
            if not new:
                if n == 1:
                    print("Titel:", page.title(), "| controleer of de pagina echt geladen is")
                break
            for i in new:
                seen.add(i["url"])
                if not ONLY_MINOR or i["titel"].lower().startswith("minor"):
                    i["id"] = len(minors) + 1
                    minors.append(i)
            time.sleep(2)  # rustig aan: we belasten de site zo weinig mogelijk
        browser.close()

    with open("minors.json", "w", encoding="utf-8") as f:
        json.dump(minors, f, ensure_ascii=False, indent=2)
    print(f"Klaar: {len(minors)} modules opgeslagen in minors.json")

if __name__ == "__main__":
    main()