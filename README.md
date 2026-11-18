# closet

그날의 TPO와 날씨에 맞춰, 옷장에 있는 옷을 밸런스 있게 조합해 추천하는 개인용 시스템입니다.

```
pip install pyyaml
python3 -m closet --tpo commute --temp 8
```

- 데이터 구조: [docs/data-model.md](docs/data-model.md)
- 추천 로직과 실행 방법: [docs/recommendation.md](docs/recommendation.md)
- 옷장 페이지 만들기: `python3 scripts/build_page.py --standalone` 후 `web/dist/closet.html` 열기
- 옷장 사진·영상: `web/assets/` (바꿀 때 규칙은 [docs/recommendation.md](docs/recommendation.md)의 "옷장 페이지")
- 데이터 검증: `python3 scripts/validate.py`
- 테스트: `python3 -m unittest discover tests`

현재 옷장과 브랜드는 샘플 데이터입니다. 옷은 페이지에서 종류·색·패턴을 따라 그린 그림으로 보이며, 실제 옷을 넣을 때 사진으로 바꿀 예정입니다.
