"""Domain objects and shared helpers for the order-processing application."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal('0.01')


def to_money(value) -> Decimal:
    """Round to cents. Floats go through str() so 29.95 stays exactly 29.95."""
    if isinstance(value, Decimal):
        amount = value
    else:
        amount = Decimal(str(value))
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass
class Product:
    sku: str
    name: str
    price: Decimal
    stock: int


@dataclass
class CartLine:
    sku: str
    name: str
    unit_price: Decimal
    quantity: int

    @property
    def line_total(self) -> Decimal:
        return to_money(self.unit_price * self.quantity)


@dataclass
class OrderResult:
    order_id: int | None
    status: str
    total: Decimal
