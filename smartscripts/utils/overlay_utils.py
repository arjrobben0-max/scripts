# smartscripts/utils/overlay_utils.py

import cv2
import numpy as np

def add_overlay(
    image: np.ndarray,
    overlay_type: str,
    position: tuple = (0, 0),
    scale: float = 0.15,
    centered: bool = True,
) -> np.ndarray:
    """
    Add tick/cross overlay on an image at a given position.

    Args:
        image: Input image (BGR).
        overlay_type: "tick" or "cross".
        position: Tuple (x, y) for overlay.
        scale: Scaling factor for overlay size.
        centered: Whether position is the center of overlay.

    Returns:
        Annotated image.
    """
    # For demonstration, draw simple colored circles
    color = (0, 255, 0) if overlay_type == "tick" else (0, 0, 255)
    radius = int(20 * scale * (image.shape[0] / 500))
    x, y = position
    if centered:
        cv2.circle(image, (x, y), radius, color, thickness=-1)
    else:
        cv2.circle(image, (x + radius, y + radius), radius, color, thickness=-1)
    return image
