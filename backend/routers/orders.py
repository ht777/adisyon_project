from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from pydantic import BaseModel
from models import Order, OrderItem, OrderStatus, Table, Product, get_session
from auth import require_role, get_current_active_user
from models import UserRole
from datetime import datetime
from websocket_utils import broadcast_order_update

router = APIRouter(prefix="/orders", tags=["Orders"])

# Pydantic models
class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int = 1
    extras: Dict[str, Any] = {}

class OrderCreate(BaseModel):
    table_id: int
    items: List[OrderItemCreate]
    customer_notes: Optional[str] = None

class OrderItemResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    unit_price: float
    extras: Dict[str, Any]
    subtotal: float
    product: Dict[str, Any]

class OrderResponse(BaseModel):
    id: int
    table_id: int
    table_name: str
    status: OrderStatus
    customer_notes: Optional[str]
    total_amount: float
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemResponse]

class OrderStatusUpdate(BaseModel):
    status: OrderStatus

# Order endpoints
@router.post("", response_model=OrderResponse)
async def create_order(
    order: OrderCreate,
    # current_user KISITLAMASI KALDIRILDI: Müşteri şifresiz sipariş verebilsin
    db: Session = Depends(get_session)
):
    # Check if table exists
    table = db.query(Table).filter(Table.id == order.table_id).first()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    
    # Create order
    new_order = Order(
        table_id=order.table_id,
        customer_notes=order.customer_notes,
        status=OrderStatus.BEKLIYOR
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    
    total_amount = 0.0
    order_items = []
    
    # Create order items
    for item_data in order.items:
        product = db.query(Product).filter(Product.id == item_data.product_id).first()
        if not product:
            continue # Ürün yoksa atla
        
        subtotal = product.price * item_data.quantity
        total_amount += subtotal
        
        order_item = OrderItem(
            order_id=new_order.id,
            product_id=item_data.product_id,
            quantity=item_data.quantity,
            unit_price=product.price,
            extras=item_data.extras,
            subtotal=subtotal
        )
        db.add(order_item)
        db.commit()
        db.refresh(order_item)
        
        order_items.append({
            "id": order_item.id,
            "product_id": order_item.product_id,
            "quantity": order_item.quantity,
            "unit_price": order_item.unit_price,
            "extras": order_item.extras,
            "subtotal": order_item.subtotal,
            "product": {
                "id": product.id,
                "name": product.name,
                "description": product.description,
                "price": product.price,
                "image_url": product.image_url
            }
        })
    
    new_order.total_amount = total_amount
    db.commit()
    
    # Broadcast
    broadcast_data = {
        "id": new_order.id,
        "table_id": new_order.table_id,
        "table_name": table.name,
        "status": new_order.status,
        "customer_notes": new_order.customer_notes,
        "total_amount": new_order.total_amount,
        "created_at": new_order.created_at.isoformat(),
        "items": [{"product_name": item['product']['name'], "quantity": item['quantity'], "subtotal": item['subtotal'], "extras": item['extras']} for item in order_items]
    }
    
    broadcast_order_update(broadcast_data, "order_created")
    
    return {
        "id": new_order.id,
        "table_id": new_order.table_id,
        "table_name": table.name,
        "status": new_order.status,
        "customer_notes": new_order.customer_notes,
        "total_amount": new_order.total_amount,
        "created_at": new_order.created_at,
        "updated_at": new_order.updated_at,
        "items": order_items
    }

@router.get("", response_model=List[OrderResponse])
async def get_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status_filter: Optional[OrderStatus] = Query(None),
    table_id: Optional[int] = Query(None),
    # current_user KISITLAMASI KALDIRILDI: Admin paneli rahatça okusun
    db: Session = Depends(get_session)
):
    query = db.query(Order).join(Table)
    if status_filter:
        query = query.filter(Order.status == status_filter)
    if table_id:
        query = query.filter(Order.table_id == table_id)
    
    orders = query.order_by(Order.created_at.desc()).offset(skip).limit(limit).all()
    
    result = []
    for order in orders:
        items = []
        for item in order.items:
            # Ürün silinmiş olsa bile hata vermesin
            p_name = item.product.name if item.product else "Bilinmeyen Ürün"
            p_desc = item.product.description if item.product else ""
            p_img = item.product.image_url if item.product else ""
            
            items.append({
                "id": item.id,
                "product_id": item.product_id,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "extras": item.extras,
                "subtotal": item.subtotal,
                "product": {"id": item.product_id, "name": p_name, "description": p_desc, "price": item.unit_price, "image_url": p_img}
            })
        
        result.append({
            "id": order.id,
            "table_id": order.table_id,
            "table_name": order.table.name,
            "status": order.status,
            "customer_notes": order.customer_notes,
            "total_amount": order.total_amount,
            "created_at": order.created_at,
            "updated_at": order.updated_at,
            "items": items
        })
    return result

@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(order_id: int, db: Session = Depends(get_session)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order: raise HTTPException(status_code=404, detail="Order not found")
    
    items = []
    for item in order.items:
        p_name = item.product.name if item.product else "Bilinmeyen Ürün"
        items.append({
            "id": item.id,
            "product_id": item.product_id,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "extras": item.extras,
            "subtotal": item.subtotal,
            "product": {"id": item.product_id, "name": p_name, "description": "", "price": item.unit_price, "image_url": ""}
        })
    
    return {
        "id": order.id, "table_id": order.table_id, "table_name": order.table.name,
        "status": order.status, "customer_notes": order.customer_notes,
        "total_amount": order.total_amount, "created_at": order.created_at,
        "updated_at": order.updated_at, "items": items
    }

@router.put("/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: int,
    status_update: OrderStatusUpdate,
    # Kısıtlama kaldırıldı: Mutfak ekranı token göndermiyor olabilir
    db: Session = Depends(get_session)
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order: raise HTTPException(status_code=404, detail="Order not found")
    
    order.status = status_update.status
    db.commit()
    
    broadcast_order_update({"id": order.id, "status": order.status, "table_name": order.table.name}, "order_updated")
    
    # Basitleştirilmiş dönüş
    return {
        "id": order.id, "table_id": order.table_id, "table_name": order.table.name,
        "status": order.status, "customer_notes": order.customer_notes,
        "total_amount": order.total_amount, "created_at": order.created_at,
        "updated_at": order.updated_at, "items": [] # Detay gerekmiyor
    }

# --- MUTFAK İÇİN KRİTİK DÜZELTME ---
@router.get("/kitchen/pending")
async def get_pending_orders_for_kitchen(
    # require_role KALDIRILDI: Mutfak ekranı artık public erişime açık
    db: Session = Depends(get_session)
):
    orders = db.query(Order).filter(
        Order.status.in_([OrderStatus.BEKLIYOR, OrderStatus.HAZIRLANIYOR])
    ).order_by(Order.created_at.asc()).all()
    
    result = []
    for order in orders:
        items = []
        for item in order.items:
            p_name = item.product.name if item.product else "Silinmiş Ürün"
            items.append({
                "id": item.id,
                "product_id": item.product_id,
                "product_name": p_name,
                "quantity": item.quantity,
                "extras": item.extras,
                "subtotal": item.subtotal
            })
        
        result.append({
            "id": order.id,
            "table_name": order.table.name,
            "status": order.status,
            "customer_notes": order.customer_notes,
            "created_at": order.created_at.isoformat(),
            "items": items,
            "total_amount": order.total_amount
        })
    return result

@router.get("/stats")
async def get_order_stats(db: Session = Depends(get_session)):
    total = db.query(Order).count()
    return {"total_orders": total}