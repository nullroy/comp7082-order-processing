"""Checkout workflow: reserve stock, charge the card, then commit or roll back."""
import logging

from models import OrderResult
from repository import DuplicateRequestError, InsufficientStockError

logger = logging.getLogger(__name__)


class CheckoutError(ValueError):
    pass


def _mask(token):
    token = str(token)
    return '*' * max(len(token) - 4, 0) + token[-4:]


class CheckoutService:
    def __init__(self, repository, payment_gateway):
        self.repository = repository
        self.payment_gateway = payment_gateway

    def _existing_result(self, cart, request_id):
        existing = self.repository.find_order_by_request(request_id)
        if existing is None:
            return None
        order_id, user_id, amount, status = existing
        if user_id != cart.user_id:
            raise CheckoutError('request_id already used by a different user')
        logger.info('Repeated checkout request %s, returning order %s', request_id, order_id)
        return OrderResult(order_id, status, amount)

    def checkout(self, cart, payment_token, request_id):
        if not request_id or not str(request_id).strip():
            raise CheckoutError('request_id is required so a retried checkout is not charged twice')
        if not payment_token:
            raise CheckoutError('payment_token is required')

        previous = self._existing_result(cart, request_id)
        if previous is not None:
            return previous

        if not cart.lines:
            return OrderResult(None, 'empty', cart.total())

        amount = cart.total()

        try:
            order_id = self.repository.reserve_order(cart.user_id, request_id, amount, cart.lines)
        except InsufficientStockError as exc:
            logger.info('Checkout %s failed: %s', request_id, exc)
            return OrderResult(None, 'out_of_stock', amount)
        except DuplicateRequestError:
            return self._existing_result(cart, request_id)

        logger.info('Charging %s to token %s for order %s', amount, _mask(payment_token), order_id)
        try:
            response = self.payment_gateway.charge(amount, payment_token)
            approved = isinstance(response, dict) and response.get('approved') is True
            status = 'paid' if approved else 'declined'
        except Exception:
            logger.exception('Payment gateway error for order %s', order_id)
            status = 'payment_error'

        self.repository.finalize_order(order_id, status)

        if status == 'paid':
            cart.clear()
            cart.save()

        return OrderResult(order_id, status, amount)
