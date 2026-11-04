"""Measure photo-identification accuracy on YOUR real parts.

Usage (from backend/):
  python scripts/evaluate.py --photos ./eval/photos --truth ./eval/truth.csv --out ./eval/out

Run it with the real Meta key and model. Do NOT run it on a substitute model and
report the numbers as Muse Spark. The model id is written into the report.
"""
import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.services import evaluation as ev  # noqa: E402
from app.services.inspector import inspect_image  # noqa: E402


async def run(args) -> None:
    truth = ev.load_ground_truth(Path(args.truth))
    photos_dir = Path(args.photos)
    sem = asyncio.Semaphore(args.concurrency)
    scores, failed, modes, raw = [], [], {}, {}

    async def one(name: str, gts):
        path = photos_dir / name
        if not path.exists():
            failed.append(f"{name} (file not found)")
            return
        async with sem:
            try:
                res = await inspect_image(path.read_bytes())
            except Exception as exc:  # report, don't hide
                failed.append(f"{name} ({type(exc).__name__}: {str(exc)[:120]})")
                return
            await asyncio.sleep(args.delay)
        props = [p.model_dump() for p in res.proposals]
        modes[res.segmentation_mode] = modes.get(res.segmentation_mode, 0) + 1
        raw[name] = props
        scores.append(ev.score_photo(name, gts, props))
        print(f"{name}: {len(props)} proposal(s)")

    await asyncio.gather(*(one(n, g) for n, g in truth.items()))
    summary = ev.summarize(scores)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    model = get_settings().muse_model
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    (out / "proposals.json").write_text(json.dumps(raw, indent=2, default=str))
    (out / "per_photo.json").write_text(json.dumps([asdict(s) for s in scores], indent=2))
    report = ev.render_report(summary, model=model, mode_counts=modes, failed=failed)
    (out / "report.md").write_text(report)
    print("\n" + report)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--photos", required=True)
    ap.add_argument("--truth", required=True)
    ap.add_argument("--out", default="./eval/out")
    ap.add_argument("--concurrency", type=int, default=2)
    ap.add_argument("--delay", type=float, default=0.5, help="seconds between calls per worker")
    asyncio.run(run(ap.parse_args()))
