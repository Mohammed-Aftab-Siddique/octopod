from __future__ import annotations

import base64
import calendar
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

from app.models.roster import RosterStatus
from app.schemas.roster import RosterGrid

FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
FALLBACK_FONT = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"

NAME_WIDTH = 230
DAY_WIDTH = 46
ROW_HEIGHT = 34
MARGIN = 24
HEADER_DAY_HEIGHT = 30
HEADER_WEEKDAY_HEIGHT = 26
TITLE_HEIGHT = 56
LEGEND_ROW_HEIGHT = 34


def _font(size: int, bold: bool = False):
    from PIL import ImageFont

    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    path = FONT_DIR / name
    try:
        return ImageFont.truetype(str(path), size)
    except OSError:
        try:
            return ImageFont.truetype(FALLBACK_FONT, size)
        except OSError:
            return ImageFont.load_default()


def _fit(draw, text: str, font, max_width: int) -> str:
    if draw.textlength(text, font=font) <= max_width:
        return text
    ellipsis = "…"
    while text and draw.textlength(text + ellipsis, font=font) > max_width:
        text = text[:-1]
    return text + ellipsis


def render_roster_png(grid: RosterGrid) -> bytes:
    from PIL import Image, ImageDraw

    font_cell = _font(14)
    font_bold = _font(14, bold=True)
    font_small = _font(11)
    font_title = _font(22, bold=True)

    days = len(grid.days)
    width = MARGIN * 2 + NAME_WIDTH + days * DAY_WIDTH
    legend_rows = max(1, (len(grid.statuses) + 3) // 4)
    height = (
        TITLE_HEIGHT
        + HEADER_DAY_HEIGHT
        + HEADER_WEEKDAY_HEIGHT
        + max(1, len(grid.employees)) * ROW_HEIGHT
        + LEGEND_ROW_HEIGHT * (legend_rows + 1)
        + MARGIN
    )

    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)

    month_name = calendar.month_name[grid.month]
    state = "Published" if grid.status == RosterStatus.published else grid.status.value.title()
    title = f"Roster — {month_name} {grid.year}  ·  {state} v{grid.version}"
    draw.text((MARGIN, MARGIN // 2), title, fill="#111827", font=font_title)

    table_top = TITLE_HEIGHT
    day_top = table_top
    weekday_top = day_top + HEADER_DAY_HEIGHT
    rows_top = weekday_top + HEADER_WEEKDAY_HEIGHT

    grid_color = "#D1D5DB"
    header_bg = "#F9FAFB"

    # Header backgrounds
    draw.rectangle(
        [MARGIN, day_top, MARGIN + NAME_WIDTH + days * DAY_WIDTH, rows_top],
        fill=header_bg,
        outline=grid_color,
    )
    draw.text((MARGIN + 8, day_top + 8), "DATE", fill="#374151", font=font_bold)

    status_by_code = {status.code: status for status in grid.statuses}
    assignment_map = {
        (assignment.employee_id, assignment.date): assignment for assignment in grid.assignments
    }

    for index, day in enumerate(grid.days):
        x0 = MARGIN + NAME_WIDTH + index * DAY_WIDTH
        if day.holiday:
            draw.rectangle([x0, day_top, x0 + DAY_WIDTH, rows_top], fill="#DDD6FE")
        elif day.is_weekend:
            draw.rectangle([x0, day_top, x0 + DAY_WIDTH, rows_top], fill="#FEF3C7")
        draw.text(
            (x0 + DAY_WIDTH / 2, day_top + 6),
            str(day.day),
            fill="#111827",
            font=font_bold,
            anchor="ma",
        )
        draw.text(
            (x0 + DAY_WIDTH / 2, weekday_top + 4),
            day.weekday_label[:3],
            fill="#4B5563",
            font=font_small,
            anchor="ma",
        )
        draw.line([(x0, day_top), (x0, rows_top)], fill=grid_color)

    draw.text((MARGIN + 8, weekday_top + 4), "EMPLOYEE", fill="#4B5563", font=font_small)
    draw.line(
        [(MARGIN, weekday_top), (MARGIN + NAME_WIDTH + days * DAY_WIDTH, weekday_top)],
        fill=grid_color,
    )
    draw.line(
        [(MARGIN, rows_top), (MARGIN + NAME_WIDTH + days * DAY_WIDTH, rows_top)], fill=grid_color
    )

    for row_index, employee in enumerate(grid.employees):
        y0 = rows_top + row_index * ROW_HEIGHT
        if row_index % 2 == 1:
            draw.rectangle([MARGIN, y0, MARGIN + NAME_WIDTH, y0 + ROW_HEIGHT], fill="#F9FAFB")
        name = _fit(draw, employee.full_name, font_cell, NAME_WIDTH - 16)
        draw.text(
            (MARGIN + 8, y0 + ROW_HEIGHT / 2), name, fill="#111827", font=font_cell, anchor="lm"
        )
        for day_index, day in enumerate(grid.days):
            x0 = MARGIN + NAME_WIDTH + day_index * DAY_WIDTH
            assignment = assignment_map.get((employee.id, day.date))
            if assignment is not None:
                status = status_by_code.get(assignment.status_code)
                color = status.color if status else "#FFFFFF"
                text_color = status.text_color if status else "#111827"
                draw.rectangle([x0, y0, x0 + DAY_WIDTH, y0 + ROW_HEIGHT], fill=color)
                draw.text(
                    (x0 + DAY_WIDTH / 2, y0 + ROW_HEIGHT / 2),
                    assignment.status_code,
                    fill=text_color,
                    font=font_bold,
                    anchor="mm",
                )
        draw.line(
            [(MARGIN, y0 + ROW_HEIGHT), (MARGIN + NAME_WIDTH + days * DAY_WIDTH, y0 + ROW_HEIGHT)],
            fill=grid_color,
        )
        draw.line([(MARGIN, y0), (MARGIN, y0 + ROW_HEIGHT)], fill=grid_color)

    # Cell separators
    for day_index in range(days + 1):
        x = MARGIN + NAME_WIDTH + day_index * DAY_WIDTH
        draw.line([(x, day_top), (x, rows_top + len(grid.employees) * ROW_HEIGHT)], fill=grid_color)
    draw.line(
        [
            (MARGIN + NAME_WIDTH, day_top),
            (MARGIN + NAME_WIDTH, rows_top + len(grid.employees) * ROW_HEIGHT),
        ],
        fill=grid_color,
    )

    # Legend
    legend_top = rows_top + len(grid.employees) * ROW_HEIGHT + 18
    draw.text((MARGIN, legend_top), "Legend", fill="#111827", font=font_bold)
    box_size = 16
    x = MARGIN
    y = legend_top + 22
    for index, status in enumerate(grid.statuses):
        if index > 0 and index % 4 == 0:
            x = MARGIN
            y += LEGEND_ROW_HEIGHT - 8
        draw.rectangle([x, y, x + box_size, y + box_size], fill=status.color, outline=grid_color)
        draw.text(
            (x + box_size + 6, y + box_size / 2),
            f"{status.code} — {status.label}",
            fill="#374151",
            font=font_small,
            anchor="lm",
        )
        x += 320

    footer = f"Generated {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')} · Octopod"
    draw.text(
        (width - MARGIN, height - MARGIN + 4), footer, fill="#6B7280", font=font_small, anchor="ra"
    )

    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


async def render_png_remote(env, grid: RosterGrid) -> bytes:
    """Render through the Renderer Durable Object on Workers.

    Pillow is not part of the main Worker dependency path; the Durable Object
    owns the CPU- and memory-heavy rendering work.
    """

    binding = getattr(env, "RENDERER", None)
    if binding is None:
        return render_roster_png(grid)
    stub = binding.get(binding.idFromName("renderer"))
    encoded = await stub.render(grid.model_dump(mode="json"))
    if isinstance(encoded, bytes):
        return encoded
    return base64.b64decode(str(encoded))
