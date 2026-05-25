import time
import os
from utils.session_manager import SessionManager

def clear_screen():
    """Terminali temizle"""
    os.system('cls' if os.name == 'nt' else 'clear')

def main():
    """Ana fonksiyon"""
    session_manager = SessionManager()
    
    try:
        while True:
            clear_screen()
            print("\n" + "="*50)
            print(session_manager.get_session_info())
            print("="*50 + "\n")
            time.sleep(1)  # Her saniye güncelle
            
    except KeyboardInterrupt:
        print("\n\nProgram sonlandırıldı...")
        
if __name__ == "__main__":
    main() 