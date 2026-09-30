#!/usr/bin/env python3
"""Busca animações clássicas livres no Internet Archive e leva as aprovadas pro app.

    search    varre o archive.org, classifica e gera a página de curadoria  (grátis)
    fetch     baixa o arquivo original das aprovadas                      (grátis, banda)
    publish   converte pra HEVC, gera pôster e entra no catálogo do app
    open      filmes abertos da Blender (classics/open_movies.json), em 1080p

A curadoria é humana e obrigatória. O `search` gera `classics/build/review.html`:
você marca aprovado/rejeitado, ajusta título e sinopse, e exporta o JSON pra
`classics/curation.json` (botão na própria página). `fetch` e `publish` só
tocam no que está aprovado ali.

POR QUE A LICENÇA VEM DO ANO, NÃO DO CAMPO DO ARCHIVE

O `licenseurl` é declarado por quem subiu, e 90% da coleção nem preenche.
Então a base legal é calculada:

    verde    publicado até 1930    domínio público nos EUA (95 anos, regra
                                   de 2026) e no Brasil (70 anos da divulgação)
    verde    CC0 / PD Mark / CC-BY / CC-BY-SA declarados em obra recente
             (é o autor licenciando — ex.: filmes abertos da Blender)
    amarelo  1931–1955             livre no Brasil; nos EUA só se o copyright
                                   não foi renovado — conferir título a título
    fora     o resto, e qualquer licença NC (o app é pago, uso é comercial)

POR QUE FILTRAR CONTEÚDO

Desenho dos anos 30 e 40 tem propaganda de guerra e caricatura racista — os
"Censored Eleven" da Warner, o Bosko, os Superman de 1942–43 contra japoneses.
A lista abaixo derruba os casos conhecidos; o resto passa pela sua revisão.

    python3 scripts/classics/harvest_classics.py search
    open classics/build/review.html
    python3 scripts/classics/harvest_classics.py fetch
    python3 scripts/classics/harvest_classics.py publish
"""

from __future__ import annotations

import argparse
import concurrent.futures
import html
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLASSICS = ROOT / "classics"
BUILD = CLASSICS / "build"
CURATION = CLASSICS / "curation.json"
APP_SHORTS = ROOT / "pedagogy" / "Content" / "Shorts"

IA = "https://archive.org"
UA = {"User-Agent": "PedagogyClassicsHarvester/1.0 (curadoria de acervo infantil)"}

QUERIES = [
    # Clássicos: tudo que é animação e tem ano até 1955.
    "mediatype:movies AND year:[1900 TO 1955] AND "
    "(collection:(animationandcartoons OR classic_cartoons) OR subject:(cartoon OR cartoons OR animation OR animated))",
    # Obras recentes que o próprio autor licenciou de forma aberta.
    "mediatype:movies AND collection:animationandcartoons AND "
    "licenseurl:(*publicdomain* OR *licenses/by/* OR *licenses/by-sa/*)",
]

OPEN_LICENSES = ("publicdomain", "/licenses/by/", "/licenses/by-sa/")

# Casos conhecidos. Casa por substring no título normalizado.
BLOCKLIST = [
    # Censored Eleven (Warner) e afins
    "hittin the trail", "sunday go to meetin", "clean pastures", "uncle tom",
    "jungle jitters", "isle of pingo pongo", "all this and rabbit stew", "coal black",
    "tin pan alley cats", "angel puss", "goldilocks and the jivin bears",
    # Propaganda da Segunda Guerra
    "tokio jokio", "nips the nips", "japoteurs", "eleventh hour", "sap mr jap", "scrap the japs",
    "fuehrers face", "education for death", "private snafu", "snafu", "commando duck", "blitz wolf",
    "herr meets hare", "daffy the commando", "plane daffy", "russian rhapsody", "reason and emotion",
    "spies", "seein red white n blue", "a lecture on camouflage",
    # Personagens derivados de blackface
    "bosko", "inki", "little black sambo", "sambo", "minstrel", "mammy two shoes", "cannibal capers",
    # Bosko sem o nome no título (Looney Tunes de 1930–33)
    "sinkin in the bathtub", "congo jazz", "hold anything", "the booze hangs high", "box car blues",
    "big man from the north", "aint nature grand", "ups n downs", "dumb patrol", "yodeling yokels",
    # Adulto: desenho pornográfico dos anos 20 também é domínio público
    "eveready harton", "virgin with the hot pants",
    # Creepypasta / "lost episode" vendido como filme de época
    "suicide mouse",
]
BLOCK_WORDS = re.compile(
    r"\b(propaganda|blackface|minstrel|nazi|hitler|war bonds?|jap|japs|racist|banned"
    r"|pornographic|pornography|porno?|stag films?|erotic|xxx|adults? only|nsfw|creepypasta|lost episode|gore)\b", re.I)

# Personagem é marca registrada mesmo com o desenho livre: pode exibir, não
# pode usar o nome/imagem no ícone, screenshot ou marketing.
TRADEMARKS = {
    "mickey": "Disney", "minnie": "Disney", "oswald": "Universal/Disney", "popeye": "King Features",
    "superman": "DC", "betty boop": "Fleischer Studios", "bugs bunny": "Warner", "daffy": "Warner",
    "looney tunes": "Warner", "merrie melodies": "Warner",
    "porky": "Warner", "felix": "Felix the Cat Productions", "woody woodpecker": "Universal",
    "mighty mouse": "Paramount", "casper": "Classic Media",
}

