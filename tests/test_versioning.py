from app.versioning import format_version, next_version_number


def test_format_version_pads_to_three_digits():
    assert format_version(1) == "v001"
    assert format_version(42) == "v042"


def test_next_version_number_starts_at_one_when_dir_missing(tmp_path):
    assert next_version_number(tmp_path / "nao-existe", "*.png") == 1


def test_next_version_number_starts_at_one_when_no_matches(tmp_path):
    tmp_path.mkdir(exist_ok=True)
    assert next_version_number(tmp_path, "*.png") == 1


def test_next_version_number_returns_max_plus_one(tmp_path):
    (tmp_path / "thumbnail_v001.png").write_bytes(b"a")
    (tmp_path / "thumbnail_v002.png").write_bytes(b"a")

    assert next_version_number(tmp_path, "*.png") == 3


def test_next_version_number_does_not_fill_gaps(tmp_path):
    (tmp_path / "thumbnail_v001.png").write_bytes(b"a")
    (tmp_path / "thumbnail_v003.png").write_bytes(b"a")

    assert next_version_number(tmp_path, "*.png") == 4


def test_next_version_number_ignores_files_without_version_pattern(tmp_path):
    (tmp_path / "selected.png").write_bytes(b"a")

    assert next_version_number(tmp_path, "*.png") == 1
