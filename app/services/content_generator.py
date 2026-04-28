import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Optional, Union

import anthropic

from app.config import settings
from app.database import get_db, insert_content_piece, log_event, get_content_pieces


def _load_prompt(name: str) -> str:
    path = Path(f"prompts/{name}")
    return path.read_text()


def _get_available_assets() -> str:
    """Build a summary of available marketing assets for the AI prompt."""
    catalog_path = Path("config/marketing_assets.json")
    if not catalog_path.exists():
        return ""
    catalog = json.loads(catalog_path.read_text())
    lines = []
    for cat in catalog.get("categories", []):
        assets = cat.get("assets", [])
        if not assets:
            continue
        image_assets = [a for a in assets if a["type"] == "image"]
        if not image_assets:
            continue
        lines.append(f"\n### {cat['name']} ({len(image_assets)} images)")
        for i, a in enumerate(image_assets):
            local = a.get("local_path", "")
            downloaded = " [DOWNLOADED]" if local else ""
            lines.append(f"  [{cat['id']}:{i}] {a['name']}{downloaded}")
    if not lines:
        return ""
    return "\n".join(lines)


def _resolve_asset(asset_ref: str) -> Optional[dict]:
    """Resolve an asset reference like 'social_media:3' to its URL and local path."""
    catalog_path = Path("config/marketing_assets.json")
    if not catalog_path.exists():
        return None
    try:
        cat_id, idx_str = asset_ref.split(":")
        idx = int(idx_str)
    except (ValueError, AttributeError):
        return None
    catalog = json.loads(catalog_path.read_text())
    for cat in catalog.get("categories", []):
        if cat["id"] != cat_id:
            continue
        assets = cat.get("assets", [])
        # Filter to images only (same as what we show Claude)
        image_assets = [a for a in assets if a["type"] == "image"]
        if 0 <= idx < len(image_assets):
            asset = image_assets[idx]
            local_path = asset.get("local_path", "")
            if local_path and Path(local_path).exists():
                # Serve from local
                url = "/" + local_path.replace("\\", "/")
            else:
                # Use source URL directly
                url = asset["url"]
            return {"url": url, "local_path": local_path, "name": asset["name"]}
    return None


def _parse_json_response(text: str) -> Union[list, dict]:
    cleaned = re.sub(r"```json\s*", "", text)
    cleaned = re.sub(r"```\s*$", "", cleaned)
    cleaned = cleaned.strip()
    return json.loads(cleaned)


def _get_recent_captions(days: int = 14) -> str:
    pieces = get_content_pieces(limit=50)
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    recent = [p for p in pieces if p.get("scheduled_date", "") >= cutoff]
    if not recent:
        return "No recent posts."
    lines = []
    for p in recent[:20]:
        body = p.get("edited_body") or p.get("body", "")
        lines.append(f"- [{p['content_type']}] {body[:150]}")
    return "\n".join(lines)


def _get_week_schedule(start_date: date) -> list[dict]:
    """Build the posting schedule for a week, avoiding existing slots."""
    preferred_times = ["09:00", "11:30", "14:00", "16:30", "19:00"]

    # Check what's already scheduled this week
    end_date = start_date + timedelta(days=6)
    existing = get_content_pieces(
        date_from=start_date.isoformat(),
        date_to=end_date.isoformat(),
        limit=200,
    )
    taken_slots = set()
    for p in existing:
        if p.get("scheduled_date") and p.get("scheduled_time"):
            taken_slots.add((p["scheduled_date"], p["scheduled_time"]))

    # Build FB schedule (4 posts) and IG schedule (5 posts)
    fb_days = [0, 2, 4, 5]  # Mon, Wed, Fri, Sat
    ig_days = [0, 1, 2, 4, 5]  # Mon, Tue, Wed, Fri, Sat

    schedule = []
    time_idx = 0
    for day_offset in fb_days:
        post_date = (start_date + timedelta(days=day_offset)).isoformat()
        assigned_time = None
        for t in preferred_times[time_idx:] + preferred_times[:time_idx]:
            if (post_date, t) not in taken_slots:
                assigned_time = t
                taken_slots.add((post_date, t))
                break
        if not assigned_time:
            assigned_time = preferred_times[time_idx % len(preferred_times)]
        schedule.append({"platform": "facebook", "date": post_date, "time": assigned_time})
        time_idx = (time_idx + 1) % len(preferred_times)

    for day_offset in ig_days:
        post_date = (start_date + timedelta(days=day_offset)).isoformat()
        assigned_time = None
        for t in preferred_times[time_idx:] + preferred_times[:time_idx]:
            if (post_date, t) not in taken_slots:
                assigned_time = t
                taken_slots.add((post_date, t))
                break
        if not assigned_time:
            assigned_time = preferred_times[time_idx % len(preferred_times)]
        schedule.append({"platform": "instagram", "date": post_date, "time": assigned_time})
        time_idx = (time_idx + 1) % len(preferred_times)

    return schedule


