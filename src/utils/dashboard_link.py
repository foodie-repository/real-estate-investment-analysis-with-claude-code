"""가격·갭 → 가격·거래량 연결에 사용하는 작은 버전별 URL 계약."""
import base64
import json
import math
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

MAX_TARGETS = 10
BANDS = ('10평 미만', '10평대', '20평대', '30평대', '40평대', '50평대', '60평 이상')


def _range(value, name, month=False):
    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f'{name} 범위를 확인하세요.')
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in value):
        raise ValueError(f'{name} 범위를 확인하세요.')
    if value[0] > value[1]:
        raise ValueError(f'{name} 범위를 확인하세요.')
    if month and any(not isinstance(x, int) or not 1900 <= x//100 <= 2100 or not 1 <= x%100 <= 12 for x in value):
        raise ValueError('기간을 확인하세요.')
    return tuple(value)


def validate_selection(data):
    if not isinstance(data, dict) or data.get('v') != 1:
        raise ValueError('지원하지 않는 연결 정보입니다. 비교표에서 링크를 다시 여세요.')
    targets = data.get('targets')
    if not isinstance(targets, (list, tuple)) or not 1 <= len(targets) <= MAX_TARGETS:
        raise ValueError(f'비교 대상은 1~{MAX_TARGETS}개를 선택하세요.')
    clean = []
    for target in targets:
        if not isinstance(target, (list, tuple)) or len(target) != 6:
            raise ValueError('단지·주소·평형대 정보를 확인하세요.')
        if any(not isinstance(x, str) or len(x) > 300 or any(ord(c)<32 for c in x) for x in target):
            raise ValueError('단지·주소·평형대 정보를 확인하세요.')
        if any(not target[i].strip() for i in (0, 1, 3, 4)) or target[5] not in BANDS:
            raise ValueError('단지·주소·평형대 정보를 확인하세요.')
        item = tuple(target)
        if item not in clean:
            clean.append(item)
    area = _range(data.get('area'), '전용면적')
    if area and area[0] < 0:
        raise ValueError('전용면적은 0 이상이어야 합니다.')
    return dict(v=1, targets=clean, area=area,
                period=_range(data.get('period'), '기간', month=True),
                floor=_range(data.get('floor'), '층'))


def encode_selection(targets, area=None, period=None, floor=None):
    # 점·행이 중복 선택되어도 링크에는 동일 대상을 한 번만 싣는다.
    targets = list(dict.fromkeys(tuple(t) for t in targets))
    data = validate_selection(dict(v=1, targets=targets, area=area, period=period, floor=floor))
    raw = json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode()
    token = base64.urlsafe_b64encode(raw).decode().rstrip('=')
    if len(token) > 16000:
        raise ValueError('연결 정보가 너무 깁니다. 선택한 대상 수를 줄여주세요.')
    return token


def decode_selection(token):
    try:
        if not isinstance(token, str) or not token or len(token) > 16000:
            raise ValueError()
        raw = base64.b64decode(token + '='*(-len(token)%4), altchars=b'-_', validate=True)
        return validate_selection(json.loads(raw))
    except (ValueError, TypeError, UnicodeError) as exc:
        raise ValueError('연결 정보가 올바르지 않습니다. 가격·갭 대시보드에서 다시 선택하세요.') from exc


def selection_url(base, token):
    parts = urlsplit(base.strip())
    if parts.scheme not in ('http', 'https') or not parts.netloc or parts.username or parts.password:
        raise ValueError('실행 중인 가격·거래량 대시보드의 http(s) 주소를 입력하세요.')
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != 'selection']
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query+[('selection', token)]), ''))


def target_label(target, options=()):
    sido, gu, dong, name, address, band = target
    region = dong
    matches = [item for item in options if (item[2], item[3], item[5]) == (dong, name, band)]
    if len({item[:2] for item in matches}) > 1:
        region = f'{gu} {dong}'
        if len({item[0] for item in matches if item[1] == gu}) > 1:
            region = f'{sido} {gu} {dong}'
    return f'{name} · {band} ({region.strip()})' if region.strip() else f'{name} · {band}'
