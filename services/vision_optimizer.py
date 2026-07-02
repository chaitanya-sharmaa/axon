import base64
import io
import logging

from PIL import Image

log = logging.getLogger(__name__)

def downscale_base64_image(b64_string: str, max_size: int = 768) -> str:
    """
    Decodes a base64 image, resizes it so the longest edge is at most max_size
    while preserving aspect ratio, and returns the re-encoded base64 string.
    
    If the image is already smaller than max_size, it is returned unchanged.
    """
    try:
        # Check if there is a mime-type prefix (e.g., data:image/jpeg;base64,...)
        prefix = ""
        data = b64_string
        if "," in b64_string:
            prefix, data = b64_string.split(",", 1)
            prefix += ","

        image_bytes = base64.b64decode(data)
        img = Image.open(io.BytesIO(image_bytes))

        # Check dimensions
        width, height = img.size
        if width <= max_size and height <= max_size:
            return b64_string

        # Calculate new dimensions
        if width > height:
            new_width = max_size
            new_height = int((max_size / width) * height)
        else:
            new_height = max_size
            new_width = int((max_size / height) * width)

        # Use Resampling.LANCZOS for high quality downscaling if available, else ANTIALIAS
        resample_filter = getattr(Image, "Resampling", Image).LANCZOS
        img_resized = img.resize((new_width, new_height), resample_filter)

        # Convert back to bytes
        # Save as the original format if known, otherwise JPEG
        img_format = img.format if img.format else "JPEG"

        # JPEG does not support RGBA
        if img_format == "JPEG" and img.mode in ("RGBA", "P"):
            img_resized = img_resized.convert("RGB")

        out_io = io.BytesIO()
        img_resized.save(out_io, format=img_format, quality=85)
        out_bytes = out_io.getvalue()

        new_data = base64.b64encode(out_bytes).decode("utf-8")

        log.info(f"Vision Optimizer: Downscaled image from {width}x{height} to {new_width}x{new_height}.")
        return prefix + new_data

    except Exception as e:
        log.warning(f"Vision Optimizer failed to downscale image: {e}")
        return b64_string
