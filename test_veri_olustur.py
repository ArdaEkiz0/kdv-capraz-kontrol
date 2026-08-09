import os

from fpdf import FPDF

YOL = os.path.dirname(os.path.abspath(__file__))
TEST_KLASORU = os.path.join(YOL, "test_veri")
FONT_YOLU = r"C:\Windows\Fonts\arial.ttf"


def yeni_pdf():
    pdf = FPDF()
    pdf.add_font("Arial", "", FONT_YOLU, uni=True)
    pdf.add_font("Arial", "B", r"C:\Windows\Fonts\arialbd.ttf", uni=True)
    pdf.set_font("Arial", "", 10)
    pdf.add_page()
    return pdf


def fatura_pdf(ad, belge_no, tarih, satici_vkn, alici_vkn, matrah, kdv, toplam, oran):
    pdf = yeni_pdf()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "E-FATURA", ln=1, align="C")
    pdf.set_font("Arial", "", 10)
    pdf.ln(4)
    pdf.cell(0, 6, f"Belge No : {belge_no}", ln=1)
    pdf.cell(0, 6, f"Düzenlenme Tarihi : {tarih}", ln=1)
    pdf.ln(4)
    pdf.cell(0, 6, "SATAN", ln=1)
    pdf.cell(0, 6, f"Ünvan : ÖRNEK SANAYİ VE TİCARET LTD. ŞTİ.", ln=1)
    pdf.cell(0, 6, f"Vergi Kimlik No : {satici_vkn}", ln=1)
    pdf.ln(4)
    pdf.cell(0, 6, "ALICI", ln=1)
    pdf.cell(0, 6, f"Ünvan : MÜŞTERİ TİCARET A.Ş.", ln=1)
    pdf.cell(0, 6, f"Vergi Kimlik No : {alici_vkn}", ln=1)
    pdf.ln(6)
    pdf.cell(0, 6, "Mal Hizmet Toplam Tutarı : " + tl(matrah), ln=1)
    pdf.cell(0, 6, f"Hesaplanan KDV(%{oran}) : " + tl(kdv), ln=1)
    pdf.cell(0, 6, "Toplam : " + tl(toplam), ln=1)
    pdf.output(os.path.join(TEST_KLASORU, ad))
    print("olusturuldu:", ad)


def cetvel_pdf(ad, satirlar):
    pdf = yeni_pdf()
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "KDV KONTROL CETVELİ", ln=1, align="C")
    pdf.set_font("Arial", "B", 8)
    pdf.cell(0, 6, "Dönem : 2024/02", ln=1, align="C")
    pdf.ln(3)
    pdf.set_font("Arial", "B", 8)
    pdf.cell(8, 6, "Sıra", border=1, align="C")
    pdf.cell(32, 6, "VKN", border=1, align="C")
    pdf.cell(55, 6, "Ünvan", border=1, align="C")
    pdf.cell(40, 6, "Belge No", border=1, align="C")
    pdf.cell(24, 6, "Tarih", border=1, align="C")
    pdf.cell(25, 6, "Matrah", border=1, align="C")
    pdf.cell(25, 6, "KDV", border=1, align="C")
    pdf.ln()
    pdf.set_font("Arial", "", 8)
    for i, s in enumerate(satirlar, start=1):
        pdf.cell(8, 6, str(i), border=1, align="C")
        pdf.cell(32, 6, s["vkn"], border=1, align="C")
        pdf.cell(55, 6, s["unvan"], border=1, align="C")
        pdf.cell(40, 6, s["belge_no"], border=1, align="C")
        pdf.cell(24, 6, s["tarih"], border=1, align="C")
        pdf.cell(25, 6, s["matrah"], border=1, align="C")
        pdf.cell(25, 6, s["kdv"], border=1, align="C")
        pdf.ln()
    pdf.output(os.path.join(TEST_KLASORU, ad))
    print("olusturuldu:", ad)


