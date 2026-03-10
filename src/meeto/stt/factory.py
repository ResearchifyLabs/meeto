"""STT adapter factory with provider registry."""

from meeto.stt.base import STTStreamingAdapter

_REGISTRY: dict[str, type[STTStreamingAdapter]] = {}


def register_stt(name: str, cls: type[STTStreamingAdapter]):
    _REGISTRY[name] = cls


def create_stt_adapter(provider: str, **kwargs) -> STTStreamingAdapter:
    cls = _REGISTRY.get(provider)
    if not cls:
        raise ValueError(f"Unknown STT provider: {provider}. Available: {list(_REGISTRY)}")
    return cls(**kwargs)
