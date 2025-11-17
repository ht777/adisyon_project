from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from pydantic import BaseModel
from models import Product, Category, ExtraGroup, ExtraItem, ProductExtraGroup, get_session
from auth import require_role, get_current_active_user
from models import UserRole
import os
import sys
from pathlib import Path
from datetime import datetime

router = APIRouter(prefix="/products", tags=["Products"])

# --- MODELLER (Schemas) ---

class CategoryCreate(BaseModel):
    name: str
    icon: Optional[str] = None
    order: int = 0

class CategoryResponse(BaseModel):
    id: int
    name: str
    icon: Optional[str]
    order: int
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

# Ürün listesinde kullanılacak hafif kategori modeli
class CategorySummary(BaseModel):
    id: int
    name: str
    icon: Optional[str] = None
    
    class Config:
        from_attributes = True

class ExtraItemCreate(BaseModel):
    name: str
    price: float = 0.0

class ExtraGroupCreate(BaseModel):
    name: str
    is_required: bool = False
    max_selections: int = 1
    items: List[ExtraItemCreate]

class ExtraGroupResponse(BaseModel):
    id: int
    name: str
    is_required: bool
    max_selections: int
    items: List[Dict[str, Any]]
    
    class Config:
        from_attributes = True

class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    category_id: int
    is_featured: bool = False
    is_active: bool = True

class ProductResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    price: float
    image_url: Optional[str]
    # DÜZELTME: Tam CategoryResponse yerine özet model kullanıldı
    category: Optional[CategorySummary] = None
    is_featured: bool
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class ProductDetailResponse(ProductResponse):
    extra_groups: List[Dict[str, Any]]

# --- ENDPOINTLER ---

# Kategori İşlemleri
@router.post("/categories", response_model=CategoryResponse)
async def create_category(
    category: CategoryCreate,
    current_user = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_session)
):
    existing = db.query(Category).filter(Category.name == category.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Category name already exists")
    
    new_category = Category(**category.dict())
    db.add(new_category)
    db.commit()
    db.refresh(new_category)
    return new_category

@router.get("/categories", response_model=List[CategoryResponse])
async def get_categories(
    active_only: bool = Query(True),
    db: Session = Depends(get_session)
):
    query = db.query(Category)
    if active_only:
        query = query.filter(Category.is_active == True)
    
    categories = query.order_by(Category.order, Category.name).all()
    return categories

@router.get("/categories/{category_id}", response_model=CategoryResponse)
async def get_category(category_id: int, db: Session = Depends(get_session)):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category

@router.put("/categories/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: int,
    category_update: CategoryCreate,
    current_user = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_session)
):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    existing = db.query(Category).filter(
        Category.name == category_update.name,
        Category.id != category_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Category name already exists")
    
    for key, value in category_update.dict().items():
        setattr(category, key, value)
    
    db.commit()
    db.refresh(category)
    return category

@router.delete("/categories/{category_id}")
async def delete_category(
    category_id: int,
    current_user = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_session)
):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    category.is_active = False
    db.commit()
    return {"message": "Category deleted successfully"}

# Ekstra Grubu İşlemleri
@router.post("/extra-groups", response_model=ExtraGroupResponse)
async def create_extra_group(
    extra_group: ExtraGroupCreate,
    current_user = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_session)
):
    new_group = ExtraGroup(
        name=extra_group.name,
        is_required=extra_group.is_required,
        max_selections=extra_group.max_selections
    )
    db.add(new_group)
    db.commit()
    db.refresh(new_group)
    
    for item in extra_group.items:
        new_item = ExtraItem(
            name=item.name,
            price=item.price,
            group_id=new_group.id
        )
        db.add(new_item)
    
    db.commit()
    group_with_items = db.query(ExtraGroup).filter(ExtraGroup.id == new_group.id).first()
    return group_with_items

@router.get("/extra-groups", response_model=List[ExtraGroupResponse])
async def get_extra_groups(
    active_only: bool = Query(True),
    db: Session = Depends(get_session)
):
    query = db.query(ExtraGroup)
    if active_only:
        query = query.filter(ExtraGroup.items.any(ExtraItem.is_active == True))
    groups = query.all()
    return groups

