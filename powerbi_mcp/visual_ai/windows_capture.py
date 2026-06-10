from __future__ import annotations

import ctypes
import ctypes.wintypes
import os
import platform
import re
import struct
import time
from pathlib import Path
from typing import Any


_ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.wintypes.LONG),
        ("dy", ctypes.wintypes.LONG),
        ("mouseData", ctypes.wintypes.DWORD),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", _ULONG_PTR),
    ]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.wintypes.WORD),
        ("wScan", ctypes.wintypes.WORD),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", _ULONG_PTR),
    ]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.wintypes.DWORD),
        ("wParamL", ctypes.wintypes.WORD),
        ("wParamH", ctypes.wintypes.WORD),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", _MOUSEINPUT),
        ("ki", _KEYBDINPUT),
        ("hi", _HARDWAREINPUT),
    ]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.wintypes.DWORD), ("union", _INPUT_UNION)]


def win32_input_size() -> int:
    """Return the native Win32 INPUT size passed to SendInput."""
    return ctypes.sizeof(_INPUT)


def _safe_filename(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")
    return safe or "powerbi-desktop"


def title_is_powerbi_candidate(title: str, preferred_terms: list[str]) -> bool:
    title_lower = title.lower()
    if "power bi" in title_lower or ".pbip" in title_lower:
        return True
    return any(term in title_lower for term in preferred_terms)


def _capture_window_to_bmp(hwnd: int, dest: Path) -> None:
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    rect = ctypes.wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        raise OSError("GetWindowRect failed")

    width = rect.right - rect.left
    height = rect.bottom - rect.top
    if width <= 0 or height <= 0:
        raise OSError(f"Window has invalid size: {width}x{height}")

    screen_dc = user32.GetDC(0)
    memory_dc = gdi32.CreateCompatibleDC(screen_dc)
    bitmap = gdi32.CreateCompatibleBitmap(screen_dc, width, height)
    old_bitmap = gdi32.SelectObject(memory_dc, bitmap)
    try:
        if not gdi32.BitBlt(memory_dc, 0, 0, width, height, screen_dc, rect.left, rect.top, 0x00CC0020):
            raise OSError("BitBlt failed")

        row_stride = ((width * 3 + 3) // 4) * 4
        image_size = row_stride * height
        pixel_buffer = ctypes.create_string_buffer(image_size)

        bitmap_info = struct.pack(
            "<IiiHHIIiiII",
            40,
            width,
            height,
            1,
            24,
            0,
            image_size,
            0,
            0,
            0,
            0,
        )
        bitmap_info_buffer = ctypes.create_string_buffer(bitmap_info)
        if not gdi32.GetDIBits(
            memory_dc,
            bitmap,
            0,
            height,
            pixel_buffer,
            ctypes.byref(bitmap_info_buffer),
            0,
        ):
            raise OSError("GetDIBits failed")

        file_header = struct.pack("<2sIHHI", b"BM", 14 + 40 + image_size, 0, 0, 14 + 40)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as handle:
            handle.write(file_header)
            handle.write(bitmap_info)
            handle.write(pixel_buffer.raw)
    finally:
        gdi32.SelectObject(memory_dc, old_bitmap)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memory_dc)
        user32.ReleaseDC(0, screen_dc)


def _candidate_windows(pid: int | None, preferred_terms: list[str]) -> list[dict[str, Any]]:
    user32 = ctypes.windll.user32
    windows: list[dict[str, Any]] = []

    enum_windows_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def callback(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True

        title_length = user32.GetWindowTextLengthW(hwnd)
        if title_length == 0:
            return True

        buffer = ctypes.create_unicode_buffer(title_length + 1)
        user32.GetWindowTextW(hwnd, buffer, title_length + 1)
        title = buffer.value
        title_lower = title.lower()
        if not title_is_powerbi_candidate(title, preferred_terms):
            return True

        window_pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
        preferred_match = any(term in title_lower for term in preferred_terms)
        if pid is not None and int(window_pid.value) != int(pid):
            # Power BI may spawn a child process, so keep title matches as fallback only.
            windows.append(
                {
                    "hwnd": hwnd,
                    "pid": int(window_pid.value),
                    "title": title,
                    "pid_match": False,
                    "preferred_match": preferred_match,
                }
            )
            return True

        windows.append(
            {
                "hwnd": hwnd,
                "pid": int(window_pid.value),
                "title": title,
                "pid_match": True,
                "preferred_match": preferred_match,
            }
        )
        return True

    user32.EnumWindows(enum_windows_proc(callback), 0)
    return sorted(windows, key=lambda item: (not item["preferred_match"], not item["pid_match"], item["title"]))


def _preferred_terms_for_project(project: dict[str, Any]) -> list[str]:
    names = [str(project["name"])]
    if project.get("capture_name"):
        names.append(str(project["capture_name"]))
    preferred_terms = [_safe_filename(name).replace("-", " ").lower() for name in names]
    preferred_terms.extend(name.lower() for name in names)
    return [term for term in preferred_terms if term]


def _find_powerbi_window(pid: int | None, project: dict[str, Any], wait_seconds: float) -> dict[str, Any] | None:
    deadline = time.monotonic() + max(wait_seconds, 0)
    preferred_terms = _preferred_terms_for_project(project)
    windows: list[dict[str, Any]] = []
    while time.monotonic() <= deadline:
        windows = _candidate_windows(pid, preferred_terms)
        if windows and windows[0]["preferred_match"]:
            break
        time.sleep(1)
    return windows[0] if windows else None


def _press_ctrl_page_down() -> None:
    user32 = ctypes.windll.user32
    INPUT_KEYBOARD = 1
    KEYEVENTF_KEYUP = 0x0002
    VK_CONTROL = 0x11
    VK_NEXT = 0x22

    events = (_INPUT * 4)(
        _INPUT(INPUT_KEYBOARD, _INPUT_UNION(ki=_KEYBDINPUT(VK_CONTROL, 0, 0, 0, 0))),
        _INPUT(INPUT_KEYBOARD, _INPUT_UNION(ki=_KEYBDINPUT(VK_NEXT, 0, 0, 0, 0))),
        _INPUT(INPUT_KEYBOARD, _INPUT_UNION(ki=_KEYBDINPUT(VK_NEXT, 0, KEYEVENTF_KEYUP, 0, 0))),
        _INPUT(INPUT_KEYBOARD, _INPUT_UNION(ki=_KEYBDINPUT(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0, 0))),
    )
    user32.SendInput.argtypes = (ctypes.wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int)
    user32.SendInput.restype = ctypes.wintypes.UINT
    sent = user32.SendInput(len(events), events, win32_input_size())
    if sent != len(events):
        raise OSError(f"SendInput sent {sent}/{len(events)} keyboard events")


def navigate_powerbi_report_page(
    pid: int | None,
    project: dict[str, Any],
    page: dict[str, Any],
    page_index: int,
    delay_seconds: float,
) -> dict[str, Any]:
    """Best-effort visible Desktop page navigation using keyboard shortcuts."""
    result = {
        "attempted": True,
        "page_index": page_index,
        "page_id": page.get("id"),
        "page_name": page.get("displayName"),
        "error": None,
    }
    if platform.system().lower() != "windows":
        result["error"] = "Power BI Desktop page navigation is only implemented on Windows."
        return result

    selected = _find_powerbi_window(pid, project, wait_seconds=5)
    if selected is None:
        result["error"] = "No visible Power BI Desktop window found for page navigation."
        return result

    user32 = ctypes.windll.user32
    user32.SetForegroundWindow(int(selected["hwnd"]))
    if page_index > 0:
        try:
            _press_ctrl_page_down()
        except OSError as exc:
            result["error"] = str(exc)
            return result
    time.sleep(max(delay_seconds, 0))
    result["window_title"] = selected["title"]
    result["pid"] = selected["pid"]
    return result


def capture_powerbi_desktop_screenshot(
    pid: int | None,
    project: dict[str, Any],
    output_dir: Path,
    wait_seconds: float,
) -> dict[str, Any]:
    """Capture the visible Power BI Desktop window as a BMP file on Windows."""
    result = {
        "attempted": True,
        "path": None,
        "window_title": None,
        "error": None,
    }
    if platform.system().lower() != "windows":
        result["error"] = "Power BI Desktop screenshot capture is only implemented on Windows."
        return result

    selected = _find_powerbi_window(pid, project, wait_seconds)
    if selected is None:
        result["error"] = f"No visible Power BI Desktop window found within {wait_seconds} seconds."
        return result

    screenshot_name = f"{_safe_filename(project['name'])}-desktop.bmp"
    if project.get("capture_name"):
        screenshot_name = f"{_safe_filename(str(project['capture_name']))}.bmp"
    screenshot_path = output_dir / screenshot_name
    try:
        _capture_window_to_bmp(int(selected["hwnd"]), screenshot_path)
    except OSError as exc:
        result["error"] = str(exc)
        return result

    result["path"] = str(screenshot_path.resolve(strict=False))
    result["window_title"] = selected["title"]
    result["pid"] = selected["pid"]
    result["size_bytes"] = os.path.getsize(screenshot_path)
    return result
