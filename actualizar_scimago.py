# -*- coding: utf-8 -*-
"""
actualizar_scimago.py
=====================
Descarga el ranking anual de Scimago (SJR) y construye un indice local
en datos/scimago.csv con la relacion: ISSN + anio -> cuartil.

Se ejecuta una vez al anio (Scimago publica los datos con retraso).

Uso:
    python actualizar_scimago.py
"""

import csv
import io
import re
import sys
import time

import requests

from config import (
    ANIO_FIN,
    ANIO_INICIO,
    CABECERAS_SCIMAGO,
    DATOS_DIR,
    SCIMAGO_CSV,
)

INTENTOS = 3
ESPERA = 5  # segundos entre reintentos


def normalizar_issn(texto):
    """Convierte un texto con uno o varios ISSN en una lista 'NNNN-NNNN'.

    Soporta los formatos que devuelve Scimago, por ejemplo:
        '15454509, 00664154'      -> ['1545-4509', '0066-4154']
        'ISSN 14710072, 14710080' -> ['1471-0072', '1471-0080']
        '1234-567X'               -> ['1234-567X']
    """
    if not texto:
        return []

    limpio = str(texto).upper().replace("ISSN", " ")
    salida = []
    for token in re.split(r"[,;\s]+", limpio):
        digitos = re.sub(r"[^0-9X]", "", token)
        if len(digitos) == 8:
            salida.append("%s-%s" % (digitos[:4], digitos[4:]))
    return salida


def descargar_anio(anio):
    """Descarga el CSV de un anio. Devuelve el texto o lanza excepcion."""
    url = "https://www.scimagojr.com/journalrank.php?out=xls&year=%s" % anio
    for intento in range(1, INTENTOS + 1):
        try:
            respuesta = requests.get(
                url, headers=CABECERAS_SCIMAGO, timeout=90
            )
            if respuesta.status_code == 200:
                # errors="replace" evita que un encoding inesperado tumbe el proceso.
                texto = respuesta.content.decode("utf-8-sig", errors="replace")
                if "SJR Best Quartile" in texto:
                    return texto
        except Exception as error:
            print("    intento %s fallo: %s" % (intento, error))
        time.sleep(ESPERA)
    raise RuntimeError("No se pudo descargar el anio %s desde Scimago" % anio)


def extraer_filas(texto, anio):
    """Devuelve (issn, anio, cuartil, tipo, titulo) por cada ISSN del CSV."""
    filas = []
    lector = csv.DictReader(io.StringIO(texto), delimiter=";")
    for registro in lector:
        titulo = (registro.get("Title") or "").strip()
        tipo = (registro.get("Type") or "").strip()
        cuartil = (registro.get("SJR Best Quartile") or "").strip()
        for issn in normalizar_issn(registro.get("Issn")):
            filas.append((issn, anio, cuartil, tipo, titulo))
    return filas


def main():
    DATOS_DIR.mkdir(parents=True, exist_ok=True)

    todas = []
    fallidos = []

    for anio in range(ANIO_INICIO, ANIO_FIN + 1):
        print("Descargando Scimago %s ..." % anio)
        try:
            texto = descargar_anio(anio)
        except RuntimeError as error:
            print("  !! %s" % error)
            fallidos.append(anio)
            continue
        filas = extraer_filas(texto, anio)
        todas.extend(filas)
        print("  %s registros" % len(filas))

    with open(SCIMAGO_CSV, "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["issn", "anio", "cuartil", "tipo", "titulo"])
        escritor.writerows(todas)

    print("\nListo: %s" % SCIMAGO_CSV)
    print("Total de registros (issn, anio): %s" % len(todas))

    if fallidos:
        print("Anios que fallaron: %s" % ", ".join(str(a) for a in fallidos))
        sys.exit(1)


if __name__ == "__main__":
    main()
