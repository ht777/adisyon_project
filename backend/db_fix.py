import sqlite3
import os

# Veritabanı dosyasının yolu (backend klasöründe olduğundan emin olun)
DB_FILE = "restaurant.db"

def fix_database():
    if not os.path.exists(DB_FILE):
        print(f"❌ '{DB_FILE}' bulunamadı! Lütfen bu scripti 'backend' klasörü içinde çalıştırın.")
        return

    print(f"🔧 Veritabanı onarılıyor: {DB_FILE}")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        # 1. Eksik 'logo_url' sütununu ekle
        try:
            print("👉 'logo_url' sütunu ekleniyor...")
            cursor.execute("ALTER TABLE restaurant_config ADD COLUMN logo_url VARCHAR")
            print("✅ 'logo_url' başarıyla eklendi.")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e):
                print("ℹ️ 'logo_url' sütunu zaten var.")
            else:
                print(f"⚠️ Hata: {e}")

        conn.commit()
        print("\n🎉 ONARIM TAMAMLANDI! Şimdi 'python run.py' ile sistemi başlatabilirsiniz.")

    except Exception as e:
        print(f"\n❌ Genel Bir Hata Oluştu: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    fix_database()