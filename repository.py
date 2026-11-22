"""SQLite persistence for products, saved carts, inventory and orders."""
import sqlite3
from contextlib import contextmanager
from decimal import Decimal

from models import Product, to_money


class InsufficientStockError(Exception):
    """Raised when a reservation asks for more units than are in stock."""

    def __init__(self, sku, requested, available):
        super().__init__(f'Not enough stock for {sku}: requested {requested}, available {available}')
        self.sku = sku
        self.requested = requested
        self.available = available


class DuplicateRequestError(Exception):
    """Raised when an order with the same request_id already exists."""


class StoreRepository:
    def __init__(self, db_path='shop.db'):
        self.db_path = db_path

    def connect(self):
        conn = sqlite3.connect(self.db_path, timeout=5, isolation_level=None)
        conn.execute('PRAGMA foreign_keys = ON')
        return conn

    @contextmanager
    def _connection(self):
        conn = self.connect()
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def _transaction(self):
        with self._connection() as conn:
            # IMMEDIATE locks up front so two checkouts can't both read the same stock
            conn.execute('BEGIN IMMEDIATE')
            try:
                yield conn
            except BaseException:
                conn.execute('ROLLBACK')
                raise
            else:
                conn.execute('COMMIT')


    def get_product(self, sku):
        with self._connection() as conn:
            row = conn.execute(
                'SELECT sku, name, price, stock FROM products WHERE sku = ?', (sku,)
            ).fetchone()
        if row is None:
            return None
        sku, name, price, stock = row
        return Product(sku, name, to_money(price), stock)


    def get_saved_cart(self, user_id):
        with self._connection() as conn:
            return conn.execute(
                'SELECT sku, quantity FROM saved_cart WHERE user_id = ? ORDER BY sku', (user_id,)
            ).fetchall()

    def save_cart(self, user_id, lines):
        with self._transaction() as conn:
            conn.execute('DELETE FROM saved_cart WHERE user_id = ?', (user_id,))
            conn.executemany(
                'INSERT INTO saved_cart (user_id, sku, quantity) VALUES (?, ?, ?)',
                [(user_id, line.sku, line.quantity) for line in lines],
            )


    def reserve_order(self, user_id, request_id, amount, lines):
        """Create a pending order and reserve its stock in one transaction. Returns the order id."""
        with self._transaction() as conn:
            try:
                cur = conn.execute(
                    'INSERT INTO orders (user_id, amount, status, request_id) VALUES (?, ?, ?, ?)',
                    (user_id, str(to_money(amount)), 'pending', request_id),
                )
            except sqlite3.IntegrityError as exc:
                raise DuplicateRequestError(request_id) from exc
            order_id = cur.lastrowid
            for line in lines:
                cur = conn.execute(
                    'UPDATE products SET stock = stock - ? WHERE sku = ? AND stock >= ?',
                    (line.quantity, line.sku, line.quantity),
                )
                if cur.rowcount != 1:
                    row = conn.execute('SELECT stock FROM products WHERE sku = ?', (line.sku,)).fetchone()
                    raise InsufficientStockError(line.sku, line.quantity, row[0] if row else 0)
                conn.execute(
                    'INSERT INTO order_lines (order_id, sku, quantity) VALUES (?, ?, ?)',
                    (order_id, line.sku, line.quantity),
                )
            return order_id

    def finalize_order(self, order_id, status):
        """Set the final status; if not paid, put the reserved stock back."""
        with self._transaction() as conn:
            current = conn.execute('SELECT status FROM orders WHERE id = ?', (order_id,)).fetchone()
            if current is None or current[0] != 'pending':
                return
            if status != 'paid':
                for sku, quantity in conn.execute(
                    'SELECT sku, quantity FROM order_lines WHERE order_id = ?', (order_id,)
                ).fetchall():
                    conn.execute('UPDATE products SET stock = stock + ? WHERE sku = ?', (quantity, sku))
            conn.execute('UPDATE orders SET status = ? WHERE id = ?', (status, order_id))

    def find_order_by_request(self, request_id):
        with self._connection() as conn:
            row = conn.execute(
                'SELECT id, user_id, amount, status FROM orders WHERE request_id = ?', (request_id,)
            ).fetchone()
        if row is None:
            return None
        order_id, user_id, amount, status = row
        return order_id, user_id, Decimal(amount), status

    def list_orders(self, user_id):
        with self._connection() as conn:
            rows = conn.execute(
                'SELECT id, user_id, amount, status FROM orders WHERE user_id = ? ORDER BY id DESC',
                (user_id,),
            ).fetchall()
        return [(oid, uid, Decimal(amount), status) for oid, uid, amount, status in rows]
