import os
import sys
import types
import logging
import yaml
import numpy as np
from PIL import Image

try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

logger = logging.getLogger("Portraitron")

config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config", "mask_filtering.yaml")
mask_cfg = {}
if os.path.exists(config_path):
    try:
        with open(config_path, 'r') as f:
            mask_cfg = yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning(f"Failed to load mask_filtering.yaml: {e}")

MASK_BINARIZATION_THRESHOLD = mask_cfg.get("mask_binarization_threshold", 128)
SWIFTSKETCH_CONFIG_NAME = mask_cfg.get("swiftsketch_config_name", "config.npy")
DEFAULT_KEEP_RATIO = mask_cfg.get("default_keep_ratio", 0.7)
PLOT_SVG_WIDTH = mask_cfg.get("plot_svg_width", 512.0)
PLOT_SVG_HEIGHT = mask_cfg.get("plot_svg_height", 512.0)
PLOT_FIGSIZE = tuple(mask_cfg.get("plot_figsize", [6.5, 6.5]))
PLOT_MASK_ALPHA = mask_cfg.get("plot_mask_alpha", 0.18)
PLOT_PAD_RATIO = mask_cfg.get("plot_pad_ratio", 0.04)
PLOT_PAD_PIXELS = mask_cfg.get("plot_pad_pixels", 10)
PLOT_DPI = mask_cfg.get("plot_dpi", 300)

def load_binary_mask(mask_path: str) -> np.ndarray:
    """
    Loads the mask image from disk and converts it to a 2D binary numpy array.
    White pixels (>= threshold) are foreground (1), dark pixels (< threshold) are background (0).
    Returns a uint8 array of shape (H, W).
    """
    if not os.path.exists(mask_path):
        raise FileNotFoundError(f"Mask file not found: {mask_path}")
    img = Image.open(mask_path).convert('L')
    mask_np = np.array(img)
    return (mask_np >= MASK_BINARIZATION_THRESHOLD).astype(np.uint8)


def get_mask_foreground_bbox(mask_np: np.ndarray) -> tuple:
    """
    Returns the bounding box (x_min, x_max, y_min, y_max) of the foreground
    pixels (value == 1) in mask image coordinates (Y=0 at top, col=x, row=y).
    Falls back to the full mask extent if no foreground is found.
    """
    rows, cols = np.where(mask_np == 1)
    if len(rows) == 0:
        H, W = mask_np.shape
        logger.warning("Mask has no foreground pixels. Using full mask extent.")
        return 0, W - 1, 0, H - 1
    return int(cols.min()), int(cols.max()), int(rows.min()), int(rows.max())


def _stroke_bbox(strokes: list) -> tuple:
    """Returns (x_min, x_max, y_min, y_max) over all points in the stroke list."""
    pts = np.vstack([np.array(s, dtype=float) for s in strokes if s])
    return (
        float(pts[:, 0].min()), float(pts[:, 0].max()),
        float(pts[:, 1].min()), float(pts[:, 1].max()),
    )