COMPILATION = re.compile(r"\b(collection|compilation|dvd|vol\.?|volume|marathon|\d+ cartoons|shorts|all public domain)\b", re.I)

# Curtas do Mickey pelo título — o nome do personagem quase nunca aparece
# nele. O filme está em domínio público; o Mickey é marca da Disney, que
# defende com unhas e dentes. Fica fora da sugestão.
# Escritas já normalizadas (sem apóstrofo): "When the Cat's Away" -> "when the cats away".
DISNEY_SHORTS = ["steamboat willie", "plane crazy", "gallopin gaucho", "barn dance", "opry house",
                 "when the cats away", "the barnyard battle", "the plow boy", "the karnival kid",
                 "mickey", "oswald", "alice comedies", "alices", "skeleton dance",
                 "silly symphony", "silly symphonies", "disney"]

# Remix, meme, reupload editado: não é o filme original.
REMIX = re.compile(r"(\bsigma|\bmeme|remix|parody|\bytp\b|re-?upload|\bedit(ed)?\b|ai upscale|coloui?rized"
                   r"|tooncast|grabaci|tv rip|\brecording\b|dubbed|doblaje|fan ?made)", re.I)

VIDEO_FORMATS = ("MPEG4", "h.264", "h.264 HD", "Matroska", "MPEG2", "QuickTime", "Ogg Video", "WebM", "512Kb MPEG4")


# ─── HTTP ───────────────────────────────────────────────────────────────────

def get_json(url: str, retries: int = 4):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read())
        except Exception as err:
            if attempt == retries - 1:
                raise
            time.sleep(3 * (attempt + 1))


def scrape(query: str, fields: list[str]) -> list[dict]:
    """API de scrape: paginada por cursor, sem o teto de 10k do advancedsearch."""
    items, cursor = [], None
    while True:
        params = {"q": query, "fields": ",".join(fields), "count": "10000"}
        if cursor:
            params["cursor"] = cursor
        page = get_json(f"{IA}/services/search/v1/scrape?{urllib.parse.urlencode(params)}")
        items += page.get("items", [])
        cursor = page.get("cursor")
        if not cursor:
            return items


# ─── Classificação ──────────────────────────────────────────────────────────

def normalize(text: str) -> str:
    text = text.lower().replace("'", "").replace("’", "")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", text)).strip()


def split_words(text: str) -> str:
    """"SteamboatWillie1928" -> "Steamboat Willie 1928": separa camelCase e
    letra/dígito, pra identificador e nome de arquivo casarem com as listas."""
    text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)
    return re.sub(r"(?<=[A-Za-z])(?=[0-9])|(?<=[0-9])(?=[A-Za-z])", " ", text)


def contains_phrase(haystack: str, phrase: str) -> bool:
    """Frase inteira, não substring: "inki" não pode derrubar "Thinking".

    O `s` opcional no fim cobre possessivo e plural, que o normalize() cola
    na palavra ("Bosko's Party" -> "boskos party")."""
    return re.search(rf"\b{re.escape(phrase)}s?\b", haystack) is not None


def first(value):
    return value[0] if isinstance(value, list) else value


def year_of(item: dict) -> int | None:
    for key in ("year", "date"):
        m = re.match(r"(\d{4})", str(first(item.get(key)) or ""))
        if m:
            return int(m.group(1))
    return None


def legal_tier(year: int | None, license_url: str) -> tuple[str, str]:
    lic = (license_url or "").lower()
    if "-nc" in lic or "/nc" in lic:
        return "out", "licença não comercial"
    if year and year <= 1930:
        return "green", f"{year}: domínio público nos EUA e no Brasil"
    if lic and any(tag in lic for tag in OPEN_LICENSES) and (year is None or year >= 1990):
        return "green", "licença aberta do autor (" + lic.rstrip("/").split("/licenses/")[-1].split("/publicdomain/")[-1] + ")"
    if year and year <= 1955:
        return "yellow", f"{year}: livre no Brasil; nos EUA conferir se o copyright foi renovado"
    return "out", "sem base legal para uso comercial"


def content_flags(title: str, subjects: str, description: str,
                  identifier: str = "", year: int | None = None,
                  creator: str = "", file_name: str = "",
                  video_count: int = 1) -> tuple[bool, list[str]]:
    # Identificador e nome do arquivo entram junto: "Sigmaboat willy" mora em
    # /SteamboatWillie, e um item chamado "1929" pode ter o The Barn Dance
    # como arquivo escolhido.
    norm = normalize(f"{title} {split_words(identifier)} {split_words(Path(file_name).stem)}")
    blocked = any(contains_phrase(norm, b) for b in BLOCKLIST)
    # Palavra proibida no título, assunto ou arquivo derruba. Na descrição
    # só sinaliza: texto livre traz aviso e negação ("free of racist
    # content", "hidden message against the Nazis"), e bloquear ali tirava
    # filme bom da revisão sem o curador poder discordar.
    if BLOCK_WORDS.search(f"{title} {subjects} {file_name}"):
        blocked = True
    flags = []
    hit = BLOCK_WORDS.search(description)
    if hit and not blocked:
        flags.append(f"descrição menciona '{hit.group(0)}' — conferir o contexto")
    for name, owner in TRADEMARKS.items():
        if contains_phrase(norm, name):
            flags.append(f"marca registrada: {name.title()} ({owner}) — não usar em marketing")
    # Em 1930 a Harman-Ising só fazia Bosko (Looney Tunes): o crédito basta.
    # (1928–29 era Oswald, que já cai no filtro de Disney/marca.)
    if year == 1930 and contains_phrase(normalize(f"{title} {creator}"), "harman"):
        blocked = True
    if any(contains_phrase(norm, d) for d in DISNEY_SHORTS) or "disney" in normalize(creator):
        flags.append("Disney (Mickey/Oswald/Alice/Silly Symphonies) — marca defendida agressivamente, evitar")
    if video_count > 1:
        flags.append(f"compilação — {video_count} filmes no mesmo item")
    if COMPILATION.search(title):
        flags.append("compilação — prefira o curta individual")
    if REMIX.search(title):
        flags.append("remix/edição/gravação de TV — não é o original")
    if year and year < 1906:
        # Animação praticamente não existia antes disso: o ano está errado,
        # e a base legal calculada em cima dele também.
        flags.append(f"ano {year} suspeito — conferir a data real")
    return blocked, flags


