"""This module implements functions for webhook_qitech module."""

from pydantic import ValidationError


class PydanticValidationErrorFormatter:
    @classmethod
    def format_error(cls, exception: ValidationError) -> dict[str, any]:
        """
        Convert a pydantic ValidationError into a DRF-style error response.

        Args:
            exception (ValidationError): The exception to convert.

        Returns:
            dict[str, any]: The error response.
        """
        drf_data: dict[str, any] = {}
        for error in exception.errors():
            cls._set_nested(drf_data, error['loc'], [error['msg']])
        return drf_data

    @staticmethod
    def _set_nested(
        data: dict[str, any], keys: tuple[int | str, ...], value: any
    ) -> None:
        """
        Set a value in a nested dictionary.

        Args:
            data (Dict[str, Any]): The dictionary to set the value in.
            keys (tuple[int | str, ...]): The keys to set the value at.
            value (Any): The value to set.

        Returns:
            None
        """
        for key in keys[:-1]:
            data = data.setdefault(str(key), {})
        data[str(keys[-1])] = value
