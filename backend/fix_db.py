import sqlite3
import os

def add_logo_url_column():
    db_path = "restaurant.db"
    
    if not os.path.exists(db_path):
        print(f"❌ HATA: '{db_path}' dosyası bulunamadı! Lütfen backend klasöründe olduğunuzdan emin olun.")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Sütunun zaten var olup olmadığını kontrol et
        cursor.execute("PRAGMA table_info(restaurant_config)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if "logo_url" in columns:
            print("✅ 'logo_url' sütunu zaten mevcut. İşlem yapılmasına gerek yok.")
        else:
            print("🛠️ 'logo_url' sütunu ekleniyor...")
            cursor.execute("ALTER TABLE restaurant_config ADD COLUMN logo_url VARCHAR")
            conn.commit()
            print("✅ BAŞARILI: 'logo_url' sütunu eklendi!")
            
    except Exception as e:
        print(f"❌ Bir hata oluştu: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    add_logo_url_column()