def best_file(files: list[dict]) -> dict | None:
    """Arquivo de vídeo com maior resolução; empate decide pelo tamanho."""
    videos = [f for f in files if f.get("format") in VIDEO_FORMATS and not f["name"].endswith((".gif", ".jpg"))]
    if not videos:
        return None

    def key(f):
        height = int(f.get("height") or 0)
        return (height, f.get("source") == "original", int(f.get("size") or 0))

    return max(videos, key=key)


def parse_length(value) -> float | None:
    if not value:
        return None
    value = str(value)
    if ":" in value:
        seconds = 0.0
        for part in value.split(":"):
            seconds = seconds * 60 + float(part)
        return seconds
    try:
        return float(value)
    except ValueError:
        return None


def full_description(text) -> str:
    text = " ".join(text) if isinstance(text, list) else (text or "")
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text))).strip()


def original_videos(files: list[dict]) -> int:
    """Quantos filmes distintos o item tem.

    Conta por duração, não por nome: o mesmo filme costuma vir em várias
    codificações originais (_DVD.mpeg, _256k.mp4, _64k.mp4) — são um filme
    só. Durações a mais de 3 s uma da outra são filmes diferentes.
    """
    originals = [f for f in files if f.get("source") == "original" and f.get("format") in VIDEO_FORMATS]
    lengths = sorted(l for l in (parse_length(f.get("length")) for f in originals) if l)
    if not lengths:
        return len({Path(f["name"]).stem for f in originals})
    films, last = 0, None
    for length in lengths:
        if last is None or length - last > 3:
            films += 1
        last = length
    return films


