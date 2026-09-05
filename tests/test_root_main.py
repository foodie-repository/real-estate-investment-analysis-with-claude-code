from main import main


def test_root_main_describes_current_runnable_projects(capsys):
    main()

    output = capsys.readouterr().out

    assert "아직 골격" not in output
    assert "Part04~08" in output
    assert "uv run streamlit run projects/part06_kb_dashboard/dashboard/app.py" in output
    assert "uv run streamlit run projects/part07_trade_map/dashboard/app.py" in output
    assert "uv run streamlit run projects/part08_price_volume/dashboard/app.py" in output
