"""Haalt minoren van kiesopmaat.nl en slaat ze op in minors.json.

LET OP: de CSS-selectors hieronder zijn een eerste gok. Open kiesopmaat.nl in je browser,
rechtermuisklik > Inspecteren, en pas SELECTORS aan op de echte HTML.
Check ook de robots.txt / gebruiksvoorwaarden en scrape rustig (sleep).
"""
import json, time, requests
from bs4 import BeautifulSoup

BASE = "https://www.kiesopmaat.nl"
LIST_URL = f"{BASE}/minoren"  # TODO: controleer de echte lijst-URL (evt. met filter op Hogeschool Utrecht)
MAX_MINOREN = 40              # subset voor de PoC

SELECTORS = {
    "links": "a[href*='/minor']",      # links naar detailpagina's
    "titel": "h1",
    "beschrijving": "main p",
    "meta": "dl, .meta, .kenmerken",   # ECTS, periode, taal, niveau, etc.
}

HEADERS = {"User-Agent": "Mozilla/5.0 (studieproject Hogeschool Utrecht)"}

def soup(url):
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")

def main():
    links = []
    for a in soup(LIST_URL).select(SELECTORS["links"]):
        href = a.get("href", "")
        url = href if href.startswith("http") else BASE + href
        if url not in links:
            links.append(url)
    links = links[:MAX_MINOREN]

    minors = []
    for i, url in enumerate(links, 1):
        try:
            s = soup(url)
            titel = s.select_one(SELECTORS["titel"])
            minors.append({
                "id": i,
                "titel": titel.get_text(strip=True) if titel else "",
                "beschrijving": " ".join(p.get_text(" ", strip=True)
                                         for p in s.select(SELECTORS["beschrijving"]))[:600],
                "kenmerken": " | ".join(m.get_text(" ", strip=True)
                                        for m in s.select(SELECTORS["meta"]))[:300],
                "url": url,
            })
            print(f"[{i}/{len(links)}] {minors[-1]['titel']}")
        except Exception as e:
            print("Fout bij", url, e)
        time.sleep(1)

    with open("minors.json", "w", encoding="utf-8") as f:
        json.dump(minors, f, ensure_ascii=False, indent=2)
    print(f"Klaar: {len(minors)} minoren opgeslagen in minors.json")

if __name__ == "__main__":
    main()
