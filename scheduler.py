from apscheduler.schedulers.background import BackgroundScheduler
from database import SessionLocal, JobLog                                                                                 
from datetime import datetime                                                                                           

scheduler = BackgroundScheduler(timezone="Asia/Tokyo")                                                                  


def check_duplicates_job():
    db = SessionLocal()
    log = JobLog(job_type="check_duplicates", status="running", message="重複注文チェック開始")
    db.add(log)
    db.commit()
    try:
        from services.ecforce import EcforceClient
        client = EcforceClient()
        duplicates = client.get_duplicate_orders()
        if duplicates:
            from services.slack_service import post_message
            names = [f"#{o.get('code', o.get('id'))} ({o.get('customer_name', '')})" for o in duplicates[:5]]
            post_message(f"⚠️  重複注文を検知しました（{len(duplicates)}件）\n" + "\n".join(names) +
"\nhttps://ec-order-manager.replit.app/orders/duplicates")
        log.status = "success"
        log.message = f"重複注文チェック完了: {len(duplicates)}件検知"
    except Exception as e:
        log.status = "error"
        log.message = f"エラー: {str(e)}"
    db.commit()
    db.close()


def check_credit_failures_job():
    db = SessionLocal()
    log = JobLog(job_type="check_credit_failures", status="running", message="与信落ちチェック開始")
    db.add(log)
    db.commit()
    try:
        from services.ecforce import EcforceClient
        client = EcforceClient()
        orders = client.get_credit_failure_orders()
        log.status = "success"
        log.message = f"与信落ちチェック完了: {len(orders)}件"
    except Exception as e:
        log.status = "error"
        log.message = f"エラー: {str(e)}"
    db.commit()
    db.close()


def start_scheduler():
    scheduler.add_job(check_duplicates_job, "interval", minutes=30, id="check_duplicates")
    scheduler.add_job(check_credit_failures_job, "interval", hours=1, id="check_credit_failures")
    scheduler.start()