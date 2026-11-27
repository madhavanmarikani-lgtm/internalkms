import os
from zoneinfo import ZoneInfo
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

_scheduler = None


def init_scheduler(app):
    """
    Starts the APScheduler BackgroundScheduler to send daily expiry reminders
    every day at 10:30 AM IST (Asia/Kolkata).
    Guarded against Flask's debug reloader double-start.
    """
    global _scheduler
    if app.config.get('TESTING'):
        return None

    # Prevent duplicate scheduler when Flask debug reloader spawns parent + child processes
    if app.debug and os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        return None

    if _scheduler is not None and _scheduler.running:
        return _scheduler

    def _daily_job():
        with app.app_context():
            from app.services.expiry_service import send_daily_expiry_reminders
            send_daily_expiry_reminders()

    _scheduler = BackgroundScheduler(timezone=ZoneInfo('Asia/Kolkata'))
    _scheduler.add_job(
        func=_daily_job,
        trigger=CronTrigger(hour=10, minute=30, timezone=ZoneInfo('Asia/Kolkata')),
        id='daily_1030am_ist_expiry_reminder',
        replace_existing=True
    )
    _scheduler.start()
    return _scheduler
