#!/usr/bin/env python3
"""Modelos 3D de um curta via Tripo: imagem → modelo → rig → animações.

Lê `shorts/<slug>/assets3d.json`:

    [{"id": "nell", "image": "build/layers/pose/nell-apose.alpha.png",
      "rig": "biped", "animations": ["preset:biped:walk", "preset:biped:sit"]},
     {"id": "box", "image": "...png"}]                         # sem rig: só o modelo

e grava em `shorts/<slug>/build/models/<id>/`:

    model.glb             o modelo com textura
    rigged.glb            com esqueleto (se "rig")
    anim-<preset>.glb     uma por animação, já com o modelo

Retomável: o id de cada tarefa fica em build/models/state.json; rodar de
novo pula o que já terminou e só baixa/gera o que falta.

Chave: TRIPO_API_KEY no ambiente ou no .env da raiz. SDK: pip install tripo3d

    python3 scripts/shorts/tripo_assets.py plan fox-3d          (grátis: mostra o custo)
    python3 scripts/shorts/tripo_assets.py run fox-3d --yes
    python3 scripts/shorts/tripo_assets.py run fox-3d --only fox --yes
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Estimativa (créditos). Os valores reais vêm em credits_consumed e vão pro ledger.
CREDITS = {"model": 40, "rig": 30, "animation": 20}
USD_PER_CREDIT = 0.01

# Modelo "game-ready" (topologia limpa) pra personagens que vão ser riggados;
# o geral pros objetos parados.
MODEL_RIGGED = "P1-20260311"
MODEL_STATIC = "v3.1-20260211"
# Rig: v1.0 é o humanoide com 90+ animações (preset:biped:*); quadrúpede usa o v2.5.
RIG_VERSION = {"biped": "v1.0-20240301", "quadruped": "v2.5-20260210"}


def api_key() -> str:
    key = os.environ.get("TRIPO_API_KEY")
    env = ROOT / ".env"
    if not key and env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("TRIPO_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not key:
        sys.exit("defina TRIPO_API_KEY (ambiente ou .env na raiz do repo)")
    return key


class Film:
    def __init__(self, slug: str):
        self.dir = ROOT / "shorts" / slug
        self.assets = json.loads((self.dir / "assets3d.json").read_text())
        self.out = self.dir / "build" / "models"
        self.out.mkdir(parents=True, exist_ok=True)
        self.state_path = self.out / "state.json"
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {}

    def save(self):
        self.state_path.write_text(json.dumps(self.state, indent=1))

    def select(self, only: str | None):
        if not only:
            return self.assets
        wanted = {w.strip() for w in only.split(",")}
        return [a for a in self.assets if a["id"] in wanted]


def anim_file(preset: str) -> str:
    return "anim-" + preset.replace("preset:", "").replace(":", "-") + ".glb"


def todo_steps(film: Film, asset: dict) -> list[tuple[str, str]]:
    """Passos que ainda faltam pra um asset: [(tipo, alvo)]."""
    st = film.state.get(asset["id"], {})
    d = film.out / asset["id"]
    steps = []
    if not (st.get("model") and (d / "model.glb").exists()):
        steps.append(("model", "model.glb"))
    if asset.get("rig"):
        if not (st.get("rig") and (d / "rigged.glb").exists()):
            steps.append(("rig", "rigged.glb"))
        for preset in asset.get("animations", []):
            if not (d / anim_file(preset)).exists():
                steps.append(("animation", preset))
    return steps


def stage_plan(film: Film, args):
    total = 0
    for a in film.select(args.only):
        steps = todo_steps(film, a)
        credits = sum(CREDITS[t] for t, _ in steps)
        total += credits
        img = film.dir / a["image"]
        flag = "" if img.exists() else "   ← falta a imagem"
        print(f"  {a['id']:10s} {a.get('rig', 'estático'):10s} {len(steps)} passos, ~{credits} créditos{flag}")
        for t, target in steps:
            print(f"      {t:9s} {target}")
    print(f"\n  total ~{total} créditos (~US$ {total * USD_PER_CREDIT:.2f})")
    return total


def white_png(src: Path) -> str:
    """O Tripo recorta o fundo sozinho, mas lida melhor com fundo branco liso
    do que com transparência: achata o PNG sobre branco num temporário."""
    from PIL import Image
    im = Image.open(src).convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    bg.alpha_composite(im)
    tmp = Path(tempfile.mkdtemp()) / (src.stem + ".png")
    bg.convert("RGB").save(tmp)
    return str(tmp)


async def run_asset(client, film: Film, asset: dict):
    from tripo3d import RigType, RigSpec
    aid = asset["id"]
    st = film.state.setdefault(aid, {})
    d = film.out / aid
    d.mkdir(exist_ok=True)

    async def finish(task_id: str, target: str, key: str):
        from tripo3d.models import TaskStatus
        task = await client.wait_for_task(task_id, verbose=False)
        if task.status != TaskStatus.SUCCESS:
            raise RuntimeError(f"{aid} {key}: tarefa {task_id} terminou com {task.status}")
        tmp = Path(tempfile.mkdtemp())
        files = await client.download_task_models(task, str(tmp))
        path = files.get("pbr_model") or files.get("model") or files.get("base_model")
        if not path:
            raise RuntimeError(f"{aid} {key}: tarefa {task_id} sem arquivo de modelo")
        Path(path).replace(d / target)
        img = files.get("rendered_image")
        if img and key == "model":
            Path(img).replace(d / "preview.jpg")
        credits = getattr(task, "credits_consumed", None) or (task.output and getattr(task.output, "credits", None))
        st.setdefault("credits", {})[target] = credits
        film.save()
        print(f"  {aid}: {target} ok")

    if not (st.get("model") and (d / "model.glb").exists()):
        if not st.get("model"):
            rigged = bool(asset.get("rig"))
            st["model"] = await client.image_to_model(
                image=white_png(film.dir / asset["image"]),
                model_version=MODEL_RIGGED if rigged else MODEL_STATIC,
                texture=True, pbr=False,                      # toon: textura difusa basta
                face_limit=asset.get("face_limit", 20000 if rigged else 12000),
                texture_quality="detailed",
            )
            film.save()
        await finish(st["model"], "model.glb", "model")

    rig = asset.get("rig")
    if not rig:
        return
    if not (st.get("rig") and (d / "rigged.glb").exists()):
        if not st.get("rig"):
            st["rig"] = await client.rig_model(
                original_model_task_id=st["model"],
                model_version=RIG_VERSION[rig],
                out_format="glb",
                rig_type=RigType(rig),
                spec=RigSpec.TRIPO,
            )
            film.save()
        await finish(st["rig"], "rigged.glb", "rig")

    for preset in asset.get("animations", []):
        target = anim_file(preset)
        if (d / target).exists():
            continue
        tasks = st.setdefault("animations", {})
        if not tasks.get(preset):
            tasks[preset] = await client.retarget_animation(
                original_model_task_id=st["rig"],
                animation=preset,
                out_format="glb",
                bake_animation=True,
                export_with_geometry=True,
                animate_in_place=True,        # o deslocamento quem faz é a cena no Blender
            )
            film.save()
        await finish(tasks[preset], target, preset)


async def stage_run_async(film: Film, args):
    from tripo3d import TripoClient
    async with TripoClient(api_key=api_key()) as client:
        try:
            bal = await client.get_balance()
            print(f"  saldo Tripo: {bal}")
        except Exception as e:                          # saldo é só informativo
            print(f"  (não consegui ler o saldo: {e})")
        for asset in film.select(args.only):
            if not (film.dir / asset["image"]).exists():
                print(f"  {asset['id']}: falta {asset['image']} — pulando")
                continue
            try:
                await run_asset(client, film, asset)
            except Exception as e:
                # Um asset com problema não derruba os outros; o estado fica salvo.
                print(f"  {asset['id']}: FALHOU — {e}")


def stage_run(film: Film, args):
    total = stage_plan(film, args)
    if total == 0:
        print("  nada a fazer")
        return
    if not args.yes:
        print("(estimativa — rode de novo com --yes pra gerar)")
        return
    asyncio.run(stage_run_async(film, args))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=["plan", "run"])
    ap.add_argument("slug")
    ap.add_argument("--only", help="ids separados por vírgula")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args()
    film = Film(args.slug)
    {"plan": stage_plan, "run": stage_run}[args.stage](film, args)


if __name__ == "__main__":
    main()
