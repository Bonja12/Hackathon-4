"""Minor-adviseur zonder LLM: lokale ML-matching (embeddings) + vaste gespreksflow.

Starten:  python -m uvicorn server:app --reload     (daarna http://localhost:8000 in Chrome/Edge)
Vereist minors.json (maak die met scraper.py). Geen API-key nodig.

Methode: antwoorden van de student en elke minor worden omgezet naar vectoren
(sentence-transformers, meertalig); cosine similarity geeft de ranking.
Valt terug op TF-IDF (scikit-learn) als sentence-transformers niet geïnstalleerd is.
"""
import json, re
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

ROOT = Path(__file__).parent
app = FastAPI()

INTRO = ("Hallo! Ik ben de AI-studieadviseur van de Hogeschool Utrecht en help je met het kiezen van een minor. "
         "Deel geen achternaam of studentnummer. ")
VRAGEN = [
    "Welke opleiding volg je, en wat vind je daar het leukst aan?",
    "Welke onderwerpen of vaardigheden wil je graag leren of verdiepen?",
    "Wat voor soort werk zie je jezelf later doen?",
]
VANGNET = "Hiervoor kun je het beste contact opnemen met je eigen studieadviseur."

minors = json.loads((ROOT / "minors.json").read_text(encoding="utf-8")) if (ROOT / "minors.json").exists() else []
docs = [f"{m['titel']}. {m.get('beschrijving', '')}" for m in minors]

try:
    from sentence_transformers import SentenceTransformer
    _model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    _emb = _model.encode(docs, normalize_embeddings=True) if docs else None
    def scores(text):
        return _emb @ _model.encode([text], normalize_embeddings=True)[0]
    DREMPEL, METHODE = 0.25, "embeddings"
except Exception as e:
    from sklearn.feature_extraction.text import TfidfVectorizer
    _vec = TfidfVectorizer(sublinear_tf=True, ngram_range=(1, 2))
    _mat = _vec.fit_transform(docs) if docs else None
    def scores(text):
        return (_mat @ _vec.transform([text]).T).toarray().ravel()
    DREMPEL, METHODE = 0.05, "tfidf"
print(f"[matching] {METHODE}, {len(minors)} minoren")

STOP = set("willen graag zijn niet maar ook meer deze naar door heel veel gaan vind leuk leren".split())
def woorden(t):
    return {w for w in re.findall(r"[a-zà-ÿ]{5,}", t.lower())} - STOP

def advies(antwoorden):
    tekst = " ".join(antwoorden)  # alleen de inhoud van de antwoorden, geen demografie
    if not minors:
        return "Ik heb nog geen minoren om uit te kiezen. " + VANGNET
    sc = scores(tekst)
    top = [i for i in sc.argsort()[::-1][:2] if sc[i] >= DREMPEL]
    if not top:
        return "Ik kan op basis van je antwoorden geen duidelijk passende minor vinden. " + VANGNET
    m = minors[top[0]]
    gem = sorted(woorden(tekst) & woorden(docs[top[0]]), key=len, reverse=True)[:3]
    reden = f"omdat die aansluit op {', '.join(gem)}" if gem else "omdat de inhoud het best aansluit bij wat je vertelde"
    zin = f"Op basis van je antwoorden past {m['titel']} het best, {reden}."
    if len(top) > 1:
        zin += f" Een tweede optie is {minors[top[1]]['titel']}."
    return zin + " Voor een definitieve keuze kun je het beste contact opnemen met je eigen studieadviseur."

class Chat(BaseModel):
    messages: list[dict]

@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")

@app.post("/chat")
def chat(body: Chat):
    # eerste user-bericht is de verborgen "start"-trigger
    antwoorden = [m["content"] for m in body.messages if m["role"] == "user"][1:]
    n = len(antwoorden)
    if n == 0:
        return {"reply": INTRO + VRAGEN[0]}
    if n < len(VRAGEN):
        return {"reply": VRAGEN[n]}
    if n == len(VRAGEN):
        return {"reply": advies(antwoorden)}
    return {"reply": "Ververs de pagina om opnieuw te beginnen. " + VANGNET}
