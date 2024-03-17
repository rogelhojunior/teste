from typing import Tuple
from django.http import HttpRequest

from django.core.paginator import EmptyPage, Paginator
from django.db.models.query import QuerySet


def get_pagination_data(request: HttpRequest, total: int) -> Tuple[int, int]:
    """
    Extracts pagination data from the given HttpRequest object.

    Parameters:
        request (HttpRequest): The HTTP request object containing pagination information.
        total (int): The total number of items to be paginated.

    Returns:
        Tuple[int, int]: A tuple containing the extracted page number and items per page.
            - The page number, defaults to 1 if not provided.
            - The number of items per page, defaults to the total number of items if not provided.
    """
    page_number = request.data.get('page') or 1
    items_per_page = request.data.get('items_per_page') or total

    return page_number, items_per_page


def paginate(query_set: QuerySet, page_number: int, items_per_page: int) -> list:
    """
    Paginates a QuerySet based on the provided page number and items
    per page.

    Parameters:
        query_set (QuerySet): The QuerySet to be paginated.
        page_number (int): The desired page number.
        items_per_page (int): The number of items to be displayed per page.

    Returns:
        list: A paginated list containing items for the
        specified page. If the page number is out of range, an empty
        QuerySet is returned.

    Note:
        This function uses Django's Paginator class to handle
        pagination. If the specified page number is out of range,
        an EmptyPage exception is caught, and an empty list is
        returned.
    """
    paginator = Paginator(query_set, items_per_page)
    if len(query_set) == 0:
        return []
    try:
        return paginator.page(page_number).object_list
    except EmptyPage:
        return []