def toplu_fatura_pdf(ad, faturalar):
    pdf = yeni_pdf()
    for i, (belge_no, tarih, satici_vkn, alici_vkn, matrah, kdv, toplam, oran) in enumerate(faturalar):
        if i > 0:
            pdf.add_page()
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "E-FATURA", ln=1, align="C")
        pdf.set_font("Arial", "", 10)
        pdf.ln(4)
        pdf.cell(0, 6, f"Belge No : {belge_no}", ln=1)
        pdf.cell(0, 6, f"Düzenlenme Tarihi : {tarih}", ln=1)
        pdf.ln(4)
        pdf.cell(0, 6, "SATAN", ln=1)
        pdf.cell(0, 6, f"Ünvan : ÖRNEK SANAYİ VE TİCARET LTD. ŞTİ.", ln=1)
        pdf.cell(0, 6, f"Vergi Kimlik No : {satici_vkn}", ln=1)
        pdf.ln(4)
        pdf.cell(0, 6, "ALICI", ln=1)
        pdf.cell(0, 6, f"Ünvan : MÜŞTERİ TİCARET A.Ş.", ln=1)
        pdf.cell(0, 6, f"Vergi Kimlik No : {alici_vkn}", ln=1)
        pdf.ln(6)
        pdf.cell(0, 6, "Mal Hizmet Toplam Tutarı : " + tl(matrah), ln=1)
        pdf.cell(0, 6, f"Hesaplanan KDV(%{oran}) : " + tl(kdv), ln=1)
        pdf.cell(0, 6, "Toplam : " + tl(toplam), ln=1)
    pdf.output(os.path.join(TEST_KLASORU, ad))
    print("olusturuldu:", ad)


def taranmis_pdf(ad, kaynak):
    import pymupdf
    doc = pymupdf.open(os.path.join(TEST_KLASORU, kaynak))
    yeni = pymupdf.open()
    for sayfa in doc:
        pix = sayfa.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
        gorsel = pix.tobytes("png")
        yeni.new_page(width=sayfa.rect.width, height=sayfa.rect.height)
        yeni[-1].insert_image(sayfa.rect, stream=gorsel)
    doc.close()
    yeni.save(os.path.join(TEST_KLASORU, ad))
    yeni.close()
    print("olusturuldu:", ad)


def excel_fatura_listesi():
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(["Fatura No", "Tarih", "VKN", "Ünvan", "Matrah", "KDV", "Toplam"])
    ws.append(["GFE202400000001", "05.02.2024", "12345678901", "ABC TİCARET", 1000.00, 200.00, 1200.00])
    ws.append(["GFE202400000002", "10.02.2024", "98765432109", "XYZ İTHALAT", 2500.00, 500.00, 3000.00])
    ws.append(["GFE202400000003", "11.02.2024", "55544433322", "DENEME ELEKTRONİK", 500.00, 50.00, 550.00])
    ws.append(["GFE202400000004", "15.02.2024", "11122233344", "BAŞKA GIDA", 300.00, 30.00, 330.00])
    ws.append(["TOPLAM", "", "", "", 4300.00, 780.00, 5080.00])
    wb.save(os.path.join(TEST_KLASORU, "fatura_listesi.xlsx"))
    print("olusturuldu: fatura_listesi.xlsx")


def excel_cetvel_listesi():
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(["Sıra No", "VKN", "Ünvan", "Belge No", "Tarih", "Matrah", "KDV"])
    ws.append([1, 12345678901, "ABC TİCARET LTD. ŞTİ.", "GFE202400000001", "05.02.2024", 1000.00, 200.00])
    ws.append([2, 98765432109, "XYZ İTHALAT A.Ş.", "GFE202400000002", "10.02.2024", 2500.00, 500.00])
    ws.append([3, 55544433322, "DENEME ELEKTRONİK", "GFE202400000003", "11.02.2024", 500.00, 45.00])
    ws.append([4, 99988877766, "FAZLA KAYIT SANAYİ", "GFE202400000009", "12.02.2024", 700.00, 140.00])
    ws.append(["GENEL TOPLAM", "", "", "", "", 4700.00, 885.00])
    wb.save(os.path.join(TEST_KLASORU, "kontrol_cetveli.xlsx"))
    print("olusturuldu: kontrol_cetveli.xlsx")


