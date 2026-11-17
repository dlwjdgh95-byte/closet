# closet

그날의 TPO와 날씨에 맞춰, 옷장에 있는 옷을 밸런스 있게 조합해 추천하는 개인용 시스템입니다.

```
pip install pyyaml
python3 -m closet --tpo commute --temp 8
```

- 데이터 구조: [docs/data-model.md](docs/data-model.md)
- 추천 로직과 실행 방법: [docs/recommendation.md](docs/recommendation.md)
- 데이터 검증: `python3 scripts/validate.py`
- 테스트: `python3 -m unittest discover tests`

현재 옷장과 브랜드는 샘플 데이터입니다.
