from gasaudit.i18n import TRANSLATIONS, translator


def test_uk_and_en_have_identical_keys():
    assert set(TRANSLATIONS["UK"]) == set(TRANSLATIONS["EN"])


def test_default_language_is_uk_resolvable():
    t = translator("UK")
    assert t("snap")  # non-empty Ukrainian string
    assert t("snap") != translator("EN")("snap")


def test_interpolation_formats_values():
    t = translator("EN")
    out = t("feasible", town=12.3, unit="mi", lo=5, hi=40)
    assert "12.3" in out and "mi" in out


def test_unknown_key_falls_back_to_raw_key():
    t = translator("EN")
    assert t("no_such_key_xyz") == "no_such_key_xyz"
