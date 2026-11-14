"""Local hypothetical price comparisons; presentation never calculates finance."""
from decimal import Decimal, ROUND_HALF_UP
from simulator import compute_state


def comparison_states(profile, price, safety_buffer, current_day):
    price = Decimal(str(price))
    if not price.is_finite() or price < 0:
        raise ValueError('price must be finite and nonnegative')
    scenarios = [('ราคาต่ำกว่า 20%', Decimal('.8')),
                 ('ราคาที่เลือก', Decimal('1')),
                 ('ราคาสูงกว่า 20%', Decimal('1.2'))]
    return [dict(label=label, hypothetical=True,
                 **compute_state(profile, str((price * factor).quantize(
                     Decimal('.01'), rounding=ROUND_HALF_UP)), safety_buffer, current_day))
            for label, factor in scenarios]
