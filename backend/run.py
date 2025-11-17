import uvicorn
import os
import sys
import socket
import time
# network_utils dosyasından fonksiyonları al
try:
    from network_utils import set_static_ip, get_current_ip_info
except ImportError:
    # Windows dışı ortamlar için boş fonksiyonlar
    def set_static_ip(): return True
    def get_current_ip_info(): return "127.0.0.1", None, None

if __name__ == "__main__":
    print("🚀 ADİSYON SİSTEMİ BAŞLATILIYOR...")
    print("="*50)

    # Sadece Windows'ta çalıştır
    if os.name == 'nt':
        # Mevcut IP'yi kontrol et
        current_ip, _, _ = get_current_ip_info()
        
        # Eğer IP zaten sabitlenmiş gibi görünüyorsa (Örn: sonu .200 ile bitiyorsa)
        # Tekrar işlem yapma. Bu kontrol basit bir mantıktır.
        # Ancak en garantisi her açılışta bir kez kontrol etmektir.
        print("⚙️  Ağ ayarları kontrol ediliyor...")
        success = set_static_ip()
        
        if success:
            print("✅ Ağ yapılandırması hazır.")
        else:
            print("⚠️  Ağ ayarları otomatik yapılamadı.")
            print("   Lütfen yönetici olarak çalıştırdığınızdan emin olun.")
            print("   Sistem yine de çalışmaya devam edecek (IP değişirse QR kodlar bozulabilir).")

    # Bilgisayarın Yerel IP adresini bul
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except:
        local_ip = "127.0.0.1"
    
    print("\n" + "="*50)
    print(f"✅ SİSTEM AKTİF!")
    print(f"📡 Sunucu Adresi: {local_ip}")
    print("-" * 50)
    print(f"📱 Müşteri Menüsü : http://{local_ip}:8000/menu")
    print(f"📱 Masa 1 Örneği  : http://{local_ip}:8000/menu?table=1")
    print(f"🍳 Mutfak Ekranı  : http://{local_ip}:8000/kitchen")
    print(f"🔧 Admin Paneli   : http://{local_ip}:8000/admin")
    print("=" * 50)
    print("\nBu pencereyi kapatırsanız sistem durur.")
    print("Durdurmak için CTRL+C yapabilirsiniz.\n")

    # Sunucuyu başlat
    # host="0.0.0.0" tüm ağdan erişime izin verir
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)