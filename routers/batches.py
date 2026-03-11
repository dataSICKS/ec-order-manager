import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse                                                              
from fastapi.templating import Jinja2Templates                                                                          
from sqlalchemy.orm import Session                                                                                        
from database import get_db, JobLog                                                                                     
from datetime import datetime

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def batch_dashboard(request: Request, db: Session = Depends(get_db)):
    logs = db.query(JobLog).order_by(JobLog.created_at.desc()).limit(50).all()
    return templates.TemplateResponse("batches.html", {"request": request, "logs": logs})


@router.post("/export-shipping-csv")
async def export_shipping_csv(db: Session = Depends(get_db)):
    log = JobLog(job_type="export_shipping_csv", status="running", message="出荷CSV出力開始")
    db.add(log)
    db.commit()
    try:
        from services.ecforce import EcforceClient
        from services.drive_service import upload_csv
        from services.chatwork_service import post_message

        client = EcforceClient()
        csv_content = client.export_shipping_csv()

        today = datetime.now().strftime("%Y%m%d")
        filename = f"出荷依頼_{today}.csv"
        file_url = upload_csv(csv_content, filename)

        post_message(f"[info][title]出荷依頼書をアップロードしました[/title]ファイル名: {filename}\n{file_url}[/info]")

        log.status = "success"
        log.message = f"出荷CSV出力完了: {filename}"
    except Exception as e:
        log.status = "error"
        log.message = f"エラー: {str(e)}"
    db.commit()
    return RedirectResponse("/batches/", status_code=303)


@router.post("/process-test-orders")
async def process_test_orders(db: Session = Depends(get_db)):
    log = JobLog(job_type="process_test_orders", status="running", message="テスト受注処理開始")
    db.add(log)
    db.commit()
    try:
        from services.ecforce import EcforceClient
        client = EcforceClient()
        orders = client.get_test_orders()
        count = 0
        for order in orders:
            client.cancel_payment(order["id"])
            count += 1
        log.status = "success"
        log.message = f"テスト受注 {count}件 処理完了"
    except Exception as e:
        log.status = "error"
        log.message = f"エラー: {str(e)}"
    db.commit()
    return RedirectResponse("/batches/", status_code=303)