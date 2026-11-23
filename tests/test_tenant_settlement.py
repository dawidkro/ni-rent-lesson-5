import pytest

from src.manager import Manager
from src.models import Apartment, Bill, Parameters, Tenant, TenantSettlement


@pytest.fixture
def manager():
    """Manager załadowany z domyślnych plików w katalogu data/.

    Mieszkanie 'apart-polanka' ma 3 najemców (tenant-1, tenant-2, tenant-3)
    i rachunki za 01.2025 na 910.0 PLN.
    """
    return Manager(Parameters())


def add_apartment(manager, key):
    manager.apartments[key] = Apartment(
        key=key,
        name=key,
        location='Testowa 1',
        area_m2=40,
        rooms={'room-1': {'name': 'Room 1', 'area_m2': 40}},
    )


def add_tenant(manager, tenant_key, apartment_key):
    manager.tenants[tenant_key] = Tenant(
        name=f'Najemca {tenant_key}',
        apartment=apartment_key,
        room='room-1',
        rent_pln=1000.0,
        deposit_pln=2000.0,
        date_agreement_from='2025-01-01',
        date_agreement_to='2025-12-31',
    )


def add_bill(manager, apartment_key, amount, year=2025, month=1):
    manager.bills.append(Bill(
        apartment=apartment_key,
        date_due=f'{year}-{month:02d}-15',
        settlement_year=year,
        settlement_month=month,
        amount_pln=amount,
        type='rent',
    ))


def test_tenants_settlements_for_three_tenants(manager):
    apartment_settlement = manager.create_apartment_settlement('apart-polanka', 2025, 1)
    tenants_settlements = manager.create_tenants_settlements(apartment_settlement)

    assert isinstance(tenants_settlements, list)
    assert len(tenants_settlements) == 3
    assert {s.tenant for s in tenants_settlements} == {'tenant-1', 'tenant-2', 'tenant-3'}

    for settlement in tenants_settlements:
        assert isinstance(settlement, TenantSettlement)
        assert settlement.apartment_settlement == apartment_settlement.key
        assert settlement.year == 2025
        assert settlement.month == 1
        assert settlement.total_due_pln == pytest.approx(910.0 / 3)
        assert settlement.total_transfers_pln == 0.0
        assert settlement.balance_pln == pytest.approx(-910.0 / 3)

    # Udziały najemców sumują się do kosztów mieszkania
    assert sum(s.total_due_pln for s in tenants_settlements) == pytest.approx(apartment_settlement.total_due_pln)


def test_tenants_settlements_for_two_tenants(manager):
    del manager.tenants['tenant-3']

    apartment_settlement = manager.create_apartment_settlement('apart-polanka', 2025, 1)
    tenants_settlements = manager.create_tenants_settlements(apartment_settlement)

    assert len(tenants_settlements) == 2
    assert {s.tenant for s in tenants_settlements} == {'tenant-1', 'tenant-2'}
    for settlement in tenants_settlements:
        assert settlement.total_due_pln == 455.0
        assert settlement.balance_pln == -455.0
    assert sum(s.total_due_pln for s in tenants_settlements) == 910.0


def test_tenants_settlements_for_one_tenant(manager):
    del manager.tenants['tenant-2']
    del manager.tenants['tenant-3']

    apartment_settlement = manager.create_apartment_settlement('apart-polanka', 2025, 1)
    tenants_settlements = manager.create_tenants_settlements(apartment_settlement)

    assert len(tenants_settlements) == 1
    settlement = tenants_settlements[0]
    assert settlement.tenant == 'tenant-1'
    assert settlement.apartment_settlement == 'apart-polanka-2025-01'
    # jedyny najemca ponosi cały koszt
    assert settlement.total_due_pln == 910.0
    assert settlement.total_transfers_pln == 0.0
    assert settlement.balance_pln == -910.0


def test_tenants_settlements_for_apartment_without_tenants(manager):
    add_apartment(manager, 'apart-pusta')
    add_bill(manager, 'apart-pusta', 500.0)

    apartment_settlement = manager.create_apartment_settlement('apart-pusta', 2025, 1)
    assert apartment_settlement.total_due_pln == 500.0

    tenants_settlements = manager.create_tenants_settlements(apartment_settlement)
    assert tenants_settlements == []

    # Polanka po wyprowadzce wszystkich najemców - też brak rozliczeń
    manager.tenants.clear()
    apartment_settlement = manager.create_apartment_settlement('apart-polanka', 2025, 1)
    assert manager.create_tenants_settlements(apartment_settlement) == []


def test_tenants_settlements_for_month_without_bills(manager):
    apartment_settlement = manager.create_apartment_settlement('apart-polanka', 2025, 2)
    tenants_settlements = manager.create_tenants_settlements(apartment_settlement)

    assert len(tenants_settlements) == 3
    for settlement in tenants_settlements:
        assert settlement.apartment_settlement == 'apart-polanka-2025-02'
        assert settlement.month == 2
        assert settlement.total_due_pln == 0.0
        assert settlement.balance_pln == 0.0


def test_tenants_of_other_apartments_are_not_included(manager):
    add_apartment(manager, 'apart-druga')
    add_tenant(manager, 'tenant-4', 'apart-druga')
    add_bill(manager, 'apart-druga', 300.0)

    polanka = manager.create_tenants_settlements(
        manager.create_apartment_settlement('apart-polanka', 2025, 1)
    )
    druga = manager.create_tenants_settlements(
        manager.create_apartment_settlement('apart-druga', 2025, 1)
    )

    assert len(polanka) == 3
    assert 'tenant-4' not in {s.tenant for s in polanka}
    assert all(s.total_due_pln == pytest.approx(910.0 / 3) for s in polanka)

    assert len(druga) == 1
    assert druga[0].tenant == 'tenant-4'
    assert druga[0].apartment_settlement == 'apart-druga-2025-01'
    assert druga[0].total_due_pln == 300.0
