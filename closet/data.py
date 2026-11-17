"""데이터 파일 읽기와 형식 검증."""
from dataclasses import dataclass
from pathlib import Path

import yaml

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

SLOTS = ("outer", "top", "bottom", "shoes", "accessory")
FITS = ("slim", "regular", "relaxed", "oversized")
SILHOUETTES = ("slim", "regular", "relaxed")
TONES = ("light", "medium", "dark")
PATTERNS = ("solid", "stripe", "check", "dot", "graphic", "other")
MATERIALS = ("cotton", "wool", "cashmere", "linen", "denim", "leather",
             "suede", "nylon", "polyester", "knit_blend", "other")
REQUIRED = ("id", "name", "slot", "category", "color", "formality", "pattern", "material")
# 액세서리는 핏이 없고, 가방·모자처럼 계절을 타지 않으면 보온도도 생략합니다.
REQUIRED_WEARABLE = ("fit", "warmth")


@dataclass
class Closet:
    items: list      # 옷 dict 목록. 각 옷에 계산된 "moods" 키가 추가됩니다.
    brands: dict
    moods: dict
    mood_pairs: dict  # {"good": {frozenset, ...}, "clash": {frozenset, ...}}
    colors: dict
    tpo: dict
    scoring: dict


def _read(data_dir, name):
    return yaml.safe_load((Path(data_dir) / name).read_text(encoding="utf-8"))


def load(data_dir=DATA_DIR):
    moods_file = _read(data_dir, "moods.yaml")
    brands = _read(data_dir, "brands.yaml")["brands"]
    items = _read(data_dir, "wardrobe.yaml")["items"]
    for it in items:
        # 무드 결정 순서: 옷의 mood_override → 브랜드 moods
        it["moods"] = list(it.get("mood_override")
                           or brands.get(it.get("brand"), {}).get("moods") or [])
    return Closet(
        items=items,
        brands=brands,
        moods=moods_file["moods"],
        mood_pairs={k: {frozenset(p) for p in moods_file["pairs"][k]} for k in ("good", "clash")},
        colors=_read(data_dir, "colors.yaml")["colors"],
        tpo=_read(data_dir, "tpo.yaml")["tpo"],
        scoring=_read(data_dir, "scoring.yaml"),
    )


def _is_range(v):
    return (isinstance(v, list) and len(v) == 2
            and all(isinstance(x, int) and 1 <= x <= 5 for x in v) and v[0] <= v[1])


def _is_level(v):
    return isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 5


def validate(data_dir=DATA_DIR):
    """문제 목록을 돌려줍니다. 빈 목록이면 정상입니다."""
    errors = []
    moods_file = _read(data_dir, "moods.yaml")
    moods = set(moods_file["moods"])
    colors = set(_read(data_dir, "colors.yaml")["colors"])
    brands = _read(data_dir, "brands.yaml")["brands"]
    items = _read(data_dir, "wardrobe.yaml")["items"]

    for kind in ("good", "clash"):
        for pair in moods_file["pairs"][kind]:
            errors += [f"moods.pairs.{kind}: 알 수 없는 무드 {m}" for m in pair if m not in moods]

    for key, tpo in _read(data_dir, "tpo.yaml")["tpo"].items():
        if not _is_range(tpo.get("formality")):
            errors.append(f"tpo.{key}: formality는 [최소, 최대] (1~5)")
        elif "target" in tpo and not tpo["formality"][0] <= tpo["target"] <= tpo["formality"][1]:
            errors.append(f"tpo.{key}: target은 formality 범위 안")

    for key, b in brands.items():
        where = f"brands.{key}"
        bm = b.get("moods") or []
        if not 1 <= len(bm) <= 3:
            errors.append(f"{where}: moods는 1~3개")
        errors += [f"{where}: 알 수 없는 무드 {m}" for m in bm if m not in moods]
        if not _is_range(b.get("formality")):
            errors.append(f"{where}: formality는 [최소, 최대] (1~5)")
        if b.get("silhouette") not in SILHOUETTES:
            errors.append(f"{where}: silhouette는 {list(SILHOUETTES)} 중 하나")

    seen = set()
    for i, it in enumerate(items):
        where = f"items[{i}] {it.get('id', '?')}"
        wearable = it.get("slot") != "accessory"
        required = REQUIRED + (REQUIRED_WEARABLE if wearable else ())
        errors += [f"{where}: {f} 누락" for f in required if f not in it]
        if it.get("id") in seen:
            errors.append(f"{where}: id 중복")
        seen.add(it.get("id"))
        if it.get("slot") not in SLOTS:
            errors.append(f"{where}: slot은 {list(SLOTS)} 중 하나")
        if "fit" in it and it["fit"] not in FITS:
            errors.append(f"{where}: fit은 {list(FITS)} 중 하나")
        if "pattern" in it and it["pattern"] not in PATTERNS:
            errors.append(f"{where}: pattern은 {list(PATTERNS)} 중 하나")
        if "material" in it and it["material"] not in MATERIALS:
            errors.append(f"{where}: material은 {list(MATERIALS)} 중 하나")
        for f in ("formality", "warmth"):
            if f in it and not _is_level(it[f]):
                errors.append(f"{where}: {f}는 1~5 정수")
        c = it.get("color") or {}
        if "color" in it:
            if "primary" not in c:
                errors.append(f"{where}: color.primary 누락")
            errors += [f"{where}: 알 수 없는 색 {c[f]}"
                       for f in ("primary", "secondary") if f in c and c[f] not in colors]
            if c.get("tone") not in TONES:
                errors.append(f"{where}: color.tone은 {list(TONES)} 중 하나")
        brand = it.get("brand")
        if brand is not None and brand not in brands:
            errors.append(f"{where}: brands.yaml에 없는 브랜드 {brand}")
        override = it.get("mood_override")
        if override is not None:
            errors += [f"{where}: 알 수 없는 무드 {m}" for m in override if m not in moods]
        if brand is None and not override:
            errors.append(f"{where}: 브랜드가 없으면 mood_override 필요")
    return errors
