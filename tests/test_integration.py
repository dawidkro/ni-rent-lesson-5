import json

import pytest

from src.manager import Manager
from src.models import Parameters


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def manager():
    """Manager załadowany z domyślnych plików w katalogu data/."""
    return Manager(Parameters())


@pytest.fixture
def custom_manager(tmp_path):
    """Manager załadowany z własnego, kontrolowanego zestawu plików JSON.

    Dwa mieszkania (A1, B2) i rachunki rozrzucone po różnych miesiącach
    i latach, plus jeden rachunek przypisany do nieistniejącego mieszkania.
    """
    apartments = {
        "A1": {
            "key": "A1",
            "name": "Mieszkanie A1",
            "location": "Testowa 1",
            "area_m2": 50,
            "rooms": {
                "r1": {"name": "Pokój 1", "area_m2": 30},
                "r2": {"name": "Pokój 2", "area_m2": 20},
            },
        },
        "B2": {
            "key": "B2",
            "name": "Mieszkanie B2",
            "location": "Testowa 2",
            "area_m2": 40,
            "rooms": {
                "r1": {"name": "Pokój 1", "area_m2": 40},
            },
        },
    }
    bills = [
        # A1, marzec 2024 -> 300 + 120.5 + 29.5 = 450.0
        {"amount_pln": 300.0, "date_due": "2024-04-10", "settlement_year": 2024, "settlement_month": 3, "apartment": "A1", "type": "rent"},
        {"amount_pln": 120.5, "date_due": "2024-04-15", "settlement_year": 2024, "settlement_month": 3, "apartment": "A1", "type": "electricity"},
        {"amount_pln": 29.5, "date_due": "2024-04-15", "settlement_year": 2024, "settlement_month": 3, "apartment": "A1", "type": "water"},
        # A1, ten sam rok, inny miesiąc
        {"amount_pln": 300.0, "date_due": "2024-05-10", "settlement_year": 2024, "settlement_month": 4, "apartment": "A1", "type": "rent"},
        # A1, ten sam miesiąc, inny rok
        {"amount_pln": 99.99, "date_due": "2023-04-10", "settlement_year": 2023, "settlement_month": 3, "apartment": "A1", "type": "gas"},
        # B2, marzec 2024 - nie może trafić do sumy A1
        {"amount_pln": 500.0, "date_due": "2024-04-10", "settlement_year": 2024, "settlement_month": 3, "apartment": "B2", "type": "rent"},
        # Rachunek "sierota" - mieszkanie X9 nie istnieje
        {"amount_pln": 1000.0, "date_due": "2024-04-10", "settlement_year": 2024, "settlement_month": 3, "apartment": "X9", "type": "rent"},
    ]

    files = {
        "apartments.json": apartments,
        "tenants.json": {},
        "transfers.json": [],
        "bills.json": bills,
    }
    for file_name, content in files.items():
        (tmp_path / file_name).write_text(json.dumps(content), encoding="utf-8")

    parameters = Parameters(
        apartments_json_path=str(tmp_path / "apartments.json"),
        tenants_json_path=str(tmp_path / "tenants.json"),
        transfers_json_path=str(tmp_path / "transfers.json"),
        bills_json_path=str(tmp_path / "bills.json"),
    )
    return Manager(parameters)



def test_costs_for_nonexistent_apartment(manager):
    assert "apart-nieistniejace" not in manager.apartments
    assert manager.get_apartment_costs("apart-nieistniejace", 2025, 1) is None


def test_costs_when_no_bills_in_month(manager):
    # Rok się zgadza, miesiąc nie
    costs = manager.get_apartment_costs("apart-polanka", 2025, 2)
    assert costs == 0.0
    assert isinstance(costs, float)

    # Miesiąc się zgadza, rok nie
    assert manager.get_apartment_costs("apart-polanka", 2024, 1) == 0.0


def test_costs_when_bills_in_month(manager):
    # rent 760.00 + electricity 150.00
    assert manager.get_apartment_costs("apart-polanka", 2025, 1) == 910.0


def test_costs_match_bills_filtered_from_global_list(manager):
    """Suma z metody musi być równa sumie ręcznie przefiltrowanej globalnej listy."""
    for bill in manager.bills:
        expected = sum(
            b.amount_pln
            for b in manager.bills
            if b.apartment == bill.apartment
            and b.settlement_year == bill.settlement_year
            and b.settlement_month == bill.settlement_month
        )
        costs = manager.get_apartment_costs(
            bill.apartment, bill.settlement_year, bill.settlement_month
        )
        assert costs == pytest.approx(expected)


@pytest.mark.parametrize(
    "apartment_key, year, month, expected",
    [
        ("A1", 2024, 3, 450.0),   # kilka rachunków w jednym miesiącu
        ("A1", 2024, 4, 300.0),   # ten sam rok, inny miesiąc
        ("A1", 2023, 3, 99.99),   # ten sam miesiąc, inny rok
        ("A1", 2024, 5, 0.0),     # mieszkanie istnieje, brak rachunków
        ("B2", 2024, 3, 500.0),   # rachunki innego mieszkania nie mieszają się z A1
        ("B2", 2024, 4, 0.0),
    ],
)
def test_costs_on_custom_dataset(custom_manager, apartment_key, year, month, expected):
    assert custom_manager.get_apartment_costs(apartment_key, year, month) == pytest.approx(expected)


def test_bill_for_nonexistent_apartment_is_ignored(custom_manager):
    # Rachunek dla X9 istnieje w bills.json, ale mieszkania X9 nie ma w apartments.json
    assert any(bill.apartment == "X9" for bill in custom_manager.bills)
    assert custom_manager.get_apartment_costs("X9", 2024, 3) is None


def test_sum_of_apartment_costs_matches_bills_of_existing_apartments(custom_manager):
    """Spójność stanu: suma kosztów wszystkich mieszkań w danym miesiącu
    = suma rachunków z tego miesiąca przypisanych do istniejących mieszkań."""
    year, month = 2024, 3
    total_from_method = sum(
        custom_manager.get_apartment_costs(key, year, month)
        for key in custom_manager.apartments
    )
    total_from_bills = sum(
        bill.amount_pln
        for bill in custom_manager.bills
        if bill.apartment in custom_manager.apartments
        and bill.settlement_year == year
        and bill.settlement_month == month
    )
    assert total_from_method == pytest.approx(total_from_bills)
    assert total_from_method == pytest.approx(950.0)  # 450 (A1) + 500 (B2), bez X9
