from decimal import Decimal


def kdv_dagilim_fatura(faturalar):
    """XML/PDF faturalarin oran bazinda KDV dagilimi."""
    toplamlar = {}
    for f in faturalar:
        detay = f.get("vergi_detay") or []
        if detay:
            for st in detay:
                o = st.get("oran")
                kdv = st.get("kdv")
                if kdv is None:
                    continue
                anahtar = o if o is not None else "BILINMIYOR"
                g = toplamlar.setdefault(anahtar, {"adet": 0, "matrah": 0, "kdv": 0})
                g["adet"] += 1
                g["matrah"] += abs(st.get("matrah") or 0)
                g["kdv"] += abs(kdv)
        else:
            oranlar = f.get("oranlar") or []
            if len(oranlar) == 1:
                anahtar = oranlar[0]
            elif len(oranlar) > 1:
                anahtar = "KARISIK"
            else:
                anahtar = "BILINMIYOR"
            g = toplamlar.setdefault(anahtar, {"adet": 0, "matrah": 0, "kdv": 0})
            g["adet"] += 1
            g["matrah"] += abs(f.get("matrah") or 0)
            g["kdv"] += abs(f.get("kdv") or 0)
    return toplamlar


def kdv_dagilim_muavin(cetvel_kayitlari):
    """Muavin kayitlarinin hesap kodu bazinda KDV dagilimi."""
    toplamlar = {}
    for c in cetvel_kayitlari:
        hesap = ""
        for n in c.get("notlar") or []:
            if n.startswith("Hesap:"):
                hesap = n.split(":", 1)[1].strip()
                break
        anahtar = hesap or "HESAPSIZ"
        g = toplamlar.setdefault(anahtar, {"adet": 0, "kdv": 0})
        g["adet"] += 1
        g["kdv"] += c.get("kdv") or 0
    return toplamlar


def ba_formu(faturalar):
    """Satici bazinda Ba formu verisi: VKN, unvan, adet, matrah, kdv."""
    saticilar = {}
    for f in faturalar:
        anahtar = (f.get("satici_vkn") or "", f.get("satici_unvan") or "")
        if not any(anahtar):
            anahtar = ("BILINMIYOR", "Bilinmeyen Satici")
        g = saticilar.setdefault(anahtar, {"adet": 0, "matrah": 0, "kdv": 0})
        g["adet"] += 1
        g["matrah"] += f.get("matrah") or 0
        g["kdv"] += f.get("kdv") or 0
    liste = []
    for (vkn, unvan), g in sorted(saticilar.items(), key=lambda x: (x[0][1] or x[0][0])):
        liste.append({
            "vkn": vkn, "unvan": unvan,
            "adet": g["adet"], "matrah": g["matrah"], "kdv": g["kdv"],
        })
    return liste


def eksik_belgeler(sonuc_satirlari):
    """Muavinde kaydi olmayan fatura belge numaralari (gecmis karsilastirmasi icin)."""
    return sorted({
        r["belge_no"] for r in sonuc_satirlari
        if r["durum"] in ("CETVELDE YOK", "İADE MUAVİNDE YOK") and r.get("belge_no")
    })
