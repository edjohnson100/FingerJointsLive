# display_utils.py
#
# Multi-monitor sanity checks for the palette's saved position.
#
# Fusion floats a palette in the virtual-desktop coordinate space, but it will
# not draw one that lands outside the screen its own main window is on. Saved
# coordinates can therefore be perfectly valid -- inside a real, connected
# display -- and still produce an invisible palette, which is what happens when
# Fusion is opened on one monitor after the palette was last parked on another.
#
# So the test is not "is this point on *a* screen" -- it is "is this point on
# *Fusion's* screen". Both halves of that come from the OS via ctypes, with no
# third party modules: the screen rectangles, and the frame of Fusion's own main
# window. The Fusion API has no window-geometry property, and the palette cannot
# stand in for one -- an already-created palette just reports back whatever
# position it was last given, which is the very value being validated.

import ctypes
import ctypes.util
import os
import sys

# Keep at least this much of the palette's title bar inside the target display
# so it stays grabbable after a remap.
_MIN_VISIBLE_W = 120
_MIN_VISIBLE_H = 40


# ==============================================================================
# DISPLAY ENUMERATION
# ==============================================================================

def _displays_macos():
    class CGPoint(ctypes.Structure):
        _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]

    class CGSize(ctypes.Structure):
        _fields_ = [("width", ctypes.c_double), ("height", ctypes.c_double)]

    class CGRect(ctypes.Structure):
        _fields_ = [("origin", CGPoint), ("size", CGSize)]

    path = (ctypes.util.find_library("CoreGraphics") or
            "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
    cg = ctypes.CDLL(path)

    cg.CGGetActiveDisplayList.argtypes = [ctypes.c_uint32,
                                          ctypes.POINTER(ctypes.c_uint32),
                                          ctypes.POINTER(ctypes.c_uint32)]
    cg.CGDisplayBounds.restype = CGRect
    cg.CGDisplayBounds.argtypes = [ctypes.c_uint32]
    cg.CGMainDisplayID.restype = ctypes.c_uint32
    cg.CGDisplayCopyDisplayMode.restype = ctypes.c_void_p
    cg.CGDisplayCopyDisplayMode.argtypes = [ctypes.c_uint32]
    cg.CGDisplayModeGetPixelWidth.restype = ctypes.c_size_t
    cg.CGDisplayModeGetPixelWidth.argtypes = [ctypes.c_void_p]
    cg.CGDisplayModeGetWidth.restype = ctypes.c_size_t
    cg.CGDisplayModeGetWidth.argtypes = [ctypes.c_void_p]
    cg.CGDisplayModeRelease.argtypes = [ctypes.c_void_p]

    count = ctypes.c_uint32(0)
    ids = (ctypes.c_uint32 * 32)()
    if cg.CGGetActiveDisplayList(32, ids, ctypes.byref(count)) != 0:
        return []

    main_id = cg.CGMainDisplayID()
    displays = []
    for i in range(count.value):
        display_id = ids[i]
        rect = cg.CGDisplayBounds(display_id)
        scale = 1.0
        mode = cg.CGDisplayCopyDisplayMode(display_id)
        if mode:
            try:
                points = cg.CGDisplayModeGetWidth(mode)
                pixels = cg.CGDisplayModeGetPixelWidth(mode)
                if points:
                    scale = pixels / float(points)
            finally:
                cg.CGDisplayModeRelease(mode)
        displays.append({
            'id': int(display_id),
            'x': int(rect.origin.x),
            'y': int(rect.origin.y),
            'width': int(rect.size.width),
            'height': int(rect.size.height),
            'scale': round(scale, 2),
            'is_primary': display_id == main_id,
        })
    return displays


def _displays_windows():
    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                    ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", RECT),
                    ("rcWork", RECT), ("dwFlags", ctypes.c_ulong)]

    user32 = ctypes.windll.user32
    MONITORINFOF_PRIMARY = 1

    # Without this, a non-DPI-aware read reports scaled-down rectangles that
    # will not match the coordinates Fusion hands back for the palette.
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass

    displays = []
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_ulonglong,
                                       ctypes.c_ulonglong,
                                       ctypes.POINTER(RECT), ctypes.c_double)

    def _collect(hmonitor, hdc, lprect, data):
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if user32.GetMonitorInfoW(ctypes.c_ulonglong(hmonitor), ctypes.byref(info)):
            rect = info.rcMonitor
            displays.append({
                'id': int(hmonitor),
                'x': rect.left,
                'y': rect.top,
                'width': rect.right - rect.left,
                'height': rect.bottom - rect.top,
                'scale': 1.0,
                'is_primary': bool(info.dwFlags & MONITORINFOF_PRIMARY),
            })
        return 1

    user32.EnumDisplayMonitors(0, 0, callback_type(_collect), 0)
    return displays