def fatura_xml(ad, belge_no, tarih, satici_vkn, alici_vkn, matrah, kdv, toplam, oran):
    icerik = f'''<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:CustomizationID>TR1.2</cbc:CustomizationID>
  <cbc:ProfileID>TEMELFATURA</cbc:ProfileID>
  <cbc:ID>{belge_no}</cbc:ID>
  <cbc:IssueDate>{tarih}</cbc:IssueDate>
  <cbc:InvoiceTypeCode>SATIS</cbc:InvoiceTypeCode>
  <cac:AccountingSupplierParty>
    <cac:Party>
      <cac:PartyIdentification><cbc:ID schemeID="VKN">{satici_vkn}</cbc:ID></cac:PartyIdentification>
      <cac:PartyName><cbc:Name>ÖRNEK SANAYİ VE TİCARET LTD. ŞTİ.</cbc:Name></cac:PartyName>
    </cac:Party>
  </cac:AccountingSupplierParty>
  <cac:AccountingCustomerParty>
    <cac:Party>
      <cac:PartyIdentification><cbc:ID schemeID="VKN">{alici_vkn}</cbc:ID></cac:PartyIdentification>
      <cac:PartyName><cbc:Name>MÜŞTERİ TİCARET A.Ş.</cbc:Name></cac:PartyName>
    </cac:Party>
  </cac:AccountingCustomerParty>
  <cac:TaxTotal>
    <cbc:TaxAmount currencyID="TRY">{kdv:.2f}</cbc:TaxAmount>
    <cac:TaxSubtotal>
      <cbc:TaxableAmount currencyID="TRY">{matrah:.2f}</cbc:TaxableAmount>
      <cbc:TaxAmount currencyID="TRY">{kdv:.2f}</cbc:TaxAmount>
      <cac:TaxCategory>
        <cbc:ID>K</cbc:ID>
        <cbc:Percent>{oran}</cbc:Percent>
        <cac:TaxScheme><cbc:Name>KDV</cbc:Name></cac:TaxScheme>
      </cac:TaxCategory>
    </cac:TaxSubtotal>
  </cac:TaxTotal>
  <cac:LegalMonetaryTotal>
    <cbc:LineExtensionAmount currencyID="TRY">{matrah:.2f}</cbc:LineExtensionAmount>
    <cbc:TaxExclusiveAmount currencyID="TRY">{matrah:.2f}</cbc:TaxExclusiveAmount>
    <cbc:TaxInclusiveAmount currencyID="TRY">{toplam:.2f}</cbc:TaxInclusiveAmount>
    <cbc:PayableAmount currencyID="TRY">{toplam:.2f}</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>
</Invoice>
'''
    with open(os.path.join(TEST_KLASORU, ad), "w", encoding="utf-8") as f:
        f.write(icerik)
    print("olusturuldu:", ad)


def fatura_xml_gzip(ad, icerik):
    import gzip
    with gzip.open(os.path.join(TEST_KLASORU, ad), "wb") as f:
        f.write(icerik.encode("utf-8"))
    print("olusturuldu:", ad)


def tl(sayi):
    return f"{sayi:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


