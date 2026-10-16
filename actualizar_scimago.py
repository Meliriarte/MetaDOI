# -*- coding: utf-8 -*-
"""
actualizar_scimago.py
=====================
Descarga el ranking anual de Scimago (SJR) y construye el indice local
datos/scimago.db (SQLite) con la relacion: ISSN + anio -> cuartil.

Se ejecuta una vez al anio (Scimago publica los datos con retraso).

Uso:
    python actualizar_scimago.py                    # descarga y regenera la BD
    python actualizar_scimago.py --desde-csv RUTA   # migra desde un CSV existente
    python actualizar_scimago.py --desde-csv        # usa datos/scimago.csv
"""

import argparse
import csv
import io
import re
import sqlite3
import sys
import time
from pathlib import Path

import requests

from config import (
    ANIO_FIN,
    ANIO_INICIO,
    CABECERAS_SCIMAGO,
    DATOS_DIR,
    SCIMAGO_CSV,
    SCIMAGO_DB,
)

INTENTOS = 3
ESPERA = 5  # segundos entre reintentos
LOTE = 50000  # filas por insercion al migrar desde CSV

SQL_CREAR = """
CREATE TABLE IF NOT EXISTS cuartiles (
    issn TEXT NOT NULL,
    anio INTEGER NOT NULL,
    cuartil TEXT,
    PRIMARY KEY (issn, anio)
) WITHOUT ROWID
"""


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


def abrir_bd():
    """Abre (o crea) datos/scimago.db y garantiza la tabla."""
    DATOS_DIR.mkdir(parents=True, exist_ok=True)
    conexion = sqlite3.connect(SCIMAGO_DB)
    conexion.execute(SQL_CREAR)
    return conexion


def guardar(conexion, filas):
    """Inserta filas (issn, anio, cuartil). Con duplicados gana el ultimo,
    igual que hacia el indice CSV anterior."""
    conexion.executemany(
        "INSERT OR REPLACE INTO cuartiles (issn, anio, cuartil) VALUES (?, ?, ?)",
        filas,
    )
    conexion.commit()


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


def filas_desde_texto(texto, anio):
    """Devuelve (issn, anio, cuartil) por cada ISSN del CSV de Scimago."""
    filas = []
    lector = csv.DictReader(io.StringIO(texto), delimiter=";")
    for registro in lector:
        cuartil = (registro.get("SJR Best Quartile") or "").strip()
        for issn in normalizar_issn(registro.get("Issn")):
            filas.append((issn, anio, cuartil))
    return filas


def descargar_todo():
    """Descarga todos los anios configurados y vuelca a la base de datos."""
    conexion = abrir_bd()
    fallidos = []
    total = 0

    for anio in range(ANIO_INICIO, ANIO_FIN + 1):
        print("Descargando Scimago %s ..." % anio)
        try:
            texto = descargar_anio(anio)
        except RuntimeError as error:
            print("  !! %s" % error)
            fallidos.append(anio)
            continue
        filas = filas_desde_texto(texto, anio)
        guardar(conexion, filas)
        total += len(filas)
        print("  %s registros" % len(filas))

    conexion.close()

    print("\nListo: %s" % SCIMAGO_DB)
    print("Total de registros (issn, anio): %s" % total)

    if fallidos:
        print("Anios que fallaron: %s" % ", ".join(str(a) for a in fallidos))
        sys.exit(1)


def migrar_desde_csv(ruta):
    """Migra un CSV de Scimago ya descargado a la base de datos."""
    if not ruta.exists():
        raise SystemExit("No existe el CSV: %s" % ruta)

    conexion = abrir_bd()
    total = 0
    lote = []

    with open(ruta, encoding="utf-8") as archivo:
        for fila in csv.DictReader(archivo):
            lote.append((fila["issn"], int(fila["anio"]), fila.get("cuartil", "")))
            if len(lote) >= LOTE:
                guardar(conexion, lote)
                total += len(lote)
                lote = []

    if lote:
        guardar(conexion, lote)
        total += len(lote)

    conexion.close()

    print("Migrados %s registros desde %s" % (total, ruta))
    print("Listo: %s" % SCIMAGO_DB)


def main():
    parser = argparse.ArgumentParser(
        description="Genera el indice local de Scimago en SQLite."
    )
    parser.add_argument(
        "--desde-csv",
        metavar="RUTA",
        nargs="?",
        const=str(SCIMAGO_CSV),
        help="Migra desde un CSV ya descargado en vez de bajar de internet.",
    )
    argumentos = parser.parse_args()

    if argumentos.desde_csv:
        migrar_desde_csv(Path(argumentos.desde_csv))
    else:
        descargar_todo()


if __name__ == "__main__":
    main()