def clean_description(text) -> str:
    text = " ".join(text) if isinstance(text, list) else (text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(re.sub(r"\s+", " ", text)).strip()
    sentence = re.split(r"(?<=[.!?])\s", text)
    out = ""
    for s in sentence:
        if len(out) + len(s) > 220:
            break
        out = f"{out} {s}".strip()
    return out or text[:220]


# ─── search ─────────────────────────────────────────────────────────────────

def stage_search(args):
    BUILD.mkdir(parents=True, exist_ok=True)
    fields = ["identifier", "title", "year", "date", "licenseurl", "downloads", "subject", "creator"]
    found: dict[str, dict] = {}
    for q in QUERIES:
        for item in scrape(q, fields):
            found.setdefault(item["identifier"], item)
    print(f"  {len(found)} itens nas buscas")

    # Classificação barata primeiro, pra só pedir metadado do que tem chance.
    pre = []
    for item in found.values():
        title = str(first(item.get("title")) or item["identifier"])
        tier, reason = legal_tier(year_of(item), str(first(item.get("licenseurl")) or ""))
        if tier == "out":
            continue
        pre.append((item, title, tier, reason))
    print(f"  {len(pre)} com base legal — buscando metadados")

    cache_dir = BUILD / "meta"
    cache_dir.mkdir(exist_ok=True)

    def meta(identifier: str) -> dict:
        path = cache_dir / f"{identifier}.json"
        if path.exists():
            return json.loads(path.read_text())
        data = get_json(f"{IA}/metadata/{urllib.parse.quote(identifier)}")
        path.write_text(json.dumps(data))
        return data

    candidates = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        metas = dict(zip([p[0]["identifier"] for p in pre],
                         pool.map(lambda p: meta(p[0]["identifier"]), pre)))

    for item, title, tier, reason in pre:
        m = metas[item["identifier"]]
        md = m.get("metadata", {})
        subjects = " ".join(md.get("subject", [])) if isinstance(md.get("subject"), list) else str(md.get("subject") or "")
        video = best_file(m.get("files", []))
        if not video:
            continue
        creator = str(first(md.get("creator")) or "")
        blocked, flags = content_flags(title, subjects, full_description(md.get("description")),
                                       item["identifier"], year_of(item), creator, video["name"],
                                       original_videos(m.get("files", [])))
        if blocked:
            continue
        seconds = parse_length(video.get("length")) or parse_length(md.get("runtime"))
        if seconds and seconds < 90:
            continue  # vinheta, trailer, abertura
        candidates.append({
            "id": item["identifier"],
            "title": title.strip(),
            "year": year_of(item),
            "tier": tier,
            "legal": reason,
            "flags": flags,
            "creator": str(first(md.get("creator")) or "").strip(),
            "minutes": round(seconds / 60, 1) if seconds else None,
            "downloads": int(item.get("downloads") or 0),
            "file": video["name"],
            "height": int(video.get("height") or 0),
            "sizeMB": round(int(video.get("size") or 0) / 1e6, 1),
            "license": str(first(item.get("licenseurl")) or ""),
            "description": clean_description(md.get("description")),
        })

    # Sugestão inicial: verde, curta (3–15 min), sem marca de compilação,
    # um por título, os mais vistos primeiro.
    candidates.sort(key=lambda c: (c["tier"] != "green", -c["downloads"]))
    seen, suggested = set(), 0
    for c in candidates:
        key = normalize(c["title"])
        is_short = c["minutes"] is not None and 3 <= c["minutes"] <= 15
        # Sugere só o que dá pra aprovar sem ressalva: nenhuma flag (marca,
        # compilação, remix) e resolução que aguenta a tela de um celular.
        c["suggested"] = (suggested < args.suggest and c["tier"] == "green" and is_short
                          and not c["flags"] and c["height"] >= 360 and key not in seen)
        if c["suggested"]:
            suggested += 1
        seen.add(key)

    (BUILD / "candidates.json").write_text(json.dumps(candidates, indent=1, ensure_ascii=False))
    write_review(candidates)
    greens = sum(c["tier"] == "green" for c in candidates)
    print(f"  {len(candidates)} candidatos ({greens} verdes, {len(candidates) - greens} amarelos), "
          f"{suggested} sugeridos")
    print(f"\nabra: open {BUILD / 'review.html'}")


def write_review(candidates: list[dict]):
    existing = json.loads(CURATION.read_text()) if CURATION.exists() else {}
    data = json.dumps({"candidates": candidates, "curation": existing}, ensure_ascii=False)
    (BUILD / "review.html").write_text(REVIEW_HTML.replace("__DATA__", data.replace("</", "<\\/")))


REVIEW_HTML = r"""<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Curadoria de clássicos</title>
<style>
:root{--bg:#fff9f0;--ink:#1a1a1a;--mut:#6e6e78;--line:#ece8e0;--pink:#ff5b8d;--green:#2f9e62;--yellow:#c98a00}
*{box-sizing:border-box}body{margin:0;font:14px/1.45 -apple-system,system-ui,sans-serif;background:var(--bg);color:var(--ink)}
header{position:sticky;top:0;z-index:2;background:var(--ink);color:var(--bg);padding:12px 20px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
header h1{font-size:16px;margin:0 12px 0 0}header select,header input{font:inherit;padding:4px 8px;border-radius:6px;border:0}
button{font:inherit;border:2px solid var(--ink);background:var(--bg);color:var(--ink);border-radius:8px;padding:4px 10px;cursor:pointer}
header button{border-color:var(--bg)}#count{opacity:.7}
main{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px;padding:20px}
.card{background:#fff;border:2px solid var(--ink);border-radius:14px;overflow:hidden;box-shadow:3px 4px 0 var(--ink)}
.card.approved{outline:4px solid var(--green)}.card.rejected{opacity:.35}
.thumb{aspect-ratio:4/3;background:#222 center/cover;position:relative;cursor:pointer}
.thumb video{width:100%;height:100%;object-fit:contain;background:#000}
.badge{position:absolute;top:8px;left:8px;font-size:11px;font-weight:700;padding:2px 8px;border-radius:99px;color:#fff}
.green{background:var(--green)}.yellow{background:var(--yellow)}
.body{padding:12px}.body h3{margin:0 0 2px;font-size:15px}.meta{color:var(--mut);font-size:12px}
.flags{margin:6px 0;padding:0;list-style:none;font-size:12px;color:#b54708}
.body input,.body textarea{width:100%;font:inherit;border:1px solid var(--line);border-radius:6px;padding:4px 6px;margin-top:6px}
.body textarea{min-height:54px;resize:vertical}.row{display:flex;gap:8px;margin-top:8px}.row button{flex:1}
.on{background:var(--ink);color:var(--bg)}a{color:inherit}
</style>
<header><h1>Clássicos · curadoria</h1>
<select id="f"><option value="suggested">Sugeridos</option><option value="green">Verdes</option><option value="yellow">Amarelos</option><option value="approved">Aprovados</option><option value="all">Todos</option></select>
<input id="q" placeholder="buscar título"><span id="count"></span><span style="flex:1"></span>
<button id="export">Copiar curation.json</button></header><main id="grid"></main>
<script>
const {candidates, curation: initial} = __DATA__;
const KEY = "pedagogy-classics-curation";
let cur = {}; try { cur = JSON.parse(localStorage.getItem(KEY)) || {} } catch {}
// Campos que só existem no curation.json (credit, posterAt, file, year,
// editados à mão) sobrevivem ao merge com o que está no navegador.
for (const [k, v] of Object.entries(initial)) cur[k] = {...v, ...(cur[k] || {})};
const save = () => { try { localStorage.setItem(KEY, JSON.stringify(cur)) } catch {} };
const slug = t => t.toLowerCase().replace(/['’]/g,"").replace(/[^a-z0-9]+/g,"-").replace(/^-|-$/g,"").slice(0,48);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
function render(){
  const f = document.getElementById("f").value, q = document.getElementById("q").value.toLowerCase();
  const list = candidates.filter(c => (f==="all" || (f==="suggested"&&c.suggested) || c.tier===f || (f==="approved"&&cur[c.id]?.status==="approved"))
    && (!q || c.title.toLowerCase().includes(q)));
  document.getElementById("count").textContent = `${list.length} itens · ${Object.values(cur).filter(v=>v.status==="approved").length} aprovados`;
  document.getElementById("grid").innerHTML = list.map(c => { const d = cur[c.id] || {};
    return `<div class="card ${d.status||""}" data-id="${esc(c.id)}">
    <div class="thumb" style="background-image:url(https://archive.org/services/img/${encodeURIComponent(c.id)})"><span class="badge ${c.tier}">${c.tier==="green"?"livre":"conferir EUA"}</span></div>
    <div class="body"><h3>${esc(c.title)}</h3>
    <div class="meta">${c.year??"?"} · ${c.minutes??"?"} min · ${c.height||"?"}p · ${c.sizeMB} MB · ${c.downloads.toLocaleString()} views · <a href="https://archive.org/details/${encodeURIComponent(c.id)}" target="_blank">archive</a></div>
    <div class="meta">${esc(c.legal)}</div>
    <ul class="flags">${c.flags.map(x=>`<li>⚠ ${esc(x)}</li>`).join("")}</ul>
    <input data-k="title" value="${esc(d.title ?? c.title)}" placeholder="título no app">
    <textarea data-k="logline" placeholder="sinopse curta pro card (inglês)">${esc(d.logline ?? c.description)}</textarea>
    <div class="row"><button data-s="approved" class="${d.status==="approved"?"on":""}">Aprovar</button><button data-s="rejected" class="${d.status==="rejected"?"on":""}">Rejeitar</button></div></div></div>` }).join("");
}
document.getElementById("grid").addEventListener("click", e => {
  const card = e.target.closest(".card"); if (!card) return; const id = card.dataset.id, c = candidates.find(x=>x.id===id);
  if (e.target.closest(".thumb")) { e.target.closest(".thumb").innerHTML = `<video controls autoplay src="https://archive.org/download/${encodeURIComponent(id)}/${encodeURIComponent(c.file)}"></video>`; return; }
  const s = e.target.dataset.s; if (!s) return;
  const d = cur[id] || {}; d.status = d.status === s ? undefined : s;
  d.title = card.querySelector('[data-k=title]').value; d.logline = card.querySelector('[data-k=logline]').value;
  d.slug = d.slug || slug(d.title); cur[id] = d; save(); render();
});
document.getElementById("grid").addEventListener("input", e => {
  const k = e.target.dataset.k; if (!k) return; const id = e.target.closest(".card").dataset.id;
  // O slug nasce no Aprovar (com o título já digitado) e não muda mais: ele
  // é o nome do arquivo e o id no app. Gerar aqui pegava a primeira tecla.
  cur[id] = {...(cur[id]||{}), [k]: e.target.value}; save();
});
document.getElementById("export").onclick = async () => {
  const out = Object.fromEntries(Object.entries(cur).filter(([,v]) => v.status));
  const text = JSON.stringify(out, null, 2);
  try { await navigator.clipboard.writeText(text); alert("Copiado. Cole em classics/curation.json"); }
  catch { const w = window.open(); w.document.write("<pre>"+esc(text)+"</pre>"); }
};
document.getElementById("f").onchange = render; document.getElementById("q").oninput = render; render();
</script>"""


# ─── fetch ──────────────────────────────────────────────────────────────────

def approved() -> list[tuple[dict, dict]]:
    if not CURATION.exists():
        sys.exit("classics/curation.json não existe — aprove títulos no review.html e exporte")
    curation = json.loads(CURATION.read_text())
    candidates = {c["id"]: c for c in json.loads((BUILD / "candidates.json").read_text())}
    out = []
    for ident, decision in curation.items():
        if decision.get("status") != "approved":
            continue
        if ident not in candidates:
            # Pular aqui faria o publish tratar o filme como reprovado e
            # apagar o que já está no app.
            sys.exit(f"{ident} está aprovado mas saiu dos candidatos (filtro novo ou metadado "
                     f"mudou no archive). Reprove no curation.json ou investigue antes de publicar.")
        out.append((candidates[ident], decision))
    return out


def source_file(c: dict, decision: dict) -> str:
    """Arquivo do item no archive. A curadoria pode trocar o escolhido pelo
    `best_file` (ex.: a cópia original em vez da derivada de 512 kb)."""
    return decision.get("file") or c["file"]


def source_path(c: dict, decision: dict) -> Path:
    return BUILD / "sources" / f"{c['id']}{Path(source_file(c, decision)).suffix}"


def stage_fetch(args):
    (BUILD / "sources").mkdir(parents=True, exist_ok=True)
    items = approved()
    pending = [(c, d) for c, d in items if not source_path(c, d).exists()]
    print(f"  {len(items)} aprovados, {len(pending)} a baixar")
    for c, decision in pending:
        dest = source_path(c, decision)
        url = f"{IA}/download/{urllib.parse.quote(c['id'])}/{urllib.parse.quote(source_file(c, decision))}"
        print(f"  ↓ {c['title']} ({c['sizeMB']} MB)")
        tmp = dest.with_suffix(dest.suffix + ".part")
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=120) as resp, open(tmp, "wb") as out:
            shutil.copyfileobj(resp, out, length=1 << 20)
        tmp.rename(dest)