def load_swiftsketch_config(svg_path: str) -> dict:
    """
    Loads the swiftsketch config file if it exists in the same folder as the SVG.
    Uses dynamic mock imports to avoid ModuleNotFoundError when torch is not installed
    in the active virtual environment.
    """
    if not svg_path:
        return {}
    parent = os.path.dirname(svg_path)
    config_path = os.path.join(parent, SWIFTSKETCH_CONFIG_NAME)
    
    # Fallback to parent directory if SVG is inside a subdirectory (e.g., intermediate SVGs)
    if not os.path.exists(config_path):
        config_path = os.path.join(os.path.dirname(parent), SWIFTSKETCH_CONFIG_NAME)
        
    if not os.path.exists(config_path):
        return {}

    restore_mods = {}
    mocked_mods = ['torch', 'torch._utils', 'torch.storage']
    for m in mocked_mods:
        if m in sys.modules:
            restore_mods[m] = sys.modules[m]

    try:
        # Create mock modules so pickle can reconstruct dicts containing PyTorch serialized data
        torch_mod = types.ModuleType('torch')
        sys.modules['torch'] = torch_mod
        torch_mod.__path__ = []

        torch_utils = types.ModuleType('torch._utils')
        sys.modules['torch._utils'] = torch_utils

        torch_storage = types.ModuleType('torch.storage')
        sys.modules['torch.storage'] = torch_storage

        # Dummy constructor mocks
        def rebuild_tensor(*args, **kwargs): return None
        def rebuild_device(*args, **kwargs): return None
        def rebuild_typed_storage(*args, **kwargs): return None
        def load_from_bytes(*args, **kwargs): return None

        class MockStorage: pass

        torch_utils._rebuild_tensor_v2 = rebuild_tensor
        torch_utils._rebuild_device = rebuild_device
        torch_utils._rebuild_typed_storage = rebuild_typed_storage
        torch_mod.device = rebuild_device
        torch_mod.HalfStorage = MockStorage
        torch_mod.FloatStorage = MockStorage
        torch_mod.DoubleStorage = MockStorage
        torch_mod.LongStorage = MockStorage
        torch_mod.IntStorage = MockStorage
        torch_mod.ShortStorage = MockStorage
        torch_mod.ByteStorage = MockStorage
        torch_mod.CharStorage = MockStorage
        torch_mod.BoolStorage = MockStorage

        torch_storage._TypedStorage = MockStorage
        torch_storage._load_from_bytes = load_from_bytes

        config = np.load(config_path, allow_pickle=True).item()
        logger.info(f"Loaded SwiftSketch configuration from {config_path}")
        return config
    except Exception as e:
        logger.warning(f"Failed to load swiftsketch config from {config_path}: {e}")
        return {}
    finally:
        # Clean up mocks and restore original packages to preserve clean workspace state
        for m in mocked_mods:
            if m in restore_mods:
                sys.modules[m] = restore_mods[m]
            elif m in sys.modules:
                del sys.modules[m]


def filter_strokes_with_mask(
    raw_strokes: list,
    mask_np: np.ndarray,
    svg_width: float,
    svg_height: float,
    keep_ratio: float = DEFAULT_KEEP_RATIO,
    svg_path: str = None,
) -> tuple:
    """
    Filters raw (pre-normalization) SVG strokes against a binary mask.

    COORDINATE ALIGNMENT:
      SwiftSketch scales/centers the target image and mask during optimization,
      then expands the optimized SVG strokes back to their original size.
      This function reverses that expansion to align SVG stroke coordinates
      with the mask coordinates, using configuration parameters from config.npy
      if present. Otherwise, it falls back to bounding-box alignment.

    Args:
        raw_strokes:  Strokes in raw SVG pixel coordinates (Y=0 at top).
        mask_np:      Binary mask (H, W), 1=foreground, 0=background.
        svg_width:    SVG viewBox width.
        svg_height:   SVG viewBox height.
        keep_ratio:   Min fraction of stroke points inside foreground to keep.
        svg_path:     Path to the SVG file (used to find config.npy).

    Returns:
        (kept_strokes, deleted_strokes) both in raw SVG pixel coordinates.
    """
    if mask_np is None or keep_ratio <= 0.0:
        return raw_strokes, []

    valid = [s for s in raw_strokes if s]
    if not valid:
        return raw_strokes, []

    H, W = mask_np.shape

    # Attempt to load configuration parameters from config.npy
    config = load_swiftsketch_config(svg_path)
    use_config_transform = False

    if config:
        # These keys will exist if the portrait was scaled/shifted in SwiftSketch
        scale_w = config.get('scale_w')
        scale_h = config.get('scale_h')
        orig_cx = config.get('original_center_x')
        orig_cy = config.get('original_center_y')
        if all(x is not None for x in [scale_w, scale_h, orig_cx, orig_cy]):
            use_config_transform = True
            logger.info("Using SwiftSketch config transform parameters for precise coordinate alignment.")

    if use_config_transform:
        # Reverse SwiftSketch's increase_object_size scaling to get canvas coordinates
        center_x = svg_width / 2.0
        center_y = svg_height / 2.0
        
        def map_point(x, y):
            cx = (x - orig_cx * svg_width) * scale_w + center_x
            cy = (y - orig_cy * svg_height) * scale_h + center_y
            return cx, cy
    else:
        logger.info("SwiftSketch config parameters missing or incomplete. Falling back to SVG viewBox alignment.")
        mask_W = mask_np.shape[1]
        mask_H = mask_np.shape[0]
        
        def map_point(x, y):
            # Map directly from SVG viewBox to Mask image dimensions
            cx = (x / svg_width) * mask_W if svg_width else x
            cy = (y / svg_height) * mask_H if svg_height else y
            return cx, cy

    kept, deleted = [], []
    for stroke in raw_strokes:
        if not stroke:
            continue

        inside = 0
        for x, y in stroke:
            cx, cy = map_point(x, y)
            px = int(np.clip(cx, 0, W - 1))
            py = int(np.clip(cy, 0, H - 1))
            if mask_np[py, px] == 1:
                inside += 1

        ratio = inside / len(stroke) if stroke else 0.0
        if ratio >= keep_ratio:
            kept.append(stroke)
        else:
            deleted.append(stroke)

    return kept, deleted


