from typing import Callable, Literal

from core.services.shorten_url.aws3_link_shortener import AWS3LinkShortURLService


class ShortURLManager:
    """
    Manages URL shortening services.

    This class functions as a factory for different URL shortening services.
    Currently, supports the 'aws3_link' service.

    Attributes:
        short_url_services (dict): A dictionary mapping service names to their
                                   respective service classes.

    Methods:
        __getattr__: Returns a function that creates an instance of the specified service.
    """

    def __init__(self) -> None:
        """
        Initializes the manager with available services.
        """
        self.short_url_services = {'aws3_link': AWS3LinkShortURLService}

    def __getattr__(
        self, attr: Literal['aws3_link']
    ) -> Callable[[dict[str, any]], AWS3LinkShortURLService]:
        """
        Returns a function that creates an instance of the URL shortening service.

        Args:
            attr (str): The name of the URL shortening service.

        Returns:
            Callable: A function that, when called with appropriate arguments,
                      returns an instance of the specified service.

        Raises:
            AttributeError: If the requested service is not available.
        """
        if service_class := self.short_url_services.get(attr):
            return lambda **kwargs: service_class(**kwargs)
        raise AttributeError(
            f"{self.__class__.__name__} does not have a service named '{attr}'"
        )
