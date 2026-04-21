from datetime import datetime, timedelta

from app.database import (
    get_db, update_failed_job, update_content_status, log_event,
)


# Backoff schedule: attempt 1 = 15 min, attempt 2 = 1 hour, attempt 3 = 4 hours
BACKOFF_MINUTES = [15, 60, 240]


def process_retries():
    """Process all pending retry jobs whose next_retry_at has passed."""
    conn = get_db()
    now = datetime.now().isoformat()
    rows = conn.execute(
        "SELECT * FROM failed_jobs WHERE status = 'pending' AND next_retry_at <= ?",
        (now,),
    ).fetchall()
    conn.close()

    for job in rows:
        job = dict(job)
        success = False

        if job["job_type"] == "image_generation":
            success = _retry_image(job["content_id"])
        elif job["job_type"] == "buffer_post":
            success = _retry_buffer(job["content_id"])

        new_attempts = job["attempts"] + 1

        if success:
            update_failed_job(job["id"], status="completed", attempts=new_attempts)
            log_event("retry", f"Retry succeeded: {job['job_type']} for content {job['content_id']}")
        elif new_attempts >= job["max_attempts"]:
            update_failed_job(job["id"], status="exhausted", attempts=new_attempts)
            update_content_status(job["content_id"], "failed")
            log_event("retry", f"Retry exhausted: {job['job_type']} for content {job['content_id']} after {new_attempts} attempts")
        else:
            backoff = BACKOFF_MINUTES[min(new_attempts, len(BACKOFF_MINUTES) - 1)]
            next_retry = (datetime.now() + timedelta(minutes=backoff)).isoformat()
            update_failed_job(
                job["id"],
                attempts=new_attempts,
                next_retry_at=next_retry,
                error_message=job.get("error_message", ""),
            )
            log_event("retry", f"Retry {new_attempts}/{job['max_attempts']} failed for {job['job_type']} content {job['content_id']}, next retry in {backoff}m")


def _retry_image(content_id: int) -> bool:
    """Retry image generation for a content piece. Returns True on success."""
    conn = get_db()
    row = conn.execute("SELECT * FROM content_pieces WHERE id = ?", (content_id,)).fetchone()
    conn.close()
    if not row or not row["image_prompt"]:
        return False
    try:
        from app.services.image_generator import generate_image
        result = generate_image(content_id, row["content_type"], row["image_prompt"])
        return result is not None
    except Exception as e:
        log_event("error", f"Retry image gen failed for {content_id}: {str(e)}")
        return False


def _retry_buffer(content_id: int) -> bool:
    """Retry Buffer posting for a content piece. Returns True on success."""
    conn = get_db()
    row = conn.execute("SELECT * FROM content_pieces WHERE id = ?", (content_id,)).fetchone()
    conn.close()
    if not row:
        return False
    try:
        from app.services.buffer_service import queue_post
        piece = dict(row)
        buffer_id = queue_post(piece)
        if buffer_id:
            update_content_status(content_id, "queued", buffer_post_id=buffer_id)
            return True
        return False
    except Exception as e:
        log_event("error", f"Retry buffer post failed for {content_id}: {str(e)}")
        return False
