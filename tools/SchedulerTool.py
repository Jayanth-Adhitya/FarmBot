from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
class Scheduler():
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()

    def schedule_task(self, task_func, trigger, *args, **kwargs):
        self.scheduler.add_job(task_func, trigger=trigger, args=args, kwargs=kwargs)
        return f"Task scheduled with trigger: {trigger}"

    def schedule_date_task(self, task_func, run_at: datetime, *args, **kwargs):
        trigger = DateTrigger(run_date=run_at)
        return self.schedule_task(task_func, trigger, *args, **kwargs)

    def schedule_interval_task(self, task_func, interval_seconds: int, *args, **kwargs):
        trigger = IntervalTrigger(seconds=interval_seconds)
        return self.schedule_task(task_func, trigger, *args, **kwargs)

    def schedule_cron_task(self, task_func, cron_expression: str, *args, **kwargs):
        trigger = CronTrigger.from_crontab(cron_expression)
        return self.schedule_task(task_func, trigger, *args, **kwargs)

    def shutdown(self):
        self.scheduler.shutdown()

    def run_task(self, task_func, *args, **kwargs):
        task_func(*args, **kwargs)
        return "Task executed immediately"