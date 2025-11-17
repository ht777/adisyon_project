import ctypes
import sys
import subprocess
import socket
import re
import os

def is_admin():
    """Program yönetici olarak mı çalışıyor kontrol et"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    """Programı yönetici haklarıyla yeniden başlat"""
    # Parametreleri al ve yönetici olarak çalıştır
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 1
    )
    sys.exit()

def get_active_interface_name():
    """Aktif internet bağlantısı olan ağ bağdaştırıcısının adını bul (Wi-Fi veya Ethernet)"""
    try:
        # netsh komutuyla aktif arayüzleri listele
        result = subprocess.check_output('netsh interface show interface', shell=True).decode('cp850', errors='ignore') # Türkçe Windows için cp850
        lines = result.split('\n')
        
        for line in lines:
            if "Connected" in line or "Bağlandı" in line: # Türkçe/İngilizce uyumu
                # Satırı parçala ve en sondaki arayüz adını al (Örn: "Wi-Fi")
                parts = line.split()
                interface_name = " ".join(parts[3:]) # İlk 3 sütun durum bilgisi
                return interface_name.strip()
    except Exception as e:
        print(f"Arayüz adı bulunamadı: {e}")
        return None
    return None

def get_current_ip_info():
    """Mevcut IP, Alt Ağ Maskesi ve Varsayılan Ağ Geçidini bul"""
    try:
        # ipconfig çıktısını al
        output = subprocess.check_output("ipconfig", shell=True).decode('cp850', errors='ignore')
        
        ip = None
        subnet = None
        gateway = None
        
        # Basit regex ile bilgileri çek (IPv4)
        # Not: Bu regex Windows çıktısına göre ayarlanmıştır
        ip_match = re.search(r"IPv4.*?: (\d+\.\d+\.\d+\.\d+)", output)
        if ip_match: ip = ip_match.group(1)
        
        subnet_match = re.search(r"Subnet Mask.*?: (\d+\.\d+\.\d+\.\d+)|Alt Ağ Maskesi.*?: (\d+\.\d+\.\d+\.\d+)", output)
        if subnet_match: subnet = subnet_match.group(1) or subnet_match.group(2)
        
        gateway_match = re.search(r"Default Gateway.*?: (\d+\.\d+\.\d+\.\d+)|Varsayılan Ağ Geçidi.*?: (\d+\.\d+\.\d+\.\d+)", output)
        if gateway_match: gateway = gateway_match.group(1) or gateway_match.group(2)

        return ip, subnet, gateway
    except:
        return None, None, None

def set_static_ip():
    """Mevcut IP adresini bu bilgisayara sabitle"""
    
    # 1. Yönetici izni kontrolü
    if not is_admin():
        print("⚠️ IP sabitlemek için yönetici izni isteniyor...")
        run_as_admin()
        return

    print("🔄 IP adresi sabitleniyor...")
    
    # 2. Bilgileri topla
    interface_name = get_active_interface_name()
    ip, subnet, gateway = get_current_ip_info()
    
    if not interface_name or not ip or not subnet or not gateway:
        print("❌ Ağ bilgileri alınamadı. İnternete bağlı olduğunuzdan emin olun.")
        return False

    print(f"📝 Algılanan Ağ: {interface_name}")
    print(f"📝 Sabitlenecek IP: {ip}")

    try:
        # 3. netsh komutu ile IP'yi sabitle
        # Komut: netsh interface ip set address "Wi-Fi" static 192.168.1.35 255.255.255.0 192.168.1.1
        cmd = f'netsh interface ip set address "{interface_name}" static {ip} {subnet} {gateway}'
        subprocess.run(cmd, shell=True, check=True)
        
        # 4. DNS'i de sabitle (Google DNS - Opsiyonel ama sağlıklı)
        cmd_dns = f'netsh interface ip set dns "{interface_name}" static 8.8.8.8'
        subprocess.run(cmd_dns, shell=True)
        
        print("✅ BAŞARILI: IP adresi bu bilgisayara sabitlendi!")
        print("✅ Artık modem resetlense bile QR kodlar çalışmaya devam edecek.")
        return True
        
    except subprocess.CalledProcessError:
        print("⚠️ HATA: IP sabitlenirken bir sorun oluştu veya zaten sabit.")
        # Zaten sabitse hata verebilir, bu büyük bir sorun değil.
        return False