# ─── publish ────────────────────────────────────────────────────────────────

def run(*cmd: str):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"falhou: {' '.join(cmd)}\n{result.stderr[-2000:]}")
    return result.stdout


def has_audio(path: Path) -> bool:
    return bool(run("ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                    "-of", "csv=p=0", str(path)).strip())


def probe_duration(path: Path) -> float:
    return float(run("ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "csv=p=0", str(path)).strip())


def hardware_hevc() -> bool:
    out = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    return "hevc_videotoolbox" in out


# Encoder de hardware do Mac: ~25x mais rápido que o x265 (30 s de 1080p em
# 4 s; o x265 medium levava 9 min pra 2,5 min de filme).
#
# Por bitrate-alvo, não qualidade constante: com `-q:v` a neve do Llamigos e
# a grama do Big Buck Bunny estouravam pra 3 Mbps e 242 MB. Medido no
# Llamigos: 1,5 Mbps dá SSIM 0,985 — indistinguível na tela de um celular.
HARDWARE_HEVC = hardware_hevc()
TARGET_KBPS = 1500
MAX_FILE_MB = 95      # abaixo do limite de 100 MB por arquivo do GitHub
AUDIO_KBPS = 96


def probe_video(src: Path) -> dict:
    out = run("ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
              "stream=width,height,sample_aspect_ratio,field_order", "-of", "json", str(src))
    return json.loads(out)["streams"][0]


def target_kbps(height: int) -> int:
    """Bitrate por resolução de saída. 1,5 Mbps é o que o 1080p precisa (SSIM
    0,985 no Llamigos); o SD dos clássicos não precisa de tudo isso."""
    if height <= 480:
        return 900
    if height <= 720:
        return 1200
    return TARGET_KBPS


def video_codec(src: Path, out_height: int) -> list[str]:
    """Bitrate-alvo, baixado quando preciso pra o arquivo caber em MAX_FILE_MB."""
    seconds = probe_duration(src)
    fits = int(MAX_FILE_MB * 8000 / seconds) - AUDIO_KBPS
    if fits < 600:
        # Abaixo disso a imagem desmancha; e subir o piso estouraria o limite
        # do GitHub. Filme longo desse jeito não é curta pra seção Watch.
        sys.exit(f"{src.name}: {seconds / 60:.0f} min não cabe em {MAX_FILE_MB} MB com qualidade aceitável")
    kbps = min(target_kbps(out_height), fits)
    if HARDWARE_HEVC:
        return ["-c:v", "hevc_videotoolbox", "-b:v", f"{kbps}k",
                "-maxrate", f"{int(kbps * 1.5)}k", "-bufsize", f"{kbps * 3}k"]
    return ["-c:v", "libx265", "-preset", "fast", "-b:v", f"{kbps}k",
            "-x265-params", f"vbv-maxrate={int(kbps * 1.5)}:vbv-bufsize={kbps * 3}:log-level=error"]


def video_filters(src: Path, max_width: int | None = None, max_height: int | None = None) -> tuple[str, int]:
    """Cadeia de filtros e a altura de saída.

    Os clássicos do archive costumam ser MPEG-2 de DVD: entrelaçados (sem
    deinterlace, pente em todo movimento) e com pixel não quadrado (720×480
    com SAR 8:9 é um 4:3). O pixel vira quadrado antes de escalar — senão o
    recorte do pôster sai esticado, porque ele ignora o SAR.
    """
    info = probe_video(src)
    width, height = int(info["width"]), int(info["height"])
    chain = []
    if info.get("field_order") not in (None, "", "progressive", "unknown"):
        chain.append("bwdif=mode=send_frame")
    sar = info.get("sample_aspect_ratio") or "1:1"
    num, _, den = sar.partition(":")
    if num.isdigit() and den.isdigit() and int(num) and int(den) and num != den:
        # O scale final com setsar=1 já entrega o pixel quadrado.
        width = int(width * int(num) / int(den)) // 2 * 2
    if max_height and height > max_height:
        width, height = int(width * max_height / height) // 2 * 2, max_height
    if max_width and width > max_width:
        width, height = max_width, int(height * max_width / width) // 2 * 2
    chain.append(f"scale={width}:{height}:flags=lanczos,setsar=1,format=yuv420p")
    return ",".join(chain), height


def make_poster(video: Path, poster: Path, at: float | None = None):
    """Um quadro recortado em 16:9 pro card. Default: 20% do filme."""
    at = at if at is not None else probe_duration(video) * 0.2
    run("ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{at:.1f}",
        "-i", str(video), "-frames:v", "1", "-vf",
        "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720", "-q:v", "3", str(poster))


def encode(src: Path, slug: str, force: bool, *, max_width: int | None = None,
           max_height: int | None = None, poster_at: float | None = None) -> Path:
    """HEVC pro app + pôster 16:9. Mantém o aspecto original do filme.

    Só troca de formato: nada de cartela, corte ou legenda por cima. Isso
    importa pro Agent 327 (CC BY-ND) — mudar o formato é permitido pela
    licença, editar o filme não.
    """
    APP_SHORTS.mkdir(parents=True, exist_ok=True)
    video = APP_SHORTS / f"short-{slug}.mp4"
    poster = APP_SHORTS / f"short-{slug}-poster.jpg"
    if not (video.exists() and poster.exists()) or force:
        filters, out_height = video_filters(src, max_width, max_height)
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-map", "0:v:0",
               "-vf", filters, *video_codec(src, out_height), "-tag:v", "hvc1"]
        # Filme mudo continua mudo: o player lida com vídeo sem faixa de áudio.
        if has_audio(src):
            cmd += ["-map", "0:a:0", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                    "-c:a", "aac", "-b:a", f"{AUDIO_KBPS}k", "-ar", "48000"]
        # Escreve ao lado e renomeia no fim: um encode interrompido não pode
        # deixar um .mp4 pela metade que a próxima rodada tomaria por pronto.
        # Fica em classics/build (ignorado pelo git) até terminar: dentro de
        # Content/Shorts, um parcial de uma falha ou Ctrl-C entraria no app
        # pelo grupo sincronizado. Mesmo volume, então o rename é atômico.
        partial = BUILD / "encoding" / video.name
        partial.parent.mkdir(parents=True, exist_ok=True)
        partial.unlink(missing_ok=True)
        run(*cmd, "-movflags", "+faststart", str(partial))
        size_mb = partial.stat().st_size / 1e6
        if size_mb > MAX_FILE_MB + 2:
            partial.unlink()
            sys.exit(f"{video.name}: {size_mb:.0f} MB passou do limite de {MAX_FILE_MB} MB")
        partial.replace(video)
        make_poster(video, poster, poster_at)
    elif poster_at is not None:
        # Quadro escolhido à mão muda sem precisar reconverter o filme.
        make_poster(video, poster, poster_at)
    return video


KIND_ORDER = {"original": 0, "open": 1, "classic": 2}


ARCHIVE_SOURCE = f"{IA}/details/"


def upsert_catalog(entries: list[dict], owned=lambda e: False):
    """Grava as entradas no catálogo do app.

    `owned(e)`: entradas que esta etapa controla por inteiro. As que ela não
    trouxe de novo saíram da curadoria e saem do app, com vídeo e pôster.
    """
    APP_SHORTS.mkdir(parents=True, exist_ok=True)
    path = APP_SHORTS / "shorts.json"
    catalog = json.loads(path.read_text()) if path.exists() else []
    ids = {e["id"] for e in entries}

    removed = [e for e in catalog if owned(e) and e["id"] not in ids]
    for e in removed:
        for f in (APP_SHORTS / f"short-{e['id']}.mp4", APP_SHORTS / f"short-{e['id']}-poster.jpg"):
            f.unlink(missing_ok=True)
        print(f"  − {e['title']} saiu do catálogo")
    catalog = [e for e in catalog if e["id"] not in ids and e not in removed] + entries
    # Dentro de cada origem, o mais novo primeiro; sort estável faz as duas chaves.
    catalog.sort(key=lambda e: e.get("publishedAt") or str(e.get("year") or ""), reverse=True)
    catalog.sort(key=lambda e: KIND_ORDER.get(e.get("kind", "original"), 9))
    path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n")
    print("\nagora, com o Xcode fechado: python3 scripts/tag_ondemand_resources.py")


def license_label(c: dict) -> tuple[str, str]:
    """(kind, texto da licença) de um candidato aprovado.

    Domínio público vem do ano; licença aberta vem do que o autor declarou.
    Um CC BY publicado como "Public domain" apagaria a atribuição que a
    própria licença exige.
    """
    url = c.get("license", "").lower()
    # Obra antiga: a base é o ano (legal_tier), e o selo CC de quem subiu não
    # é do autor. Mesma regra do legal_tier: só confia na licença declarada
    # em obra recente.
    if c.get("year") and c["year"] <= 1955:
        return "classic", "Public domain"
    m = re.search(r"/licenses/(by(?:-sa)?)/?([0-9.]*)", url)
    if m:
        version = f" {m.group(2)}" if m.group(2) else ""
        return "open", f"CC {m.group(1).upper()}{version}"
    if "publicdomain/zero" in url:
        return "open", "CC0"
    if "publicdomain/mark" in url:
        return "classic", "Public domain"
    return "classic", "Public domain"


def assert_slug_free(slug: str, source_url: str):
    """Antes de encodar: um slug que já é de outro filme (ex.: 'spring', da
    Blender) faria o encode sobrescrever o vídeo e o pôster dele. Compara só
    a origem — o mesmo filme republicado pode mudar de `kind`."""
    path = APP_SHORTS / "shorts.json"
    for e in json.loads(path.read_text()) if path.exists() else []:
        if e["id"] == slug and e.get("sourceURL") != source_url:
            sys.exit(f"slug '{slug}' já é de outro filme ({e.get('sourceURL')}) — troque o slug")


def stage_publish(args):
    APP_SHORTS.mkdir(parents=True, exist_ok=True)
    entries, seen = [], {}
    for c, decision in approved():
        src = source_path(c, decision)
        if not src.exists():
            sys.exit(f"falta o arquivo de {c['id']} — rode `fetch`")
        slug = decision.get("slug") or normalize(c["title"]).replace(" ", "-")
        if not slug:
            sys.exit(f"{c['id']}: slug vazio")
        if slug in seen:
            sys.exit(f"slug '{slug}' repetido: {seen[slug]} e {c['id']}")
        seen[slug] = c["id"]
        assert_slug_free(slug, f"https://archive.org/details/{c['id']}")
        kind, license_text = license_label(c)
        credit = decision.get("credit") or c["creator"] or None
        if license_text.startswith("CC BY") and not credit:
            sys.exit(f"{c['id']}: {license_text} exige crédito — preencha `credit` na curadoria")
        print(f"  ⚙ {decision.get('title') or c['title']}")
        # Clássico é 4:3 e SD quase sempre; teto de 720p sem inventar resolução.
        video = encode(src, slug, args.force, max_height=720, poster_at=decision.get("posterAt"))
        entries.append({
            "id": slug,
            "kind": kind,
            "title": decision.get("title") or c["title"],
            "logline": decision.get("logline") or c["description"],
            "durationSeconds": int(round(probe_duration(video))),
            # Watch é premium com 3 grátis por semana em rodízio (Short.freeThisWeek
            # no app); "isPremium": false na curadoria deixa um filme sempre aberto.
            "isPremium": decision.get("isPremium", True),
            "publishedAt": None,
            "year": decision.get("year") or c["year"],
            "credit": credit,
            "sourceURL": f"https://archive.org/details/{c['id']}",
            "license": license_text,
        })
        print(f"  ✓ short-{slug}.mp4  {video.stat().st_size / 1e6:.1f} MB")
    # O que veio do archive é exatamente o aprovado: reprovar tira do app.
    upsert_catalog(entries, owned=lambda e: str(e.get("sourceURL", "")).startswith(ARCHIVE_SOURCE))


# ─── open movies (Blender) ──────────────────────────────────────────────────

OPEN_MOVIES = CLASSICS / "open_movies.json"


def commons_original(file_title: str) -> str:
    """URL do arquivo original no Wikimedia Commons."""
    params = urllib.parse.urlencode({"action": "query", "titles": file_title, "prop": "imageinfo",
                                     "iiprop": "url", "format": "json"})
    pages = get_json(f"https://commons.wikimedia.org/w/api.php?{params}")["query"]["pages"]
    return next(iter(pages.values()))["imageinfo"][0]["url"]


def download(url: str, dest: Path):
    tmp = dest.with_name(dest.name + ".part")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as resp, open(tmp, "wb") as out:
        shutil.copyfileobj(resp, out, length=1 << 20)
    tmp.rename(dest)


def stage_open(args):
    """Baixa, converte e publica os filmes de classics/open_movies.json."""
    movies = json.loads(OPEN_MOVIES.read_text())["movies"]
    if args.only:
        wanted = set(args.only.split(","))
        movies = [m for m in movies if m["slug"] in wanted]
    sources = BUILD / "open"
    sources.mkdir(parents=True, exist_ok=True)

    entries = []
    for m in movies:
        url = m.get("source") or commons_original(m["commonsFile"])
        # Sem a query: o Commons devolve a URL com ?utm_source=..., e o sufixo
        # do arquivo salvo virava ".org&utm_campaign=...".
        name = urllib.parse.unquote(urllib.parse.urlparse(url).path.rsplit("/", 1)[-1])
        src = sources / f"{m['slug']}{Path(name).suffix}"
        if not src.exists():
            print(f"  ↓ {m['title']}")
            download(url, src)
        if src.suffix == ".zip":
            # Big Buck Bunny vem zipado no servidor da Blender.
            unzipped = sources / f"{m['slug']}.mp4"
            if not unzipped.exists():
                partial = unzipped.with_name(unzipped.name + ".part")
                with zipfile.ZipFile(src) as z:
                    inner = next(n for n in z.namelist() if n.endswith(".mp4"))
                    with z.open(inner) as fin, open(partial, "wb") as fout:
                        shutil.copyfileobj(fin, fout, length=1 << 20)
                partial.rename(unzipped)
            src = unzipped

        print(f"  ⚙ {m['title']}")
        # Full HD: teto de 1920 de largura. Os scope (2,39:1) ficam 1920×804.
        assert_slug_free(m["slug"], m["sourcePage"])
        # posterAt: quadro escolhido à mão quando os 20% caem numa cena ruim de capa.
        video = encode(src, m["slug"], args.force, max_width=1920, poster_at=m.get("posterAt"))
        entries.append({
            "id": m["slug"],
            "kind": "open",
            "title": m["title"],
            "logline": m["logline"],
            "durationSeconds": int(round(probe_duration(video))),
            # Mesma regra dos clássicos: premium, com o rodízio semanal no app.
            "isPremium": m.get("isPremium", True),
            "publishedAt": None,
            "year": m["year"],
            "credit": m["credit"],
            "sourceURL": m["sourcePage"],
            "license": m["license"],
        })
        print(f"  ✓ short-{m['slug']}.mp4  {video.stat().st_size / 1e6:.1f} MB")
    upsert_catalog(entries)


# ─── CLI ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("stage", choices=["search", "fetch", "publish", "open"])
    parser.add_argument("--only", help="open: slugs separados por vírgula")
    parser.add_argument("--suggest", type=int, default=20, help="search: quantos sugerir (default 20)")
    parser.add_argument("--force", action="store_true", help="publish: reconverte mesmo o que já existe")
    args = parser.parse_args()
    {"search": stage_search, "fetch": stage_fetch, "publish": stage_publish, "open": stage_open}[args.stage](args)


if __name__ == "__main__":
    main()
