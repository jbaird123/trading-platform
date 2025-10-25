"""Extract field descriptions from Pydantic models for brief generation.

This module provides utilities to extract field descriptions from Pydantic models,
replacing the previous approach of reading descriptions from JSON schemas.
"""

from typing import get_args, get_origin

from pydantic import BaseModel


def get_field_descriptions(model_class: type[BaseModel]) -> dict[str, str]:
    """Extract all field descriptions from a Pydantic model.

    Args:
        model_class: Pydantic BaseModel class

    Returns:
        Dict mapping field names to descriptions.
        Example: {"user_id": "Identifier for the user...", ...}
    """
    descriptions = {}

    for field_name, field_info in model_class.model_fields.items():
        if field_info.description:
            descriptions[field_name] = field_info.description

    return descriptions


def get_nested_descriptions(
    model_class: type[BaseModel], prefix: str = ""
) -> dict[str, str]:
    """Recursively extract descriptions including nested models.

    Args:
        model_class: Pydantic BaseModel class
        prefix: Optional prefix for nested paths (used in recursion)

    Returns:
        Dict with dot-notation paths mapping to descriptions.
        Example: {
            "user_id": "Identifier for the user...",
            "strategy.name": "Strategy name...",
            "strategy.params": "Strategy parameters...",
        }
    """
    descriptions = {}

    for field_name, field_info in model_class.model_fields.items():
        full_path = f"{prefix}.{field_name}" if prefix else field_name

        # Add this field's description
        if field_info.description:
            descriptions[full_path] = field_info.description

        # Check if this field is a nested Pydantic model
        annotation = field_info.annotation

        # Handle Optional[Model], list[Model], etc.
        origin = get_origin(annotation)
        if origin is not None:
            # Get the actual type from Optional/List/etc
            args = get_args(annotation)
            if args:
                # Take first arg for Optional, List, etc
                annotation = args[0]

        # Recursively extract from nested models
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            nested = get_nested_descriptions(annotation, full_path)
            descriptions.update(nested)

    return descriptions


def get_field_description_from_path(
    model_class: type[BaseModel], field_path: str
) -> str | None:
    """Get description for a specific field path.

    Args:
        model_class: Pydantic BaseModel class
        field_path: Dot-notation path (e.g., "strategy.params.length")

    Returns:
        Description string if found, None otherwise

    Example:
        >>> get_field_description_from_path(RunConfig, "user_id")
        "Identifier for the user or owner of the run."
    """
    all_descriptions = get_nested_descriptions(model_class)
    return all_descriptions.get(field_path)


def extract_descriptions_for_brief(
    brief_schema_class: type[BaseModel],
) -> dict[str, str]:
    """Extract descriptions for brief schema fields.

    This is a convenience function specifically for brief generation,
    replacing the old approach of reading from brief.schema.json.

    Args:
        brief_schema_class: The Pydantic model for the brief

    Returns:
        Dict mapping field paths to descriptions for all fields in the brief
    """
    return get_nested_descriptions(brief_schema_class)
