"""Presentation-only helpers for TerraLoop's knowledge module.

This module does not score, rank, filter, or recommend rotations. It formats
values already produced by the decision engine/API and looks up documented
crop metadata from crops.csv.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, Mapping, Optional


KNOWLEDGE_DIR = Path(__file__).resolve().parent
CROP_TABLE_PATH = KNOWLEDGE_DIR / "crops.csv"
TEMPLATE_DIR = KNOWLEDGE_DIR / "templates"


def load_crop_table(path: Path = CROP_TABLE_PATH) -> Dict[str, Dict[str, Any]]:
    """Load crop metadata keyed by crop_id; values remain source-traceable."""
    crops: Dict[str, Dict[str, Any]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        for row in csv.DictReader(csv_file):
            row["is_legume"] = row.get("is_legume", "").strip().lower() == "true"
            for field in ("duration_min_days", "duration_max_days", "tnau_reference_water_mm"):
                value = row.get(field, "").strip()
                row[field] = int(value) if field != "tnau_reference_water_mm" and value else (
                    float(value) if value else None
                )
            crops[row["crop_id"]] = row
    return crops


def _display(value: Any, missing: str = "Not provided") -> Any:
    """Return a display fallback without inventing a value."""
    return missing if value is None or value == "" else value


def build_explanation_context(engine_result: Mapping[str, Any]) -> Dict[str, Any]:
    """Prepare template context while preserving engine-produced values.

    Expected top-level keys: farm, options, climate, trust_checks, limits_note.
    No scores, labels, verdicts, or recommendations are calculated here.
    """
    required = ("farm", "options", "climate", "trust_checks", "limits_note")
    missing = [key for key in required if key not in engine_result]
    if missing:
        raise ValueError(
            "Engine result is missing required fields: " + ", ".join(missing)
        )

    # Copy containers for safe presentation; do not mutate the engine result.
    farm = dict(engine_result["farm"])
    climate = dict(engine_result["climate"])
    trust_checks = dict(engine_result["trust_checks"])
    options = [dict(option) for option in engine_result["options"]]

    farm["soil_ph"] = _display(farm.get("soil_ph"))
    farm["soil_ec"] = _display(farm.get("soil_ec"))
    farm["latitude"] = _display(farm.get("latitude"))
    farm["longitude"] = _display(farm.get("longitude"))

    # Leave scores, traffic-light values, explanations and trust-check text
    # exactly as supplied by the decision engine.
    return {
        "farm": farm,
        "options": options,
        "climate": climate,
        "trust_checks": trust_checks,
        "limits_note": engine_result["limits_note"],
    }


def get_crop_metadata(crop_id: str) -> Optional[Dict[str, Any]]:
    """Return documented crop-table metadata, or None for an unknown crop."""
    return load_crop_table().get(crop_id)


def render_explanation(
    engine_result: Mapping[str, Any], language: str = "en"
) -> str:
    """Render the engine result in English or Tamil using a Jinja2 template."""
    if language not in {"en", "ta"}:
        raise ValueError("language must be 'en' or 'ta'")

    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape
    except ImportError as error:
        raise RuntimeError(
            "Jinja2 is required to render TerraLoop explanation templates."
        ) from error

    environment = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(enabled_extensions=("html", "xml")),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = environment.get_template(f"{language}.j2")
    context = build_explanation_context(engine_result)

    # Translate only fixed engine status tokens for display. Scores, ranking,
    # explanations, trust messages and verdicts remain exactly engine-owned.
    if language == "ta":
        status_labels = {
            "green": "பச்சை",
            "yellow": "மஞ்சள்",
            "red": "சிவப்பு",
            "solid": "உறுதியானது",
            "mixed": "கலந்த ஆதாரம்",
            "fragile": "பலவீனமான ஆதாரம்",
            "not_calculated": "கணக்கிடப்படவில்லை",
        }
        for option in context["options"]:
            for field in ("water", "soil", "cost_risk"):
                value = option.get(field)
                if isinstance(value, str):
                    option[field] = status_labels.get(value.lower(), value)
        agreement = context["trust_checks"].get("source_agreement")
        if isinstance(agreement, dict):
            value = agreement.get("status")
            if isinstance(value, str):
                agreement["status"] = status_labels.get(value.lower(), value)

    return template.render(**context)
