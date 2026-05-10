from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union

from src.core.exceptions import ConfigError
from src.document import Document

logger = logging.getLogger(__name__)

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not YAML_AVAILABLE:
        raise ConfigError("PyYAML is required to load YAML config files")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_config(path: Union[str, Path]) -> Dict[str, Any]:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")

    suffix = path.suffix.lower()
    loaders = {
        ".yaml": _load_yaml,
        ".yml": _load_yaml,
        ".json": _load_json,
    }

    loader = loaders.get(suffix)
    if loader is None:
        raise ConfigError(f"Unsupported config format: {suffix} (use .yaml, .yml, or .json)")

    config = loader(path)
    logger.info("Loaded config from %s", path)
    return config


def _parse_stages(config: Dict[str, Any]) -> list[str]:
    stages_config = config.get("pipeline", {}).get("stages", [])
    if not stages_config:
        stages_config = config.get("stages", [])

    names: list[str] = []
    for entry in stages_config:
        if isinstance(entry, str):
            names.append(entry)
        elif isinstance(entry, dict):
            names.append(entry.get("name", ""))
    return [n for n in names if n]


def run_from_config(
    config_path: Union[str, Path],
    override_input: Optional[str] = None,
) -> Document:
    config = load_config(config_path)

    input_section = config.get("input", {})
    input_path = override_input or input_section.get("path", "")
    input_format = input_section.get("format", "")

    if input_path:
        doc = Document.from_file(input_path)
    elif input_format:
        data = input_section.get("data", "")
        if input_format == "text":
            doc = Document.from_text(data)
        elif input_format == "dict":
            doc = Document.from_dict(data)
        else:
            raise ConfigError(f"Unsupported input format: {input_format}")
    else:
        raise ConfigError("Config must specify 'input.path' or 'input.format'")

    stages = _parse_stages(config)
    if stages:
        doc = doc.run_pipeline(stages)

    return doc