def get_displays():
    """Screen rectangles in the virtual-desktop space, or [] if unavailable."""
    try:
        if sys.platform == 'darwin':
            return _displays_macos()
        if sys.platform.startswith('win'):
            return _displays_windows()
    except Exception:
        pass
    return []


def layout_signature(displays=None):
    """Stable string for the current monitor arrangement."""
    if displays is None:
        displays = get_displays()
    return '|'.join('{x},{y},{width},{height}'.format(**d)
                    for d in sorted(displays, key=lambda d: (d['x'], d['y'])))


# ==============================================================================
# HOST WINDOW GEOMETRY
#
# An add-in runs inside Fusion's own process, so "our largest normal top-level
# window" is Fusion's main window. Both lookups need no special permissions:
# window bounds and owner PIDs are public, unlike window titles or contents.
# ==============================================================================

def _app_window_rect_macos():
    class CGPoint(ctypes.Structure):
        _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]

    class CGSize(ctypes.Structure):
        _fields_ = [("width", ctypes.c_double), ("height", ctypes.c_double)]

    class CGRect(ctypes.Structure):
        _fields_ = [("origin", CGPoint), ("size", CGSize)]

    cg = ctypes.CDLL(ctypes.util.find_library("CoreGraphics") or
                     "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
    cf = ctypes.CDLL(ctypes.util.find_library("CoreFoundation") or
                     "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")

    cf.CFStringCreateWithCString.restype = ctypes.c_void_p
    cf.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
    cf.CFArrayGetCount.restype = ctypes.c_long
    cf.CFArrayGetCount.argtypes = [ctypes.c_void_p]
    cf.CFArrayGetValueAtIndex.restype = ctypes.c_void_p
    cf.CFArrayGetValueAtIndex.argtypes = [ctypes.c_void_p, ctypes.c_long]
    cf.CFDictionaryGetValue.restype = ctypes.c_void_p
    cf.CFDictionaryGetValue.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    cf.CFNumberGetValue.restype = ctypes.c_bool
    cf.CFNumberGetValue.argtypes = [ctypes.c_void_p, ctypes.c_long, ctypes.c_void_p]
    cf.CFRelease.argtypes = [ctypes.c_void_p]

    cg.CGWindowListCopyWindowInfo.restype = ctypes.c_void_p
    cg.CGWindowListCopyWindowInfo.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
    cg.CGRectMakeWithDictionaryRepresentation.restype = ctypes.c_bool
    cg.CGRectMakeWithDictionaryRepresentation.argtypes = [ctypes.c_void_p,
                                                          ctypes.POINTER(CGRect)]

    kCFStringEncodingUTF8 = 0x08000100
    kCFNumberSInt32Type = 3
    kCGWindowListOptionOnScreenOnly = 1
    kCGWindowListExcludeDesktopElements = 16

    keys = []

    def cfstr(text):
        ref = cf.CFStringCreateWithCString(None, text.encode('utf-8'),
                                           kCFStringEncodingUTF8)
        keys.append(ref)
        return ref

    key_pid = cfstr('kCGWindowOwnerPID')
    key_bounds = cfstr('kCGWindowBounds')
    key_layer = cfstr('kCGWindowLayer')

    windows = cg.CGWindowListCopyWindowInfo(
        kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements, 0)
    if not windows:
        for ref in keys:
            cf.CFRelease(ref)
        return None

    our_pid = os.getpid()
    best = None
    try:
        for i in range(cf.CFArrayGetCount(windows)):
            info = cf.CFArrayGetValueAtIndex(windows, i)

            pid = ctypes.c_int32(0)
            pid_ref = cf.CFDictionaryGetValue(info, key_pid)
            if not pid_ref or not cf.CFNumberGetValue(pid_ref, kCFNumberSInt32Type,
                                                      ctypes.byref(pid)):
                continue
            if pid.value != our_pid:
                continue

            # Layer 0 is the normal window layer; panels and popups sit above it.
            layer = ctypes.c_int32(0)
            layer_ref = cf.CFDictionaryGetValue(info, key_layer)
            if layer_ref and cf.CFNumberGetValue(layer_ref, kCFNumberSInt32Type,
                                                 ctypes.byref(layer)):
                if layer.value != 0:
                    continue

            rect = CGRect()
            bounds_ref = cf.CFDictionaryGetValue(info, key_bounds)
            if not bounds_ref or not cg.CGRectMakeWithDictionaryRepresentation(
                    bounds_ref, ctypes.byref(rect)):
                continue

            candidate = {'x': int(rect.origin.x), 'y': int(rect.origin.y),
                         'width': int(rect.size.width), 'height': int(rect.size.height)}
            # The main window is the biggest one we own -- this skips the modal
            # dialog that a diagnostic run puts on screen alongside it.
            if best is None or candidate['width'] * candidate['height'] > best['width'] * best['height']:
                best = candidate
    finally:
        cf.CFRelease(windows)
        for ref in keys:
            cf.CFRelease(ref)

    return best


def _app_window_rect_windows():
    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                    ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    user32 = ctypes.windll.user32
    our_pid = ctypes.windll.kernel32.GetCurrentProcessId()
    best = []

    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_ulonglong,
                                       ctypes.c_longlong)

    def _visit(hwnd, _param):
        pid = ctypes.c_ulong(0)
        user32.GetWindowThreadProcessId(ctypes.c_ulonglong(hwnd), ctypes.byref(pid))
        if pid.value != our_pid or not user32.IsWindowVisible(ctypes.c_ulonglong(hwnd)):
            return True
        rect = RECT()
        if not user32.GetWindowRect(ctypes.c_ulonglong(hwnd), ctypes.byref(rect)):
            return True
        candidate = {'x': rect.left, 'y': rect.top,
                     'width': rect.right - rect.left,
                     'height': rect.bottom - rect.top}
        if candidate['width'] > 0 and candidate['height'] > 0:
            if not best or candidate['width'] * candidate['height'] > best[0]['width'] * best[0]['height']:
                best[:] = [candidate]
        return True

    user32.EnumWindows(callback_type(_visit), 0)
    return best[0] if best else None


