"""LLM 단계(선택): 점수 상위 후보 중 최종 선택과 설명을 맡길 때 쓸 프롬프트.

아직 API 호출은 붙이지 않았습니다. 프롬프트만 만들어 두고, 연결은 써 보면서 결정합니다.
"""
from .recommend import AXIS_LABELS, CORE_SLOTS


def build_prompt(closet, ctx, outfits):
    lines = [
        "당신은 개인 스타일리스트입니다. 아래 후보 중 오늘 입기 가장 좋은 코디 하나를 고르고,",
        "이유를 두세 문장으로 설명해 주십시오. 후보에 없는 옷은 쓰지 마십시오.",
        "",
        f"상황: {closet.tpo[ctx.tpo]['label']}, 체감 {ctx.temp}℃" + (", 비" if ctx.rain else ""),
        "",
    ]
    for i, o in enumerate(outfits, 1):
        lines.append(f"후보 {i} (점수 {o.total:.2f})")
        for slot in CORE_SLOTS + ("accessory",):
            it = o.items.get(slot)
            if it:
                brand = closet.brands.get(it.get("brand"), {})
                note = f" / {brand['name']}: {brand['note']}" if brand else ""
                lines.append(f"- {it['name']} [{', '.join(it['moods'])}]{note}")
        lines.append("  " + ", ".join(f"{AXIS_LABELS[k]} {v:.2f}" for k, v in o.scores.items())
                     + f", 날씨: {o.reasons['weather']}")
        lines.append("")
    return "\n".join(lines)
