import yaml
from pydantic import BaseModel, Field, field_validator
from typing import List

class LayerRule(BaseModel):
    name: str
    allowed_calls: List[str] = Field(default_factory=list)
    forbidden_calls: List[str] = Field(default_factory=list)

class ArchitectureConfig(BaseModel):
    layers: List[LayerRule]
    
    @field_validator('layers')
    def check_layer_references(cls, layers):
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
    with open(file_path, 'r') as f:
        data = yaml.safe_load(f)
    return ArchitectureConfig(**data)