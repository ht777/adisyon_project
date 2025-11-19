import requests
import random
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, User, Product, Category, Table, Order, OrderItem, OrderStatus, RestaurantConfig, UserRole
from auth import get_password_hash
import os

# Veritabanı Ayarları
DB_URL = "sqlite:///./restaurant.db"
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

def setup_system():
    print("🚀 Sistem Kurulumu ve Veri Doldurma Başlıyor...")

    # 1. Kategoriler
    print("📂 Kategoriler kontrol ediliyor...")
    categories = [
        {"name": "Ana Yemekler", "icon": "🍖", "order": 1},
        {"name": "İçecekler", "icon": "🥤", "order": 2},
        {"name": "Tatlılar", "icon": "🍰", "order": 3},
    ]
    
    db_cats = []
    for cat_data in categories:
        cat = db.query(Category).filter(Category.name == cat_data["name"]).first()
        if not cat:
            cat = Category(**cat_data, is_active=True)
            db.add(cat)
            print(f"   + {cat_data['name']} eklendi.")
        db_cats.append(cat)
    db.commit()

    # 2. Ürünler
    print("🍔 Ürünler kontrol ediliyor...")
    products_data = [
        {"name": "Izgara Köfte", "price": 120.0, "category_id": db_cats[0].id, "description": "Pilav ve köz biber ile"},
        {"name": "Tavuk Şiş", "price": 95.0, "category_id": db_cats[0].id, "description": "Özel soslu"},
        {"name": "Ayran", "price": 15.0, "category_id": db_cats[1].id, "description": "Yayık"},
        {"name": "Kola", "price": 25.0, "category_id": db_cats[1].id, "description": "330ml"},
        {"name": "Künefe", "price": 80.0, "category_id": db_cats[2].id, "description": "Kaymaklı"},
    ]

    db_products = []
    for p_data in products_data:
        prod = db.query(Product).filter(Product.name == p_data["name"]).first()
        if not prod:
            prod = Product(**p_data, is_active=True, is_featured=True)
            db.add(prod)
            print(f"   + {p_data['name']} eklendi.")
        db_products.append(prod)
    db.commit()

    # 3. Masalar (Hata almamak için en önemli kısım)
    print("🪑 Masalar oluşturuluyor...")
    for i in range(1, 11): # 1'den 10'a kadar masalar
        table = db.query(Table).filter(Table.number == i).first()
        if not table:
            table = Table(name=f"Masa {i}", number=i, is_active=True, qr_url=f"http://localhost:8000/menu?table={i}")
            db.add(table)
            print(f"   + Masa {i} eklendi.")
    db.commit()

    # 4. Örnek Siparişler (Raporların Dolması İçin)
    print("📊 Geçmiş ve Güncel Sipariş Verileri Oluşturuluyor...")
    
    # Son 7 güne yayılmış rastgele siparişler
    statuses = [OrderStatus.TESLIM_EDILDI, OrderStatus.TESLIM_EDILDI, OrderStatus.IPTAL, OrderStatus.HAZIR]
    
    tables = db.query(Table).all()
    prods = db.query(Product).all()

    if not tables or not prods:
        print("❌ Hata: Masa veya ürün bulunamadı, sipariş oluşturulamıyor.")
        return

    for i in range(20): # 20 adet rastgele sipariş
        # Rastgele tarih (Bugün ve son 1 hafta)
        days_ago = random.randint(0, 7)
        order_date = datetime.now() - timedelta(days=days_ago, hours=random.randint(1, 12))
        
        selected_table = random.choice(tables)
        status = random.choice(statuses)
        
        # Sipariş oluştur
        order = Order(
            table_id=selected_table.id,
            status=status,
            customer_notes="Örnek veri",
            created_at=order_date,
            updated_at=order_date
        )
        db.add(order)
        db.flush() # ID almak için

        # Siparişe ürün ekle
        total_amount = 0
        for _ in range(random.randint(1, 4)): # 1-4 arası ürün
            prod = random.choice(prods)
            qty = random.randint(1, 2)
            price = prod.price
            subtotal = price * qty
            total_amount += subtotal
            
            item = OrderItem(
                order_id=order.id,
                product_id=prod.id,
                quantity=qty,
                unit_price=price,
                subtotal=subtotal,
                created_at=order_date
            )
            db.add(item)
        
        order.total_amount = total_amount
    
    db.commit()
    print(f"✅ 20 adet örnek sipariş başarıyla eklendi!")
    print("\n🎉 KURULUM TAMAMLANDI!")
    print("👉 Şimdi 'python run.py' komutuyla sistemi başlatıp Admin panelini kontrol edin.")

if __name__ == "__main__":
    setup_system()