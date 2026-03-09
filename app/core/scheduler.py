import logging
import threading

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import settings
from app.context import req_or_thread_id

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _run_sync(injector):
    from app.modules.certificate.service import CertificateService

    try:
        service = injector.get(CertificateService)
        service.sync_courses_from_guru()
    except Exception as e:
        logger.error(f"Scheduled course sync failed: {e}")


def start_scheduler(injector) -> BackgroundScheduler:
    global _scheduler

    if _scheduler is not None:
        return _scheduler

    _scheduler = BackgroundScheduler()

    interval = settings.GURU_SYNC_INTERVAL_MINUTES
    _scheduler.add_job(
        _run_sync,
        "interval",
        minutes=interval,
        args=[injector],
        id="guru_course_sync",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info(f"Scheduler started: course sync every {interval} minutes")

    # Run initial sync in a background thread
    thread = threading.Thread(target=_run_sync, args=[injector], daemon=True)
    thread.start()

    return _scheduler


def stop_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler stopped")
