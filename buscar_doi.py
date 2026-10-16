# -*- coding: utf-8 -*-
"""
buscar_doi.py
=============
Le das uno o varios DOI y devuelve, por cada uno, una lista con:
    - Anio
    - Fecha de publicacion / creacion
    - Revista
    - Indexacion (cuartil Q1..Q4)
    - Enlace

Los datos bibliograficos salen de Crossref; el cuartil, del indice local
datos/scimago.db (generado por actualizar_scimago.py). La logica vive en
nucleo.py; aqui solo se maneja la consola.

Uso:
    python buscar_doi.py
"""

import re
import sys

import requests

# Evita errores/caracteres rotos al imprimir titulos con acentos o en otros idiomas.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config import LINEA, VALOR_REVISAR
from nucleo import (
    conectar_indice,
    construir_resultado,
    consultar_crossref,
    limpiar_doi,
)


def mostrar(resultado):
    print(LINEA)
    print("DOI: %s" % resultado["doi"])
    print("  %-21s %s" % ("Anio:", resultado["anio"]))
    print("  %-21s %s" % ("Fecha de publicacion:", resultado["fecha"]))
    print("  %-21s %s" % ("Revista:", resultado["revista"]))
    print("  %-21s %s" % ("Indexacion:", resultado["indexacion"]))
    print("  %-21s %s" % ("Enlace:", resultado["enlace"]))
    print(LINEA)


def leer_dois():
    """Lee DOI(s) de consola hasta una linea vacia."""
    print("Pega el/los DOI (uno por linea). ENTER en vacio para terminar.\n")
    dois = []
    while True:
        try:
            linea = input("DOI > ")
        except EOFError:
            break
        if not linea.strip():
            break
        for token in re.split(r"[\s,;]+", linea):
            doi = limpiar_doi(token)
            if doi and doi not in dois:
                dois.append(doi)
    return dois


def main():
    dois = leer_dois()
    if not dois:
        print("No ingresaste ningun DOI.")
        return

    conexion = conectar_indice()

    for doi in dois:
        print()
        try:
            mensaje = consultar_crossref(doi)
        except LookupError as error:
            mostrar(
                {
                    "doi": doi,
                    "anio": VALOR_REVISAR,
                    "fecha": VALOR_REVISAR,
                    "revista": VALOR_REVISAR,
                    "indexacion": VALOR_REVISAR,
                    "enlace": "https://doi.org/%s" % doi,
                }
            )
            print("  (!) %s" % error)
            continue
        except requests.RequestException as error:
            print("%s\n  Error de red al consultar %s: %s" % (LINEA, doi, error))
            continue

        mostrar(construir_resultado(doi, mensaje, conexion))


if __name__ == "__main__":
    main()
