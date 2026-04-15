import httpx
import replicate
from pathlib import Path
from datetime import date
from typing import Optional

from app.config import settings
from app.database import update_content_status, log_event


SIZES = {
    "social_ig": {"width": 1024, "height": 1024},
    "social_fb": {"width": 1200, "height": 630},
    "blog": {"width": 1200, "height": 628},
}


def generate_image(content_id: int, content_type: str, image_prompt: str) -> Optional[str]:
    """Generate an image via Replicate Flux Schnell. Returns local file path or None."""
    size = SIZES.get(content_type, SIZES["social_ig"])
    images_dir = Path("media/images")
    images_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{date.today().isoformat()}_{content_id}.png"
    local_path = images_dir / filename

    try:
        output = replicate.run(
            "black-forest-labs/flux-schnell",
            input={
                "prompt": image_prompt,
                "width": size["width"],
                "height": size["height"],
                "num_outputs": 1,
            },
        )

        image_url = output[0] if isinstance(output, list) else str(output)

        # Download image locally
        with httpx.Client(timeout=60) as client:
            resp = client.get(image_url)
            resp.raise_for_status()
            local_path.write_bytes(resp.content)

        update_content_status(
            content_id,
            status="pending",
            image_url=f"/media/images/{filename}",
            image_local_path=str(local_path),
        )

        log_event("generation", f"Image generated for content {content_id}", {"filename": filename})
        return str(local_path)

    except Exception as e:
        log_event("error", f"Image generation failed for content {content_id}", {"error": str(e)})
        update_content_status(content_id, status="pending", image_url="/static/css/placeholder.png")
        return None


def generate_images_for_batch(content_ids: list[int], pieces: list[dict]):
    """Generate images for a batch of content pieces."""
    for piece in pieces:
        if piece["id"] in content_ids and piece.get("image_prompt"):
            generate_image(piece["id"], piece["content_type"], piece["image_prompt"])
