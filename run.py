import os
import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler
from app.config import UPLOADS_DIR, REPORTS_DIR

scheduler = BackgroundScheduler()


def scheduled_job():
    """Фоновая задача: проверка новых файлов в uploads/ и формирование отчётов."""
    pass


if __name__ == "__main__":
    scheduler.add_job(scheduled_job, "cron", hour=8, minute=0, day_of_week="mon-fri")
    scheduler.start()
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
