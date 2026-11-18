"""추천 페이지 만들기: python3 scripts/build_page.py [출력 경로]

조건(TPO × 목표 보온도 × 비)마다 추천을 미리 계산해 web/template.html에 넣습니다.
페이지는 서버 없이 열리는 HTML 한 장과 그 옆 assets 폴더(옷장 사진과 영상)입니다.
옷장 데이터를 바꾸면 다시 실행합니다.
--standalone 을 붙이면 브라우저에서 바로 열 수 있게 문서 틀을 씌웁니다.
"""
import json
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from closet import data  # noqa: E402
from closet.recommend import Context, recommend, target_warmth  # noqa: E402

PER_SCENARIO = 10


def representative_temps(closet):
    """목표 보온도마다 그 구간에 드는 기온 하나."""
    rows = closet.scoring["warmth_by_temp"]
    temps = {}
    for i, row in enumerate(rows):
        temp = row["min_temp"] + 1 if row["min_temp"] > -50 else rows[i - 1]["min_temp"] - 5
        temps[target_warmth(closet, temp)] = temp
    return temps


def weather(closet):
    """AccuWeather 커넥터로 날씨를 불러올 곳과, 비 오는 날로 볼 강수확률."""
    loc = yaml.safe_load((ROOT / "data" / "weather.yaml").read_text(encoding="utf-8"))["location"]
    return {"name": loc["name"], "key": str(loc["accuweather_key"]),
            "rain_probability": closet.scoring["rain_probability"]}


def build():
    closet = data.load()
    scenarios, used = {}, set()
    for tpo in closet.tpo:
        for warmth, temp in representative_temps(closet).items():
            for rain in (False, True):
                outfits = recommend(closet, Context(tpo, temp, rain), PER_SCENARIO)
                scenarios[f"{tpo}|{warmth}|{int(rain)}"] = [{
                    "items": {slot: it["id"] for slot, it in o.items.items()},
                    "total": o.total, "scores": o.scores, "reasons": o.reasons,
                } for o in outfits]
                used |= {it["id"] for o in outfits for it in o.items.values()}
    keep = ("name", "slot", "category", "brand", "color", "pattern", "fit", "material")
    payload = {
        "tpo": {k: v["label"] for k, v in closet.tpo.items()},
        "warmth_by_temp": closet.scoring["warmth_by_temp"],
        "colors": {k: {"label": v["label"], "hex": v["hex"]} for k, v in closet.colors.items()},
        "brands": {k: v["name"] for k, v in closet.brands.items()},
        "items": {it["id"]: {k: it[k] for k in keep if k in it}
                  for it in closet.items if it["id"] in used},
        "scenarios": scenarios,
        "weather": weather(closet),
    }
    template = (ROOT / "web" / "template.html").read_text(encoding="utf-8")
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return template.replace("/*__DATA__*/null", blob)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--standalone"]
    out = Path(args[0]) if args else ROOT / "web" / "dist" / "closet.html"
    page = build()
    if "--standalone" in sys.argv:
        page = ('<!doctype html><html lang="ko"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width, initial-scale=1">'
                '<style>body{margin:0}[hidden]{display:none!important}</style></head><body>'
                + page + "</body></html>")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    shutil.copytree(ROOT / "web" / "assets", out.parent / "assets", dirs_exist_ok=True)
    print(f"{out} ({len(page) // 1024}KB)")
