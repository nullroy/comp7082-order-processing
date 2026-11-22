"""Unit tests for CheckoutService using the supplied fake gateway plus small test doubles."""
import logging
from decimal import Decimal
from unittest.mock import Mock

import pytest

from cart import ShoppingCart
from checkout import CheckoutError, CheckoutService
from payments import FakePaymentGateway


class ExplodingGateway:
    """Stands in for a gateway that times out or crashes."""

    def __init__(self):
        self.calls = 0

    def charge(self, amount, payment_token):
        self.calls += 1
        raise TimeoutError('gateway timed out')


def test_empty_cart_does_not_charge(repo, cart):
    gateway = FakePaymentGateway()
    result = CheckoutService(repo, gateway).checkout(cart, 'tok_1234', 'req-1')
    assert result.status == 'empty'
    assert result.order_id is None
    assert gateway.calls == []


def test_successful_checkout_charges_discounted_total_and_clears_cart(repo, cart, stock_of):
    cart.add_item('MOU-01', 2)
    cart.apply_discount('WELCOME10')
    cart.save()
    gateway = FakePaymentGateway(should_approve=True)

    result = CheckoutService(repo, gateway).checkout(cart, 'tok_1234', 'req-1')

    assert result.status == 'paid'
    assert result.total == Decimal('53.91')
    assert gateway.calls == [(Decimal('53.91'), 'tok_1234')]
    assert stock_of('MOU-01') == 18
    assert cart.lines == [] and cart.discount_code is None
    assert repo.get_saved_cart('alice') == []
    assert repo.list_orders('alice')[0][3] == 'paid'


def test_declined_payment_keeps_stock_and_cart(repo, cart, stock_of):
    cart.add_item('LAP-01', 1)
    gateway = FakePaymentGateway(should_approve=False)

    result = CheckoutService(repo, gateway).checkout(cart, 'tok_1234', 'req-1')

    assert result.status == 'declined'
    assert stock_of('LAP-01') == 5
    assert cart.quantity_of('LAP-01') == 1
    assert repo.list_orders('alice')[0][3] == 'declined'


def test_gateway_exception_is_recorded_and_stock_restored(repo, cart, stock_of):
    cart.add_item('USB-01', 4)
    gateway = ExplodingGateway()

    result = CheckoutService(repo, gateway).checkout(cart, 'tok_1234', 'req-1')

    assert result.status == 'payment_error'
    assert gateway.calls == 1
    assert stock_of('USB-01') == 50
    assert cart.quantity_of('USB-01') == 4


@pytest.mark.parametrize('response', [None, {}, {'approved': 'yes'}, {'transaction_id': 'X'}])
def test_malformed_gateway_response_is_not_treated_as_paid(repo, cart, stock_of, response):
    cart.add_item('USB-01', 1)
    gateway = Mock()
    gateway.charge.return_value = response

    result = CheckoutService(repo, gateway).checkout(cart, 'tok_1234', 'req-1')

    assert result.status != 'paid'
    assert stock_of('USB-01') == 50


def test_stock_change_after_adding_to_cart_blocks_checkout(repo, cart, set_stock, stock_of):
    cart.add_item('LAP-01', 3)
    set_stock('LAP-01', 2)
    gateway = FakePaymentGateway()

    result = CheckoutService(repo, gateway).checkout(cart, 'tok_1234', 'req-1')

    assert result.status == 'out_of_stock'
    assert gateway.calls == []
    assert stock_of('LAP-01') == 2


def test_repeated_checkout_with_same_request_id_charges_once(repo, cart, stock_of):
    cart.add_item('MOU-01', 1)
    saved_lines = list(cart.lines)
    gateway = FakePaymentGateway()
    service = CheckoutService(repo, gateway)

    first = service.checkout(cart, 'tok_1234', 'req-1')
    cart.lines = saved_lines
    second = service.checkout(cart, 'tok_1234', 'req-1')

    assert second.order_id == first.order_id
    assert second.status == 'paid'
    assert len(gateway.calls) == 1
    assert stock_of('MOU-01') == 19
    assert len(repo.list_orders('alice')) == 1


def test_request_id_from_another_user_is_rejected(repo, cart):
    cart.add_item('USB-01', 1)
    service = CheckoutService(repo, FakePaymentGateway())
    service.checkout(cart, 'tok_1234', 'req-1')

    bob = ShoppingCart('bob', repo)
    bob.add_item('USB-01', 1)
    with pytest.raises(CheckoutError):
        service.checkout(bob, 'tok_5678', 'req-1')


@pytest.mark.parametrize('request_id', [None, '', '   '])
def test_missing_request_id_is_rejected(repo, cart, request_id):
    cart.add_item('USB-01', 1)
    gateway = FakePaymentGateway()
    with pytest.raises(CheckoutError):
        CheckoutService(repo, gateway).checkout(cart, 'tok_1234', request_id)
    assert gateway.calls == []


def test_payment_token_is_not_written_to_output(repo, cart, capsys, caplog):
    cart.add_item('USB-01', 1)
    with caplog.at_level(logging.DEBUG):
        CheckoutService(repo, FakePaymentGateway()).checkout(cart, 'tok_SECRET_9876', 'req-1')
    printed = capsys.readouterr()
    assert 'tok_SECRET' not in printed.out + printed.err
    assert 'tok_SECRET' not in caplog.text
    assert '9876' in caplog.text
