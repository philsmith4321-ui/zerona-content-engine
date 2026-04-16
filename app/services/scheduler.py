from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.database import log_event


scheduler = BackgroundScheduler(timezone="America/Chicago")


def weekly_social_job():
    try:
        from app.services.content_generator import generate_weekly_social
        from app.services.image_generator import generate_images_for_batch  # parallel, blocks until done
        from app.database import get_content_pieces
        ids = generate_weekly_social()
        pieces = get_content_pieces(limit=200)
        batch_pieces = [p for p in pieces if p["id"] in ids]
        generate_images_for_batch(ids, batch_pieces)  # scheduler jobs can wait
        log_event("generation", f"Scheduled: generated {len(ids)} social posts")
        try:
            from app.services.email_service import send_notification
            send_notification(
                f"Zerona: {len(ids)} New Posts Ready for Review",
                f"{len(ids)} new social media posts have been generated and are waiting for your review.\n\nVisit your dashboard to approve them.",
            )
        except Exception:
            pass
    except Exception as e:
        log_event("error", f"Scheduled social generation failed: {str(e)}")


def blog_generation_job():
    try:
        from app.services.content_generator import generate_blog_post
        from app.services.image_generator import generate_image
        from app.database import get_db
        row_id = generate_blog_post()
        if row_id:
            conn = get_db()
            row = conn.execute("SELECT * FROM content_pieces WHERE id = ?", (row_id,)).fetchone()
            conn.close()
            if row and row["image_prompt"]:
                generate_image(row_id, "blog", row["image_prompt"])
            log_event("generation", f"Scheduled: generated blog post {row_id}")
    except Exception as e:
        log_event("error", f"Scheduled blog generation failed: {str(e)}")


def daily_buffer_queue_job():
    try:
        from app.services.buffer_service import queue_todays_posts
        count = queue_todays_posts()
        if count > 0:
            log_event("queue", f"Scheduled: queued {count} posts to Buffer")
    except Exception as e:
        log_event("error", f"Scheduled Buffer queue failed: {str(e)}")


def init_scheduler():
    day_map = {
        "sunday": "sun", "monday": "mon", "tuesday": "tue",
        "wednesday": "wed", "thursday": "thu", "friday": "fri", "saturday": "sat",
    }
    gen_day = day_map.get(settings.generation_day.lower(), "sun")
    gen_hour = settings.generation_hour

    scheduler.add_job(
        weekly_social_job, CronTrigger(day_of_week=gen_day, hour=gen_hour, minute=0),
        id="weekly_social", replace_existing=True,
    )

    scheduler.add_job(
        blog_generation_job, CronTrigger(day="1,15", hour=gen_hour, minute=0),
        id="blog_generation", replace_existing=True,
    )

    scheduler.add_job(
        daily_buffer_queue_job, CronTrigger(hour=7, minute=0),
        id="daily_buffer", replace_existing=True,
    )

    scheduler.start()
    log_event("system", "Scheduler initialized", {
        "social_gen": f"{gen_day} at {gen_hour}:00",
        "blog_gen": f"1st & 15th at {gen_hour}:00",
        "buffer_queue": "daily at 7:00",
    })
