from __future__ import annotations

import struct
from pathlib import Path
from typing import Any


def _base_result(path: str | None) -> dict[str, Any]:
    return {
        "attempted": True,
        "path": path,
        "status": "unknown",
        "width": None,
        "height": None,
        "canvas_bounds": None,
        "content_ratio": None,
        "edge_ratio": None,
        "distinct_sample_colors": None,
        "error": None,
    }


def _luminance(red: int, green: int, blue: int) -> float:
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _read_bmp_pixels(path: Path) -> tuple[int, int, list[list[tuple[int, int, int]]]]:
    data = path.read_bytes()
    if len(data) < 54 or data[:2] != b"BM":
        raise ValueError("Unsupported screenshot format: expected BMP.")

    pixel_offset = struct.unpack_from("<I", data, 10)[0]
    dib_size = struct.unpack_from("<I", data, 14)[0]
    if dib_size < 40:
        raise ValueError("Unsupported BMP DIB header.")

    width, raw_height, planes, bit_count, compression = struct.unpack_from("<iiHHI", data, 18)
    if width <= 0 or raw_height == 0:
        raise ValueError("Invalid BMP dimensions.")
    if planes != 1 or bit_count not in (24, 32) or compression != 0:
        raise ValueError("Only uncompressed 24-bit and 32-bit BMP screenshots are supported.")

    height = abs(raw_height)
    bytes_per_pixel = bit_count // 8
    row_stride = ((width * bytes_per_pixel + 3) // 4) * 4
    expected_size = pixel_offset + row_stride * height
    if len(data) < expected_size:
        raise ValueError("BMP pixel data is truncated.")

    rows: list[list[tuple[int, int, int]]] = []
    for row_index in range(height):
        source_row = row_index if raw_height < 0 else height - 1 - row_index
        row_offset = pixel_offset + source_row * row_stride
        row: list[tuple[int, int, int]] = []
        for x in range(width):
            pixel_offset_in_row = row_offset + x * bytes_per_pixel
            blue, green, red = data[pixel_offset_in_row : pixel_offset_in_row + 3]
            row.append((red, green, blue))
        rows.append(row)
    return width, height, rows


def _canvas_bounds(width: int, height: int) -> tuple[int, int, int, int]:
    left = int(width * 0.08)
    top = int(height * 0.18)
    right = int(width * 0.86)
    bottom = int(height * 0.95)
    if right <= left or bottom <= top:
        return 0, 0, width, height
    return left, top, right, bottom


def analyze_screenshot_readiness(path: str | None) -> dict[str, Any]:
    """Estimate whether a captured Power BI Desktop screenshot contains rendered report content."""
    result = _base_result(path)
    if not path:
        result["status"] = "missing-actual"
        result["error"] = "No screenshot path was provided."
        return result

    screenshot = Path(path)
    if not screenshot.exists():
        result["status"] = "missing-actual"
        result["error"] = f"Screenshot not found: {path}"
        return result

    try:
        width, height, rows = _read_bmp_pixels(screenshot)
    except (OSError, ValueError, struct.error) as exc:
        result["status"] = "unsupported"
        result["error"] = str(exc)
        return result

    left, top, right, bottom = _canvas_bounds(width, height)
    result["width"] = width
    result["height"] = height
    result["canvas_bounds"] = {"left": left, "top": top, "right": right, "bottom": bottom}

    content_pixels = 0
    edge_pixels = 0
    sampled_colors: set[tuple[int, int, int]] = set()
    total_pixels = max((right - left) * (bottom - top), 1)
    stride = max(1, int(total_pixels**0.5 / 24))

    previous_luma_by_x: dict[int, float] = {}
    for y in range(top, bottom):
        previous_luma: float | None = None
        for x in range(left, right):
            red, green, blue = rows[y][x]
            luma = _luminance(red, green, blue)
            if luma < 245:
                content_pixels += 1
            if previous_luma is not None and abs(luma - previous_luma) > 35:
                edge_pixels += 1
            previous_row_luma = previous_luma_by_x.get(x)
            if previous_row_luma is not None and abs(luma - previous_row_luma) > 35:
                edge_pixels += 1
            previous_luma = luma
            previous_luma_by_x[x] = luma
            if (x - left) % stride == 0 and (y - top) % stride == 0:
                sampled_colors.add((red // 16, green // 16, blue // 16))

    content_ratio = content_pixels / total_pixels
    edge_ratio = edge_pixels / max(total_pixels * 2, 1)
    result["content_ratio"] = round(content_ratio, 4)
    result["edge_ratio"] = round(edge_ratio, 4)
    result["distinct_sample_colors"] = len(sampled_colors)
    result["status"] = "ready" if content_ratio >= 0.025 or edge_ratio >= 0.006 else "low-content"
    if result["status"] == "low-content":
        result["error"] = "Screenshot canvas appears blank or still loading."
    return result
