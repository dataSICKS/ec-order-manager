import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import APIRouter, Request, Form, Depends                                                                   
from fastapi.responses import HTMLResponse, RedirectResponse                                                              
from fastapi.templating import Jinja2Templates                                                                            
from sqlalchemy.orm import Session                                                                                        
from database import get_db, ProcessedOrder                                                                               
from services.ecforce import EcforceClient                                                                              

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/address-errors", response_class=HTMLResponse)
async def address_errors(request: Request):
    client = EcforceClient()
    orders = client.get_address_error_orders()
    return templates.TemplateResponse("address_errors.html", {"request": request, "orders": orders})


@router.post("/address-errors/{order_id}/fix")
async def fix_address(
    order_id: str,
    last_name: str = Form(...),
    first_name: str = Form(...),
    zip_code: str = Form(...),
    prefecture: str = Form(...),
    city: str = Form(...),
    address1: str = Form(...),
    address2: str = Form(""),
    db: Session = Depends(get_db)
):
    client = EcforceClient()
    address = {
        "last_name": last_name, "first_name": first_name,
        "zip_code": zip_code, "prefecture": prefecture,
        "city": city, "address1": address1, "address2": address2,
    }
    client.update_address(order_id, address)
    client.re_authorize(order_id)
    client.add_inquiry_history(order_id, f"住所不備のため住所を修正し再与信を実施しました。修正後住所:{prefecture}{city}{address1}{address2}")
    db.add(ProcessedOrder(order_id=order_id, action="fix_address", note=f"{prefecture}{city}{address1}"))
    db.commit()
    return RedirectResponse("/orders/address-errors", status_code=303)


@router.get("/credit-failures", response_class=HTMLResponse)
async def credit_failures(request: Request):
    client = EcforceClient()
    orders = client.get_credit_failure_orders()
    return templates.TemplateResponse("credit_failures.html", {"request": request, "orders": orders})


@router.post("/credit-failures/{order_id}/reauth")
async def reauth(order_id: str, db: Session = Depends(get_db)):
    client = EcforceClient()
    client.re_authorize(order_id)
    client.add_inquiry_history(order_id, "与信落ちのため再オーソリを実施しました。")
    db.add(ProcessedOrder(order_id=order_id, action="reauth"))
    db.commit()
    return RedirectResponse("/orders/credit-failures", status_code=303)


@router.get("/duplicates", response_class=HTMLResponse)
async def duplicates(request: Request):
    client = EcforceClient()
    orders = client.get_duplicate_orders()
    return templates.TemplateResponse("duplicates.html", {"request": request, "orders": orders})


@router.post("/duplicates/{order_id}/cancel")
async def cancel_duplicate(order_id: str, db: Session = Depends(get_db)):
    client = EcforceClient()
    client.cancel_payment(order_id)
    client.add_inquiry_history(order_id, "重複注文のため決済をキャンセルしました。")
    db.add(ProcessedOrder(order_id=order_id, action="cancel_duplicate"))
    db.commit()
    return RedirectResponse("/orders/duplicates", status_code=303)


@router.get("/test-orders", response_class=HTMLResponse)
async def test_orders(request: Request):
    client = EcforceClient()
    orders = client.get_test_orders()
    return templates.TemplateResponse("test_orders.html", {"request": request, "orders": orders})


@router.post("/test-orders/{order_id}/process")
async def process_test_order(order_id: str, subscription_id: str = Form(""), db: Session = Depends(get_db)):
    client = EcforceClient()
    client.cancel_payment(order_id)
    if subscription_id:
        client.cancel_subscription(subscription_id)
        client.delete_subscription(subscription_id)
    db.add(ProcessedOrder(order_id=order_id, action="test_order_cleanup"))
    db.commit()
    return RedirectResponse("/orders/test-orders", status_code=303)