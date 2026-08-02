"""M-RI-14: PIN normalization (audit/pins.py)."""
import pytest

from audit import pins


def test_cook_format_accepts_hyphenated_cook_pin():
    assert pins.is_cook_format("29-02-408-053-0000")


@pytest.mark.parametrize("bad", [
    "4545",                      # malformed value present in the real inventory
    "21-14-02-210-010-0000",     # Will County six-group format
    "30-07-15-221-004-0000",     # Will County six-group format
    "29024080530000",            # unhyphenated
    "", None,
])
def test_cook_format_rejects_non_cook(bad):
    assert not pins.is_cook_format(bad)


def test_to14_round_trip():
    assert pins.to14("29-02-408-053-0000") == "29024080530000"
    assert pins.to_hyphen("29024080530000") == "29-02-408-053-0000"


def test_to14_raises_on_non_cook():
    with pytest.raises(ValueError):
        pins.to14("21-14-02-210-010-0000")
    with pytest.raises(ValueError):
        pins.to_hyphen("4545")
