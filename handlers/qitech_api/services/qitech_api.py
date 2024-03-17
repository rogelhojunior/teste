from typing import Literal, Type, TypeVar

from handlers.qitech_api.adapters import (
    QiTechAPIHandlerAdapter,
    QITechResponseModelType,
)
from handlers.qitech_api.adapters.portability_proposal import PortabilityProposalAdapter
from handlers.qitech_api.exceptions import AdapterNotImplementedError

AdapterType = TypeVar('AdapterType', bound=QiTechAPIHandlerAdapter)
AdapterName = Literal['portability_proposal']


class QiTechApiService:
    """
    Service class for QiTech's API interactions using various adapters.

    This class serves as an interface to different QiTech API functionalities,
    delegating specific API tasks to dedicated adapter classes.

    Attributes:
        __adapters (dict[AdapterName, AdapterType]): Mapping of adapter names
            to their respective classes.

    Inner Classes:
        _AdapterProxy: Proxy class to dynamically invoke adapter methods.

    Methods:
        __getattr__: Returns an adapter proxy for a specified attribute name.
        _get_adapter: Retrieves the adapter class for a given adapter name.
        execute: Executes API interaction using the specified adapter.
    """

    __adapters: dict[AdapterName, AdapterType] = {
        'portability_proposal': PortabilityProposalAdapter
    }

    @classmethod
    def _get_adapter(cls, adapter_name: AdapterName) -> Type[AdapterType]:
        """
        Retrieves the adapter class for a given adapter name.

        Args:
            adapter_name (AdapterName): The name of the adapter.

        Returns:
            Type[AdapterType]: The adapter class associated with the given name.

        Raises:
            AdapterNotImplementedError: If the adapter is not implemented.
        """
        try:
            return cls.__adapters[adapter_name]
        except KeyError as e:
            raise AdapterNotImplementedError from e

    @classmethod
    def execute(
        cls, adapter_name: AdapterName, endpoint_params: dict[str, any]
    ) -> QITechResponseModelType:
        """
        Executes the API interaction using the specified adapter.

        Args:
            adapter_name (AdapterName): The name of the adapter to use.
            endpoint_params (dict[str, any]): Parameters for the API endpoint.

        Returns:
            QITechResponseModelType: The response model from the executed adapter.
        """
        adapter: AdapterType = cls._get_adapter(adapter_name=adapter_name)(
            endpoint_params=endpoint_params
        )
        adapter.adapt()
        return adapter.get_response_data()
