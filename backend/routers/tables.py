from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from pydantic import BaseModel
from models import Table, get_session, Order
from auth import require_role, get_current_active_user
from models import UserRole
import qrcode
import io
import base64
import socket
from datetime import datetime

router = APIRouter(prefix="/tables", tags=["Tables"])

# Pydantic models
class TableCreate(BaseModel):
    name: str
    number: int

class TableResponse(BaseModel):
    id: int
    name: str
    number: int
    qr_url: Optional[str]
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class TableUpdate(BaseModel):
    name: Optional[str] = None
    number: Optional[int] = None
    is_active: Optional[bool] = None

# Helper function to get local IP
def get_base_url():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except:
        local_ip = "127.0.0.1"
    return f"http://{local_ip}:8000"

# Generate QR code for table
async def generate_table_qr(table_number: int) -> str:
    """Generate QR code for table that links to customer menu"""
    base_url = get_base_url()
    
    # QR code data - link to customer menu with table number
    qr_data = f"{base_url}/menu?table={table_number}"
    
    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    # Create image
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    
    img_base64 = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{img_base64}"

# Table endpoints
@router.post("", response_model=TableResponse)
async def create_table(
    table: TableCreate,
    current_user = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_session)
):
    # Check if table number already exists
    existing = db.query(Table).filter(Table.number == table.number).first()
    if existing:
        raise HTTPException(status_code=400, detail="Table number already exists")
    
    new_table = Table(
        name=table.name,
        number=table.number
    )
    db.add(new_table)
    db.commit()
    db.refresh(new_table)
    
    # Generate QR code
    qr_data = await generate_table_qr(new_table.number)
    new_table.qr_url = qr_data
    db.commit()
    
    return new_table

@router.get("", response_model=List[TableResponse])
async def get_tables(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    active_only: bool = Query(True),
    db: Session = Depends(get_session)
):
    query = db.query(Table)
    if active_only:
        query = query.filter(Table.is_active == True)
    
    tables = query.order_by(Table.number).offset(skip).limit(limit).all()
    return tables

@router.get("/{table_id}", response_model=TableResponse)
async def get_table(
    table_id: int,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_session)
):
    table = db.query(Table).filter(Table.id == table_id).first()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    
    return table

@router.put("/{table_id}", response_model=TableResponse)
async def update_table(
    table_id: int,
    table_update: TableUpdate,
    current_user = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_session)
):
    table = db.query(Table).filter(Table.id == table_id).first()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    
    # Check if table number already exists (excluding current table)
    if table_update.number:
        existing = db.query(Table).filter(
            Table.number == table_update.number,
            Table.id != table_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Table number already exists")
    
    for key, value in table_update.dict(exclude_unset=True).items():
        setattr(table, key, value)
    
    db.commit()
    db.refresh(table)
    return table

@router.delete("/{table_id}")
async def delete_table(
    table_id: int,
    current_user = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_session)
):
    table = db.query(Table).filter(Table.id == table_id).first()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    
    # Soft delete
    table.is_active = False
    db.commit()
    
    return {"message": "Table deleted successfully"}

@router.get("/{table_id}/qr")
async def get_table_qr(
    table_id: int,
    current_user = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_session)
):
    """Get QR code for specific table"""
    table = db.query(Table).filter(Table.id == table_id).first()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    
    # Her zaman güncel IP ile yeniden üret (IP değişmiş olabilir)
    qr_data = await generate_table_qr(table.number)
    table.qr_url = qr_data
    db.commit()
    
    base_url = get_base_url()
    return {
        "table_id": table.id,
        "table_name": table.name,
        "table_number": table.number,
        "qr_url": table.qr_url,
        "menu_url": f"{base_url}/menu?table={table.number}"
    }

@router.post("/{table_id}/regenerate-qr")
async def regenerate_table_qr(
    table_id: int,
    current_user = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_session)
):
    """Regenerate QR code for table"""
    table = db.query(Table).filter(Table.id == table_id).first()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    
    # Generate new QR code
    qr_data = await generate_table_qr(table.number)
    table.qr_url = qr_data
    db.commit()
    
    base_url = get_base_url()
    return {
        "message": "QR code regenerated successfully",
        "qr_url": qr_data,
        "menu_url": f"{base_url}/menu?table={table.number}"
    }

# Bulk operations
@router.post("/bulk-create")
async def create_tables_bulk(
    tables: List[TableCreate],
    current_user = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_session)
):
    """Create multiple tables at once"""
    created_tables = []
    
    for table_data in tables:
        # Check if table number already exists
        existing = db.query(Table).filter(Table.number == table_data.number).first()
        if existing:
            continue  # Skip duplicates
        
        new_table = Table(
            name=table_data.name,
            number=table_data.number
        )
        db.add(new_table)
        db.commit()
        db.refresh(new_table)
        
        # Generate QR code
        qr_data = await generate_table_qr(new_table.number)
        new_table.qr_url = qr_data
        db.commit()
        
        created_tables.append(new_table)
    
    return {
        "message": f"{len(created_tables)} tables created successfully",
        "tables": created_tables
    }

@router.get("/stats/summary")
async def get_tables_summary(
    current_user = Depends(require_role([UserRole.ADMIN, UserRole.SUPERVISOR])),
    db: Session = Depends(get_session)
):
    """Get tables summary statistics"""
    total_tables = db.query(Table).filter(Table.is_active == True).count()
    
    # Get tables with recent orders
    from datetime import datetime, timedelta
    recent_time = datetime.now() - timedelta(hours=2)
    
    active_tables = db.query(Table).join(Order).filter(
        Table.is_active == True,
        Order.created_at >= recent_time,
        ~Order.status.in_(["teslim_edildi", "iptal"])
    ).distinct().count()
    
    return {
        "total_tables": total_tables,
        "active_tables": active_tables,
        "available_tables": total_tables - active_tables
    }