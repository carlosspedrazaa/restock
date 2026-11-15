#Check the log-a-visit form's text boxes and turn them into counts or error messages
from datetime import date


def parse_whole_number(text):
    #Return text as a whole number 0 or more, or None if it isn't one
    if text.isascii() and text.isdigit():
        return int(text)
    return None


def parse_visit_date(text):
    #Return text like '2026-11-13' as a date, or None if it isn't a real date
    try:
        return date.fromisoformat(text.strip())
    except ValueError:
        return None


def parse_one_count(on_hand_text, received_text):
    #Check one product's two boxes; return (count_numbers, error_message)
    if not on_hand_text:
        if received_text:
            return None, "Enter on hand too, or clear received."
        return None, None  # both blank: product not counted this visit
    on_hand = parse_whole_number(on_hand_text)
    # A blank received box just means nothing was delivered.
    received = parse_whole_number(received_text) if received_text else 0
    if on_hand is None or received is None:
        return None, "Use whole numbers, 0 or more."
    return (on_hand, received), None


def parse_counts(form, product_ids):
    #Read the on_hand_<id> and received_<id> boxes -> return (counts, errors_by_product)
    counts = []
    errors = {}
    for product_id in product_ids:
        on_hand_text = form.get(f"on_hand_{product_id}", "").strip()
        received_text = form.get(f"received_{product_id}", "").strip()
        numbers, error = parse_one_count(on_hand_text, received_text)
        if error:
            errors[product_id] = error
        elif numbers:
            on_hand, received = numbers
            counts.append(
                {"product_id": product_id, "on_hand": on_hand, "received": received}
            )
    return counts, errors


def parse_visit_form(form, product_ids, today):
    #Check the whole form; return (visit_date, counts, errors). Empty errors means OK 
    errors = {}
    visit_date = parse_visit_date(form.get("visit_date", ""))
    if visit_date is None:
        errors["visit_date"] = "Enter a real date."
    elif visit_date > today:
        # A future date is almost always a mis-tap on the date picker.
        errors["visit_date"] = "The visit date can't be in the future."

    counts, count_errors = parse_counts(form, product_ids)
    errors.update(count_errors)
    if not counts and not count_errors:
        errors["form"] = "Count at least one product."
    return visit_date, counts, errors
