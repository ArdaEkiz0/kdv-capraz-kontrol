"""conftest.py — pytest konfigürasyonu."""
import os
import sys

# Proje kök dizinini Python path'e ekle
PROJE_KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJE_KOK not in sys.path:
    sys.path.insert(0, PROJE_KOK)
