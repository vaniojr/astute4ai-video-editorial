import pytest

from app.timestamps import (
    TimestampAmbiguousError,
    TimestampFormatError,
    TimestampOutOfRangeError,
    parse_timestamp,
    to_relative_seconds,
)

# Duração de referência usada no exemplo da seção 18/30 do PRD (01:45:03).
_VIDEO_DURATION = 1 * 3600 + 45 * 60 + 3


def test_two_parts_mmss_is_unambiguous():
    result = parse_timestamp("29:07", _VIDEO_DURATION)
    assert result.seconds == 29 * 60 + 7
    assert result.adjusted is False


def test_three_parts_with_nonzero_seconds_is_unambiguous_hms():
    result = parse_timestamp("01:12:09", _VIDEO_DURATION)
    assert result.seconds == 1 * 3600 + 12 * 60 + 9
    assert result.adjusted is False


def test_three_parts_trailing_zero_resolves_when_only_mmss_plausible():
    # "29:07:00": 29h seria maior que a duração do vídeo (01:45:03) -> só MM:SS cabe.
    result = parse_timestamp("29:07:00", _VIDEO_DURATION)
    assert result.seconds == 29 * 60 + 7
    assert result.adjusted is True
    assert result.note is not None


def test_three_parts_trailing_zero_accepts_literal_when_it_fits():
    # "00:05:00" já é H:MM:SS canônico (0h 5min 0s) e cabe na duração --
    # não deve suspeitar de corrupção de planilha quando a leitura literal
    # já é plausível.
    result = parse_timestamp("00:05:00", _VIDEO_DURATION)
    assert result.seconds == 5 * 60
    assert result.adjusted is False


def test_three_parts_trailing_zero_accepts_literal_at_exact_duration_boundary():
    result = parse_timestamp("02:00:00", 2 * 3600)
    assert result.seconds == 2 * 3600
    assert result.adjusted is False


def test_three_parts_trailing_zero_ambiguous_when_neither_plausible():
    with pytest.raises(TimestampAmbiguousError):
        parse_timestamp("29:07:00", 1000)  # nem 29h nem 29min cabem em ~16min


def test_three_parts_trailing_zero_ambiguous_without_duration():
    with pytest.raises(TimestampAmbiguousError):
        parse_timestamp("29:07:00", None)


def test_four_parts_drops_spurious_trailing_component():
    result = parse_timestamp("1:12:09:00", _VIDEO_DURATION)
    assert result.seconds == 1 * 3600 + 12 * 60 + 9
    assert result.adjusted is True


def test_four_parts_with_nonzero_trailing_component_is_format_error():
    with pytest.raises(TimestampFormatError):
        parse_timestamp("1:12:09:05", _VIDEO_DURATION)


def test_invalid_text_is_format_error():
    with pytest.raises(TimestampFormatError):
        parse_timestamp("abc", _VIDEO_DURATION)


def test_wrong_number_of_parts_is_format_error():
    with pytest.raises(TimestampFormatError):
        parse_timestamp("1:2:3:4:5", _VIDEO_DURATION)


def test_trivial_zero_timestamp_is_unambiguous():
    result = parse_timestamp("00:00:00", _VIDEO_DURATION)
    assert result.seconds == 0.0
    assert result.adjusted is False


def test_two_parts_out_of_range_raises():
    with pytest.raises(TimestampOutOfRangeError):
        parse_timestamp("999:99", 100)


def test_three_parts_nonzero_seconds_out_of_range_raises():
    with pytest.raises(TimestampOutOfRangeError):
        parse_timestamp("05:00:09", 100)


def test_to_relative_seconds_subtracts_cut_start():
    assert to_relative_seconds(1747.0, 1747.0) == 0.0
    assert to_relative_seconds(1800.0, 1747.0) == 53.0


def test_to_relative_seconds_never_negative():
    assert to_relative_seconds(100.0, 200.0) == 0.0