if __name__ == "__main__":
    os.makedirs(TEST_KLASORU, exist_ok=True)
    fatura_pdf("fatura_1_ok.pdf", "GFE202400000001", "05.02.2024", "12345678901", "99900011122", 1000.00, 200.00, 1200.00, 20)
    fatura_pdf("fatura_2_ok.pdf", "GFE202400000002", "10.02.2024", "98765432109", "99900011122", 2500.00, 500.00, 3000.00, 20)
    fatura_pdf("fatura_3_kdv_fark.pdf", "GFE202400000003", "11.02.2024", "55544433322", "99900011122", 500.00, 50.00, 550.00, 10)
    fatura_pdf("fatura_4_cetvelde_yok.pdf", "GFE202400000004", "15.02.2024", "11122233344", "99900011122", 300.00, 30.00, 330.00, 10)
    fatura_pdf("fatura_5_vkn_fark.pdf", "GFE202400000010", "13.02.2024", "00099988877", "99900011122", 800.00, 160.00, 960.00, 20)

    cetvel_pdf("kontrol_cetveli.pdf", [
        {"vkn": "12345678901", "unvan": "ABC TİCARET LTD. ŞTİ.", "belge_no": "GFE202400000001", "tarih": "05.02.2024", "matrah": tl(1000.00), "kdv": tl(200.00)},
        {"vkn": "98765432109", "unvan": "XYZ İTHALAT A.Ş.", "belge_no": "GFE202400000002", "tarih": "10.02.2024", "matrah": tl(2500.00), "kdv": tl(500.00)},
        {"vkn": "55544433322", "unvan": "DENEME ELEKTRONİK", "belge_no": "GFE202400000003", "tarih": "11.02.2024", "matrah": tl(500.00), "kdv": tl(45.00)},
        {"vkn": "99988877766", "unvan": "FAZLA KAYIT SANAYİ", "belge_no": "GFE202400000009", "tarih": "12.02.2024", "matrah": tl(700.00), "kdv": tl(140.00)},
        {"vkn": "12345678901", "unvan": "ABC TİCARET LTD. ŞTİ.", "belge_no": "GFE202400000001", "tarih": "05.02.2024", "matrah": tl(1000.00), "kdv": tl(200.00)},
        {"vkn": "11122233344", "unvan": "BAŞKA GIDA LTD. ŞTİ.", "belge_no": "GFE202400000010", "tarih": "13.02.2024", "matrah": tl(800.00), "kdv": tl(160.00)},
    ])

    toplu_fatura_pdf("Toplu Fatura Yazdırma.pdf", [
        ("GFE202400000011", "05.02.2024", "12345678901", "99900011122", 1000.00, 200.00, 1200.00, 20),
        ("GFE202400000012", "10.02.2024", "98765432109", "99900011122", 2500.00, 500.00, 3000.00, 20),
    ])

    taranmis_pdf("taranmis_cetvel.pdf", "kontrol_cetveli.pdf")

    fatura_xml("fatura_1.xml", "GFE202400000001", "2024-02-05", "12345678901", "99900011122", 1000.00, 200.00, 1200.00, 20)
    fatura_xml("fatura_2.xml", "GFE202400000002", "2024-02-10", "98765432109", "99900011122", 2500.00, 500.00, 3000.00, 20)
    fatura_xml("fatura_3.xml", "GFE202400000003", "2024-02-11", "55544433322", "99900011122", 500.00, 50.00, 550.00, 10)
    fatura_xml("fatura_4.xml", "GFE202400000004", "2024-02-15", "11122233344", "99900011122", 300.00, 30.00, 330.00, 10)
    fatura_xml("fatura_5.xml", "GFE202400000010", "2024-02-13", "00099988877", "99900011122", 800.00, 160.00, 960.00, 20)

    import io
    gz_icerik = io.StringIO()
    fatura_xml_gzip("sikistirilmis_fatura.xml",
                    f'''<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:ID>GFE202400000099</cbc:ID>
  <cbc:IssueDate>2024-02-20</cbc:IssueDate>
  <cac:AccountingSupplierParty>
    <cac:Party><cac:PartyIdentification><cbc:ID>12345678901</cbc:ID></cac:PartyIdentification></cac:Party>
  </cac:AccountingSupplierParty>
  <cac:AccountingCustomerParty>
    <cac:Party><cac:PartyIdentification><cbc:ID>99900011122</cbc:ID></cac:PartyIdentification></cac:Party>
  </cac:AccountingCustomerParty>
  <cac:TaxTotal><cbc:TaxAmount>90.00</cbc:TaxAmount></cac:TaxTotal>
  <cac:LegalMonetaryTotal>
    <cbc:TaxExclusiveAmount>450.00</cbc:TaxExclusiveAmount>
    <cbc:TaxInclusiveAmount>540.00</cbc:TaxInclusiveAmount>
  </cac:LegalMonetaryTotal>
</Invoice>
''')

    excel_fatura_listesi()
    excel_cetvel_listesi()
    print("Test verileri hazır:", TEST_KLASORU)
