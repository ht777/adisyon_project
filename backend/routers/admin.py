from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from pydantic import BaseModel
from models import User, Product, Category, Order, Table, OrderItem, OrderStatus, RestaurantConfig, get_session
from auth import require_role, get_current_active_user
from models import UserRole
from datetime import datetime, date, timedelta
from sqlalchemy import func
import os
import shutil
import logging

# Hata ayıklama için logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("admin_reports")

router = APIRouter(prefix="/admin", tags=["Admin"])

# --- MODELLER ---
class SettingsUpdate(BaseModel):
    restaurant_name: str
    currency: str
    tax_rate: float
    service_charge: float
    wifi_password: Optional[str] = None
    order_timeout_minutes: int
    logo_url: Optional[str] = None

# --- YARDIMCI FONKSİYONLAR ---
def safe_parse_date(date_val):
    """Tarih verisini her türlü formattan kurtarmaya çalışan fonksiyon"""
    if not date_val:
        return None
    
    # Zaten datetime objesiyse direkt döndür
    if isinstance(date_val, datetime):
        return date_val
    
    # String ise parse etmeyi dene
    if isinstance(date_val, str):
        try:
            # 1. Format: ISO (2023-11-20T14:30:00)
            return datetime.fromisoformat(date_val)
        except:
            pass
        
        try:
            # 2. Format: SQL Standart (2023-11-20 14:30:00.000000)
            return datetime.strptime(date_val, "%Y-%m-%d %H:%M:%S.%f")
        except:
            pass

        try:
            # 3. Format: Saniyesiz (2023-11-20 14:30:00)
            return datetime.strptime(date_val, "%Y-%m-%d %H:%M:%S")
        except:
            pass

    # Hiçbiri olmazsa None dön (Bu veri bozuktur)
    return None

# --- ENDPOINTLER ---

