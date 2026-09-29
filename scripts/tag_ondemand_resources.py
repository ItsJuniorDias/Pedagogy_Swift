#!/usr/bin/env python3
"""Grava as tags de On-Demand Resources da narração e do motion no pbxproj.

O alvo usa grupo sincronizado (PBXFileSystemSynchronizedRootGroup), então não
existe PBXBuildFile por arquivo onde pendurar ASSET_TAGS. As tags vão no
exception set do grupo, em `assetTagsByRelativePath`, e a lista de tags
conhecidas em `KnownAssetTags` nos atributos do projeto — as mesmas chaves que
o Xcode escreve quando se preenche "On Demand Resource Tags" no File Inspector.

    Content/Audio/<slug>-ch<N>.mp3  ->  narration-<slug>
    Content/Motion/<slug>.mp4       ->  motion-<slug>
    Content/Shorts/short-<id>.mp4   ->  short-<id>   (arquivo .part.mp4 de encode pela metade não entra)

Precisa bater com `ContentPack.tag` em pedagogy/Content/ContentPacks.swift.

Os .timings.json NÃO recebem tag: ficam no bundle porque são o índice que diz
ao app quais capítulos têm narração antes de qualquer download.

Uso:
    python3 scripts/tag_ondemand_resources.py          # regrava o pbxproj
    python3 scripts/tag_ondemand_resources.py --check  # só confere (exit 1 se desatualizado)

Rode com o projeto fechado no Xcode, ou o Xcode pode sobrescrever a mudança
com a versão que tem em memória.
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PBXPROJ = ROOT / "pedagogy.xcodeproj" / "project.pbxproj"
SOURCES = ROOT / "pedagogy"

CHAPTER_MP3 = re.compile(r"^(?P<slug>.+)-ch\d+\.mp3$")


def collect_tags() -> dict[str, str]:
    """Caminho relativo à pasta sincronizada -> tag."""
    tags: dict[str, str] = {}

    for mp3 in sorted((SOURCES / "Content" / "Audio").glob("*.mp3")):
        match = CHAPTER_MP3.match(mp3.name)
        if not match:
            sys.exit(f"nome fora do padrão <slug>-ch<N>.mp3: {mp3.name}")
        tags[mp3.relative_to(SOURCES).as_posix()] = f"narration-{match['slug']}"

    for mp4 in sorted((SOURCES / "Content" / "Motion").glob("*.mp4")):
        tags[mp4.relative_to(SOURCES).as_posix()] = f"motion-{mp4.stem}"

    # O nome do arquivo já é a tag. O pôster e o shorts.json ficam no bundle.
    for mp4 in sorted((SOURCES / "Content" / "Shorts").glob("short-*.mp4")):
        if mp4.name.endswith(".part.mp4"):
            continue
        tags[mp4.relative_to(SOURCES).as_posix()] = mp4.stem

    return tags


def render_tags_by_path(tags: dict[str, str]) -> str:
    # Formato de uma linha, igual ao que o Xcode grava ao salvar o projeto.
    # No formato de várias linhas, cada save do Xcode reescrevia o bloco
    # inteiro e o --check acusava "desatualizado" com as tags todas certas.
    lines = ["\t\t\tassetTagsByRelativePath = {"]
    lines += [f'\t\t\t\t"{path}" = ("{tag}", );' for path, tag in tags.items()]
    lines.append("\t\t\t};")
    return "\n".join(lines) + "\n"


def parse_tags(text: str) -> tuple[dict[str, str], set[str]]:
    """Tags que o pbxproj tem hoje, em qualquer um dos dois formatos."""
    by_path: dict[str, str] = {}
    block = re.search(r"assetTagsByRelativePath = \{(.*?)\n\t\t\t\};", text, re.S)
    if block:
        entry = re.compile(r'"?([^"\s=]+)"?\s*=\s*\(\s*"?([^"\s,)]+)"?\s*,?\s*\);', re.S)
        by_path = {m.group(1): m.group(2) for m in entry.finditer(block.group(1))}
    known: set[str] = set()
    block = re.search(r"KnownAssetTags = \((.*?)\);", text, re.S)
    if block:
        known = {t.strip().strip('"') for t in block.group(1).split(",") if t.strip()}
    return by_path, known


def render_known_tags(tags: dict[str, str]) -> str:
    lines = ["\t\t\t\tKnownAssetTags = ("]
    lines += [f'\t\t\t\t\t"{tag}",' for tag in sorted(set(tags.values()))]
    lines.append("\t\t\t\t);")
    return "\n".join(lines) + "\n"


def update(text: str, tags: dict[str, str]) -> str:
    # ── Exception set do grupo sincronizado ──────────────────────────────
    # Troca só o bloco de tags; as outras chaves do exception set (membership,
    # flags de compilação, atributos) ficam intactas.
    by_path = re.compile(r"\t\t\tassetTagsByRelativePath = \{\n.*?\n\t\t\t\};\n", re.S)
    if by_path.search(text):
        text = by_path.sub(lambda _: render_tags_by_path(tags), text, count=1)
    else:
        isa = "isa = PBXFileSystemSynchronizedBuildFileExceptionSet;\n"
        if text.count(isa) != 1:
            sys.exit("esperava exatamente um exception set de grupo sincronizado no pbxproj")
        text = text.replace(isa, isa + render_tags_by_path(tags), 1)

    # ── Tags conhecidas do projeto ───────────────────────────────────────
    known = re.compile(r"\t\t\t\tKnownAssetTags = \(\n.*?\t\t\t\t\);\n", re.S)
    if known.search(text):
        text = known.sub(lambda _: render_known_tags(tags), text, count=1)
    else:
        attrs = "isa = PBXProject;\n\t\t\tattributes = {\n"
        if attrs not in text:
            sys.exit("atributos do PBXProject não encontrados no pbxproj")
        text = text.replace(attrs, attrs + render_known_tags(tags), 1)

    return text


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="só confere, não grava")
    args = parser.parse_args()

    tags = collect_tags()
    current = PBXPROJ.read_text()

    narration = sum(t.startswith("narration-") for t in tags.values())
    shorts = sum(t.startswith("short-") for t in tags.values())
    motion = len(tags) - narration - shorts
    summary = (f"{narration} mp3 + {motion} motion + {shorts} filmes "
               f"em {len(set(tags.values()))} tags")

    # Compara as tags, não o texto: o mesmo conteúdo pode estar formatado
    # pelo Xcode ou por este script.
    by_path, known = parse_tags(current)
    if by_path == tags and known == set(tags.values()):
        print(f"pbxproj em dia ({summary})")
        return
    missing = sorted(set(tags) - set(by_path))
    if missing:
        print(f"  sem tag: {len(missing)} arquivo(s), ex.: {missing[0]}")
    updated = update(current, tags)
    if args.check:
        sys.exit(f"pbxproj desatualizado — rode scripts/tag_ondemand_resources.py ({summary})")

    PBXPROJ.write_text(updated)
    print(f"pbxproj atualizado ({summary})")


if __name__ == "__main__":
    main()
