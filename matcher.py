from decimal import Decimal
from collections import defaultdict

TOLERANS = Decimal("0.02")

DURUM_OK = "EŞLEŞTİ"
DURUM_TUTAR_FARKI = "TUTAR FARKI"
DURUM_VKN_FARKI = "VKN FARKI"
DURUM_CETVELDE_YOK = "CETVELDE YOK"
DURUM_FATURADA_YOK = "FATURALARDA YOK"
DURUM_MUKERRER = "MÜKERRER"
DURUM_PARSE_SORUNU = "PARSE SORUNU"

SORUNLU_DURUMLAR = (
    DURUM_TUTAR_FARKI, DURUM_VKN_FARKI, DURUM_CETVELDE_YOK,
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
            if alan == "kdv" and (f.get("tip") or "").upper() == "IADE":
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


def capraz_kontrol(faturalar, cetvel_kayitlari):
    sonuc_satirlari = []
    ozet = {
        "fatura_adet": len(faturalar),
        "cetvel_adet": len(cetvel_kayitlari),
        "eslesen": 0,
        "tutar_farki": 0,
        "vkn_farki": 0,
        "cetvelde_yok": 0,
        "faturada_yok": 0,
        "mukerrer": 0,
        "parse_sorunu": 0,
    }

    def anahtar_fatura(f):
        return (f["belge_no"] or "").upper()

    def anahtar_cetvel(c):
        return (c["belge_no"] or "").upper()

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
        f_tip = f.get("tip") if f else ""
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
        eslenen = min(len(f_listesi), len(c_listesi))
        for i in range(eslenen):
            f = f_listesi[i]
            c = c_listesi[i]
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
                durum = DURUM_TUTAR_FARKI
                ozet["tutar_farki"] += 1
                detay = " | ".join(fark_parcalari(f, c))
                if f["tarih"] and c["tarih"] and f["tarih"] != c["tarih"]:
                    detay += f" | Tarih: {f['tarih']} vs {c['tarih']}"
            else:
                durum = DURUM_OK
                ozet["eslesen"] += 1
                detay = ""
            durum_ekle(durum, f, c, detay)
        if len(f_listesi) > eslenen:
            for f in f_listesi[eslenen:]:
                ozet["mukerrer"] += 1
                durum_ekle(DURUM_MUKERRER, f, None, "Aynı fatura birden fazla kayıt halinde")
        if len(c_listesi) > eslenen:
            for c in c_listesi[eslenen:]:
                ozet["mukerrer"] += 1
                durum_ekle(DURUM_MUKERRER, None, c, "Cetvelde aynı fatura birden fazla satır halinde")

    kalan_f = []
    for f in faturalar:
        if id(f) in kullanilan_f:
            continue
        if f["belge_no"] and f["satici_vkn"]:
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
    sonuc, ozet = capraz_kontrol(normal_faturalar, cetvel_kayitlari)

    # İade faturaları ayrı kontrol (muavin 191 hesabında aranmalı)
    if iade_faturalar:
        iade_eksikler = []
        eslesen_belge_nolar = {
            r.get("belge_no") for r in sonuc
            if r.get("belge_no") and r["durum"] == DURUM_OK
        }

        for f in iade_faturalar:
            belge = f.get("belge_no")
            if belge and belge in eslesen_belge_nolar:
                # Muavinde var, eşleşti sayılır
                sonuc.append({
                    "durum": "İADE EŞLEŞTİ",
                    "belge_no": belge,
                    "vkn": f.get("satici_vkn"),
                    "tarih": f.get("tarih"),
                    "matrah": f.get("matrah"),
                    "kdv": abs(f["kdv"]) if f.get("kdv") is not None else None,
                    "toplam": f.get("toplam"),
                    "oranlar": f.get("oranlar") or [],
                    "tip": f.get("tip") or "",
                    "unvan": f.get("satici_unvan") or "",
                    "kaynak": "Fatura (İade)",
                    "detay": "İade faturası muavinde eşleşti (191 hesabı)",
                })
            else:
                iade_eksikler.append(f)
                sonuc.append({
                    "durum": "İADE MUAVİNDE YOK",
                    "belge_no": belge or "",
                    "vkn": f.get("satici_vkn"),
                    "tarih": f.get("tarih"),
                    "matrah": f.get("matrah"),
                    "kdv": abs(f["kdv"]) if f.get("kdv") is not None else None,
                    "toplam": f.get("toplam"),
                    "oranlar": f.get("oranlar") or [],
                    "tip": f.get("tip") or "",
                    "unvan": f.get("satici_unvan") or "",
                    "kaynak": "Fatura (İade)",
                    "detay": "İade faturası - muavin 191 hesabında aranmalı",
                })

        # Özete iade bilgisi ekle
        iade_ozet = iade_ozet_hesapla(iade_faturalar)
        ozet["iade_adet"] = iade_ozet["iade_adet"]
        ozet["iade_kdv_toplam"] = float(iade_ozet["toplam_iade_kdv"])
        ozet["iade_matrah_toplam"] = float(iade_ozet["toplam_iade_matrah"])

    return sonuc, ozet

