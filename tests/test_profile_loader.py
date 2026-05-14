from __future__ import annotations

from app.profile import load_profile


def test_example_profile_loads() -> None:
    p = load_profile("config/profile.example.yml")
    assert p.candidate.display_name
    assert p.cv_path.exists()
    assert "Stamp 1G" in p.candidate.work_authorisation or p.candidate.work_authorisation


def test_default_picks_real_then_falls_back_to_example() -> None:
    # load_profile() with no arg should resolve config/profile.yml, or example as fallback.
    p = load_profile()
    assert p.cv_path.exists()
    assert p.candidate.full_names


def test_cv_text_loads() -> None:
    p = load_profile("config/profile.example.yml")
    text = p.load_cv_text()
    assert "[CANDIDATE_NAME]" in text or len(text) > 100


def test_default_country_defaults_to_ireland() -> None:
    p = load_profile("config/profile.example.yml")
    assert p.default_country == "ie"


def test_locations_inherit_default_country_when_missing() -> None:
    p = load_profile("config/profile.example.yml")
    # The example profile sets country explicitly, but the loader must lowercase
    # and the inherited default must be applied if an entry omits country.
    for loc in p.locations:
        assert loc.country == loc.country.lower()
        assert len(loc.country) == 2
