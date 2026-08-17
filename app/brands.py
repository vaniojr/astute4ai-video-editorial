"""Carregamento de Brand Profile (`brands/<slug>/brand.toml`).

Único módulo do projeto que faz parsing de `brand.toml` — `app/project.py`
(validação do `--brand` no `init`) e as futuras etapas de editorialização e
thumbnail sempre passam por `load_brand()`/`list_brands()`, nunca leem o
TOML diretamente.

Todo projeto tem um profile (nunca `None`); `generic` é o profile neutro,
sem logo/CTA/assets — processamento normal sem identidade de marca.
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

_BRAND_FILENAME = "brand.toml"


class BrandError(Exception):
    """Erro acionável ao carregar um Brand Profile."""


class BrandNotFoundError(BrandError):
    """`--brand` não corresponde a nenhum profile cadastrado em `brands/`."""


class BrandConfigError(BrandError):
    """`brand.toml` tem uma feature habilitada sem a configuração/asset correspondente."""


@dataclass(frozen=True)
class BrandColors:
    primary: Optional[str] = None
    background: Optional[str] = None
    text: Optional[str] = None
    accent: Optional[str] = None


@dataclass(frozen=True)
class BrandFeatures:
    logo_enabled: bool = False
    intro_enabled: bool = False
    outro_enabled: bool = False
    cta_enabled: bool = False
    source_attribution_enabled: bool = False


@dataclass(frozen=True)
class BrandAssets:
    logo: Optional[Path] = None
    intro: Optional[Path] = None
    outro: Optional[Path] = None
    primary_font: Optional[Path] = None


@dataclass(frozen=True)
class BrandVideoConfig:
    cta_text: Optional[str] = None
    cta_image: Optional[Path] = None
    cta_video: Optional[Path] = None


@dataclass(frozen=True)
class BrandThumbnailConfig:
    width: int = 1280
    height: int = 720
    style: Optional[str] = None


@dataclass(frozen=True)
class Brand:
    slug: str
    name: str
    colors: BrandColors
    features: BrandFeatures
    assets: BrandAssets
    video: BrandVideoConfig
    thumbnail: BrandThumbnailConfig


def list_brands(brands_dir: Path) -> List[str]:
    """Lista os slugs de profiles cadastrados (diretórios com `brand.toml`)."""
    if not brands_dir.is_dir():
        return []
    return sorted(
        entry.name
        for entry in brands_dir.iterdir()
        if entry.is_dir() and (entry / _BRAND_FILENAME).is_file()
    )


def load_brand(slug: str, brands_dir: Path) -> Brand:
    brand_dir = brands_dir / slug
    toml_path = brand_dir / _BRAND_FILENAME
    if not toml_path.is_file():
        available = list_brands(brands_dir)
        raise BrandNotFoundError(
            f"Brand Profile '{slug}' não encontrado em '{brands_dir}'.\n\n"
            f"Disponíveis: {', '.join(available) if available else '(nenhum)'}"
        )

    with toml_path.open("rb") as fh:
        data = tomllib.load(fh)

    brand_section = data.get("brand", {})
    name = brand_section.get("name")
    if not name:
        raise BrandConfigError(f"'{toml_path}' não define 'brand.name'.")

    colors = BrandColors(**data.get("colors", {}))
    features = BrandFeatures(**data.get("features", {}))

    raw_assets = data.get("assets", {})
    assets = BrandAssets(
        logo=_resolve_asset_path(brand_dir, raw_assets.get("logo")),
        intro=_resolve_asset_path(brand_dir, raw_assets.get("intro")),
        outro=_resolve_asset_path(brand_dir, raw_assets.get("outro")),
        primary_font=_resolve_asset_path(brand_dir, data.get("typography", {}).get("primary_font")),
    )

    raw_video = data.get("video", {})
    video = BrandVideoConfig(
        cta_text=raw_video.get("cta_text"),
        cta_image=_resolve_asset_path(brand_dir, raw_video.get("cta_image")),
        cta_video=_resolve_asset_path(brand_dir, raw_video.get("cta_video")),
    )
    thumbnail = BrandThumbnailConfig(**data.get("thumbnail", {}))

    _validate_features(toml_path, features, assets, video)

    return Brand(
        slug=slug,
        name=name,
        colors=colors,
        features=features,
        assets=assets,
        video=video,
        thumbnail=thumbnail,
    )


def _resolve_asset_path(brand_dir: Path, raw_path: Optional[str]) -> Optional[Path]:
    if not raw_path:
        return None
    return brand_dir / raw_path


def _validate_features(
    toml_path: Path, features: BrandFeatures, assets: BrandAssets, video: BrandVideoConfig
) -> None:
    """Cada feature habilitada exige sua configuração/asset — nunca falha em silêncio."""
    if features.logo_enabled and (assets.logo is None or not assets.logo.is_file()):
        raise BrandConfigError(
            f"'{toml_path}': logo_enabled=true mas 'assets.logo' não está configurado "
            f"ou o arquivo não existe ({assets.logo})."
        )
    if features.intro_enabled and (assets.intro is None or not assets.intro.is_file()):
        raise BrandConfigError(
            f"'{toml_path}': intro_enabled=true mas 'assets.intro' não está configurado "
            f"ou o arquivo não existe ({assets.intro})."
        )
    if features.outro_enabled and (assets.outro is None or not assets.outro.is_file()):
        raise BrandConfigError(
            f"'{toml_path}': outro_enabled=true mas 'assets.outro' não está configurado "
            f"ou o arquivo não existe ({assets.outro})."
        )
    if features.cta_enabled:
        configured = [
            name
            for name, value in (
                ("video.cta_text", video.cta_text),
                ("video.cta_image", video.cta_image),
                ("video.cta_video", video.cta_video),
            )
            if value
        ]
        if not configured:
            raise BrandConfigError(
                f"'{toml_path}': cta_enabled=true mas nenhuma opção de conteúdo do CTA foi "
                "configurada (defina exatamente uma entre 'video.cta_text', 'video.cta_image' "
                "ou 'video.cta_video')."
            )
        if len(configured) > 1:
            raise BrandConfigError(
                f"'{toml_path}': cta_enabled=true mas mais de uma opção de conteúdo do CTA foi "
                f"configurada ({', '.join(configured)}) — defina exatamente uma entre "
                "'video.cta_text', 'video.cta_image' ou 'video.cta_video'."
            )
        if video.cta_image is not None and not video.cta_image.is_file():
            raise BrandConfigError(
                f"'{toml_path}': 'video.cta_image' configurado mas o arquivo não existe "
                f"({video.cta_image})."
            )
        if video.cta_video is not None and not video.cta_video.is_file():
            raise BrandConfigError(
                f"'{toml_path}': 'video.cta_video' configurado mas o arquivo não existe "
                f"({video.cta_video})."
            )
