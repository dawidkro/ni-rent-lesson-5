import pytest

from src.manager import Manager
from src.models import Apartment, ApartmentSettlement, Bill, Parameters


@pytest.fixture
def manager():
    """Manager załadowany z domyślnych plików w katalogu data/."""
    return Manager(Parameters())


def test_settlement_for_apartment_with_bills(manager):
    settlement = manager.create_apartment_settlement('apart-polanka', 2025, 1)

    assert isinstance(settlement, ApartmentSettlement)
    assert settlement.key == 'apart-polanka-2025-01'
    assert settlement.apartment == 'apart-polanka'
    assert settlement.year == 2025
    assert settlement.month == 1
    # rent 760.00 + electricity 150.00
    assert settlement.total_due_pln == 910.0
    # przelewy będą uwzględnione w kolejnym kroku
    assert settlement.total_transfers_pln == 0.0
    # bilans = suma przelewów - suma rachunków
    assert settlement.balance_pln == -910.0
    assert settlement.balance_pln == settlement.total_transfers_pln - settlement.total_due_pln


def test_settlement_for_apartment_without_bills_in_month(manager):
    # Rok się zgadza, miesiąc nie
    settlement = manager.create_apartment_settlement('apart-polanka', 2025, 2)

    assert isinstance(settlement, ApartmentSettlement)
    assert settlement.key == 'apart-polanka-2025-02'
    assert settlement.apartment == 'apart-polanka'
    assert settlement.year == 2025
    assert settlement.month == 2
    assert settlement.total_due_pln == 0.0
    assert settlement.total_transfers_pln == 0.0
    assert settlement.balance_pln == 0.0

    # Miesiąc się zgadza, rok nie
    settlement = manager.create_apartment_settlement('apart-polanka', 2024, 1)
    assert settlement.key == 'apart-polanka-2024-01'
    assert settlement.total_due_pln == 0.0
    assert settlement.balance_pln == 0.0


def test_settlement_for_nonexistent_apartment(manager):
    assert manager.create_apartment_settlement('apart-nieistniejace', 2025, 1) is None


@pytest.mark.parametrize('year, month', [
    (2025, 0),
    (2025, 13),
    (2025, None),   # rozliczenie zawsze dotyczy konkretnego miesiąca
    (None, 1),      # ... i konkretnego roku
    (0, 1),
])
def test_settlement_for_invalid_period_raises_value_error(manager, year, month):
    with pytest.raises(ValueError):
        manager.create_apartment_settlement('apart-polanka', year, month)


def test_settlement_uses_only_bills_of_given_apartment_and_month(manager):
    manager.apartments['apart-druga'] = Apartment(
        key='apart-druga',
        name='Druga',
        location='Testowa 2',
        area_m2=40,
        rooms={'room-1': {'name': 'Room 1', 'area_m2': 40}},
    )
    # Rachunek innego mieszkania w tym samym miesiącu
    manager.bills.append(Bill(
        apartment='apart-druga',
        date_due='2025-02-10',
        settlement_year=2025,
        settlement_month=1,
        amount_pln=400.0,
        type='rent',
    ))
    # Kolejny rachunek Polanki, ale za luty
    manager.bills.append(Bill(
        apartment='apart-polanka',
        date_due='2025-03-10',
        settlement_year=2025,
        settlement_month=2,
        amount_pln=120.0,
        type='water',
    ))

    polanka_jan = manager.create_apartment_settlement('apart-polanka', 2025, 1)
    polanka_feb = manager.create_apartment_settlement('apart-polanka', 2025, 2)
    druga_jan = manager.create_apartment_settlement('apart-druga', 2025, 1)
    druga_feb = manager.create_apartment_settlement('apart-druga', 2025, 2)

    assert polanka_jan.total_due_pln == 910.0
    assert polanka_jan.balance_pln == -910.0
    assert polanka_feb.total_due_pln == 120.0
    assert polanka_feb.balance_pln == -120.0
    assert druga_jan.key == 'apart-druga-2025-01'
    assert druga_jan.total_due_pln == 400.0
    assert druga_jan.balance_pln == -400.0
    assert druga_feb.total_due_pln == 0.0
    assert druga_feb.balance_pln == 0.0


def test_settlement_is_consistent_with_apartment_costs(manager):
    """Suma rachunków w rozliczeniu = wynik get_apartment_costs dla tego samego okresu."""
    for bill in manager.bills:
        settlement = manager.create_apartment_settlement(
            bill.apartment, bill.settlement_year, bill.settlement_month
        )
        expected = manager.get_apartment_costs(
            bill.apartment, bill.settlement_year, bill.settlement_month
        )
        assert settlement.total_due_pln == pytest.approx(expected)
        assert settlement.balance_pln == pytest.approx(-expected)