def get_app_window_rect():
    """Fusion's main window frame in virtual-desktop coordinates, or None."""
    try:
        if sys.platform == 'darwin':
            return _app_window_rect_macos()
        if sys.platform.startswith('win'):
            return _app_window_rect_windows()
    except Exception:
        pass
    return None


# ==============================================================================
# POSITION VALIDATION
# ==============================================================================

def display_containing(x, y, displays=None):
    """The display whose bounds contain the point, or None."""
    if displays is None:
        displays = get_displays()
    for d in displays:
        if d['x'] <= x < d['x'] + d['width'] and d['y'] <= y < d['y'] + d['height']:
            return d
    return None


def _clamp_into(display, left, top, width, height):
    # Keep a grabbable strip of the title bar on the display, without forcing a
    # palette narrower than that strip to move.
    max_left = display['x'] + display['width'] - min(width, _MIN_VISIBLE_W)
    max_top = display['y'] + display['height'] - _MIN_VISIBLE_H
    return (int(max(display['x'], min(left, max_left))),
            int(max(display['y'], min(top, max_top))))


def display_for_rect(rect, displays=None):
    """The display a window sits on -- the one it overlaps most, or None."""
    if rect is None:
        return None
    if displays is None:
        displays = get_displays()
    best, best_area = None, 0
    for d in displays:
        overlap_w = min(rect['x'] + rect['width'], d['x'] + d['width']) - max(rect['x'], d['x'])
        overlap_h = min(rect['y'] + rect['height'], d['y'] + d['height']) - max(rect['y'], d['y'])
        if overlap_w > 0 and overlap_h > 0 and overlap_w * overlap_h > best_area:
            best, best_area = d, overlap_w * overlap_h
    return best


