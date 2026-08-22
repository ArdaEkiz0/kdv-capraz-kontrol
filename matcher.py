from decimal import Decimal
from collections import defaultdict

TOLERANS = Decimal("0.02")

DURUM_OK = "EŞLEŞTİ"
DURUM_TUTAR_FARKI = "TUTAR FARKI"
DURUM_VKN_FARKI = "VKN FARKI"
DURUM_KDV_SIFIR = "KDV 0"
DURUM_CETVELDE_YOK = "CETVELDE YOK"
DURUM_FATURADA_YOK = "FATURALARDA YOK"
DURUM_MUKERRER = "MÜKERRER"
DURUM_PARSE_SORUNU = "PARSE SORUNU"
DURUM_TEVKIFATLI = "TEVKİFATLI"
DURUM_INDIRIMLI = "İNDİRİMLİ"

# Faturanın KDV/matrahının muavin defterine tevkifat sonrası düşülen oranları.
# Örn. %30 tevkifat -> muavinde %70 (0.70) kayıtlı; akaryakıt %5 -> 0.95.
# Gerçek uygulamada gördüğün oranları: 0.70 (otömotiv/şarj/akaryakıt %30 tevk),
# 0.95 (akaryakıt %5). Düşkün oranları (0.9/0.8/0.5 vb.) tutar farklıdan
# ayırt etmek için katılmamıştır.
TEVKIFAT_ORANLARI = (Decimal("0.70"), Decimal("0.95"))

SORUNLU_DURUMLAR = (
    DURUM_TUTAR_FARKI, DURUM_VKN_FARKI, DURUM_KDV_SIFIR, DURUM_CETVELDE_YOK,
    DURUM_FATURADA_YOK, DURUM_MUKERRER, DURUM_PARSE_SORUNU,
)


def vkn_uyumlu(f, c):
    f_vkn = f["satici_vkn"] or ""
    c_vkn = c["vkn"] or ""
    if not f_vkn or not c_vkn:
        return True
    return f_vkn == c_vkn


def tutarlar_uyumlu(f, c):
    for alan in ("matrah", "kdv"):
        f_deger = f.get(alan)
        c_deger = c.get(alan)
        if f_deger is not None and c_deger is not None:
            if alan == "kdv" and (f.get("fatura_tipi") or f.get("tip") or "").upper() == "IADE":
                f_deger = abs(f_deger)
            if abs(f_deger - c_deger) > TOLERANS:
                return False
    return True


