import pytest

from app.brands import BrandConfigError, BrandNotFoundError, list_brands, load_brand


def _write_brand(brands_dir, slug, content):
    brand_dir = brands_dir / slug
    brand_dir.mkdir(parents=True)
    (brand_dir / "brand.toml").write_text(content, encoding="utf-8")
    return brand_dir


def test_load_brand_generic_minimal(tmp_path):
    brands_dir = tmp_path / "brands"
    _write_brand(brands_dir, "generic", '[brand]\nslug = "generic"\nname = "Genérico"\n')

    brand = load_brand("generic", brands_dir)

    assert brand.slug == "generic"
    assert brand.name == "Genérico"
    assert brand.features.logo_enabled is False
    assert brand.features.cta_enabled is False
    assert brand.assets.logo is None


def test_load_brand_with_full_sections(tmp_path):
    brands_dir = tmp_path / "brands"
    _write_brand(
        brands_dir,
        "bussola-politica",
        """
[brand]
slug = "bussola-politica"
name = "Bússola Política"

[colors]
primary = "#F5C400"
background = "#090909"

[features]
cta_enabled = true
source_attribution_enabled = true

[video]
cta_text = "BÚSSOLA POLÍTICA"

[thumbnail]
width = 1280
height = 720
style = "political-editorial"
""",
    )

    brand = load_brand("bussola-politica", brands_dir)

    assert brand.colors.primary == "#F5C400"
    assert brand.features.cta_enabled is True
    assert brand.video.cta_text == "BÚSSOLA POLÍTICA"
    assert brand.thumbnail.style == "political-editorial"


def test_load_brand_raises_when_slug_unknown(tmp_path):
    brands_dir = tmp_path / "brands"
    _write_brand(brands_dir, "generic", '[brand]\nslug = "generic"\nname = "Genérico"\n')

    with pytest.raises(BrandNotFoundError) as exc_info:
        load_brand("nao-existe", brands_dir)
    assert "generic" in str(exc_info.value)


def test_load_brand_raises_when_logo_enabled_without_asset(tmp_path):
    brands_dir = tmp_path / "brands"
    _write_brand(
        brands_dir,
        "sem-logo",
        '[brand]\nslug = "sem-logo"\nname = "Sem Logo"\n\n[features]\nlogo_enabled = true\n',
    )

    with pytest.raises(BrandConfigError):
        load_brand("sem-logo", brands_dir)


def test_load_brand_raises_when_cta_enabled_without_text(tmp_path):
    brands_dir = tmp_path / "brands"
    _write_brand(
        brands_dir,
        "sem-cta",
        '[brand]\nslug = "sem-cta"\nname = "Sem CTA"\n\n[features]\ncta_enabled = true\n',
    )

    with pytest.raises(BrandConfigError):
        load_brand("sem-cta", brands_dir)


def test_load_brand_accepts_logo_when_asset_present(tmp_path):
    brands_dir = tmp_path / "brands"
    brand_dir = _write_brand(
        brands_dir,
        "com-logo",
        '[brand]\nslug = "com-logo"\nname = "Com Logo"\n\n'
        '[features]\nlogo_enabled = true\n\n[assets]\nlogo = "assets/logo.png"\n',
    )
    (brand_dir / "assets").mkdir()
    (brand_dir / "assets" / "logo.png").write_bytes(b"fake png")

    brand = load_brand("com-logo", brands_dir)

    assert brand.assets.logo == brand_dir / "assets" / "logo.png"


def test_list_brands_returns_sorted_slugs(tmp_path):
    brands_dir = tmp_path / "brands"
    _write_brand(brands_dir, "zeta", '[brand]\nslug = "zeta"\nname = "Zeta"\n')
    _write_brand(brands_dir, "alfa", '[brand]\nslug = "alfa"\nname = "Alfa"\n')

    assert list_brands(brands_dir) == ["alfa", "zeta"]


def test_list_brands_empty_when_dir_missing(tmp_path):
    assert list_brands(tmp_path / "nao-existe") == []
