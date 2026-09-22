import yaml
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional

class LayerRule(BaseModel):
    name: str
    allowed_calls: List[str] = Field(default_factory=list)
    forbidden_calls: List[str] = Field(default_factory=list)

    @field_validator('name')
    def validate_name(cls, v):
        if not v or not isinstance(v, str) or not v.strip():
            raise ValueError("Layer name must be a non-empty string")
        return v.strip()

class CIConfig(BaseModel):
    fail_on: str = Field(default="HIGH", description="Severity threshold to fail CI: HIGH, MEDIUM, or LOW")

    @field_validator('fail_on')
    def validate_fail_on(cls, v):
        if not v or not isinstance(v, str):
            return "HIGH"
        upper = v.upper().strip()
        if upper not in {"HIGH", "MEDIUM", "LOW"}:
            raise ValueError(f"Invalid fail_on threshold '{v}'. Must be one of: HIGH, MEDIUM, LOW")
        return upper

class ArchitectureConfig(BaseModel):
    layers: List[LayerRule]
    ci: Optional[CIConfig] = Field(default_factory=CIConfig)
    
    @field_validator('layers')
    def check_layer_references(cls, layers):
        if not layers:
            raise ValueError("Architecture configuration must contain at least one layer definition")
        layer_names = {layer.name for layer in layers}
        for layer in layers:
            for allowed in layer.allowed_calls:
                if allowed not in layer_names and allowed != "*":
                    raise ValueError(f"Unknown layer '{allowed}' in allowed_calls for '{layer.name}'")
            for forbidden in layer.forbidden_calls:
                if forbidden not in layer_names and forbidden != "*":
                    raise ValueError(f"Unknown layer '{forbidden}' in forbidden_calls for '{layer.name}'")
        return layers


def load_config(file_path: str) -> ArchitectureConfig:
    """Loads and validates a YAML rules configuration file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Malformed YAML syntax in configuration file: {e}")
    except Exception as e:
        raise ValueError(f"Could not read configuration file: {e}")

    if not isinstance(data, dict):
        raise ValueError("Invalid YAML configuration format: Root content must be a dictionary")

    return ArchitectureConfig(**data)