"""This module implements unit tests for contract.api.views.ListarContratos
class."""

# built in
from unittest.mock import MagicMock

# thirty
from django.test import TestCase

# local
from contract.api.views import ListarContratos
from contract.models.contratos import Contrato
from core.models.cliente import Cliente


class GetPaginationDataTest(TestCase):
    """
    Implement tests for ListarContratos.get_pagination_data function.
    """

    def setUp(self):
        self.view = ListarContratos()

    def test_valid_data(self):
        # prepare scenario
        request = MagicMock()
        request.data = {'page': 2, 'items_per_page': 10}
        total = 20

        # execute
        response = self.view.get_pagination_data(request, total)

        # assert response
        self.assertIsInstance(response, tuple)
        self.assertEqual(len(response), 2)
        self.assertEqual(response[0], 2)
        self.assertEqual(response[1], 10)

    def test_missing_fields(self):
        # prepare scenario
        request = MagicMock()
        request.data = {}
        total = 20

        # execute
        response = self.view.get_pagination_data(request, total)

        # assert response
        self.assertIsInstance(response, tuple)
        self.assertEqual(len(response), 2)
        self.assertEqual(response[0], 1)
        self.assertEqual(response[1], 20)

    def test_missing_page_field(self):
        # prepare scenario
        request = MagicMock()
        request.data = {'items_per_page': 10}
        total = 20

        # execute
        response = self.view.get_pagination_data(request, total)

        # assert response
        self.assertIsInstance(response, tuple)
        self.assertEqual(len(response), 2)
        self.assertEqual(response[0], 1)
        self.assertEqual(response[1], 20)

    def test_missing_items_per_page_field(self):
        # prepare scenario
        request = MagicMock()
        request.data = {'page': 1}
        total = 20

        # execute
        response = self.view.get_pagination_data(request, total)

        # assert response
        self.assertIsInstance(response, tuple)
        self.assertEqual(len(response), 2)
        self.assertEqual(response[0], 1)
        self.assertEqual(response[1], 20)


class Paginate(TestCase):
    """
    Implement tests for ListarContratos.paginate function.
    """

    def setUp(self):
        self.view = ListarContratos()

        # create a bunch of contracts
        self.number_of_contracts = 50
        client = Cliente.objects.create(
            nome_cliente='Paginate Teste Client',
        )
        records_to_create = [
            Contrato(
                cliente=client,
                cd_contrato_tipo=1,
            )
            for _ in range(self.number_of_contracts)
        ]
        Contrato.objects.bulk_create(records_to_create)
        self.query_set = Contrato.objects.filter(cliente=client)
        self.assertEqual(len(self.query_set), self.number_of_contracts)

    def test_pages_except_last(self):
        for items_per_page in range(1, self.number_of_contracts):
            total_filled_pages = self.number_of_contracts // items_per_page

            # loop all pages except last
            last_page = total_filled_pages + 1
            for page in range(1, last_page):
                response = self.view.paginate(
                    query_set=self.query_set,
                    page_number=page,
                    items_per_page=items_per_page,
                )

                # assert type
                self.assertIsInstance(response, list)

                # assert size
                msg = (
                    'Wrong numbers of items on page %d, '
                    'using %d items per page' % (page, items_per_page)
                )
                self.assertEqual(len(response), items_per_page, msg)

    def test_last_page(self):
        for items_per_page in range(1, self.number_of_contracts):
            total_filled_pages = self.number_of_contracts // items_per_page
            number_of_listed_items = total_filled_pages * items_per_page
            items_on_last_page = len(self.query_set) - number_of_listed_items
            last_page = total_filled_pages + 1
            response = self.view.paginate(
                query_set=self.query_set,
                page_number=last_page,
                items_per_page=items_per_page,
            )

            # assert type
            self.assertIsInstance(response, list)

            # assert size
            msg = (
                'Wrong numbers of items on last page '
                'using %d items per page' % items_per_page
            )
            self.assertEqual(len(response), items_on_last_page, msg)

    def test_negative_page(self):
        page = -1
        items_per_page = 50
        response = self.view.paginate(
            query_set=self.query_set, page_number=page, items_per_page=items_per_page
        )
        # assert type
        self.assertIsInstance(response, list)

        # assert size
        self.assertEqual(len(response), 0)

    def test_negative_items_per_page(self):
        page = 1
        items_per_page = -10
        response = self.view.paginate(
            query_set=self.query_set, page_number=page, items_per_page=items_per_page
        )
        # assert type
        self.assertIsInstance(response, list)

        # assert size
        self.assertEqual(len(response), 0)

    def test_both_negative(self):
        page = -1
        items_per_page = -10
        response = self.view.paginate(
            query_set=self.query_set, page_number=page, items_per_page=items_per_page
        )
        # assert type
        self.assertIsInstance(response, list)

        # assert size
        self.assertEqual(len(response), 0)

    def test_empty_query_set(self):
        page = 1
        items_per_page = 10
        response = self.view.paginate(
            query_set=Contrato.objects.none(),
            page_number=page,
            items_per_page=items_per_page,
        )
        # assert type
        self.assertIsInstance(response, list)

        # assert size
        self.assertEqual(len(response), 0)

    def test_items_per_page_bigger_than_total(self):
        page = 1
        items_per_page = self.number_of_contracts * 2
        response = self.view.paginate(
            query_set=self.query_set, page_number=page, items_per_page=items_per_page
        )
        # assert type
        self.assertIsInstance(response, list)

        # assert size
        self.assertEqual(len(response), self.number_of_contracts)

    def test_page_does_not_exists(self):
        page = 10
        items_per_page = self.number_of_contracts
        response = self.view.paginate(
            query_set=self.query_set, page_number=page, items_per_page=items_per_page
        )
        # assert type
        self.assertIsInstance(response, list)

        # assert size
        self.assertEqual(len(response), 0)
