import os

def test_frontend_files_exist():
    current_dir = os.path.dirname(__file__)
    index_path = os.path.join(current_dir, "index.html")
    assert os.path.exists(index_path), "index.html must exist in frontend_ui"

def test_index_content():
    current_dir = os.path.dirname(__file__)
    index_path = os.path.join(current_dir, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "Tailwind" in content or "tailwindcss" in content
    assert "Alpine" in content or "alpine" in content
    assert "wavesurfer" in content.lower()
    assert 'id="waveform"' in content
    assert 'x-data="melodyApp()"' in content
