from orchestrator.scouts.inmuebles24 import Inmuebles24Scout
from orchestrator.scouts.lamudi import LamudiScout
from orchestrator.scouts.propiedades import PropiedadesScout
from orchestrator.scouts.vivanuncios import VivanunciosScout

SCOUT_REGISTRY = {
    "inmuebles24": Inmuebles24Scout,
    "lamudi": LamudiScout,
    "propiedades": PropiedadesScout,
    "vivanuncios": VivanunciosScout,
}

__all__ = ["SCOUT_REGISTRY", "Inmuebles24Scout", "LamudiScout", "PropiedadesScout", "VivanunciosScout"]
