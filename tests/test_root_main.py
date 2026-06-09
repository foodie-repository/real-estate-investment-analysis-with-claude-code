from main import main


def test_root_main_describes_current_runnable_projects(capsys):
    main()

    output = capsys.readouterr().out

    assert "아직 골격" not in output
    assert "Part04~10" in output
    assert "uv run streamlit run projects/part08_kb_dashboard/dashboard/app.py" in output
    assert "uv run streamlit run projects/part09_trade_map/dashboard/app.py" in output
    assert "uv run streamlit run projects/part10_price_volume/dashboard/app.py" in output
