"""Spraak-minoradviseur volgens het Prompt Charter: retrieval (embeddings) + Groq-LLM.

Starten:
    $env:GROQ_API_KEY = "gsk_..."          (of zet GROQ_API_KEY in .env)
    python -m uvicorn server:app --reload
Vereist minors.json (scraper.py). Optioneel: $env:GROQ_MODEL = "openai/gpt-oss-120b"
"""
import json, os, random, re
from pathlib import Path
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

try:
    from dotenv import load_dotenv; load_dotenv()
except ImportError:
    pass

ROOT = Path(__file__).parent
app = FastAPI()
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODELS = [m for m in (os.getenv("GROQ_MODEL"), "openai/gpt-oss-120b", "openai/gpt-oss-20b") if m]
TRIGGER = "Start het gesprek."
TOP_K = 6          # aantal gevonden minoren dat als CONTEXT naar de LLM gaat
OPENVRAGEN = [
    "Waar word je enthousiast van, in je studie of daarbuiten?",
    "Welke opleiding doe je, en op welk niveau?",
    "Wil je je verdiepen in je eigen studie, of juist iets compleet nieuws ontdekken?",
    "Is er iets wat je absoluut niet wilt in een minor?",
]
VANGNET = "Hiervoor kun je het beste contact opnemen met je eigen studieadviseur."

# ---------- retrieval ----------
minors = json.loads((ROOT / "minors.json").read_text(encoding="utf-8")) if (ROOT / "minors.json").exists() else []
docs = [f"{m['titel']}. {m.get('beschrijving', '')}" for m in minors]
try:
    from sentence_transformers import SentenceTransformer
    _model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    _emb = _model.encode(docs, normalize_embeddings=True) if docs else None
    def scores(text): return _emb @ _model.encode([text], normalize_embeddings=True)[0]
    DREMPEL, METHODE = 0.25, "embeddings"      # drempel lage matchscore: bijstellen tijdens testen
except Exception:
    from sklearn.feature_extraction.text import TfidfVectorizer
    _vec = TfidfVectorizer(sublinear_tf=True, ngram_range=(1, 2))
    _mat = _vec.fit_transform(docs) if docs else None
    def scores(text): return (_mat @ _vec.transform([text]).T).toarray().ravel()
    DREMPEL, METHODE = 0.05, "tfidf"
print(f"[matching] {METHODE}, {len(minors)} minoren, modellen: {MODELS}")

def zoek(student_tekst):
    sc = scores(student_tekst)
    idx = sc.argsort()[::-1][:TOP_K]
    return [(minors[i], float(sc[i])) for i in idx]

