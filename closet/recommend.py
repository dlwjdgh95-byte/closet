"""추천 로직: 날씨와 TPO로 먼저 거르고, 남은 조합을 색·격식·핏·무드 점수로 순위 매깁니다."""
from dataclasses import dataclass, field
from itertools import combinations, product

CORE_SLOTS = ("outer", "top", "bottom", "shoes")
FIT_WIDTH = {"slim": 0, "regular": 1, "relaxed": 2, "oversized": 3}
AXIS_LABELS = {"color": "색", "formality": "격식", "fit": "핏", "mood": "무드"}


@dataclass
class Context:
    tpo: str
    temp: float          # 체감기온(℃)
    rain: bool = False


@dataclass
class Outfit:
    items: dict                      # slot -> 옷 (없는 슬롯은 빠짐)
    scores: dict = field(default_factory=dict)
    reasons: dict = field(default_factory=dict)
    total: float = 0.0
    weather_gap: int = 0             # 목표 보온도와의 차이. 0이면 날씨에 딱 맞음

    @property
    def core(self):
        return [self.items[s] for s in CORE_SLOTS if s in self.items]


# ---------- 1. 필터 ----------

def target_warmth(closet, temp):
    for row in closet.scoring["warmth_by_temp"]:
        if temp >= row["min_temp"]:
            return row["warmth"]
    return 5


def candidates(closet, ctx):
    """슬롯별로 오늘 입을 수 있는 옷만 남깁니다."""
    lo, hi = closet.tpo[ctx.tpo]["formality"]
    target = target_warmth(closet, ctx.temp)
    avoid = set(closet.scoring["rain_avoid_materials"]) if ctx.rain else set()
    out = {}
    for it in closet.items:
        if not lo <= it["formality"] <= hi:
            continue
        if it["material"] in avoid:
            continue
        if "warmth" in it:
            below, above = closet.scoring["warmth_tolerance"][it["slot"]]
            if not target + below <= it["warmth"] <= target + above:
                continue
        out.setdefault(it["slot"], []).append(it)
    return out


def outer_options(closet, ctx, outers):
    """아우터 선택지. None은 아우터 없이 입는 경우입니다."""
    target = target_warmth(closet, ctx.temp)
    rule = closet.scoring["outer"]
    if target <= rule["none_until"]:
        return [None]
    if target >= rule["required_from"]:
        return list(outers)
    return [None] + list(outers)


# ---------- 2. 점수 (각 0~1) ----------

def _label(closet, color):
    return closet.colors[color]["label"]


def score_color(closet, core):
    families = {}
    for it in core:
        for key in ("primary", "secondary"):
            c = it["color"].get(key)
            if c and not closet.colors[c]["neutral"]:
                families.setdefault(closet.colors[c].get("family", c), c)
    n = len(families)
    points = ", ".join(_label(closet, c) for c in families.values())
    if n == 0:
        palette, why = 0.85, "기본색으로만 구성"
    elif n == 1:
        palette, why = 1.0, f"기본색 바탕에 포인트 색 하나({points})"
    elif n == 2:
        palette, why = 0.5, f"유채색이 두 계열({points})"
    else:
        palette, why = 0.2, f"유채색이 너무 많음({points})"

    by_slot = {it["slot"]: it for it in core}
    top, bottom, outer = by_slot["top"], by_slot["bottom"], by_slot.get("outer")
    if top["color"]["tone"] != bottom["color"]["tone"]:
        contrast = 1.0
        why += ", 위아래 명암 대비"
    elif outer and outer["color"]["tone"] != top["color"]["tone"]:
        contrast = 0.8
    else:
        contrast = 0.6

    patterned = sum(1 for it in core if it["pattern"] != "solid")
    pattern = 1.0 if patterned <= 1 else 0.4 if patterned == 2 else 0.1
    if patterned >= 2:
        why += f", 패턴 {patterned}개가 겹침"
    return 0.5 * palette + 0.3 * contrast + 0.2 * pattern, why


def score_formality(closet, core, tpo):
    levels = [it["formality"] for it in core]
    spread = max(levels) - min(levels)
    consistency = {0: 1.0, 1: 0.85, 2: 0.4}.get(spread, 0.0)
    mean = sum(levels) / len(levels)
    spec = closet.tpo[tpo]
    target = spec.get("target", sum(spec["formality"]) / 2)
    closeness = max(0.0, 1 - abs(mean - target) / 1.5)
    why = "격식이 고름" if spread <= 1 else f"격식 차이가 큼({min(levels)}~{max(levels)})"
    return 0.7 * consistency + 0.3 * closeness, f"{why}, 평균 {mean:.1f}"


def score_fit(core):
    by_slot = {it["slot"]: it for it in core}
    top, bottom = FIT_WIDTH[by_slot["top"]["fit"]], FIT_WIDTH[by_slot["bottom"]["fit"]]
    diff = abs(top - bottom)
    if diff in (1, 2):
        score = 1.0 if diff == 1 else 0.9
        why = "상의가 여유 있고 하의가 정돈됨" if top > bottom else "상의가 단정하고 하의가 여유 있음"
    elif diff == 3:
        score, why = 0.7, "위아래 실루엣 차이가 큼"
    else:
        score, why = {0: (0.6, "위아래 모두 슬림"), 1: (0.85, "위아래 모두 레귤러"),
                      2: (0.8, "위아래 모두 여유 있는 핏"), 3: (0.5, "위아래 모두 오버핏")}[top]
    outer = by_slot.get("outer")
    if outer:
        gap = top - FIT_WIDTH[outer["fit"]]   # 아우터가 상의보다 좁으면 불편
        if gap >= 2:
            score, why = score * 0.5, why + ", 아우터가 상의보다 많이 좁음"
        elif gap == 1:
            score, why = score * 0.8, why + ", 아우터가 상의보다 좁음"
    return score, why


