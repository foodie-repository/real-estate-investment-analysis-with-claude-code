from main import main


def test_root_main_describes_current_runnable_projects(capsys):
    main()

    output = capsys.readouterr().out

    assert "아직 골격" not in output
    assert "4장부터 9장까지" in output
    assert "uv run streamlit run projects/chapter06_kb_dashboard/dashboard/app.py" in output
    assert "uv run streamlit run projects/chapter07_price_gap_table/dashboard/app.py" in output
    assert "uv run streamlit run projects/chapter08_trade_map/dashboard/app.py" in output
    assert "uv run streamlit run projects/chapter09_price_volume/dashboard/app.py" in output
