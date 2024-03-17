import hashlib
import logging
from datetime import date, datetime

import pytz
from django.utils import timezone

logger = logging.getLogger('digitacao')


def gerar_md5(input):
    # Use input string to calculate MD5 hash
    md5 = hashlib.md5()
    md5.update(input.encode('ascii'))
    hash_bytes = md5.digest()

    return hash_bytes.hex()


def data_atual():
    tz = pytz.timezone('Etc/GMT+3')  # Adjust the timezone according to your needs
    return datetime.now(tz).astimezone(tz).strftime('%Y-%m-%d %H:%M:%S')


def data_atual_sem_hora():  # Adjust the timezone according to your needs
    return timezone.localtime().strftime('%Y-%m-%d')


def calcular_idade_com_mes(dt_inicio, dt_fim):
    try:
        if dt_inicio is None or dt_fim is None:
            return None

        ano = 0
        mes = 0

        if dt_fim <= dt_inicio:
            return 0

        if dt_fim.year == dt_inicio.year:
            if int(dt_inicio.strftime('%Y%m%d')) > int(dt_fim.strftime('%Y%m%d')):
                return 0
            else:
                return (dt_fim - dt_inicio).days / 365.25

        if int(dt_inicio.strftime('%Y%m%d')) <= int(dt_fim.strftime('%Y%m%d')):
            ano = dt_fim.year - dt_inicio.year
        else:
            ano = dt_fim.year - dt_inicio.year - 1

        if int(dt_inicio.strftime('%m%d')) <= int(dt_fim.strftime('%m%d')):
            mes = (dt_fim.month - dt_inicio.month) / 100.0
        else:
            mes = ((12 - dt_inicio.month) + dt_fim.month) / 100.0

        if mes == 0.12:
            mes = 0.11

        return ano + mes
    except Exception as e:
        logger.error(f'Erro ao calcular idade com mes (calcular_idade_com_mes): {e}')
        raise


def convert_string_to_date_yyyymmdd(date_string: str) -> date:
    date_format = '%Y-%m-%d'

    return datetime.strptime(date_string, date_format).date()


def convert_string_to_date_ddmmyyyy(date_string: str, date_separator: str):
    date_format = f'%d{date_separator}%m{date_separator}%Y'
    return datetime.strptime(date_string, date_format).date()


class DateUtils:
    """
    A utility class for formatting dates based on user-defined date order and spacer.

    Attributes
    ----------
    date_order : str
        The order of the date components. Possible values are "dmy", "dym", "ymd", "ydm", "mdy", "myd".
    date_spacer : str
        The character used for separating date components, such as "-" or "/".
    day : str
        Format for the day component. Default is "%d".
    month : str
        Format for the month component. Default is "%m".
    year : str
        Format for the year component. Default is "%Y".

    Methods
    -------
    set_format_placeholders(day: str, month: str, year: str) -> None
        Set new format placeholders for day, month, and year components.

    _get_date_format() -> str
        Internal method to get the date format string based on `date_order` and `date_spacer`.

    get_formatted_date(date_to_format: str) -> str
        Formats a given date string based on `date_order` and `date_spacer`, and returns a formatted date string.

    Examples
    --------
    >>> date_utils = DateUtils('dmy', '-')
    >>> date_utils.get_formatted_date('25-12-2022')
    '2022-12-25'
    """

    day: str = '%d'  # 01
    month: str = '%m'  # 01
    year: str = '%Y'  # 2023

    def __init__(self, date_order: str, date_spacer: str) -> None:
        """
        Initialize the DateUtils class.

        Parameters
        ----------
        date_order : str
            The order of the date components. Possible values are "dmy", "dym", "ymd", "ydm", "mdy", "myd".
        date_spacer : str
            The character used for separating date components.
        """
        self.date_order = date_order
        self.date_spacer = date_spacer

    def set_format_placeholders(self, day: str, month: str, year: str) -> None:
        """
        Set new format placeholders for day, month, and year components.

        Parameters
        ----------
        day : str
            New format placeholder for the day component.
        month : str
            New format placeholder for the month component.
        year : str
            New format placeholder for the year component.
        """
        self.day = day
        self.month = month
        self.year = year

    def get_date_format(self) -> str:
        """
        Internal method to get the date format string based on `date_order` and `date_spacer`.

        Returns
        -------
        str
            The date format string.
        """
        return {
            'dmy': f'{self.day}{self.date_spacer}{self.month}{self.date_spacer}{self.year}',
            'dym': f'{self.day}{self.date_spacer}{self.year}{self.date_spacer}{self.month}',
            'ymd': f'{self.year}{self.date_spacer}{self.month}{self.date_spacer}{self.day}',
            'ydm': f'{self.year}{self.date_spacer}{self.day}{self.date_spacer}{self.month}',
            'mdy': f'{self.month}{self.date_spacer}{self.day}{self.date_spacer}{self.year}',
            'myd': f'{self.month}{self.date_spacer}{self.year}{self.date_spacer}{self.day}',
        }[self.date_order]

    def get_formatted_date(self, date_to_format: str) -> date:
        """
        Formats a given date string based on `date_order` and `date_spacer`.

        Parameters
        ----------
        date_to_format : str
            The date string to be formatted.

        Returns
        -------
        str
            The formatted date string.
        """
        return datetime.strptime(date_to_format, self.get_date_format()).date()

    def data_atual(self):
        # TODO: Refactor DateUtils.data_atual
        raise NotImplementedError

        # tz = pytz.timezone("Etc/GMT+3")  # Adjust the timezone according to your needs
        # return datetime.now(tz).astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")

    def data_atual_sem_hora(self):
        # TODO: Refactor DateUtils.data_atual_sem_hora
        raise NotImplementedError

        # tz = pytz.timezone("Etc/GMT+3")
        # # Adjust the timezone according to your needs
        # return datetime.now(tz).astimezone(tz).date().isoformat()
