"""Run using synthetic data only. Not executed on import."""
import logging
import uuid

from cart import CartError, ShoppingCart
from checkout import CheckoutService
from payments import FakePaymentGateway
from repository import StoreRepository
from setup_db import initialize


def main(db_path='shop.db'):
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    initialize(db_path)
    repo = StoreRepository(db_path)
    cart = ShoppingCart('demo-user', repo)
    try:
        cart.add_item('MOU-01', 2)
        cart.apply_discount('WELCOME10')
    except CartError as exc:
        print('Could not build cart:', exc)
        return
    print(f'Subtotal {cart.subtotal()}  discount {cart.discount_amount()}  total {cart.total()}')
    request_id = f'demo-{uuid.uuid4()}'
    result = CheckoutService(repo, FakePaymentGateway()).checkout(cart, 'TEST_TOKEN', request_id)
    print('Order result:', result)


if __name__ == '__main__':
    main()