def plot_mask_filtering_results(
    original_strokes: list,
    kept_strokes: list,
    deleted_strokes: list,
    mask_path: str,
    save_path_prefix: str,
    svg_width: float = PLOT_SVG_WIDTH,
    svg_height: float = PLOT_SVG_HEIGHT,
    svg_path: str = None,
    keep_ratio: float = DEFAULT_KEEP_RATIO,
):
    """
    Generates and saves a visualization of mask filtering results.

    The mask image is scaled and positioned using the same parameters
    as the filtering function, ensuring the plot matches reality.
    """
    if not MATPLOTLIB_AVAILABLE:
        logger.error("matplotlib is required to plot mask filtering results.")
        return

    all_strokes = [s for s in (original_strokes or (kept_strokes + deleted_strokes)) if s]
    if not all_strokes:
        logger.warning("No strokes to plot.")
        return

    # Attempt to load configuration
    config = load_swiftsketch_config(svg_path)
    use_config_transform = False

    if config:
        scale_w = config.get('scale_w')
        scale_h = config.get('scale_h')
        orig_cx = config.get('original_center_x')
        orig_cy = config.get('original_center_y')
        if all(x is not None for x in [scale_w, scale_h, orig_cx, orig_cy]):
            use_config_transform = True

    mask_arr_display = None
    mask_extent = None
    mask_fg_bbox = None

    try:
        mask_img = Image.open(mask_path).convert('L')
        mask_arr_raw = np.array(mask_img)
        mask_H, mask_W = mask_arr_raw.shape
        binary = (mask_arr_raw >= MASK_BINARIZATION_THRESHOLD).astype(np.uint8)
        mask_fg_bbox = get_mask_foreground_bbox(binary)

        if use_config_transform:
            # Map full mask canvas coordinates [0, mask_W] to original SVG coordinates.
            # Forward transform (increase_object_size):
            # x_svg = (x_canvas - center_x) / scale_w + orig_cx * svg_width
            center_x = svg_width / 2.0
            center_y = svg_height / 2.0
            
            ext_x0 = (0.0 - center_x) / scale_w + orig_cx * svg_width
            ext_x1 = (float(mask_W) - center_x) / scale_w + orig_cx * svg_width
            
            # Incorporating Y-flip for display: display_y = svg_height - y_svg
            # For y_canvas = 0: y_svg = (0 - center_y)/scale_h + orig_cy*svg_height
            # display_y0 = svg_height - y_svg
            y_svg_0 = (0.0 - center_y) / scale_h + orig_cy * svg_height
            y_svg_1 = (float(mask_H) - center_y) / scale_h + orig_cy * svg_height
            
            ext_y0 = svg_height - y_svg_1
            ext_y1 = svg_height - y_svg_0
        else:
            # Bounding box fallback
            mfx_min, mfx_max, mfy_min, mfy_max = mask_fg_bbox
            stroke_bbox = _stroke_bbox(all_strokes)
            sx_min, sx_max, sy_min, sy_max = stroke_bbox
            
            mfx_range = max(mfx_max - mfx_min, 1)
            mfy_range = max(mfy_max - mfy_min, 1)
            sx_range = max(sx_max - sx_min, 1.0)
            sy_range = max(sy_max - sy_min, 1.0)

            scale_x = sx_range / mfx_range
            ext_x0 = sx_min + (0 - mfx_min) * scale_x
            ext_x1 = sx_min + (mask_W - 1 - mfx_min) * scale_x

            mask_py = mask_H - 1
            A = (mask_py - mfy_min) / mask_py
            B = (mask_py - mfy_max) / mask_py
            disp_top = svg_height - sy_min
            disp_bot = svg_height - sy_max
            y_span = (disp_top - disp_bot) / max(A - B, 1e-9)
            ext_y0 = disp_top - A * y_span
            ext_y1 = ext_y0 + y_span

        mask_arr_display = np.flipud(mask_arr_raw)
        mask_extent = [ext_x0, ext_x1, ext_y0, ext_y1]
    except Exception as e:
        logger.error(f"Failed to compute mask extent: {e}")

    fig, ax = plt.subplots(figsize=PLOT_FIGSIZE)

    if mask_arr_display is not None and mask_extent is not None:
        ax.imshow(mask_arr_display, extent=mask_extent,
                  cmap='gray', alpha=PLOT_MASK_ALPHA, origin='lower')

    def _flip_y(stroke):
        arr = np.array(stroke, dtype=float)
        return arr[:, 0], svg_height - arr[:, 1]

    # Initialize auto-limits seeds
    stroke_bbox = _stroke_bbox(all_strokes)
    sx_min, sx_max, sy_min, sy_max = stroke_bbox
    y_bottom_stroke = svg_height - sy_max
    y_top_stroke = svg_height - sy_min

    ax_x = [sx_min, sx_max]
    ax_y = [y_bottom_stroke, y_top_stroke]

    if mask_extent is not None:
        ax_x.extend([mask_extent[0], mask_extent[1]])
        ax_y.extend([mask_extent[2], mask_extent[3]])

    # ── Draw Bounding Boxes for Alignment verification ─────────────────────────
    # 1. Stroke Envelope bbox (Dotted magenta)
    stroke_rect = patches.Rectangle(
        (sx_min, y_bottom_stroke),
        sx_max - sx_min,
        y_top_stroke - y_bottom_stroke,
        fill=False,
        edgecolor='#e377c2',
        linestyle=':',
        linewidth=1.2,
        label='Stroke BBox'
    )
    ax.add_patch(stroke_rect)

    # 2. Mask Foreground bbox (Dotted cyan)
    if mask_fg_bbox:
        mfx_min, mfx_max, mfy_min, mfy_max = mask_fg_bbox
        if use_config_transform:
            center_x = svg_width / 2.0
            center_y = svg_height / 2.0
            fg_x0 = (mfx_min - center_x) / scale_w + orig_cx * svg_width
            fg_x1 = (mfx_max - center_x) / scale_w + orig_cx * svg_width
            fg_y0 = (mfy_min - center_y) / scale_h + orig_cy * svg_height
            fg_y1 = (mfy_max - center_y) / scale_h + orig_cy * svg_height
            fg_display_y0 = svg_height - fg_y1
            fg_display_y1 = svg_height - fg_y0
        else:
            fg_x0, fg_x1, fg_display_y0, fg_display_y1 = sx_min, sx_max, y_bottom_stroke, y_top_stroke

        mask_rect = patches.Rectangle(
            (fg_x0, fg_display_y0),
            fg_x1 - fg_x0,
            fg_display_y1 - fg_display_y0,
            fill=False,
            edgecolor='#17becf',
            linestyle='--',
            linewidth=1.2,
            label='Mask FG BBox'
        )
        ax.add_patch(mask_rect)

    # Plot deleted strokes (red dashed)
    first_del = True
    for stroke in deleted_strokes:
        if not stroke:
            continue
        xs, ys = _flip_y(stroke)
        ax.plot(xs, ys, 'r--', linewidth=1.5,
                label='Deleted stroke (noise)' if first_del else "")
        first_del = False
        ax_x.extend([xs.min(), xs.max()])
        ax_y.extend([ys.min(), ys.max()])

    # Plot kept strokes (green solid)
    first_kept = True
    for stroke in kept_strokes:
        if not stroke:
            continue
        xs, ys = _flip_y(stroke)
        ax.plot(xs, ys, 'g-', linewidth=2.0,
                label='Kept stroke' if first_kept else "")
        first_kept = False
        ax_x.extend([xs.min(), xs.max()])
        ax_y.extend([ys.min(), ys.max()])

    # Set margins and limits with padding
    x_lo, x_hi = min(ax_x), max(ax_x)
    y_lo, y_hi = min(ax_y), max(ax_y)
    px_pad = (x_hi - x_lo) * PLOT_PAD_RATIO or PLOT_PAD_PIXELS
    py_pad = (y_hi - y_lo) * PLOT_PAD_RATIO or PLOT_PAD_PIXELS
    ax.set_xlim(x_lo - px_pad, x_hi + px_pad)
    ax.set_ylim(y_lo - py_pad, y_hi + py_pad)
    ax.set_aspect('equal')
    
    ax.set_title("Mask Filtering Verification & Alignment")
    ax.set_xlabel("SVG X (pixels)")
    ax.set_ylabel("SVG Y (pixels, flipped — top=high)")
    ax.grid(True, which='both', linestyle=':', alpha=0.5)

    # ── Info box with stats and SwiftSketch metadata ──────────────────────────
    info_lines = []
    info_lines.append(r"$\bf{FILTER\ STATS}$")
    info_lines.append(f"Threshold: {keep_ratio*100:.0f}%")
    info_lines.append(f"Input Strokes: {len(original_strokes)}")
    
    total_n = len(original_strokes) or 1
    kept_n = len(kept_strokes)
    del_n = len(deleted_strokes)
    info_lines.append(f"Kept: {kept_n} ({kept_n/total_n*100:.1f}%)")
    info_lines.append(f"Pruned: {del_n} ({del_n/total_n*100:.1f}%)")



    textstr = "\n".join(info_lines)
    props = dict(boxstyle='round,pad=0.5', facecolor='#f8f9fa', alpha=0.9, edgecolor='#cccccc', linewidth=1)
    # Put it in the upper left corner in axes-relative space
    ax.text(0.02, 0.98, textstr, transform=ax.transAxes, fontsize=8.5,
            verticalalignment='top', bbox=props, fontfamily='sans-serif')

    handles, labels = ax.get_legend_handles_labels()
    if labels:
        ax.legend(handles, labels, loc='upper right', framealpha=0.9)

    os.makedirs(os.path.dirname(save_path_prefix), exist_ok=True)
    try:
        plt.savefig(f"{save_path_prefix}.png", dpi=PLOT_DPI, bbox_inches='tight')
        plt.savefig(f"{save_path_prefix}.pdf", bbox_inches='tight')
        logger.info(f"Saved mask filtering debug plots to '{save_path_prefix}.png' and '.pdf'")
    except Exception as e:
        logger.error(f"Failed to save mask filtering plots: {e}")
    finally:
        plt.close(fig)
