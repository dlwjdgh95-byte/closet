"""실행: python3 -m closet --tpo commute --temp 8"""
import argparse
import json
import sys

from . import data, llm, weather
from .recommend import AXIS_LABELS, CORE_SLOTS, Context, recommend, target_warmth

SLOT_LABELS = {"outer": "아우터", "top": "상의", "bottom": "하의", "shoes": "신발", "accessory": "액세서리"}


def main(argv=None):
    closet = data.load()
    p = argparse.ArgumentParser(prog="closet", description="오늘의 코디 추천")
    p.add_argument("--tpo", required=True, choices=list(closet.tpo),
                   help=", ".join(f"{k}={v['label']}" for k, v in closet.tpo.items()))
    p.add_argument("--temp", type=float, help="체감기온(℃). 생략하면 오늘 날씨를 가져옵니다")
    p.add_argument("--rain", action="store_true", help="비 오는 날")
    p.add_argument("--lat", type=float, default=weather.SEOUL[0])
    p.add_argument("--lon", type=float, default=weather.SEOUL[1])
    p.add_argument("-n", type=int, default=3, help="추천 개수")
    p.add_argument("--json", action="store_true", help="JSON으로 출력")
    p.add_argument("--prompt", action="store_true", help="LLM에 넘길 프롬프트 출력")
    args = p.parse_args(argv)

    temp, rain = args.temp, args.rain
    if temp is None:
        try:
            temp, auto_rain = weather.today(args.lat, args.lon, closet.scoring["rain_probability"])
        except Exception as e:  # 네트워크 오류 등
            sys.exit(f"날씨를 가져오지 못했습니다({e}). --temp로 기온을 직접 넣어 주십시오.")
        rain = rain or auto_rain

    ctx = Context(tpo=args.tpo, temp=temp, rain=rain)
    outfits = recommend(closet, ctx, args.n)

    if args.prompt:
        print(llm.build_prompt(closet, ctx, outfits))
    elif args.json:
        print(json.dumps([{
            "total": o.total, "scores": o.scores, "reasons": o.reasons,
            "weather_gap": o.weather_gap,
            "items": {slot: it["id"] for slot, it in o.items.items()},
        } for o in outfits], ensure_ascii=False, indent=2))
    else:
        print(f"{closet.tpo[ctx.tpo]['label']} / 체감 {temp}℃" + (" / 비" if rain else "")
              + f" / 목표 보온도 {target_warmth(closet, temp)}")
        if not outfits:
            print("조건에 맞는 코디가 없습니다.")
        for i, o in enumerate(outfits, 1):
            print(f"\n{i}. 점수 {o.total:.2f}")
            for slot in CORE_SLOTS + ("accessory",):
                it = o.items.get(slot)
                if it:
                    brand = closet.brands.get(it.get("brand"), {}).get("name", "")
                    print(f"   {SLOT_LABELS[slot]:<5} {it['name']}" + (f" ({brand})" if brand else ""))
            print(f"   - 날씨: {o.reasons['weather']}")
            for axis, score in o.scores.items():
                print(f"   - {AXIS_LABELS[axis]} {score:.2f}: {o.reasons[axis]}")


if __name__ == "__main__":
    main()
