import random
from decimal import Decimal

def generate_random_decimal(low, high) -> Decimal:
    return Decimal(str(random.uniform(float(low), float(high)))).quantize(Decimal('0.001'))
