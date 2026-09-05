"""
전처리 분류 로직 테스트 (DuckDB 연결 없이 경계값 검증)

SQL CTE와 동일한 분류 로직을 Python으로 재현하여 테스트한다.
"""
from src.config import CURRENT_YEAR


def classify_면적대(전용면적: float) -> str:
    """전용면적 → 전용면적_구분 (테스트용 Python 구현)"""
    if 전용면적 <= 40:
        return "초소형"
    elif 전용면적 <= 60:
        return "소형"
    elif 전용면적 <= 85:
        return "중소형"
    elif 전용면적 <= 135:
        return "중대형"
    else:
        return "대형"


def classify_평형대(전용면적: float) -> str:
    """전용면적 → 평형대_구분 (테스트용 Python 구현)"""
    추정평형 = 전용면적 * 0.4
    if 추정평형 < 10:
        return "10평 미만"
    elif 추정평형 < 20:
        return "10평대"
    elif 추정평형 < 30:
        return "20평대"
    elif 추정평형 < 40:
        return "30평대"
    elif 추정평형 < 50:
        return "40평대"
    elif 추정평형 < 60:
        return "50평대"
    else:
        return "60평 이상"


def classify_연식(건축년도: int) -> tuple[int, str]:
    """건축년도 → (연식, 연식_구분) (테스트용 Python 구현)"""
    연식 = max(CURRENT_YEAR - 건축년도, 1)
    if 연식 < 5:
        return 연식, "5년 미만"
    elif 연식 < 10:
        return 연식, "5~10년"
    elif 연식 < 20:
        return 연식, "10~20년"
    elif 연식 < 30:
        return 연식, "20~30년"
    else:
        return 연식, "30년 이상"


# =============================================================================
# 면적대 테스트
# =============================================================================
class TestClassify면적대:
    def test_초소형_경계(self):
        assert classify_면적대(39.9) == "초소형"
        assert classify_면적대(40.0) == "초소형"  # 40㎡ 이하

    def test_소형_경계(self):
        assert classify_면적대(40.1) == "소형"
        assert classify_면적대(60.0) == "소형"    # 60㎡ 이하

    def test_중소형_경계(self):
        assert classify_면적대(60.1) == "중소형"
        assert classify_면적대(85.0) == "중소형"   # 85㎡ 이하

    def test_중대형_경계(self):
        assert classify_면적대(85.1) == "중대형"
        assert classify_면적대(135.0) == "중대형"  # 135㎡ 이하

    def test_대형(self):
        assert classify_면적대(135.1) == "대형"
        assert classify_면적대(200.0) == "대형"


# =============================================================================
# 평형대 테스트
# =============================================================================
class TestClassify평형대:
    def test_10평_미만(self):
        """전용면적 24㎡ → 추정평형 9.6 → 10평 미만"""
        assert classify_평형대(24.0) == "10평 미만"

    def test_20평대(self):
        """전용면적 59㎡ → 추정평형 23.6 → 20평대"""
        assert classify_평형대(59.0) == "20평대"

    def test_30평대(self):
        """전용면적 84㎡ → 추정평형 33.6 → 30평대"""
        assert classify_평형대(84.0) == "30평대"

    def test_60평_이상(self):
        """전용면적 160㎡ → 추정평형 64 → 60평 이상"""
        assert classify_평형대(160.0) == "60평 이상"


# =============================================================================
# 연식 테스트
# =============================================================================
class TestClassify연식:
    def test_신축(self):
        건축년도 = CURRENT_YEAR - 2
        연식, 구분 = classify_연식(건축년도)
        assert 연식 == 2
        assert 구분 == "5년 미만"

    def test_5_10년(self):
        건축년도 = CURRENT_YEAR - 6
        연식, 구분 = classify_연식(건축년도)
        assert 연식 == 6
        assert 구분 == "5~10년"

    def test_30년_이상(self):
        건축년도 = CURRENT_YEAR - 36
        연식, 구분 = classify_연식(건축년도)
        assert 연식 == 36
        assert 구분 == "30년 이상"

    def test_최소_1년(self):
        """미래 건축년도도 최소 1년"""
        건축년도 = CURRENT_YEAR + 1
        연식, 구분 = classify_연식(건축년도)
        assert 연식 == 1
        assert 구분 == "5년 미만"
