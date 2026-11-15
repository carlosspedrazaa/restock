"""Reorder logic: how many units of a product to order, based on how fast it sells

    units sold = previous on-hand + units received - current on-hand
    sell-through rate = units sold / days between the two visits
    suggested order   = rate * days until next visit + safety buffer - on-hand
    never negative, rounded up to whole units
"""
import math
#Safety buffer is the amount we always want at minimum per item
SAFETY_BUFFER = 10


def units_sold(previous_on_hand, received, current_on_hand):
    #Return how many units sold between two visits (can be negative if a count was wrong)
    return previous_on_hand + received - current_on_hand


def sell_through_rate(sold, days_between):
    #Return units sold per day over the gap between two visits
    # No zero check here: suggest_order() never calls this when days_between is 0
    return sold / days_between


def order_quantity(rate, days_until_next_visit, safety_buffer, on_hand):
    #Return whole units to order so stock lasts until the next visit, never below 0
    needed = rate * days_until_next_visit + safety_buffer - on_hand
    # Decimals aren't exact (0.1 * 3 is 0.30000000000000004), so round off that
    # tiny noise first; otherwise ceil could order one extra unit
    needed = round(needed, 6)
    # Round up so we never under-order, and never suggest a negative order
    return max(0, math.ceil(needed))


def suggest_order(
    previous_on_hand,
    received,
    current_on_hand,
    days_between,
    days_until_next_visit,
    safety_buffer=SAFETY_BUFFER,
):
    #Return the suggested order for one product, or None if there's no trustworthy history.

    # First visit, or product not counted last time: no history to compare against
    if previous_on_hand is None or days_between is None:
        return None
    # Two visits on the same day: can't divide by 0 days to get a rate
    if days_between == 0:
        return None
    sold = units_sold(previous_on_hand, received, current_on_hand)
    # Negative sales means a miscount; show it for review instead of guessing
    if sold < 0:
        return None
    rate = sell_through_rate(sold, days_between)
    return order_quantity(rate, days_until_next_visit, safety_buffer, current_on_hand)
