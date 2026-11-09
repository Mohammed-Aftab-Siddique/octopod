"""Optional roster-generation offload.

The main Worker loads the inputs from D1 and can ship them to this Durable
Object when the pure compute step does not fit the request CPU budget. The
algorithm itself lives in ``app.services.generation`` and has no database
access.
"""

from app.services.generation import compute_roster, inputs_from_payload
from workers import DurableObject


class Generator(DurableObject):
    async def compute(self, payload: dict) -> dict:
        rows, shortages, warnings = compute_roster(inputs_from_payload(payload))
        return {
            "rows": [
                {
                    "employee_id": row["employee_id"],
                    "date": row["date"].isoformat(),
                    "status_code": row["status_code"],
                }
                for row in rows
            ],
            "shortages": shortages,
            "warnings": warnings,
        }