def mood_relation(closet, a, b):
    """두 옷의 무드 궁합: 1 같은 무드 / 0.75 어울림 / 0.5 중립 / 0 충돌"""
    if set(a) & set(b):
        return 1.0
    pairs = {frozenset((x, y)) for x in a for y in b}
    if pairs & closet.mood_pairs["good"]:
        return 0.75
    if pairs & closet.mood_pairs["clash"]:
        return 0.0
    return 0.5


def score_mood(closet, core):
    rels = [(mood_relation(closet, a["moods"], b["moods"]), a, b) for a, b in combinations(core, 2)]
    score = sum(r for r, _, _ in rels) / len(rels)
    clashes = [f"{a['name']}와 {b['name']}" for r, a, b in rels if r == 0.0]
    if clashes:
        return score, "무드 충돌: " + ", ".join(clashes)
    counts = {}
    for it in core:
        for m in it["moods"]:
            counts[m] = counts.get(m, 0) + 1
    main = max(counts, key=counts.get)
    name = closet.moods[main].split(" (")[0]
    return score, f"{name} 무드 중심" if counts[main] >= len(core) - 1 else "무드가 무난하게 섞임"


def weather_fit(closet, core, temp):
    """날씨는 점수가 아니라 필터입니다. 목표 보온도와의 차이(0이면 딱 맞음)를 돌려줍니다."""
    target = target_warmth(closet, temp)
    by_slot = {it["slot"]: it for it in core}
    upper = max(by_slot[s]["warmth"] for s in ("outer", "top") if s in by_slot)
    if upper < target:
        why = "조금 춥게 느껴질 수 있음"
    elif upper > target:
        why = "조금 덥게 느껴질 수 있음"
    else:
        why = "기온에 맞는 두께"
    if by_slot["bottom"]["warmth"] <= target - 2:
        why += ", 하의는 얇은 편"
    return abs(upper - target), why


def score_outfit(closet, ctx, outfit):
    core = outfit.core
    parts = {
        "color": score_color(closet, core),
        "formality": score_formality(closet, core, ctx.tpo),
        "fit": score_fit(core),
        "mood": score_mood(closet, core),
    }
    weights = closet.scoring["weights"]
    outfit.scores = {k: round(v[0], 3) for k, v in parts.items()}
    outfit.reasons = {k: v[1] for k, v in parts.items()}
    outfit.total = round(sum(weights[k] * v[0] for k, v in parts.items())
                         / sum(weights[k] for k in parts), 4)
    outfit.weather_gap, outfit.reasons["weather"] = weather_fit(closet, core, ctx.temp)
    return outfit


# ---------- 3. 액세서리 ----------

def pick_accessory(closet, outfit, accessories):
    """코어 코디에 가장 잘 맞는 액세서리 하나. 맞는 것이 없으면 None."""
    core = outfit.core
    mean = sum(it["formality"] for it in core) / len(core)
    used = {closet.colors[it["color"]["primary"]].get("family") for it in core}
    best, best_score = None, 0.6
    for acc in accessories:
        mood = sum(mood_relation(closet, acc["moods"], it["moods"]) for it in core) / len(core)
        formality = max(0.0, 1 - abs(acc["formality"] - mean) / 2)
        color = closet.colors[acc["color"]["primary"]]
        # 기본색이거나 이미 쓴 계열이면 안전, 코디에 유채색이 없으면 포인트로 허용
        harmony = 1.0 if color["neutral"] or color.get("family") in used else \
            0.9 if used == {None} else 0.3
        score = 0.4 * mood + 0.3 * formality + 0.3 * harmony
        if score > best_score:
            best, best_score = acc, score
    return best


# ---------- 4. 순위 ----------

def recommend(closet, ctx, n=3):
    """상위 n개 코디.

    날씨가 최우선입니다. 기온에 딱 맞는 조합(weather_gap 0)을 먼저 다 보고,
    그것만으로 n개가 안 될 때에만 한 단계 덜 맞는 조합으로 넓힙니다.
    서로 한 벌만 다른 코디는 건너뛰어 다양하게 고릅니다.
    """
    cands = candidates(closet, ctx)
    outers = outer_options(closet, ctx, cands.get("outer", []))
    outfits = []
    for outer, top, bottom, shoes in product(
            outers, cands.get("top", []), cands.get("bottom", []), cands.get("shoes", [])):
        items = {"top": top, "bottom": bottom, "shoes": shoes}
        if outer:
            items["outer"] = outer
        outfits.append(score_outfit(closet, ctx, Outfit(items=items)))
    outfits.sort(key=lambda o: (o.weather_gap, -o.total))

    picked = []
    for o in outfits:
        ids = {it["id"] for it in o.core}
        if all(len(ids & {it["id"] for it in p.core}) < max(len(ids), len(p.core)) - 1
               for p in picked):
            picked.append(o)
            if len(picked) == n:
                break
    for o in picked:
        acc = pick_accessory(closet, o, cands.get("accessory", []))
        if acc:
            o.items["accessory"] = acc
    return picked
