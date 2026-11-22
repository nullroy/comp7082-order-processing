# Order processing: reliable programming and unit testing lab

![tests](https://github.com/nullroy/comp7082-order-processing/actions/workflows/tests.yml/badge.svg)

This is the order-processing starter with its defects fixed, a pytest suite, and a GitHub Actions workflow.

- **DEFECTS.md** lists the 15 defects, how each one was fixed, the assumptions I made, and the test output.
- **tests/** has 37 test functions (50 cases with parametrize) covering the cart, the repository and checkout.
- **.github/workflows/tests.yml** runs `python -m pytest -q` on every push and pull request.

## Files

- `models.py`: domain objects and the `to_money` Decimal helper
- `cart.py`: shopping cart, quantity validation and discounts
- `repository.py`: SQLite access, with stock reservation and orders in transactions
- `checkout.py`: reserve stock, charge, then commit or roll back
- `payments.py`: simulated payment gateway (unchanged)
- `setup_db.py` / `demo.py`: demo database and a sample run

## Running locally

```bash
python -m pip install -r requirements.txt
python -m pytest -q
python setup_db.py
python demo.py
```
