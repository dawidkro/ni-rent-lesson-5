from src.models import Apartment, ApartmentSettlement, Bill, Parameters, Tenant, TenantSettlement, Transfer


class Manager:
    def __init__(self, parameters: Parameters):
        self.parameters = parameters 

        self.apartments = {}
        self.tenants = {}
        self.transfers = []
        self.bills = []
       
        self.load_data()

    def load_data(self):
        self.apartments = Apartment.from_json_file(self.parameters.apartments_json_path)
        self.tenants = Tenant.from_json_file(self.parameters.tenants_json_path)
        self.transfers = Transfer.from_json_file(self.parameters.transfers_json_path)
        self.bills = Bill.from_json_file(self.parameters.bills_json_path)

    def check_tenants_apartment_keys(self) -> bool:
        for tenant in self.tenants.values():
            if tenant.apartment not in self.apartments:
                return False
        return True

    def get_apartment_costs(
        self,
        apartment_key: str,
        year: int | None = None,
        month: int | None = None,
    ) -> float | None:
        """Suma rachunków (bills) mieszkania za wskazany okres.

        - podany rok i miesiąc -> rachunki z tego miesiąca,
        - tylko rok            -> rachunki z całego roku,
        - bez roku i miesiąca  -> rachunki z całej historii,
        - tylko miesiąc        -> ten miesiąc we wszystkich latach.

        Zwraca None, gdy mieszkanie nie istnieje, oraz 0.0, gdy mieszkanie
        istnieje, ale nie ma rachunków w podanym okresie.
        Rzuca ValueError przy nieprawidłowym roku lub miesiącu (np. 13).
        """
        if year is not None and not self._is_int(year, min_value=1):
            raise ValueError(f"Nieprawidłowy rok: {year!r} (oczekiwano liczby całkowitej >= 1)")
        if month is not None and not self._is_int(month, min_value=1, max_value=12):
            raise ValueError(f"Nieprawidłowy miesiąc: {month!r} (oczekiwano liczby całkowitej 1-12)")

        if apartment_key not in self.apartments:
            return None

        return sum(
            (
                bill.amount_pln
                for bill in self.bills
                if bill.apartment == apartment_key
                and (year is None or bill.settlement_year == year)
                and (month is None or bill.settlement_month == month)
            ),
            0.0,
        )

    def create_apartment_settlement(self, apartment_key: str, year: int, month: int) -> ApartmentSettlement | None:
        """Rozliczenie mieszkania za konkretny miesiąc.

        Zwraca None, gdy mieszkanie nie istnieje.
        Rzuca ValueError, gdy rok lub miesiąc jest nieprawidłowy albo nie został podany.
        """
        if year is None or month is None:
            raise ValueError("Rozliczenie wymaga podania roku i miesiąca")

        total_due = self.get_apartment_costs(apartment_key, year, month)
        if total_due is None:
            return None

        total_transfers = 0.0  # przelewy uwzględnimy w kolejnym kroku

        return ApartmentSettlement(
            key=f"{apartment_key}-{year}-{month:02d}",
            apartment=apartment_key,
            year=year,
            month=month,
            total_due_pln=total_due,
            total_transfers_pln=total_transfers,
            balance_pln=total_transfers - total_due,
        )

    def create_tenants_settlements(self, apartment_settlement: ApartmentSettlement) -> list[TenantSettlement]:
        """Rozliczenia najemców na podstawie rozliczenia mieszkania.

        Koszty mieszkania dzielimy po równo między najemców przypisanych
        do tego mieszkania. Brak najemców -> pusta lista (nie tworzymy rozliczeń).
        """
        tenant_keys = [
            key for key, tenant in self.tenants.items()
            if tenant.apartment == apartment_settlement.apartment
        ]
        if not tenant_keys:
            return []

        share = apartment_settlement.total_due_pln / len(tenant_keys)
        total_transfers = 0.0  # przelewy uwzględnimy w kolejnym kroku

        return [
            TenantSettlement(
                tenant=key,
                apartment_settlement=apartment_settlement.key,
                year=apartment_settlement.year,
                month=apartment_settlement.month,
                total_due_pln=share,
                total_transfers_pln=total_transfers,
                balance_pln=total_transfers - share,
            )
            for key in tenant_keys
        ]

    @staticmethod
    def _is_int(value, min_value: int | None = None, max_value: int | None = None) -> bool:
        # bool dziedziczy po int (True == 1), więc odrzucamy go jawnie
        if not isinstance(value, int) or isinstance(value, bool):
            return False
        if min_value is not None and value < min_value:
            return False
        if max_value is not None and value > max_value:
            return False
        return True