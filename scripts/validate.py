"""옷장 데이터 검증: python3 scripts/validate.py"""
import sys
from pathlib import Path

import yaml

DATA = Path(__file__).resolve().parent.parent / "data"

SLOTS = {"outer", "top", "bottom", "shoes", "accessory"}
FITS = {"slim", "regular", "relaxed", "oversized"}
SILHOUETTES = {"slim", "regular", "relaxed"}
TONES = {"light", "medium", "dark"}
PATTERNS = {"solid", "stripe", "check", "dot", "graphic", "other"}
MATERIALS = {"cotton", "wool", "cashmere", "linen", "denim", "leather",
             "suede", "nylon", "polyester", "knit_blend", "other"}
REQUIRED = ["id", "name", "slot", "category", "color", "formality",
            "fit", "warmth", "pattern", "material"]


def load(name):
    return yaml.safe_load((DATA / name).read_text(encoding="utf-8"))


def is_range(v):
    return (isinstance(v, list) and len(v) == 2
            and all(isinstance(x, int) and 1 <= x <= 5 for x in v) and v[0] <= v[1])


def main():
    errors = []
    moods = set(load("moods.yaml")["moods"])
    colors = set(load("colors.yaml")["colors"])
    brands = load("brands.yaml")["brands"]
    items = load("wardrobe.yaml")["items"]

    mood_pairs = load("moods.yaml")["pairs"]
    for kind in ("good", "clash"):
        for pair in mood_pairs[kind]:
            for m in pair:
                if m not in moods:
                    errors.append(f"moods.pairs.{kind}: 알 수 없는 무드 {m}")

    for key, tpo in load("tpo.yaml")["tpo"].items():
        if not is_range(tpo.get("formality")):
            errors.append(f"tpo.{key}: formality는 [최소, 최대] (1~5)")

    for key, b in brands.items():
        where = f"brands.{key}"
        bm = b.get("moods") or []
        if not 1 <= len(bm) <= 3:
            errors.append(f"{where}: moods는 1~3개")
        errors += [f"{where}: 알 수 없는 무드 {m}" for m in bm if m not in moods]
        if not is_range(b.get("formality")):
            errors.append(f"{where}: formality는 [최소, 최대] (1~5)")
        if b.get("silhouette") not in SILHOUETTES:
            errors.append(f"{where}: silhouette는 {sorted(SILHOUETTES)} 중 하나")

    seen = set()
    for i, it in enumerate(items):
        where = f"items[{i}] {it.get('id', '?')}"
        errors += [f"{where}: {f} 누락" for f in REQUIRED if f not in it]
        if it.get("id") in seen:
            errors.append(f"{where}: id 중복")
        seen.add(it.get("id"))
        if it.get("slot") not in SLOTS:
            errors.append(f"{where}: slot은 {sorted(SLOTS)} 중 하나")
        if it.get("fit") not in FITS:
            errors.append(f"{where}: fit은 {sorted(FITS)} 중 하나")
        if it.get("pattern") not in PATTERNS:
            errors.append(f"{where}: pattern은 {sorted(PATTERNS)} 중 하나")
        if it.get("material") not in MATERIALS:
            errors.append(f"{where}: material은 {sorted(MATERIALS)} 중 하나")
        for f in ("formality", "warmth"):
            v = it.get(f)
            if not (isinstance(v, int) and 1 <= v <= 5):
                errors.append(f"{where}: {f}는 1~5 정수")
        c = it.get("color") or {}
        for f in ("primary", "secondary"):
            if f in c and c[f] not in colors:
                errors.append(f"{where}: 알 수 없는 색 {c[f]}")
        if "primary" not in c:
            errors.append(f"{where}: color.primary 누락")
        if c.get("tone") not in TONES:
            errors.append(f"{where}: color.tone은 {sorted(TONES)} 중 하나")
        brand = it.get("brand")
        if brand is not None and brand not in brands:
            errors.append(f"{where}: brands.yaml에 없는 브랜드 {brand}")
        override = it.get("mood_override")
        if override is not None:
            errors += [f"{where}: 알 수 없는 무드 {m}" for m in override if m not in moods]
        if brand is None and not override:
            errors.append(f"{where}: 브랜드가 없으면 mood_override 필요")

    if errors:
        print("\n".join(errors))
        sys.exit(1)
    print(f"OK: 옷 {len(items)}벌, 브랜드 {len(brands)}개")


if __name__ == "__main__":
    main()
