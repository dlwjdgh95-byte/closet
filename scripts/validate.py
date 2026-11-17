"""옷장 데이터 검증: python3 scripts/validate.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from closet import data  # noqa: E402

errors = data.validate()
if errors:
    print("\n".join(errors))
    sys.exit(1)
c = data.load()
print(f"OK: 옷 {len(c.items)}벌, 브랜드 {len(c.brands)}개")
