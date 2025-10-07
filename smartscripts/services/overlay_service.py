# smartscripts/services/overlay_service.py

import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Union

from smartscripts.utils.overlay_utils import add_overlay

def overlay_marks(
    image_path: Union[str, Path],
    marks: List[Dict],
    output_path: Union[str, Path],
) -> None:
    """
    Overlay ticks, crosses, or text scores on an image.

    Each mark in marks should be a dict like:
        {"x": int, "y": int, "type": "tick"|"cross"|"score", "value": str (optional)}
    """
    image_path = Path(image_path)
    output_path = Path(output_path)

    # Load the image
    img = cv2.imread(str(image_path))
    if img is None:
        raise FileNotFoundError(f"Cannot load image: {image_path}")

    for mark in marks:
        x = mark.get("x")
        y = mark.get("y")
        m_type = mark.get("type")
        value = mark.get("value", "")

        # Skip if x or y are None
        if x is None or y is None:
            continue

        # Convert to int
        x, y = int(x), int(y)

        if m_type in ("tick", "cross"):
            # ✅ Pass position as a tuple
            img = add_overlay(img, m_type, position=(x, y), scale=0.15, centered=True)
        elif m_type == "score" and value:
            # Overlay text
            cv2.putText(
                img,
                str(value),
                (x, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2,
                lineType=cv2.LINE_AA,
            )
        else:
            # Unknown type: skip
            continue

    # Save the annotated image
    cv2.imwrite(str(output_path), img)
