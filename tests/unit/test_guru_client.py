import httpx
import pytest
import respx

from app.services.guru.client import GuruClient
from app.services.guru.schemas import GuruContact, GuruProduct, GuruTransaction

GURU_BASE_URL = "https://api.guru.test/v2"


@pytest.fixture
def guru_settings(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.GURU_API_URL", GURU_BASE_URL)
    monkeypatch.setattr("app.core.config.settings.GURU_API_KEY", "test-guru-key")
    monkeypatch.setattr(
        "app.core.config.settings.GURU_INGRESSO_GROUP_ID", "group-123"
    )


class TestFindContactByCpf:
    @respx.mock
    def test_found(self, guru_settings):
        respx.get(f"{GURU_BASE_URL}/contacts").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "id": "c1",
                        "name": "João Silva",
                        "doc": "12345678901",
                        "email": "joao@test.com",
                        "address_city": "São Paulo",
                        "address_state": "SP",
                    }
                ],
            )
        )

        client = GuruClient()
        contact = client.find_contact_by_cpf("12345678901")

        assert contact is not None
        assert isinstance(contact, GuruContact)
        assert contact.id == "c1"
        assert contact.name == "João Silva"
        assert contact.email == "joao@test.com"

    @respx.mock
    def test_not_found(self, guru_settings):
        respx.get(f"{GURU_BASE_URL}/contacts").mock(
            return_value=httpx.Response(200, json=[])
        )

        client = GuruClient()
        contact = client.find_contact_by_cpf("00000000000")

        assert contact is None

    @respx.mock
    def test_api_error(self, guru_settings):
        respx.get(f"{GURU_BASE_URL}/contacts").mock(
            return_value=httpx.Response(500, json={"error": "Internal Server Error"})
        )

        client = GuruClient()
        with pytest.raises(httpx.HTTPStatusError):
            client.find_contact_by_cpf("12345678901")


class TestGetTransactionsForContact:
    @respx.mock
    def test_returns_transactions(self, guru_settings):
        respx.get(f"{GURU_BASE_URL}/transactions").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "id": "tx1",
                        "status": "approved",
                        "product": {"id": "prod-1", "internal_id": "int-1"},
                    },
                    {
                        "id": "tx2",
                        "status": "pending",
                        "product": {"id": "prod-2"},
                    },
                ],
            )
        )

        client = GuruClient()
        transactions = client.get_transactions_for_contact("c1")

        assert len(transactions) == 2
        assert all(isinstance(t, GuruTransaction) for t in transactions)
        assert transactions[0].id == "tx1"
        assert transactions[0].status == "approved"

    @respx.mock
    def test_handles_pagination(self, guru_settings):
        route = respx.get(f"{GURU_BASE_URL}/transactions")
        route.side_effect = [
            httpx.Response(
                200,
                json={
                    "data": [{"id": "tx1", "status": "approved"}],
                    "cursor_next": "page2",
                },
            ),
            httpx.Response(
                200,
                json={
                    "data": [{"id": "tx2", "status": "approved"}],
                },
            ),
        ]

        client = GuruClient()
        transactions = client.get_transactions_for_contact("c1")

        assert len(transactions) == 2
        assert transactions[0].id == "tx1"
        assert transactions[1].id == "tx2"


class TestGetAllProducts:
    @respx.mock
    def test_returns_products(self, guru_settings):
        respx.get(f"{GURU_BASE_URL}/products").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "id": "prod-1",
                        "name": "Curso A",
                        "group": {"id": "group-123", "name": "Ingressos"},
                    },
                    {
                        "id": "prod-2",
                        "name": "Curso B",
                        "group": {"id": "group-456", "name": "Outros"},
                    },
                ],
            )
        )

        client = GuruClient()
        products = client.get_all_products()

        assert len(products) == 2
        assert all(isinstance(p, GuruProduct) for p in products)


class TestGetIngressoProducts:
    @respx.mock
    def test_filters_by_group_id(self, guru_settings):
        respx.get(f"{GURU_BASE_URL}/products").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "id": "prod-1",
                        "name": "Curso A",
                        "group": {"id": "group-123", "name": "Ingressos"},
                    },
                    {
                        "id": "prod-2",
                        "name": "Curso B",
                        "group": {"id": "group-456", "name": "Outros"},
                    },
                ],
            )
        )

        client = GuruClient()
        products = client.get_ingresso_products()

        assert len(products) == 1
        assert products[0].id == "prod-1"

    @respx.mock
    def test_returns_all_when_no_group_id(self, monkeypatch, guru_settings):
        monkeypatch.setattr(
            "app.core.config.settings.GURU_INGRESSO_GROUP_ID", ""
        )
        respx.get(f"{GURU_BASE_URL}/products").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"id": "prod-1", "name": "A"},
                    {"id": "prod-2", "name": "B"},
                ],
            )
        )

        client = GuruClient()
        products = client.get_ingresso_products()

        assert len(products) == 2
