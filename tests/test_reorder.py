# Tests for reorder.py. Run them with:  .venv/bin/pytest
# Each test passes safety_buffer explicitly so changing SAFETY_BUFFER never breaks them.

from reorder import order_quantity, sell_through_rate, suggest_order, units_sold


# --- units_sold ---------------------------------------------------------------

def test_units_sold_normal():
    # 20 on the shelf + 10 delivered - 12 left = 18 sold
    assert units_sold(20, 10, 12) == 18


def test_units_sold_can_be_negative():
    # 5 before, nothing delivered, 8 now: 3 plants appeared, so a count was wrong
    assert units_sold(5, 0, 8) == -3


# --- sell_through_rate --------------------------------------------------------

def test_rate_is_units_per_day():
    # 14 sold over 7 days = 2 a day
    assert sell_through_rate(14, 7) == 2.0


# --- order_quantity -----------------------------------------------------------

def test_order_covers_days_until_next_visit():
    # 2 a day * 7 days + 3 buffer - 5 on hand = 12
    assert order_quantity(2.0, 7, 3, 5) == 12


def test_order_rounds_up():
    # 0.6 a day * 7 days = 4.2 units needed, so order 5 (can't order part of a plant)
    assert order_quantity(0.6, 7, 0, 0) == 5


def test_order_ignores_float_noise():
    # 0.1 * 30 is 3.0000000000000004 in Python; that must not round up to 4
    assert order_quantity(0.1, 30, 0, 0) == 3


def test_order_never_negative():
    # 0.5 a day * 7 days = 3.5 needed, but 100 on hand: order nothing, not -96
    assert order_quantity(0.5, 7, 0, 100) == 0


# --- suggest_order -------------------------------------------------------------

def test_suggest_normal_case():
    # sold 20 + 10 - 12 = 18 over 6 days = 3 a day; 3 * 7 + 3 buffer - 12 = 12
    assert suggest_order(20, 10, 12, 6, 7, safety_buffer=3) == 12


def test_suggest_no_sales_still_tops_up_buffer():
    # Nothing sold, but only 1 on hand and a buffer of 3: order 2
    assert suggest_order(1, 0, 1, 7, 7, safety_buffer=3) == 2


def test_suggest_first_visit():
    # No previous visit at all: nothing to compare against
    assert suggest_order(None, 0, 5, None, 7, safety_buffer=3) is None


def test_suggest_product_new_since_last_visit():
    # The store had a previous visit, but this product wasn't counted then
    assert suggest_order(None, 24, 20, 7, 7, safety_buffer=3) is None


def test_suggest_zero_days_between_visits():
    # Two visits on the same day: no rate, and no ZeroDivisionError
    assert suggest_order(10, 0, 5, 0, 7, safety_buffer=3) is None


def test_suggest_negative_sales():
    # A miscount (5 -> 8 with no delivery) is left for review instead of guessed
    assert suggest_order(5, 0, 8, 7, 7, safety_buffer=3) is None
