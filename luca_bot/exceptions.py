class LucaHata(Exception):
    """Luca entegrasyonu genel hata sınıfı."""
    pass

class LucaLoginHata(LucaHata):
    """Giriş yapılamadığında veya CAPTCHA zaman aşımına uğradığında fırlatılır."""
    pass

class LucaTimeoutHata(LucaHata):
    """Tarayıcı sayfa yüklemelerinde zaman aşımına uğrarsa fırlatılır."""
    pass
