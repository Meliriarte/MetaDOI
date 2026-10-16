# -*- coding: utf-8 -*-
"""Configuracion central del proyecto Metadatos-DOI."""

import sys
from pathlib import Path

# --------------------------------------------------------------------------
# Rutas
# --------------------------------------------------------------------------
# Empaquetada con PyInstaller, la app corre junto a su .exe; si no, junto a este
# archivo. Asi datos/scimago.db siempre queda al lado del ejecutable.
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent
DATOS_DIR = BASE_DIR / "datos"
SCIMAGO_DB = DATOS_DIR / "scimago.db"
# CSV legado: solo se usa para migrar a la base de datos (ver --desde-csv).
SCIMAGO_CSV = DATOS_DIR / "scimago.csv"

# --------------------------------------------------------------------------
# Scimago
# --------------------------------------------------------------------------
# Rango de anios que se descargan del ranking de Scimago.
ANIO_INICIO = 1999
ANIO_FIN = 2025

# Cabeceras de navegador reales: Scimago esta detras de Cloudflare y bloquea
# peticiones "normales". Con estas cabeceras la descarga del CSV funciona.
CABECERAS_SCIMAGO = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://www.scimagojr.com/",
}

# --------------------------------------------------------------------------
# Crossref
# --------------------------------------------------------------------------
# El correo entra al "polite pool" de Crossref (te tratan mejor). Pon uno real.
MAILTO = "soporte@tuinstitucion.edu.co"

CABECERAS_CROSSREF = {
    "User-Agent": "Metadatos-DOI/1.0 (mailto:%s)" % MAILTO,
    "Accept": "application/json",
}

CROSSREF_URL = "https://api.crossref.org/works/%s"

# --------------------------------------------------------------------------
# Reglas de negocio
# --------------------------------------------------------------------------
# Tipos de obra de Crossref que NO tienen cuartil en Scimago.
# (Los articulos de revista y de congreso si lo tienen.)
TIPOS_SIN_CUARTIL = {
    "book",
    "book-chapter",
    "book-part",
    "book-section",
    "book-track",
    "edited-book",
    "monograph",
    "reference-book",
    "reference-entry",
    "component",
    "dataset",
    "dissertation",
    "grant",
    "peer-review",
    "posted-content",
    "report",
    "standard",
}

# Valores especiales de la columna "Indexacion".
VALOR_SIN_CUARTIL = "otro"   # libros y capitulos de libro
VALOR_REVISAR = "REVISAR"    # no se pudo localizar el dato

# Cuartiles validos. Scimago usa "-" cuando la revista no tiene cuartil ese
# anio; ese valor NO es un cuartil y se ignora.
CUARTILES_VALIDOS = {"Q1", "Q2", "Q3", "Q4"}

# Si el cuartil no existe en el anio exacto de publicacion, se busca en el anio
# mas cercano de esa revista (Scimago publica con ~1 anio de rezago). Este es el
# limite de diferencia permitido; mas alla, se marca REVISAR.
MAX_GAP_ANIOS = 3

# --------------------------------------------------------------------------
# Meses en espaniol (para "Fecha de publicacion")
# --------------------------------------------------------------------------
MESES_ES = {
    1: "enero",
    2: "febrero",
    3: "marzo",
    4: "abril",
    5: "mayo",
    6: "junio",
    7: "julio",
    8: "agosto",
    9: "septiembre",
    10: "octubre",
    11: "noviembre",
    12: "diciembre",
}

# --------------------------------------------------------------------------
# Presentacion
# --------------------------------------------------------------------------
LINEA = "-" * 60
