"""Unit tests for ShoppingCart: quantities, stock checks, discounts and saved carts."""
from decimal import Decimal

import pytest

from cart import (
    CartError,
    InvalidDiscountError,
    InvalidQuantityError,
    OutOfStockError,
    ShoppingCart,
    UnknownProductError,
)


@pytest.mark.parametrize('bad_quantity', [0, -1, -50, 1.5, '2', None, True])
def test_add_item_rejects_invalid_quantities(cart, bad_quantity):
    with pytest.raises(InvalidQuantityError):
        cart.add_item('USB-01', bad_quantity)
    assert cart.lines == []


def test_add_unknown_product_raises(cart):
    with pytest.raises(UnknownProductError):
        cart.add_item('NOPE-99', 1)


def test_adding_same_product_twice_merges_into_one_line(cart):
    cart.add_item('MOU-01', 2)
    cart.add_item('MOU-01', 3)
    assert len(cart.lines) == 1
    assert cart.lines[0].quantity == 5


def test_repeated_adds_cannot_exceed_stock(cart, set_stock):
    set_stock('MOU-01', 20)
    cart.add_item('MOU-01', 15)
    with pytest.raises(OutOfStockError):
        cart.add_item('MOU-01', 15)
    assert cart.quantity_of('MOU-01') == 15


def test_add_exactly_all_remaining_stock_is_allowed(cart, set_stock):
    set_stock('LAP-01', 2)
    cart.add_item('LAP-01', 2)
    assert cart.quantity_of('LAP-01') == 2


def test_remove_item_partial_full_and_missing(cart):
    cart.add_item('USB-01', 5)
    cart.remove_item('USB-01', 2)
    assert cart.quantity_of('USB-01') == 3
    cart.remove_item('USB-01')
    assert cart.lines == []
    with pytest.raises(CartError):
        cart.remove_item('USB-01')


@pytest.mark.parametrize('bad_quantity', [0, -3])
def test_remove_item_rejects_non_positive_quantity(cart, bad_quantity):
    cart.add_item('USB-01', 2)
    with pytest.raises(InvalidQuantityError):
        cart.remove_item('USB-01', bad_quantity)
    assert cart.quantity_of('USB-01') == 2


def test_subtotal_is_exact_to_the_cent(cart):
    cart.add_item('MOU-01', 1)
    cart.add_item('USB-01', 7)
    assert cart.subtotal() == Decimal('99.88')
    assert isinstance(cart.total(), Decimal)


def test_percentage_discount_rounds_half_up_to_cents(cart):
    cart.add_item('MOU-01', 1)
    cart.apply_discount('WELCOME10')
    assert cart.discount_amount() == Decimal('3.00')
    assert cart.total() == Decimal('26.95')


def test_discount_recalculates_after_cart_is_edited(cart):
    cart.add_item('MOU-01', 1)
    cart.apply_discount('STUDENT20')
    cart.add_item('MOU-01', 1)
    assert cart.total() == Decimal('47.92')
    cart.remove_item('MOU-01')
    assert cart.total() == Decimal('0.00')


def test_discounts_do_not_stack(cart):
    cart.add_item('USB-01', 10)
    cart.apply_discount('WELCOME10')
    cart.apply_discount('WELCOME10')
    assert cart.total() == Decimal('89.91')
    cart.apply_discount('STUDENT20')
    assert cart.discount_code == 'STUDENT20'
    assert cart.total() == Decimal('79.92')


@pytest.mark.parametrize('quantity, expected_total', [
    (1, Decimal('0.00')),
    (2, Decimal('4.98')),
])
def test_fixed_discount_never_makes_total_negative(cart, quantity, expected_total):
    cart.add_item('USB-01', quantity)
    cart.apply_discount('SAVE15')
    assert cart.total() == expected_total


def test_fixed_discount_at_exact_boundary(cart, add_product):
    add_product('GFT-15', 'Gift card', 15.00, 10)
    cart.add_item('GFT-15', 1)
    cart.apply_discount('SAVE15')
    assert cart.total() == Decimal('0.00')


def test_invalid_code_raises_and_keeps_previous_code(cart):
    cart.add_item('USB-01', 10)
    cart.apply_discount('WELCOME10')
    with pytest.raises(InvalidDiscountError):
        cart.apply_discount('FAKE50')
    assert cart.discount_code == 'WELCOME10'
    assert cart.total() == Decimal('89.91')


def test_discount_code_is_case_and_space_insensitive(cart):
    cart.add_item('USB-01', 10)
    cart.apply_discount('  welcome10 ')
    assert cart.discount_code == 'WELCOME10'


def test_loading_twice_does_not_duplicate_quantities(cart, repo):
    cart.add_item('MOU-01', 2)
    cart.save()
    other = ShoppingCart('alice', repo)
    other.load()
    other.load()
    assert other.quantity_of('MOU-01') == 2
    assert len(other.lines) == 1


def test_load_replaces_unsaved_lines(cart):
    cart.add_item('USB-01', 1)
    cart.save()
    cart.add_item('MOU-01', 1)
    cart.load()
    assert cart.quantity_of('MOU-01') == 0
    assert cart.quantity_of('USB-01') == 1


def test_load_caps_quantity_when_stock_dropped(cart, set_stock):
    cart.add_item('LAP-01', 4)
    cart.save()
    set_stock('LAP-01', 1)
    messages = cart.load()
    assert cart.quantity_of('LAP-01') == 1
    assert any('LAP-01' in m for m in messages)