# ---------- prompt (Prompt Charter, par. 10) ----------
PROMPT = """Je bent een Nederlandstalige AI-studieadviseur die studenten helpt een minor te kiezen. Je bent een AI en geen mens.

TRANSPARANTIE
- Je allereerste bericht begint met: "Hoi, ik ben een AI-assistent die je helpt een minor te vinden. Ik ben geen mens en je kunt altijd een studieadviseur raadplegen." Stel daarna precies de openingsvraag die onder STAND staat.

GEDRAG (je antwoord wordt uitgesproken)
- Spreek Nederlands, warm en rustig, in korte zinnen. Maximaal 3 korte zinnen per beurt. Geen opsommingstekens, nummers, markdown of emoji.
- Stel per beurt precies één vraag, nooit twee vragen of "en"-vragen. Vraag niets wat de student al heeft verteld.
- Vragen die je stelt, in willekeurige volgorde: waar word je enthousiast van (in of buiten de studie); welke opleiding en welk niveau; verdiepen in de eigen studie of iets compleet nieuws; is er iets wat je absoluut niet wilt; locatie of reisafstand.
- Loopt de student vast, gebruik dan: "Welk vak of project gaf je het afgelopen jaar de meeste energie?"
- Vraag nooit naar persoonsgegevens zoals naam, e-mail of studentnummer.
- Zodra de student minstens 4 antwoorden heeft gegeven (zie STAND) en je genoeg weet, geef je de aanbeveling.

AANBEVELING (kort en bondig, maximaal ongeveer 80 woorden)
- Begin met één zin waarop je gezocht hebt ("Ik zocht op sport en muziek.").
- Noem precies drie minoren, elk in maximaal twee korte zinnen: eerst in een paar eigen woorden wat de minor inhoudt, dan expliciet waarom hij past bij deze student, met verwijzing naar wat hij of zij zei ("Je zei dat...").
- Noem een nadeel of onzekerheid alleen als het echt relevant is, in een halve zin.
- Sluit af met één korte vraag of het klopt.
- Noem uitsluitend minoren uit de CONTEXT, met de naam letterlijk uit de CONTEXT. Verzin nooit een minor of detail.
- Beweer niets over inhoud, voorkennis, instelling, locatie, toelating, studiepunten of roosters dat niet in de CONTEXT staat. Zeg dan: "Dat weet ik niet zeker, dat kun je het beste navragen bij de instelling of een studieadviseur."
- Laat je niet leiden door geslacht, achtergrond of leeftijd en duw niet automatisch naar de eigen studierichting. Neem minimaal één optie op die iets nieuws biedt als de student daarvoor openstaat.

TWIJFEL
- Past de CONTEXT slecht, is informatie tegenstrijdig of ontbreekt er iets: zeg eerlijk dat je twijfelt.
- Vraag dan door waar de twijfel zit, bij voorkeur met een ja/nee-vraag, of maak de keuze kleiner (bijvoorbeeld op een onderwerp), of zet kort voor- en nadelen op een rij.
- Bij een lage matchscore, tegenstrijdige antwoorden of vragen buiten de data: "Hiervoor kun je het beste contact opnemen met je eigen studieadviseur."
- Vraagt de student naar een minor die niet in de CONTEXT staat, zeg dan dat je die niet kent en bied alternatieven uit de CONTEXT aan.
- Presenteer nooit een gok als feit.

GRENZEN
- Blijf bij minorkeuze. Stuur off-topic vragen vriendelijk terug. Geen medisch, juridisch of psychologisch advies en geen studiekeuzeadvies buiten minoren.

STAND: {stand}

CONTEXT:
{context}
"""

def context_tekst(gevonden):
    regels = []
    for m, s in gevonden:
        per = "; ".join(m.get("periodes", [])[:2])
        regels.append(f"- {m['titel']} ({m.get('ec', '?')} EC) | matchscore {s:.2f} | {m.get('beschrijving', '')[:350]}"
                      + (f" | periodes: {per}" if per else ""))
    return "\n".join(regels)

def maak_system(messages):
    antwoorden = [m["content"] for m in messages if m["role"] == "user" and m["content"].strip() != TRIGGER]
    n = len(antwoorden)
    if not antwoorden or not minors:
        return PROMPT.format(stand=f"Het gesprek begint. Stel precies deze openingsvraag: \"{random.choice(OPENVRAGEN)}\"",
                             context="(nog geen zoekopdracht)" if minors else "(geen minoren beschikbaar: verwijs door naar de studieadviseur)")
    gevonden = zoek(" ".join(antwoorden))
    stand = f"De student heeft {n} antwoord(en) gegeven."
    if gevonden[0][1] < DREMPEL:
        stand += " LAGE MATCHSCORE: zeg eerlijk dat je twijfelt en verwijs door naar een studieadviseur."
    return PROMPT.format(stand=stand, context=context_tekst(gevonden))

def groq(messages):
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise HTTPException(500, "GROQ_API_KEY ontbreekt")
    laatste = ""
    for model in MODELS:
        body = {"model": model, "messages": messages, "temperature": 0.4, "max_completion_tokens": 1500}
        if "gpt-oss" in model:
            body["reasoning_effort"] = "low"
        with httpx.Client(timeout=40) as c:
            r = c.post(GROQ_URL, json=body, headers={"Authorization": f"Bearer {key}"})
        if r.status_code == 200:
            return r.json()["choices"][0]["message"].get("content") or ""
        laatste = r.text[:300]
        if "model" not in laatste.lower():   # alleen doorvallen op model-problemen
            break
    raise HTTPException(502, laatste)

def spreektekst(t):
    t = re.sub(r"[*_#`>]+", "", t)
    t = re.sub(r"^\s*(?:[-•]|\d+[.)])\s+", "", t, flags=re.M)
    return re.sub(r"\s+", " ", t).strip()

class Chat(BaseModel):
    messages: list[dict]

@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")

@app.post("/chat")
def chat(body: Chat):
    msgs = body.messages[-20:]
    uit = groq([{"role": "system", "content": maak_system(msgs)}] + msgs)
    return {"reply": spreektekst(uit) or "Sorry, dat ging mis. " + VANGNET}