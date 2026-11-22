"""Shopping cart and discount logic."""
from decimal import Decimal

from models import CartLine, to_money


class CartError(ValueError):
    """Base class for cart errors the caller should handle."""


class InvalidQuantityError(CartError):
    pass


class UnknownProductError(CartError):
    pass


class OutOfStockError(CartError):
    pass


class InvalidDiscountError(CartError):
    pass


PERCENT_CODES = {'WELCOME10': Decimal('0.10'), 'STUDENT20': Decimal('0.20')}
FIXED_CODES = {'SAVE15': Decimal('15.00')}
NO_EFFECT_CODES = {'FREESHIP'}
VALID_CODES = set(PERCENT_CODES) | set(FIXED_CODES) | NO_EFFECT_CODES


def _validate_quantity(quantity):
    # bool is a subclass of int, so True would otherwise count as 1
    if isinstance(quantity, bool) or not isinstance(quantity, int):
        raise InvalidQuantityError(f'Quantity must be a whole number, got {quantity!r}')
    if quantity <= 0:
        raise InvalidQuantityError(f'Quantity must be positive, got {quantity}')


class ShoppingCart:
    def __init__(self, user_id, repository):
        if not user_id:
            raise ValueError('user_id is required')
        self.user_id = user_id
        self.repository = repository
        self.lines = []
        self.discount_code = None

    def _find_line(self, sku):
        return next((line for line in self.lines if line.sku == sku), None)

    def quantity_of(self, sku):
        line = self._find_line(sku)
        return line.quantity if line else 0

    def add_item(self, sku, quantity):
        _validate_quantity(quantity)
        product = self.repository.get_product(sku)
        if product is None:
            raise UnknownProductError(f'Unknown product {sku!r}')
        wanted = self.quantity_of(sku) + quantity
        if wanted > product.stock:
            raise OutOfStockError(
                f'Only {product.stock} of {sku} in stock, cart would hold {wanted}'
            )
        existing = self._find_line(sku)
        if existing:
            existing.quantity = wanted
        else:
            self.lines.append(CartLine(sku, product.name, product.price, quantity))
        return True

    def remove_item(self, sku, quantity=None):
        if quantity is not None:
            _validate_quantity(quantity)
        line = self._find_line(sku)
        if line is None:
            raise CartError(f'{sku!r} is not in the cart')
        if quantity is None or quantity >= line.quantity:
            self.lines.remove(line)
        else:
            line.quantity -= quantity
        return True

    def clear(self):
        self.lines.clear()
        self.discount_code = None


    def subtotal(self) -> Decimal:
        return to_money(sum((line.line_total for line in self.lines), Decimal('0')))

    def discount_amount(self) -> Decimal:
        """Recalculated from the current subtotal and capped at it."""
        subtotal = self.subtotal()
        code = self.discount_code
        if code in PERCENT_CODES:
            discount = to_money(subtotal * PERCENT_CODES[code])
        elif code in FIXED_CODES:
            discount = FIXED_CODES[code]
        else:
            discount = Decimal('0.00')
        return min(discount, subtotal)

    def total(self) -> Decimal:
        return to_money(self.subtotal() - self.discount_amount())

    def apply_discount(self, code):
        """A new valid code replaces the old one; codes don't stack."""
        normalized = code.strip().upper() if isinstance(code, str) else ''
        if normalized not in VALID_CODES:
            raise InvalidDiscountError(f'Invalid discount code {code!r}')
        self.discount_code = normalized
        return True

    def remove_discount(self):
        self.discount_code = None


    def load(self):
        """Replace the cart with the saved one, capped at current stock. Returns adjustment messages."""
        self.lines = []
        adjustments = []
        for sku, quantity in self.repository.get_saved_cart(self.user_id):
            product = self.repository.get_product(sku)
            if product is None:
                adjustments.append(f'{sku} is no longer sold and was removed')
                continue
            if product.stock <= 0:
                adjustments.append(f'{sku} is out of stock and was removed')
                continue
            if quantity > product.stock:
                adjustments.append(f'{sku} reduced from {quantity} to {product.stock}')
                quantity = product.stock
            self.lines.append(CartLine(sku, product.name, product.price, quantity))
        return adjustments

    def save(self):
        self.repository.save_cart(self.user_id, self.lines)
