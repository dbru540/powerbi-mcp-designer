import struct
import unittest
from pathlib import Path

from powerbi_mcp.visual_ai.screenshot_quality import analyze_screenshot_readiness


TEMP_ROOT = Path(__file__).resolve().parents[1] / "temp_test_workspace" / "screenshot_quality"


def write_bmp(path: Path, width: int, height: int, pixels: list[list[tuple[int, int, int]]]) -> None:
    row_stride = ((width * 3 + 3) // 4) * 4
    image_size = row_stride * height
    header = struct.pack("<2sIHHI", b"BM", 14 + 40 + image_size, 0, 0, 14 + 40)
    dib = struct.pack("<IiiHHIIiiII", 40, width, height, 1, 24, 0, image_size, 0, 0, 0, 0)
    rows = []
    for row in reversed(pixels):
        raw = bytearray()
        for red, green, blue in row:
            raw.extend((blue, green, red))
        raw.extend(b"\0" * (row_stride - width * 3))
        rows.append(bytes(raw))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + dib + b"".join(rows))


class ScreenshotQualityTests(unittest.TestCase):
    def setUp(self) -> None:
        if TEMP_ROOT.exists():
            for item in TEMP_ROOT.glob("*"):
                item.unlink()
        TEMP_ROOT.mkdir(parents=True, exist_ok=True)

    def test_blank_desktop_canvas_is_low_content(self) -> None:
        pixels = [[(255, 255, 255) for _ in range(120)] for _ in range(80)]
        path = TEMP_ROOT / "blank.bmp"
        write_bmp(path, 120, 80, pixels)

        result = analyze_screenshot_readiness(str(path))

        self.assertTrue(result["attempted"])
        self.assertEqual(result["status"], "low-content")
        self.assertLess(result["content_ratio"], 0.01)

    def test_visual_canvas_with_shapes_is_ready(self) -> None:
        pixels = [[(255, 255, 255) for _ in range(120)] for _ in range(80)]
        for y in range(20, 60):
            for x in range(20, 55):
                pixels[y][x] = (20, 90, 160)
            for x in range(70, 105):
                pixels[y][x] = (210, 120, 30)
        path = TEMP_ROOT / "ready.bmp"
        write_bmp(path, 120, 80, pixels)

        result = analyze_screenshot_readiness(str(path))

        self.assertEqual(result["status"], "ready")
        self.assertGreater(result["content_ratio"], 0.1)
        self.assertGreaterEqual(result["distinct_sample_colors"], 3)

    def test_missing_screenshot_reports_missing_actual(self) -> None:
        result = analyze_screenshot_readiness(str(TEMP_ROOT / "missing.bmp"))

        self.assertEqual(result["status"], "missing-actual")
        self.assertIsNotNone(result["error"])


if __name__ == "__main__":
    unittest.main()