@router.get("/dashboard")
async def get_dashboard_stats(
    current_user = Depends(require_role([UserRole.ADMIN, UserRole.SUPERVISOR])),
    db: Session = Depends(get_session)
):
    # Tüm siparişleri çek ve Python tarafında işle (En güvenli yöntem)
    all_orders = db.query(Order).all()
    
    total_products = db.query(Product).filter(Product.is_active == True).count()
    total_tables = db.query(Table).filter(Table.is_active == True).count()
    
    today = date.today()
    today_order_count = 0
    today_revenue = 0.0
    active_orders = 0
    
    # Grafik için son 7 günü hazırla
    daily_revenue = {} 
    for i in range(6, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        daily_revenue[d] = 0.0

    for o in all_orders:
        o_dt = safe_parse_date(o.created_at)
        if not o_dt: continue # Tarihi bozuk siparişi atla
        
        o_date = o_dt.date()
        o_date_str = o_date.isoformat()
        
        # Sipariş durumu kontrolü (Büyük/küçük harf duyarsız)
        status = str(o.status).lower() if o.status else ""
        is_cancelled = status in ["cancelled", "iptal"]
        is_active = status in ["pending", "preparing", "bekliyor", "hazirlaniyor"]
        
        # Bugünün verileri
        if o_date == today:
            today_order_count += 1
            if not is_cancelled:
                today_revenue += (o.total_amount or 0.0)
        
        if is_active:
            active_orders += 1
            
        # Grafik verisi (İptal olmayanlar)
        if o_date_str in daily_revenue and not is_cancelled:
            daily_revenue[o_date_str] += (o.total_amount or 0.0)

    return {
        "overview": {
            "total_products": total_products,
            "total_tables": total_tables,
        },
        "sales": {
            "today_orders": today_order_count,
            "today_revenue": today_revenue,
            "active_orders": active_orders,
            "daily_trend": [{"date": k, "revenue": v} for k, v in daily_revenue.items()]
        }
    }

@router.get("/reports/sales")
async def get_sales_report(
    start_date: date = Query(None),
    end_date: date = Query(None),
    current_user = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_session)
):
    # Tarih seçilmediyse varsayılan ata
    if not start_date: start_date = date.today() - timedelta(days=30)
    if not end_date: end_date = date.today()
    
    # DEBUG: Konsola bilgi bas
    print(f"📊 RAPOR İSTEĞİ: {start_date} - {end_date}")
    
    all_orders = db.query(Order).all()
    print(f"🗄️  Veritabanındaki Toplam Sipariş: {len(all_orders)}")

    filtered_orders = []
    total_revenue = 0.0
    
    breakdown = {}
    delta = end_date - start_date
    for i in range(delta.days + 1):
        day = (start_date + timedelta(days=i)).isoformat()
        breakdown[day] = {"revenue": 0, "count": 0}

    product_stats = {}
    processed_count = 0

    for o in all_orders:
        # Tarihi güvenli parse et
        o_dt = safe_parse_date(o.created_at)
        
        if not o_dt: 
            continue
            
        o_date = o_dt.date()
        
        # Tarih aralığı kontrolü
        if start_date <= o_date <= end_date:
            processed_count += 1
            
            # İptal kontrolü
            status = str(o.status).lower() if o.status else ""
            if status in ["cancelled", "iptal"]:
                continue
                
            filtered_orders.append(o)
            amount = o.total_amount or 0.0
            total_revenue += amount
            
            # Günlük kırılım
            d_str = o_date.isoformat()
            if d_str in breakdown:
                breakdown[d_str]["revenue"] += amount
                breakdown[d_str]["count"] += 1
            
            # Ürün istatistikleri
            for item in o.items:
                if not item.product: continue
                pid = item.product_id
                if pid not in product_stats:
                    product_stats[pid] = {"name": item.product.name, "qty": 0, "total": 0}
                
                product_stats[pid]["qty"] += item.quantity
                product_stats[pid]["total"] += (item.subtotal or 0.0)

    print(f"✅ Tarih Aralığına Giren Sipariş: {processed_count}")
    print(f"💰 Rapora Dahil Edilen (İptal Olmayan): {len(filtered_orders)}")
    print(f"💵 Toplam Ciro: {total_revenue}")

    top_products = sorted(product_stats.values(), key=lambda x: x["total"], reverse=True)[:10]
    daily_data = [{"date": k, **v} for k, v in sorted(breakdown.items())]

    return {
        "total_revenue": total_revenue,
        "total_orders": len(filtered_orders),
        "average_order": total_revenue / len(filtered_orders) if len(filtered_orders) > 0 else 0,
        "daily_breakdown": daily_data,
        "top_products": top_products
    }

@router.get("/settings")
async def get_system_settings(db: Session = Depends(get_session)):
    config = db.query(RestaurantConfig).first()
    if not config:
        config = RestaurantConfig()
        db.add(config)
        db.commit()
        db.refresh(config)
    return config

@router.put("/settings")
async def update_system_settings(
    settings: SettingsUpdate,
    current_user = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_session)
):
    config = db.query(RestaurantConfig).first()
    if not config:
        config = RestaurantConfig()
        db.add(config)
    
    config.restaurant_name = settings.restaurant_name
    config.currency = settings.currency
    config.tax_rate = settings.tax_rate
    config.service_charge = settings.service_charge
    config.wifi_password = settings.wifi_password
    config.order_timeout_minutes = settings.order_timeout_minutes
    
    if settings.logo_url is not None:
        config.logo_url = settings.logo_url
    
    db.commit()
    return {"message": "Ayarlar başarıyla güncellendi"}

@router.post("/settings/logo")
async def upload_restaurant_logo(
    file: UploadFile = File(...),
    current_user = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_session)
):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Sadece resim dosyası yüklenebilir.")
    
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    UPLOAD_DIR = os.path.join(BASE_DIR, "frontend", "static", "uploads")
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    file_extension = file.filename.split(".")[-1] if "." in file.filename else "png"
    filename = f"restaurant_logo.{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dosya kaydedilemedi: {str(e)}")
        
    logo_url = f"/static/uploads/{filename}"
    
    config = db.query(RestaurantConfig).first()
    if not config:
        config = RestaurantConfig()
        db.add(config)
    
    config.logo_url = logo_url
    db.commit()
    
    return {"logo_url": logo_url}