def resolve_palette_position(saved_left, saved_top, width, height, app_rect=None,
                             displays=None):
    """Where the palette should actually open.

    ``app_rect`` is Fusion's main window frame; it is looked up from the OS when
    not supplied. Passing ``False`` skips the lookup, which validates the saved
    position against the connected displays only.

    Returns ``(left, top, report)``. ``report['status']`` is one of:
      ``ok``            saved position is on Fusion's display, used as-is
      ``remapped``      saved position was on another display, translated over
      ``clamped``       saved position was on no display at all
      ``unverified``    no display info available, saved position used as-is
    """
    if app_rect is None:
        app_rect = get_app_window_rect()

    report = {
        'saved': {'left': saved_left, 'top': saved_top},
        'app_rect': app_rect or None,
    }

    if displays is None:
        displays = get_displays()
    report['displays'] = displays

    if not displays:
        report['status'] = 'unverified'
        report['reason'] = 'Could not enumerate displays on this platform.'
        return saved_left, saved_top, report

    saved_display = display_containing(saved_left, saved_top, displays)
    app_display = display_for_rect(app_rect or None, displays)
    report['saved_display'] = saved_display
    report['app_display'] = app_display

    # Fusion's display is the target. Fall back to the display holding the saved
    # point, then to the primary, so a failed window lookup never makes things
    # worse than leaving the position alone.
    target = app_display or saved_display
    if target is None:
        target = next((d for d in displays if d['is_primary']), displays[0])

    if saved_display is target:
        report['status'] = 'ok'
        left, top = _clamp_into(target, saved_left, saved_top, width, height)
        report['resolved'] = {'left': left, 'top': top}
        return left, top, report

    if saved_display is not None:
        # Same relative spot on the target display, so a palette parked in the
        # bottom-right corner of one monitor lands in the bottom-right of the
        # other rather than snapping to a corner.
        fx = (saved_left - saved_display['x']) / float(saved_display['width'])
        fy = (saved_top - saved_display['y']) / float(saved_display['height'])
        left = target['x'] + fx * target['width']
        top = target['y'] + fy * target['height']
        report['status'] = 'remapped'
        report['reason'] = ('Saved position is on a display Fusion is not on; '
                            'moved to Fusion\'s display.')
    else:
        left, top = target['x'] + 80, target['y'] + 80
        report['status'] = 'clamped'
        report['reason'] = 'Saved position is not on any connected display.'

    left, top = _clamp_into(target, left, top, width, height)
    report['resolved'] = {'left': left, 'top': top}
    return left, top, report


# ==============================================================================
# DIAGNOSTICS
# ==============================================================================

def describe(saved_geometry=None, app_rect=None):
    """Human-readable multi-monitor report, for troubleshooting."""
    displays = get_displays()
    if app_rect is None:
        app_rect = get_app_window_rect()
    lines = ['Platform: {}'.format(sys.platform)]

    if not displays:
        lines.append('Displays: could not be enumerated on this platform.')
    else:
        lines.append('Displays ({}):'.format(len(displays)))
        for d in displays:
            lines.append('  {}{}  origin=({}, {})  size={}x{}  scale={}'.format(
                d['id'], ' [primary]' if d['is_primary'] else '',
                d['x'], d['y'], d['width'], d['height'], d['scale']))
        xs = [d['x'] for d in displays] + [d['x'] + d['width'] for d in displays]
        ys = [d['y'] for d in displays] + [d['y'] + d['height'] for d in displays]
        lines.append('Virtual desktop: x {}..{}, y {}..{}'.format(
            min(xs), max(xs), min(ys), max(ys)))
        lines.append('Layout signature: {}'.format(layout_signature(displays)))

    if app_rect:
        d = display_for_rect(app_rect, displays)
        lines.append("Fusion's window: origin=({}, {}) size={}x{} -> {}".format(
            app_rect['x'], app_rect['y'], app_rect['width'], app_rect['height'],
            'display {}'.format(d['id']) if d else 'no display'))
    else:
        lines.append("Fusion's window: could not be located.")

    if saved_geometry:
        left = saved_geometry.get('left')
        top = saved_geometry.get('top')
        lines.append('Saved geometry: left={} top={} width={} height={} docking={}'.format(
            left, top, saved_geometry.get('width'), saved_geometry.get('height'),
            saved_geometry.get('docking_state')))
        saved_layout = saved_geometry.get('display_layout')
        if saved_layout is not None:
            lines.append('Monitor arrangement since save: {}'.format(
                'unchanged' if saved_layout == layout_signature(displays)
                else 'CHANGED (was {})'.format(saved_layout or '<none recorded>')))
        if left is not None and top is not None:
            d = display_containing(left, top, displays)
            lines.append('Saved position lands on: {}'.format(
                'display {}'.format(d['id']) if d else 'NO DISPLAY (off-screen)'))
            resolved_l, resolved_t, report = resolve_palette_position(
                left, top, saved_geometry.get('width', 340),
                saved_geometry.get('height', 600), app_rect, displays)
            lines.append('Verdict: {} -> would open at ({}, {})'.format(
                report['status'], resolved_l, resolved_t))
            if report.get('reason'):
                lines.append('  {}'.format(report['reason']))

    return '\n'.join(lines)
