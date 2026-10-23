from projects.chapter04_tracking import main


def test_run_prints_console_table_when_sheet_credentials_are_incomplete(
    monkeypatch,
    capsys,
):
    """시트 ID와 키 중 하나라도 없으면 결과를 잃지 않고 화면에 출력한다."""
    monkeypatch.setattr(
        main,
        "get_all",
        lambda: [
            {
                "시군구": "서울특별시 강동구 고덕동",
                "단지명": "고덕그라시움",
                "전용면적": 84.24,
            }
        ],
    )
    monkeypatch.setattr(
        main,
        "get_tracking_data",
        lambda _: [
            {
                "시군구": "강동구",
                "읍면동": "고덕동",
                "단지명": "고덕그라시움",
                "전용면적": 84.24,
                "평형": 34,
                "세대수": 4932,
                "건축년도": 2019,
                "연식": 7,
                "기준월": 202511,
                "데이터최신월": 202512,
                "잠정수치": True,
                "최근매매가": 250_000,
                "매매거래건수": 2,
                "직거래제외건수": 1,
                "매매전월대비": None,
                "최근전세가": 95_000,
                "신규전세거래건수": 3,
                "갱신전세가": 85_000,
                "갱신전세거래건수": 4,
                "전세전월대비": None,
                "매매전세갭": 155_000,
                "갭전월대비": None,
                "전세가율": 38.0,
                "전세가율전월대비": None,
                "전고점": 260_000,
                "전고점대비": -3.8,
                "전월기준월": 202510,
                "전월매매": None,
                "전월전세": None,
                "전월갭": None,
                "전월전세가율": None,
                "비고": "최근 1~2개월 잠정 수치",
            }
        ],
    )
    monkeypatch.setattr(main, "SHEET_ID", "sheet-id")
    monkeypatch.setattr(main, "SERVICE_ACCOUNT_KEY", None, raising=False)

    def fail_if_sheet_is_called(_):
        raise AssertionError("서비스 계정 키가 없는데 구글 시트 출력을 시도했습니다.")

    monkeypatch.setattr(main, "update_sheet", fail_if_sheet_is_called)

    main.run()

    output = capsys.readouterr().out
    assert "구글 시트 미설정 → 콘솔 출력" in output
    assert "관심단지 시세 트래킹" in output
