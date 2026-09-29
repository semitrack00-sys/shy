from dataclasses import dataclass
import importlib.util
import sys
from pathlib import Path


def _load_module(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


app_path = Path(__file__).resolve().parent
contracts_module = _load_module("shy_model_contracts", app_path / "contracts.py")

ModelCapability = contracts_module.ModelCapability
ProviderHealth = contracts_module.ProviderHealth
ProviderHealthStatus = contracts_module.ProviderHealthStatus
ModelProfile = contracts_module.ModelProfile


@dataclass(frozen=True)
class RegistrySnapshot:
    provider_ids: tuple[str, ...]
    model_ids: tuple[str, ...]


class ModelRegistry:
    def __init__(self):
        self._providers: dict[str, object] = {}
        self._models: dict[str, ModelProfile] = {}
        self._provider_order: list[str] = []
        self._model_order: list[str] = []

    def register_provider(self, provider):
        provider_id = provider.provider_id.strip()
        if not provider_id:
            raise ValueError("provider_id is required")
        if provider_id in self._providers:
            raise ValueError(f"duplicate provider_id: {provider_id}")
        self._providers[provider_id] = provider
        self._provider_order.append(provider_id)

    def register_model(self, profile: ModelProfile):
        if profile.provider_id not in self._providers:
            raise ValueError(f"provider not registered: {profile.provider_id}")
        if profile.model_id in self._models:
            raise ValueError(f"duplicate model_id: {profile.model_id}")
        self._models[profile.model_id] = profile
        self._model_order.append(profile.model_id)

    def discover_models(self):
        for provider_id in self._provider_order:
            provider = self._providers[provider_id]
            for profile in provider.list_models():
                if profile.model_id not in self._models:
                    self.register_model(profile)

    def get_provider(self, provider_id: str):
        provider = self._providers.get(provider_id)
        if provider is None:
            raise KeyError(f"unknown provider: {provider_id}")
        return provider

    def get_model(self, model_id: str) -> ModelProfile:
        profile = self._models.get(model_id)
        if profile is None:
            raise KeyError(f"unknown model: {model_id}")
        return profile

    def provider_health(self, provider_id: str) -> ProviderHealth:
        provider = self.get_provider(provider_id)
        return provider.health()

    def list_provider_health(self) -> dict[str, ProviderHealth]:
        output: dict[str, ProviderHealth] = {}
        for provider_id in self._provider_order:
            output[provider_id] = self._providers[provider_id].health()
        return output

    def enabled_models(self) -> tuple[ModelProfile, ...]:
        models: list[ModelProfile] = []
        for model_id in self._model_order:
            profile = self._models[model_id]
            if profile.enabled:
                models.append(profile)
        return tuple(models)

    def models_for_capability(self, capability: ModelCapability) -> tuple[ModelProfile, ...]:
        models: list[ModelProfile] = []
        for profile in self.enabled_models():
            if capability in profile.capabilities:
                models.append(profile)
        return tuple(models)

    def models_with_health(
        self,
        capability: ModelCapability,
        include_degraded: bool = True,
        include_unknown: bool = True,
    ) -> tuple[ModelProfile, ...]:
        allowed = {ProviderHealthStatus.HEALTHY}
        if include_degraded:
            allowed.add(ProviderHealthStatus.DEGRADED)
        if include_unknown:
            allowed.add(ProviderHealthStatus.UNKNOWN)

        models: list[ModelProfile] = []
        for profile in self.models_for_capability(capability):
            health = self.provider_health(profile.provider_id)
            if health.status in allowed:
                models.append(profile)
        return tuple(models)

    def snapshot(self) -> RegistrySnapshot:
        return RegistrySnapshot(
            provider_ids=tuple(self._provider_order),
            model_ids=tuple(self._model_order),
        )