def fark_metni(f_alan, c_alan):
    f_deger = "" if f_alan is None else f"{f_alan:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    c_deger = "" if c_alan is None else f"{c_alan:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"Fatura: {f_deger} | Cetvel: {c_deger}"


def duplikat_bul(liste, anahtar_fonksiyonu):
    sayac = defaultdict(int)
    for oge in liste:
        sayac[anahtar_fonksiyonu(oge)] += 1
    return {a: n for a, n in sayac.items() if n > 1}


def _tutar_esit(a, b):
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(a - b) < TOLERANS


def _oran_yaklasik(f_deger, c_deger, hedef):
    """f_deger'in c_deger'e oranı hedef tevkifat oranına yakın mı?"""
    if f_deger is None or c_deger is None:
        return False
    if f_deger == 0:
        return False
    oran = c_deger / f_deger
    return abs(oran - hedef) <= Decimal("0.02")


def tevkifat_kes(f, c):
    """Fatura ile cetvel KDV/matrahı tevkifat oranıyla ilişkiliyse oranı döndürür, yoksa None."""
    f_kdv = f.get("kdv")
    c_kdv = c.get("kdv")
    if f_kdv is not None and c_kdv is not None and f_kdv != 0:
        for oran in TEVKIFAT_ORANLARI:
            if _oran_yaklasik(f_kdv, c_kdv, oran):
                return oran
    return None


def tevkifat_detay(f, c, oran):
    parcalar = []
    for alan in ("matrah", "kdv"):
        f_deger = f.get(alan)
        c_deger = c.get(alan)
        if f_deger is not None and c_deger is not None:
            parcalar.append(alan.capitalize() + ": " + fark_metni(f_deger, c_deger))
    yuzde = int(round((1 - oran) * 100))
    return " | ".join(parcalar) + f" | Muavin KDV tevkifatlı (≈%{yuzde} düşülmüş, oran {oran})"


def capraz_kontrol(faturalar, cetvel_kayitlari):
    def anahtar_fatura(f):
        return (f["belge_no"] or "").upper()

    def anahtar_cetvel(c):
        return (c["belge_no"] or "").upper()

    def _kdv0_fatura(f):
        f_kdv = f.get("kdv")
        if f_kdv is None:
            return True
        if (f.get("fatura_tipi") or f.get("tip") or "").upper() == "IADE":
            f_kdv = abs(f_kdv)
        return abs(f_kdv) < TOLERANS

    kdv0_belges = {anahtar_fatura(f) for f in faturalar if _kdv0_fatura(f)}
    if kdv0_belges:
        faturalar = [f for f in faturalar if anahtar_fatura(f) not in kdv0_belges]
        cetvel_kayitlari = [c for c in cetvel_kayitlari if anahtar_cetvel(c) not in kdv0_belges]

    sonuc_satirlari = []
    ozet = {
        "fatura_adet": len(faturalar),
        "cetvel_adet": len(cetvel_kayitlari),
        "eslesen": 0,
        "tutar_farki": 0,
        "vkn_farki": 0,
        "kdv_sifir": len(kdv0_belges),
        "cetvelde_yok": 0,
        "faturada_yok": 0,
        "mukerrer": 0,
        "parse_sorunu": 0,
        "tevkifatli": 0,
    }

    f_grup = defaultdict(list)
    for f in faturalar:
        if f["belge_no"]:
            f_grup[anahtar_fatura(f)].append(f)

    c_grup = defaultdict(list)
    for c in cetvel_kayitlari:
        if c["belge_no"]:
            c_grup[anahtar_cetvel(c)].append(c)

    kullanilan_c = set()
    kullanilan_f = set()

    def durum_ekle(durum, f, c, detay=""):
        f_belge = f["belge_no"] if f else (c["belge_no"] if c else "")
        f_vkn = f["satici_vkn"] if f else (c["vkn"] if c else "")
        f_tarih = f["tarih"] if f else (c["tarih"] if c else "")
        f_matrah = f["matrah"] if f else (c["matrah"] if c else "")
        f_kdv = f["kdv"] if f else (c["kdv"] if c else "")
        f_unvan = f.get("satici_unvan") if f else (c.get("unvan") if c else "")
        f_toplam = f.get("toplam") if f else None
        f_oranlar = f.get("oranlar") if f else []
        f_tip = f.get("fatura_tipi") if f else ""
        f_ok = f.get("oran_kontrol") if f else ""
        sonuc_satirlari.append({
            "durum": durum,
            "belge_no": f_belge,
            "vkn": f_vkn,
            "tarih": f_tarih,
            "matrah": f_matrah,
            "kdv": f_kdv,
            "toplam": f_toplam,
            "oranlar": list(f_oranlar) if f_oranlar else [],
            "tip": (f_tip or "") if f_tip else "",
            "oran_kontrol": (f_ok or "") if f_ok else "",
            "unvan": (f_unvan or "") if f_unvan else "",
            "kaynak": "Fatura" if f else ("Cetvel" if c else ""),
            "detay": detay,
        })

    def fark_parcalari(f, c):
        parcalar = []
        for alan in ("matrah", "kdv"):
            f_deger = f.get(alan)
            c_deger = c.get(alan)
            if f_deger is not None and c_deger is not None and abs(f_deger - c_deger) > TOLERANS:
                parcalar.append(alan.capitalize() + ": " + fark_metni(f_deger, c_deger))
        return parcalar

    for anahtar, f_listesi in f_grup.items():
        c_listesi = c_grup.pop(anahtar, [])
        if not c_listesi:
            continue

        # Akıllı eşleştirme: aynı belge numarasında birden fazla fatura ve/veya
        # cetvel kaydı olabilir (belge numarası çakışması). Sırayla değil,
        # içerik uyumuna göre eşleştirilir:
        #   1) tarih eşit + tutar uyumlu, 2) yalnız tutar uyumlu, 3) kalanlar sırayla.
        c_kullanilan = set()
        eslesmeler = []

        def _bos_indeksler():
            return [j for j in range(len(c_listesi)) if j not in c_kullanilan]

        for f in f_listesi:
            for j in _bos_indeksler():
                c = c_listesi[j]
                if f.get("tarih") and f["tarih"] == c.get("tarih") and tutarlar_uyumlu(f, c):
                    eslesmeler.append((f, j))
                    c_kullanilan.add(j)
                    break
        eslenen_f = {id(f) for f, _ in eslesmeler}
        for f in f_listesi:
            if id(f) in eslenen_f:
                continue
            for j in _bos_indeksler():
                if tutarlar_uyumlu(f, c_listesi[j]):
                    eslesmeler.append((f, j))
                    c_kullanilan.add(j)
                    break
        eslenen_f = {id(f) for f, _ in eslesmeler}
        kalan_f = [f for f in f_listesi if id(f) not in eslenen_f]
        for f, j in zip(kalan_f, sorted(_bos_indeksler())):
            eslesmeler.append((f, j))
            c_kullanilan.add(j)

        for f, j in eslesmeler:
            c = c_listesi[j]
            kullanilan_c.add((id(c), anahtar))
            kullanilan_f.add(id(f))
            if not vkn_uyumlu(f, c):
                durum = DURUM_VKN_FARKI
                ozet["vkn_farki"] += 1
                detay = f"Fatura satıcı VKN: {f['satici_vkn']} | Cetvel VKN: {c['vkn']}"
                farklar = fark_parcalari(f, c)
                if farklar:
                    detay += " | " + " | ".join(farklar)
            elif not tutarlar_uyumlu(f, c):
                tk_oran = tevkifat_kes(f, c)
                if tk_oran is not None:
                    durum = DURUM_TEVKIFATLI
                    ozet["tevkifatli"] += 1
                    detay = tevkifat_detay(f, c, tk_oran)
                else:
                    durum = DURUM_TUTAR_FARKI
                    ozet["tutar_farki"] += 1
                    detay = " | ".join(fark_parcalari(f, c))
                    if f["tarih"] and c["tarih"] and f["tarih"] != c["tarih"]:
                        detay += f" | Tarih: {f['tarih']} vs {c['tarih']}"
            else:
                durum = DURUM_OK
                ozet["eslesen"] += 1
                detay = ""
                if (f.get("indirim_toplam") or Decimal("0")) > Decimal("0"):
                    durum = DURUM_INDIRIMLI
                    detay = f"Fatura özel indirim içerir (≈{f['indirim_toplam']:,.2f})"
            durum_ekle(durum, f, c, detay)

        # Artan faturalar: eşleşen bir faturanın birebir kopyasıysa mükerrer,
        # değilse muavindefterinde hiç yoktur → CETVELDE YOK.
        eslesen_f = {id(f) for f, _ in eslesmeler}
        eslesen_icerik = [(p.get("tarih"), p.get("matrah"), p.get("kdv")) for p, _ in eslesmeler]
        for f in f_listesi:
            if id(f) in eslesen_f:
                continue
            kullanilan_f.add(id(f))
            if any(f.get("tarih") == t and _tutar_esit(f.get("matrah"), m)
                   and _tutar_esit(f.get("kdv"), kdv)
                   for t, m, kdv in eslesen_icerik):
                ozet["mukerrer"] += 1
                durum_ekle(DURUM_MUKERRER, f, None, "Aynı fatura birden fazla kayıt halinde")
            else:
                ozet["cetvelde_yok"] += 1
                detay = []
                if f["matrah"] is None or f["kdv"] is None:
                    detay.append("Tutarlar okunamadı")
                durum_ekle(DURUM_CETVELDE_YOK, f, None, " / ".join(detay) if detay else "Cetvelde kaydı yok")
        # Artan cetvel satırları: defterde mükerrer kayıt.
        for j, c in enumerate(c_listesi):
            if j in c_kullanilan:
                continue
            ozet["mukerrer"] += 1
            durum_ekle(DURUM_MUKERRER, None, c, "Cetvelde aynı fatura birden fazla satır halinde")

    kalan_f = []
    for f in faturalar:
        if id(f) in kullanilan_f:
            continue
        if f["belge_no"]:
            kalan_f.append(f)

    for f in kalan_f:
        ozet["cetvelde_yok"] += 1
        detay = []
        if f["matrah"] is None or f["kdv"] is None:
            detay.append("Tutarlar okunamadı")
        durum_ekle(DURUM_CETVELDE_YOK, f, None, " / ".join(detay) if detay else "Cetvelde kaydı yok")

    for anahtar, c_listesi in list(c_grup.items()):
        for c in c_listesi:
            if (id(c), anahtar) in kullanilan_c:
                continue
            if not c["belge_no"]:
                continue
            ozet["faturada_yok"] += 1
            durum_ekle(DURUM_FATURADA_YOK, None, c, "Faturalar arasında kaydı yok")

    for f in faturalar:
        if f["belge_no"] is None and f["satici_vkn"] is None and f["matrah"] is None:
            ozet["parse_sorunu"] += 1
            durum_ekle(DURUM_PARSE_SORUNU, f, None, "PDF'den veri çıkarılamadı (taranmış PDF olabilir)")

    ozet["fark_toplami"] = sum((r["durum"] == DURUM_TUTAR_FARKI) for r in sonuc_satirlari)
    sonuc_satirlari.sort(key=lambda r: (SORUNLU_DURUMLAR.index(r["durum"]) if r["durum"] in SORUNLU_DURUMLAR else 99, r["belge_no"] or ""))
    return sonuc_satirlari, ozet


# ============================================================================
# İADE FATURA DESTEĞİ (YENİ)
# ============================================================================

def z_raporu_hesap_kontrol(fis_kayitlari, muavin_kayitlari):
    """MAHSUP fişi PDF'i ile muavin defterini hesap bazında karşılaştırır.

    Kayıt formatı (her iki taraf için): {belge, tarih, hesap, hesap_adi, borc, alacak}
    Sonuç satırları capraz_kontrol ile aynı formatta üretilir.
    """
    sonuc_satirlari = []
    ozet = {
        "fatura_adet": len(fis_kayitlari),
        "cetvel_adet": len(muavin_kayitlari),
        "eslesen": 0, "tutar_farki": 0, "vkn_farki": 0, "kdv_sifir": 0,
        "cetvelde_yok": 0, "faturada_yok": 0, "mukerrer": 0,
        "parse_sorunu": 0, "fark_toplami": 0,
    }

    def anahtar(k):
        return ((k["belge"] or "").upper(), k.get("hesap") or "")

    f_grup = defaultdict(list)
    for k in fis_kayitlari:
        f_grup[anahtar(k)].append(k)
    m_grup = defaultdict(list)
    for k in muavin_kayitlari:
        m_grup[anahtar(k)].append(k)

    kullanilan_f = set()
    kullanilan_m = set()

    def kayit_tutar(k):
        return k["alacak"] if k["alacak"] else k["borc"]

    def durum_ekle(durum, f, m, detay=""):
        k = f if f is not None else m
        tutar = kayit_tutar(k) if k is not None else None
        belge = (k["belge"] or "") if k is not None else ""
        sonuc_satirlari.append({
            "durum": durum,
            "belge_no": belge,
            "vkn": "",
            "tarih": k.get("tarih") if k is not None else None,
            "matrah": tutar,
            "kdv": None,
            "toplam": None,
            "oranlar": [],
            "tip": "Z RAPORU" if belge.startswith("Z") else "MAHSUP",
            "oran_kontrol": "",
            "unvan": (k.get("hesap_adi") or "") if k is not None else "",
            "kaynak": "Fatura" if f is not None else "Cetvel",
            "detay": detay,
        })

    for a, f_list in f_grup.items():
        m_list = m_grup.pop(a, [])
        if not m_list:
            continue
        es = min(len(f_list), len(m_list))
        for i in range(es):
            f = f_list[i]
            m = m_list[i]
            kullanilan_f.add(id(f))
            kullanilan_m.add((id(m), a))
            f_tutar = kayit_tutar(f)
            m_tutar = kayit_tutar(m)
            hesap = a[1]
            if f_tutar is not None and m_tutar is not None and abs(f_tutar - m_tutar) > TOLERANS:
                ozet["tutar_farki"] += 1
                durum_ekle(DURUM_TUTAR_FARKI, f, m, "Hesap: " + hesap + " | " + fark_metni(f_tutar, m_tutar))
            else:
                ozet["eslesen"] += 1
                durum_ekle(DURUM_OK, f, m, "Hesap: " + hesap)
        for f in f_list[es:]:
            ozet["mukerrer"] += 1
            durum_ekle(DURUM_MUKERRER, f, None, "Hesap: " + a[1] + " | Aynı belge/hesap birden fazla kayıt")
        for m in m_list[es:]:
            ozet["mukerrer"] += 1
            durum_ekle(DURUM_MUKERRER, None, m, "Hesap: " + a[1] + " | Muavinde aynı belge/hesap birden fazla kayıt")

    kalan_f = [f for f in fis_kayitlari if id(f) not in kullanilan_f and f["belge"]]
    for f in kalan_f:
        ozet["cetvelde_yok"] += 1
        durum_ekle(DURUM_CETVELDE_YOK, f, None, "Hesap: " + (f.get("hesap") or "") + " | Muavinde kaydı yok")

    for a, m_list in list(m_grup.items()):
        for m in m_list:
            if (id(m), a) in kullanilan_m or not m["belge"]:
                continue
            ozet["faturada_yok"] += 1
            durum_ekle(DURUM_FATURADA_YOK, None, m, "Hesap: " + (m.get("hesap") or "") + " | Faturada kaydı yok")

    ozet["fark_toplami"] = ozet["tutar_farki"]
    sonuc_satirlari.sort(key=lambda r: (SORUNLU_DURUMLAR.index(r["durum"]) if r["durum"] in SORUNLU_DURUMLAR else 99, r["belge_no"] or ""))
    return sonuc_satirlari, ozet


def capraz_kontrol_iade_destekli(faturalar, cetvel_kayitlari):
    """İade faturalarını ayrı ele alarak çapraz kontrol yapar.

    capraz_kontrol ile aynı sonucu verir, ancak:
    - İade faturaları "İADE MUAVİNDE YOK" olarak ayrı raporlanır
    - İadeler mutlak değerle muavinle eşleşir
    """
    from iade_ayristirici import iade_ayristirici_ozet, iade_ozet_hesapla

    gruplar = iade_ayristirici_ozet(faturalar)
    normal_faturalar = gruplar["normal"]
    iade_faturalar = gruplar["iade"]

    # Normal faturaları normal kontrol
    if normal_faturalar:
        sonuc, ozet = capraz_kontrol(normal_faturalar, cetvel_kayitlari)
    else:
        sonuc = []
        ozet = {
            "fatura_adet": 0, "cetvel_adet": len(cetvel_kayitlari),
            "eslesen": 0, "tutar_farki": 0, "vkn_farki": 0, "kdv_sifir": 0,
            "cetvelde_yok": 0, "faturada_yok": 0, "mukerrer": 0,
            "parse_sorunu": 0, "fark_toplami": 0,
        }

    # İade faturaları ayrı kontrol (muavin 191 hesabında aranmalı).
    # Sorun: normal ve iade faturalar ayn cetvel listesini kullandığdan,
    # iade'le eşleşen muavin kayıtlarını normal kontrol'de "FATURALARDA YOK"
    # olarak ikire gösterdı. Düzeltme: iade faturaları SONRA kontrol edilip,
    # eşleşen belge'ler normal "FATURALARDA YOK" sonuc'dan tam kaldırılır.
    if iade_faturalar:
        iade_eksikler = []
        durum_cevir = {
            DURUM_OK: "İADE EŞLEŞTİ",
            DURUM_CETVELDE_YOK: "İADE MUAVİNDE YOK",
            DURUM_TUTAR_FARKI: "İADE MATRAH FARKI",
            DURUM_VKN_FARKI: "İADE VKN FARKI",
            DURUM_MUKERRER: "İADE MÜKERRER",
            DURUM_TEVKIFATLI: "İADE TEVKİFATLI",
        }
        # İade kontrolü SADECE iade belge numaralarına uyan muavin satırlarıyla
        # yapılır. Tüm liste verilirse, normal geçişte eşleşmiş muavin kayıtları
        # iade geçişinde tekrar "FATURALARDA YOK" olarak raporlanıyordu.
        import copy as _cpy
        iade_belge_kumesi = {(f["belge_no"] or "").upper() for f in iade_faturalar}
        iade_cetvel = [
            c for c in cetvel_kayitlari
            if (c.get("belge_no") or "").upper() in iade_belge_kumesi
        ]
        iade_abs = []
        for f in iade_faturalar:
            f2 = _cpy.deepcopy(f)
            if f2.get("kdv") is not None:
                f2["kdv"] = abs(f2["kdv"])
            if f2.get("matrah") is not None:
                f2["matrah"] = abs(f2["matrah"])
            iade_abs.append(f2)
        iade_sonuc, iade_ozet2 = capraz_kontrol(iade_abs, iade_cetvel)
        for r, f in zip(iade_sonuc, iade_faturalar):
            r["durum"] = durum_cevir.get(r["durum"], r["durum"])
            if r["kdv"] is not None:
                r["kdv"] = abs(r["kdv"])
            if r["matrah"] is not None:
                r["matrah"] = abs(r["matrah"])
            r["belge_no"] = f["belge_no"]
            r["kaynak"] = "Fatura (İade)"
            if r["durum"] == "İADE MUAVİNDE YOK":
                iade_eksikler.append(r["belge_no"] or "")
        sonuc.extend(iade_sonuc)

        # Normal kontrolde "FATURALARDA YOK" çıkmış, iade ile eşleşen muavin satırlarını kaldır
        ozet["tevkifatli"] = ozet.get("tevkifatli", 0) + iade_ozet2.get("tevkifatli", 0)
        eslesen_iade_belge = {r["belge_no"] for r in iade_sonuc if r["durum"] == "İADE EŞLEŞTİ"}
        if eslesen_iade_belge:
            onceki_sayı = len(sonuc)
            sonuc = [
                r for r in sonuc
                if not (r["durum"] == DURUM_FATURADA_YOK and r["belge_no"] in eslesen_iade_belge)
            ]
            cikan = onceki_sayı - len(sonuc)
            ozet["faturada_yok"] = max(0, ozet.get("faturada_yok", 0) - cikan)

        # Özete iade bilgisi ekle
        iade_ozet = iade_ozet_hesapla(iade_faturalar)
        ozet["iade_adet"] = iade_ozet["iade_adet"]
        ozet["iade_kdv_toplam"] = float(iade_ozet["toplam_iade_kdv"])
        ozet["iade_matrah_toplam"] = float(iade_ozet["toplam_iade_matrah"])
        ozet["iade_muavinde_yok"] = len(iade_eksikler)
        ozet["fatura_adet"] = ozet.get("fatura_adet", 0) + len(iade_faturalar)

    return sonuc, ozet

