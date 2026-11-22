import sqlite3

import pytest

from cart import ShoppingCart
from repository import StoreRepository
from setup_db import initialize


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / 'test.db')
    initialize(path)
    return path


@pytest.fixture
def repo(db_path):
    return StoreRepository(db_path)


@pytest.fixture
def cart(repo):
    return ShoppingCart('alice', repo)


@pytest.fixture
def set_stock(db_path):
    def _set(sku, stock):
        conn = sqlite3.connect(db_path)
        with conn:
            conn.execute('UPDATE products SET stock = ? WHERE sku = ?', (stock, sku))
        conn.close()
    return _set


@pytest.fixture
def add_product(db_path):
    def _add(sku, name, price, stock):
        conn = sqlite3.connect(db_path)
        with conn:
            conn.execute('INSERT INTO products VALUES (?, ?, ?, ?)', (sku, name, price, stock))
        conn.close()
    return _add


@pytest.fixture
def stock_of(repo):
    return lambda sku: repo.get_product(sku).stock
