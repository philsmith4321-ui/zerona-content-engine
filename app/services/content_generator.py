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
    """Build the posting schedule for a week starting from start_date (Monday)."""
    fb_days = [0, 2, 4, 5]  # Mon, Wed, Fri, Sat
    ig_days = [0, 1, 2, 4, 5]  # Mon, Tue, Wed, Fri, Sat
    fb_times = ["10:00", "12:00", "15:00", "11:00"]
    ig_times = ["11:00", "13:00", "17:00", "12:00", "10:00"]

    schedule = []
    for i, day_offset in enumerate(fb_days):
        schedule.append({
            "platform": "facebook",
            "date": (start_date + timedelta(days=day_offset)).isoformat(),
            "time": fb_times[i],
        })
    for i, day_offset in enumerate(ig_days):
        schedule.append({
            "platform": "instagram",
            "date": (start_date + timedelta(days=day_offset)).isoformat(),
            "time": ig_times[i],
        })
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

    user_message = f"""Generate social media content for the week of {target_week_start.isoformat()}.

Posting schedule this week:
{json.dumps(schedule, indent=2)}

Recent posts (avoid repeating similar content):
{recent}

Generate exactly {len(schedule)} posts — one for each slot in the schedule. Return a JSON array."""

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
        content_type = f"social_{slot['platform'][:2]}"

        # Handle both old format (single "caption") and new format ("captions" array)
        captions_list = post.get("captions", [])
        if captions_list and isinstance(captions_list, list):
            # New 3-variant format
            default_body = captions_list[0].get("caption", "")
            caption_variants = json.dumps(captions_list)
        else:
            # Fallback: single caption (old format or parsing error)
            default_body = post.get("caption", "")
            caption_variants = json.dumps([
                {"tone": "professional", "caption": default_body},
                {"tone": "conversational", "caption": default_body},
                {"tone": "story_driven", "caption": default_body},
            ])

        row_id = insert_content_piece({
            "content_type": content_type,
            "category": post.get("category", "education"),
            "title": post.get("title", ""),
            "body": default_body,
            "hashtags": post.get("hashtags", ""),
            "image_prompt": post.get("image_prompt", ""),
            "scheduled_date": slot["date"],
            "scheduled_time": slot["time"],
            "status": "pending",
            "generation_batch": batch_id,
            "caption_variants": caption_variants,
            "selected_variant": 0,
        })
        ids.append(row_id)

    log_event("generation", f"Generated {len(ids)} social posts for week of {target_week_start}", {"batch": batch_id, "count": len(ids)})
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