def generate_weekly_social(target_week_start: Optional[date] = None) -> list[int]:
    """Generate a week of social media posts. Returns list of content_piece IDs."""
    if target_week_start is None:
        today = date.today()
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        target_week_start = today + timedelta(days=days_until_monday)

    prompt_template = _load_prompt("social_media.txt")
    recent = _get_recent_captions()
    schedule = _get_week_schedule(target_week_start)

    batch_id = f"social_{target_week_start.isoformat()}"

    available_assets = _get_available_assets()
    asset_instruction = ""
    if available_assets:
        asset_instruction = f"""

AVAILABLE MARKETING ASSETS:
You have access to pre-made marketing images from Erchonia. When a pre-made asset fits the post topic better than a generated image, use it by setting "use_asset" to the asset ID (e.g. "social_media:3") instead of providing an "image_prompt". Use existing assets for at least 30-40% of posts when they fit well — especially logos, branded graphics, and social media templates. Still use "image_prompt" for posts that need custom/specific imagery.
{available_assets}
"""

    user_message = f"""Generate social media content for the week of {target_week_start.isoformat()}.

Posting schedule this week:
{json.dumps(schedule, indent=2)}

Recent posts (avoid repeating similar content):
{recent}
{asset_instruction}
Generate exactly {len(schedule)} posts — one for each slot in the schedule. Return a JSON array.

For each post, include EITHER:
- "image_prompt": "..." (for AI-generated images)
- "use_asset": "category_id:index" (to use a pre-made marketing asset)

Do NOT include both. Pick whichever is more appropriate for the post content."""

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=prompt_template,
            messages=[{"role": "user", "content": user_message}],
        )
        posts = _parse_json_response(response.content[0].text)
    except json.JSONDecodeError:
        # Retry with explicit JSON instruction
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=prompt_template,
            messages=[
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": "I'll provide the content as a raw JSON array:"},
            ],
        )
        posts = _parse_json_response(response.content[0].text)

    ids = []
    for i, post in enumerate(posts):
        slot = schedule[i] if i < len(schedule) else schedule[-1]
        platform_map = {"facebook": "social_fb", "instagram": "social_ig"}
        content_type = platform_map.get(slot["platform"], f"social_{slot['platform'][:2]}")

        # Handle both old format (single "caption") and new format ("captions" array)
        captions_list = post.get("captions", [])
        if captions_list and isinstance(captions_list, list):
            default_body = captions_list[0].get("caption", "")
            caption_variants = json.dumps(captions_list)
        else:
            default_body = post.get("caption", "")
            caption_variants = json.dumps([
                {"tone": "professional", "caption": default_body},
                {"tone": "conversational", "caption": default_body},
                {"tone": "story_driven", "caption": default_body},
            ])

        # Resolve marketing asset if specified
        image_url = ""
        image_local_path = ""
        image_prompt = post.get("image_prompt", "")
        use_asset = post.get("use_asset", "")

        if use_asset:
            resolved = _resolve_asset(use_asset)
            if resolved:
                image_url = resolved.get("url", "")
                image_local_path = resolved.get("local_path", "")
                image_prompt = f"[ASSET:{use_asset}] {resolved.get('name', '')}"

        piece_data = {
            "content_type": content_type,
            "category": post.get("category", "education"),
            "title": post.get("title", ""),
            "body": default_body,
            "hashtags": post.get("hashtags", ""),
            "image_prompt": image_prompt,
            "scheduled_date": slot["date"],
            "scheduled_time": slot["time"],
            "status": "pending",
            "generation_batch": batch_id,
            "caption_variants": caption_variants,
            "selected_variant": 0,
        }
        if image_url:
            piece_data["image_url"] = image_url
        if image_local_path:
            piece_data["image_local_path"] = image_local_path

        row_id = insert_content_piece(piece_data)
        ids.append(row_id)

    asset_count = sum(1 for p in posts if p.get("use_asset"))
    log_event("generation", f"Generated {len(ids)} social posts for week of {target_week_start} ({asset_count} using marketing assets)", {"batch": batch_id, "count": len(ids), "assets_used": asset_count})
    return ids


def generate_blog_post() -> Optional[int]:
    """Generate the next blog post from the topic queue. Returns content_piece ID."""
    topics_path = Path("config/blog_topics.json")
    topics = json.loads(topics_path.read_text())

    next_topic = None
    topic_index = -1
    for i, t in enumerate(topics):
        if not t.get("used", False):
            next_topic = t
            topic_index = i
            break

    if next_topic is None:
        log_event("error", "No unused blog topics remaining")
        return None

    prompt_template = _load_prompt("blog_post.txt")

    user_message = f"""Write a blog post about: {next_topic['topic']}
Target keyword: {next_topic['keyword']}"""

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=prompt_template,
            messages=[{"role": "user", "content": user_message}],
        )
        blog = _parse_json_response(response.content[0].text)
    except json.JSONDecodeError:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=prompt_template,
            messages=[
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": "Here is the blog post as raw JSON:"},
            ],
        )
        blog = _parse_json_response(response.content[0].text)

    row_id = insert_content_piece({
        "content_type": "blog",
        "category": "education",
        "title": blog.get("title", next_topic["topic"]),
        "body": blog.get("body_html", ""),
        "hashtags": blog.get("target_keyword", ""),
        "image_prompt": blog.get("image_prompt", ""),
        "scheduled_date": date.today().isoformat(),
        "status": "pending",
        "generation_batch": f"blog_{date.today().isoformat()}",
    })

    # Mark topic as used
    topics[topic_index]["used"] = True
    topics_path.write_text(json.dumps(topics, indent=2))

    log_event("generation", f"Generated blog post: {blog.get('title', '')}", {"topic": next_topic["topic"]})
    return row_id
