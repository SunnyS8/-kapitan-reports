import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler
from app.config import UPLOADS_DIR, REPORTS_DIR

scheduler = BackgroundScheduler()


def scheduled_job():
    """Фоновая задача: проверка новых файлов в uploads/ и формирование отчётов."""
    pass  # Будет реализовано на этапе 11


if __name__ == "__main__":
    scheduler.add_job(scheduled_job, "cron", hour=8, minute=0, day_of_week="mon-fri")
    scheduler.start()
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
