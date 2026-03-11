import sys
import os                                                                                                                 
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from contextlib import asynccontextmanager                                                                                
from fastapi import FastAPI, Request                                                                                    
from fastapi.templating import Jinja2Templates                                                                            
from fastapi.responses import HTMLResponse                                                                              
import uvicorn

from database import init_db
from routers import orders, batches
from scheduler import start_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    yield


app = FastAPI(title="EC Order Manager", lifespan=lifespan)
templates = Jinja2Templates(directory="templates")

app.include_router(orders.router, prefix="/orders")
app.include_router(batches.router, prefix="/batches")


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    try:
        from services.ecforce import EcforceClient
        stats = EcforceClient().get_dashboard_stats()
    except Exception as e:
        stats = {"address_errors": 0, "credit_failures": 0, "test_orders": 0, "duplicates": 0, "error": str(e)}
    return templates.TemplateResponse("index.html", {"request": request, "stats": stats})


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=5000)