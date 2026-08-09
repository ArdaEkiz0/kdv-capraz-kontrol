"""Raporları e-posta ile gönder (Outlook varsayılan + SMTP destekli)."""
import os
import subprocess
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.encoders import encode_base64
from typing import List, Optional, Tuple


def outlook_ile_gonder(ek_dosyalar: List[str], konu: str, govde: str, alici: str) -> bool:
    """Windows'ta Outlook'u açıp hazır mail penceresi oluşturur."""
    try:
        ekler_str = ", ".join(f'"{f}"' for f in ek_dosyalar)
        govde_temiz = govde.replace('"', "'").replace("\n", " ")
        script = (
            f'$outlook = New-Object -ComObject Outlook.Application;'
            f'$mail = $outlook.CreateItem(0);'
            f'$mail.To = "{alici}";'
            f'$mail.Subject = "{konu}";'
            f'$mail.Body = "{govde_temiz}";'
        )
        for ek in ek_dosyalar:
            script += f'$mail.Attachments.Add("{ek}");'
        script += '$mail.Display();'

        subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            check=True,
            timeout=10,
        )
        return True
    except Exception:
        return False


def smtp_ile_gonder(
    ek_dosyalar: List[str],
    konu: str,
    govde_html: str,
    alici: str,
    smtp_server: str,
    smtp_port: int,
    kullanici: str,
    sifre: str,
    gonderen: Optional[str] = None,
) -> Tuple[bool, str]:
    """SMTP ile mail gönder."""
    try:
        msg = MIMEMultipart()
        msg["From"] = gonderen or kullanici
        msg["To"] = alici
        msg["Subject"] = konu
        msg.attach(MIMEText(govde_html, "html", "utf-8"))

        for ek_yol in ek_dosyalar:
            if not os.path.exists(ek_yol):
                continue
            with open(ek_yol, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
                encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename= {os.path.basename(ek_yol)}",
                )
                msg.attach(part)

        with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
            server.starttls()
            server.login(kullanici, sifre)
            server.send_message(msg)
        return True, "Mail gönderildi"
    except Exception as hata:
        return False, str(hata)


def mail_icerigi_olustur(ozet: dict, donem: str = "") -> Tuple[str, str, str]:
    """HTML ve plain-text mail içeriği hazırla.

    Returns: (konu, govde_html, govde_text)
    """
    konu = f"KDV Kontrol Raporu - {donem}" if donem else "KDV Kontrol Raporu"
    sorunlu = (
        ozet.get("tutar_farki", 0) + ozet.get("vkn_farki", 0)
        + ozet.get("cetvelde_yok", 0) + ozet.get("faturada_yok", 0)
    )

    html = f"""
<html><body style="font-family:Segoe UI,Arial">
<h2 style="color:#4472C4">KDV Çapraz Kontrol Raporu</h2>
<p><b>Dönem:</b> {donem or '-'}</p>
<table border="1" cellpadding="6" style="border-collapse:collapse">
  <tr style="background:#4472C4;color:white"><th>Ölçüt</th><th>Adet</th></tr>
  <tr><td>Fatura Sayısı</td><td>{ozet.get('fatura_adet', 0)}</td></tr>
  <tr><td>Cetvel Kayıt Sayısı</td><td>{ozet.get('cetvel_adet', 0)}</td></tr>
  <tr style="background:#C6EFCE"><td>✅ Eşleşen</td><td>{ozet.get('eslesen', 0)}</td></tr>
  <tr style="background:#FFC7CE"><td>❌ Sorunlu Toplam</td><td>{sorunlu}</td></tr>
  <tr><td>Tutar Farkı</td><td>{ozet.get('tutar_farki', 0)}</td></tr>
  <tr><td>VKN Farkı</td><td>{ozet.get('vkn_farki', 0)}</td></tr>
  <tr><td>Muavinde Yok</td><td>{ozet.get('cetvelde_yok', 0)}</td></tr>
  <tr><td>Faturalarda Yok</td><td>{ozet.get('faturada_yok', 0)}</td></tr>
  <tr><td>Mükerrer</td><td>{ozet.get('mukerrer', 0)}</td></tr>
</table>
<p style="color:#888">Ek: detaylı rapor dosyaları.</p>
</body></html>
"""
    text = (
        f"KDV Çapraz Kontrol Raporu\n"
        f"Dönem: {donem or '-'}\n"
        f"Fatura: {ozet.get('fatura_adet', 0)} | Cetvel: {ozet.get('cetvel_adet', 0)}\n"
        f"Eşleşen: {ozet.get('eslesen', 0)} | Sorunlu: {sorunlu}\n"
        f"Tutar Farkı: {ozet.get('tutar_farki', 0)}\n"
        f"VKN Farkı: {ozet.get('vkn_farki', 0)}\n"
        f"Muavinde Yok: {ozet.get('cetvelde_yok', 0)}\n"
        f"Faturalarda Yok: {ozet.get('faturada_yok', 0)}\n"
        f"Mükerrer: {ozet.get('mukerrer', 0)}\n"
    )
    return konu, html, text
