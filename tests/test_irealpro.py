import urllib.parse as _up

from notare.irealpro import score_to_irealpro_url


def _assert_ireal_url_components(url: str) -> None:
    # URL should be percent-encoded; decode for checks
    decoded = _up.unquote(url)
    assert decoded.startswith("irealbook://")
    parts = decoded[len("irealbook://"):].split("=")
    # Expect exactly 6 components: title, composer, style, key, n, progression
    assert len(parts) == 6
    title, composer, style, key_sig, n_token, progression = parts
    assert title.strip() != ""
    assert composer.strip() != ""
    assert style.strip() != ""
    assert key_sig.strip() != ""
    assert n_token.strip() == "n"
    assert progression.strip() != ""


def test_irealpro_c_scale_progression():
    url = score_to_irealpro_url(
        source="tests/data/c_scale_chords.musicxml",
        style="Test Style",
    )
    _assert_ireal_url_components(url)


def test_irealpro_c_iv_v_with_endings():
    url = score_to_irealpro_url(
        source="tests/data/c_iv_v_endings.musicxml",
        style="Test Style",
    )
    _assert_ireal_url_components(url)


def test_irealpro_three_sections_quality_and_inversion():
    url = score_to_irealpro_url(
        source="tests/data/three_sections_quality_inversion.musicxml",
        style="Test Style",
    )
    _assert_ireal_url_components(url)


def test_irealpro_with_coda():
    url = score_to_irealpro_url(
        source="tests/data/with_coda.musicxml",
        style="Test Style",
    )
    _assert_ireal_url_components(url)


def test_irealpro_dc_al_fine_time_change():
    url = score_to_irealpro_url(
        source="tests/data/dc_al_fine_time_change.musicxml",
        style="Test Style",
    )
    _assert_ireal_url_components(url)


def test_irealpro_all_roots_and_qualities():
    url = score_to_irealpro_url(
        source="tests/data/all_roots_and_qualities.musicxml",
        style="Test Style",
    )
    _assert_ireal_url_components(url)
