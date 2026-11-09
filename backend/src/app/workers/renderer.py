"""Server-side PNG rendering fallback.

The preferred export path renders in the browser. This Durable Object exists
for compatibility with clients that still request ``/export.png`` and for cases
where server-side pixel parity is required. It keeps Pillow out of the main
Worker's hot path.
"""

import base64

from app.schemas.roster import RosterGrid
from app.services.export import render_roster_png
from workers import DurableObject


class Renderer(DurableObject):
    async def render(self, grid_json: dict) -> str:
        grid = RosterGrid.model_validate(grid_json)
        return base64.b64encode(render_roster_png(grid)).decode("ascii")
