import requests
import json
import time

# API base URL
BASE_URL = "http://localhost:8000/api"

def create_admin_user():
    """Create admin user for authentication"""
    print("👤 Admin kullanıcısı oluşturuluyor...")
    
    # First try to login with default credentials
    login_data = {
        "username": "admin",
        "password": "admin123"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
        if response.status_code == 200:
            token = response.json()["access_token"]
            print("✅ Admin kullanıcısı mevcut, giriş yapıldı")
            return token
        else:
            print("❌ Admin girişi başarısız, kullanıcı oluşturulamıyor")
            return None
    except Exception as e:
        print(f"❌ Admin girişi hatası: {e}")
        return None

def create_categories(token):
    """Create sample categories"""
    print("\n📂 Kategoriler oluşturuluyor...")
    
    categories = [
        {"name": "Pizza", "icon": "🍕", "order": 1},
        {"name": "Burger", "icon": "🍔", "order": 2},
        {"name": "Dürüm", "icon": "🌯", "order": 3},
        {"name": "Tatlı", "icon": "🍰", "order": 4},
        {"name": "İçecek", "icon": "🥤", "order": 5},
        {"name": "Aperitif", "icon": "🥗", "order": 6}
    ]
    
    headers = {"Authorization": f"Bearer {token}"}
    category_ids = {}
    
    for category in categories:
        try:
            response = requests.post(f"{BASE_URL}/products/categories", 
                                   json=category, headers=headers)
            if response.status_code == 200:
                cat_data = response.json()
                category_ids[category["name"]] = cat_data["id"]
                print(f"✅ {category['name']} kategorisi oluşturuldu")
            else:
                print(f"❌ {category['name']} kategorisi oluşturulamadı: {response.status_code}")
        except Exception as e:
            print(f"❌ {category['name']} kategorisi hatası: {e}")
    
    return category_ids

def create_products(token, category_ids):
    """Create sample products"""
    print("\n🍽️ Ürünler oluşturuluyor...")
    
    products = [
        {
            "name": "Margherita Pizza",
            "description": "Klasik İtalyan pizzası, domates sos, mozzarella peyniri, taze fesleğen",
            "price": 89.90,
            "category_id": category_ids.get("Pizza", 1),
            "is_featured": True,
            "is_active": True
        },
        {
            "name": "Pepperoni Pizza",
            "description": "Domates sos, mozzarella, pepperoni, zeytin",
            "price": 105.50,
            "category_id": category_ids.get("Pizza", 1),
            "is_featured": False,
            "is_active": True
        },
        {
            "name": "Vegan Sebze Dürüm",
            "description": "Taze sebzeler, humus ve tahin soslu sağlıklı dürüm",
            "price": 65.00,
            "category_id": category_ids.get("Dürüm", 3),
            "is_featured": True,
            "is_active": True
        },
        {
            "name": "Acılı Tavuk Dürüm",
            "description": "Baharatlı tavuk, marul, domates, özel sos",
            "price": 75.50,
            "category_id": category_ids.get("Dürüm", 3),
            "is_featured": False,
            "is_active": True
        },
        {
            "name": "Cheeseburger",
            "description": "Dana köfte, cheddar peyniri, marul, domates, soğan",
            "price": 85.90,
            "category_id": category_ids.get("Burger", 2),
            "is_featured": True,
            "is_active": True
        },
        {
            "name": "Double Burger",
            "description": "İki kat dana köfte, cheddar, marul, domates, özel sos",
            "price": 125.00,
            "category_id": category_ids.get("Burger", 2),
            "is_featured": False,
            "is_active": True
        },
        {
            "name": "Çikolatalı Brownie",
            "description": "Sıcak servis edilen yoğun çikolatalı brownie, vanilya dondurma",
            "price": 45.00,
            "category_id": category_ids.get("Tatlı", 4),
            "is_featured": True,
            "is_active": True
        },
        {
            "name": "Tiramisu",
            "description": "Klasik İtalyan tatlısı, kahve ve mascarpone ile",
            "price": 55.00,
            "category_id": category_ids.get("Tatlı", 4),
            "is_featured": False,
            "is_active": True
        },
        {
            "name": "Limonata",
            "description": "Taze sıkılmış limon, buz, nane yaprakları",
            "price": 25.00,
            "category_id": category_ids.get("İçecek", 5),
            "is_featured": True,
            "is_active": True
        },
        {
            "name": "Köri Soslu Sebze Kızartması",
            "description": "Hint baharatlarıyla marine edilmiş sebzeler, köri sos",
            "price": 55.00,
            "category_id": category_ids.get("Aperitif", 6),
            "is_featured": False,
            "is_active": True
        }
    ]
    
    headers = {"Authorization": f"Bearer {token}"}
    product_ids = []
    
    for product in products:
        try:
            response = requests.post(f"{BASE_URL}/products/products", 
                                   json=product, headers=headers)
            if response.status_code == 200:
                prod_data = response.json()
                product_ids.append(prod_data["id"])
                print(f"✅ {product['name']} ürünü oluşturuldu")
            else:
                print(f"❌ {product['name']} ürünü oluşturulamadı: {response.status_code}")
        except Exception as e:
            print(f"❌ {product['name']} ürünü hatası: {e}")
    
    return product_ids

def create_tables(token):
    """Create sample tables"""
    print("\n🪑 Masalar oluşturuluyor...")
    
    tables = [
        {"name": "Masa 1", "number": 1},
        {"name": "Masa 2", "number": 2},
        {"name": "Masa 3", "number": 3},
        {"name": "Masa 4", "number": 4},
        {"name": "Masa 5", "number": 5},
        {"name": "Masa 6", "number": 6},
        {"name": "Masa 7", "number": 7},
        {"name": "Masa 8", "number": 8}
    ]
    
    headers = {"Authorization": f"Bearer {token}"}
    table_ids = []
    
    for table in tables:
        try:
            response = requests.post(f"{BASE_URL}/tables", 
                                   json=table, headers=headers)
            if response.status_code == 200:
                table_data = response.json()
                table_ids.append(table_data["id"])
                print(f"✅ {table['name']} oluşturuldu")
            else:
                print(f"❌ {table['name']} oluşturulamadı: {response.status_code}")
        except Exception as e:
            print(f"❌ {table['name']} hatası: {e}")
    
    return table_ids

def test_endpoints():
    """Test basic endpoints"""
    print("\n🔍 Endpoint'ler test ediliyor...")
    
    # Test categories endpoint (no auth required)
    try:
        response = requests.get(f"{BASE_URL}/products/categories")
        if response.status_code == 200:
            categories = response.json()
            print(f"✅ Kategoriler endpoint'i çalışıyor ({len(categories)} kategori)")
        else:
            print(f"❌ Kategoriler endpoint'i hatası: {response.status_code}")
    except Exception as e:
        print(f"❌ Kategoriler endpoint'i hatası: {e}")
    
    # Test products endpoint (no auth required)
    try:
        response = requests.get(f"{BASE_URL}/products/products")
        if response.status_code == 200:
            products = response.json()
            print(f"✅ Ürünler endpoint'i çalışıyor ({len(products)} ürün)")
        else:
            print(f"❌ Ürünler endpoint'i hatası: {response.status_code}")
    except Exception as e:
        print(f"❌ Ürünler endpoint'i hatası: {e}")

def main():
    print("🚀 Restoran Sipariş Sistemi - Yeni Test Verileri Oluşturma")
    print("=" * 60)
    
    # Wait for server to be ready
    print("⏳ Sunucunun hazır olması bekleniyor...")
    time.sleep(3)
    
    # Create admin user and get token
    token = create_admin_user()
    if not token:
        print("❌ Admin girişi başarısız, işlem durduruluyor")
        return
    
    # Create categories
    category_ids = create_categories(token)
    
    # Create products
    product_ids = create_products(token, category_ids)
    
    # Create tables
    table_ids = create_tables(token)
    
    # Test endpoints
    test_endpoints()
    
    print("\n🎉 Test verileri oluşturma tamamlandı!")
    print(f"\n📊 Özet:")
    print(f"- {len(category_ids)} kategori oluşturuldu")
    print(f"- {len(product_ids)} ürün oluşturuldu") 
    print(f"- {len(table_ids)} masa oluşturuldu")
    print(f"\n🔗 Test adresleri:")
    print(f"- Swagger UI: http://localhost:8000/docs")
    print(f"- Kategoriler: http://localhost:8000/api/products/categories")
    print(f"- Ürünler: http://localhost:8000/api/products/products")
    print(f"- Masalar: http://localhost:8000/api/tables")

if __name__ == "__main__":
    main()