@router.get("/extra-groups/{group_id}", response_model=ExtraGroupResponse)
async def get_extra_group(group_id: int, db: Session = Depends(get_session)):
    group = db.query(ExtraGroup).filter(ExtraGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Extra group not found")
    return group

# Ürün İşlemleri
@router.post("", response_model=ProductResponse)
async def create_product(
    product: ProductCreate,
    current_user = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_session)
):
    category = db.query(Category).filter(Category.id == product.category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    new_product = Product(**product.dict())
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    return new_product

@router.get("", response_model=List[ProductResponse])
async def get_products(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    category_id: Optional[int] = Query(None),
    featured_only: bool = Query(False),
    active_only: bool = Query(True),
    db: Session = Depends(get_session)
):
    query = db.query(Product)
    
    if category_id:
        query = query.filter(Product.category_id == category_id)
    if featured_only:
        query = query.filter(Product.is_featured == True)
    if active_only:
        query = query.filter(Product.is_active == True)
    
    products = query.offset(skip).limit(limit).all()
    return products

@router.get("/{product_id}", response_model=ProductDetailResponse)
async def get_product(product_id: int, db: Session = Depends(get_session)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    extra_groups = []
    for peg in product.extra_groups:
        group_data = {
            "id": peg.extra_group.id,
            "name": peg.extra_group.name,
            "is_required": peg.extra_group.is_required,
            "max_selections": peg.extra_group.max_selections,
            "items": [
                {
                    "id": item.id,
                    "name": item.name,
                    "price": item.price,
                    "is_active": item.is_active
                }
                for item in peg.extra_group.items if item.is_active
            ]
        }
        extra_groups.append(group_data)
    
    # Kategori özeti oluştur
    category_data = None
    if product.category:
        category_data = {
            "id": product.category.id,
            "name": product.category.name,
            "icon": product.category.icon
        }

    product_dict = {
        "id": product.id,
        "name": product.name,
        "description": product.description,
        "price": product.price,
        "image_url": product.image_url,
        "category": category_data,
        "is_featured": product.is_featured,
        "is_active": product.is_active,
        "created_at": product.created_at,
        "extra_groups": extra_groups
    }
    
    return product_dict

@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    product_update: ProductCreate,
    current_user = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_session)
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    category = db.query(Category).filter(Category.id == product_update.category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    for key, value in product_update.dict().items():
        setattr(product, key, value)
    
    db.commit()
    db.refresh(product)
    return product

@router.delete("/{product_id}")
async def delete_product(
    product_id: int,
    current_user = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_session)
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    product.is_active = False
    db.commit()
    return {"message": "Product deleted successfully"}

@router.post("/{product_id}/extra-groups/{group_id}")
async def assign_extra_group_to_product(
    product_id: int,
    group_id: int,
    current_user = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_session)
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    group = db.query(ExtraGroup).filter(ExtraGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Extra group not found")
    
    existing = db.query(ProductExtraGroup).filter(
        ProductExtraGroup.product_id == product_id,
        ProductExtraGroup.extra_group_id == group_id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Extra group already assigned to product")
    
    assignment = ProductExtraGroup(product_id=product_id, extra_group_id=group_id)
    db.add(assignment)
    db.commit()
    
    return {"message": "Extra group assigned to product successfully"}

@router.delete("/{product_id}/extra-groups/{group_id}")
async def remove_extra_group_from_product(
    product_id: int,
    group_id: int,
    current_user = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_session)
):
    assignment = db.query(ProductExtraGroup).filter(
        ProductExtraGroup.product_id == product_id,
        ProductExtraGroup.extra_group_id == group_id
    ).first()
    
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    db.delete(assignment)
    db.commit()
    return {"message": "Extra group removed from product successfully"}

@router.post("/{product_id}/image")
async def upload_product_image(
    product_id: int,
    file: UploadFile = File(...),
    current_user = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_session)
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size must be less than 5MB")
    
    # DÜZELTME: Uploads klasörünün yolu (PyInstaller uyumlu)
    # Backend klasörünün bir üstüne (proje köküne) çık, oradan frontend/static/uploads'a git
    if getattr(sys, 'frozen', False):
        # Exe modunda: exe'nin olduğu yerde 'uploads' klasörü oluştur
        base_dir = Path(sys.executable).parent
        uploads_dir = base_dir / "uploads"
        # URL, static sunucuya mount edilecek (main.py'da ayarlanmalı veya bu yol /uploads/.. olmalı)
        # Basitlik için frontend/static klasörünü exe'nin yanına koyduğumuzu varsayıyoruz.
    else:
        # Geliştirme modunda
        base_dir = Path(__file__).resolve().parents[2]
        uploads_dir = base_dir / "frontend" / "static" / "uploads"

    uploads_dir.mkdir(parents=True, exist_ok=True)
    
    filename = f"product_{product_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
    file_path = uploads_dir / filename
    
    with open(file_path, "wb") as f:
        f.write(content)
    
    # Frontend'in erişeceği URL
    image_url = f"/static/uploads/{filename}"
    # Eğer exe modunda dışarıdan sunulacaksa URL değişebilir, şimdilik standart bırakıyoruz.

    product.image_url = image_url
    db.commit()
    
    return {"image_url": image_url}