"""Configuration management."""

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel


class Config(BaseModel):
    """Application configuration."""

    spreadsheet_id: str
    sheet_name: str = "Applications"
    log_level: str = "INFO"
    gmail_query_days: int = 7
    confidence_threshold: float = 0.5


_config: Optional[Config] = None


def load_config(config_path: Optional[Path] = None) -> Config:
    """Load configuration from YAML file."""
    global _config

    if _config is not None:
        return _config

    if config_path is None:
        config_path = Path(__file__).parent.parent / "config" / "config.yaml"

    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}. "
            "Copy config/config.yaml.example to config/config.yaml and fill in your settings."
        )

    with open(config_path) as f:
        data = yaml.safe_load(f)

    _config = Config(**data)
    return _config


def get_config() -> Config:
    """Get the loaded configuration."""
    if _config is None:
        return load_config()
    return _config
