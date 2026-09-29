from abc import ABC, abstractmethod


class ModelProvider(ABC):
    @property
    @abstractmethod
    def provider_id(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def health(self):
        raise NotImplementedError

    @abstractmethod
    def list_models(self):
        raise NotImplementedError

    @abstractmethod
    def generate(self, request, model_id: str):
        raise NotImplementedError
