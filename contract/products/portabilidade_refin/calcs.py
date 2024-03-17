def calc_refin_change(
    due_amount: float,
    refin_total_amount: float,
) -> float:
    return round(refin_total_amount - due_amount, 2)


def calc_free_margin(
    original_installment_amount: float,
    refin_installment_amount: float,
) -> float:
    return round(original_installment_amount - refin_installment_amount, 2)


def calc_percentage_interest(interest: float) -> float:
    return interest / 100
