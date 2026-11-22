"""Unit tests for StoreRepository (each test gets its own temporary database)."""
from decimal import Decimal

import pytest

from models import CartLine
from repository import DuplicateRequestError, InsufficientStockError


def test_product_price_is_returned_as_exact_decimal(repo):
    assert repo.get_product('MOU-01').price == Decimal('29.95')


def test_sku_with_sql_injection_is_treated_as_plain_text(repo):
    assert repo.get_product("x' OR '1'='1") is None


def test_saved_cart_lookup_cannot_read_other_users(repo):
    repo.save_cart('bob', [CartLine('USB-01', 'USB cable', Decimal('9.99'), 3)])
    assert repo.get_saved_cart("nobody' OR '1'='1") == []
    assert repo.get_saved_cart('bob') == [('USB-01', 3)]


def test_list_orders_only_returns_that_users_orders(repo):
    line = [CartLine('USB-01', 'USB cable', Decimal('9.99'), 1)]
    repo.reserve_order('alice', 'r1', Decimal('9.99'), line)
    repo.reserve_order('bob', 'r2', Decimal('9.99'), line)
    orders = repo.list_orders('alice')
    assert len(orders) == 1
    assert orders[0][1] == 'alice'


def test_reserve_is_all_or_nothing_when_one_line_is_short(repo, stock_of):
    lines = [
        CartLine('USB-01', 'USB cable', Decimal('9.99'), 2),
        CartLine('LAP-01', 'Laptop', Decimal('999.99'), 99),
    ]
    with pytest.raises(InsufficientStockError):
        repo.reserve_order('alice', 'r1', Decimal('1.00'), lines)
    assert stock_of('USB-01') == 50
    assert stock_of('LAP-01') == 5
    assert repo.find_order_by_request('r1') is None


def test_reserve_rejects_reused_request_id(repo):
    line = [CartLine('USB-01', 'USB cable', Decimal('9.99'), 1)]
    repo.reserve_order('alice', 'same', Decimal('9.99'), line)
    with pytest.raises(DuplicateRequestError):
        repo.reserve_order('alice', 'same', Decimal('9.99'), line)


def test_finalize_declined_restores_stock_only_once(repo, stock_of):
    line = [CartLine('LAP-01', 'Laptop', Decimal('999.99'), 2)]
    order_id = repo.reserve_order('alice', 'r1', Decimal('1999.98'), line)
    assert stock_of('LAP-01') == 3
    repo.finalize_order(order_id, 'declined')
    repo.finalize_order(order_id, 'declined')
    assert stock_of('LAP-01') == 5
