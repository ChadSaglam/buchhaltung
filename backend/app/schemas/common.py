"""Field types shared by every schema that carries money (B-47).

CHF amounts are bounded and finite: JSON `Infinity`/`NaN` and 1e308 must be a
422 at the edge, not a `Decimal` exception or a poisoned export later.
"""

from typing import Annotated

from pydantic import Field

MONEY_LIMIT = 1e9  # nothing a Swiss SME books is a billion francs

Money = Annotated[float, Field(allow_inf_nan=False, ge=-MONEY_LIMIT, le=MONEY_LIMIT)]
