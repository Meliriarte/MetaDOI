# -*- coding: utf-8 -*-
"""
buscar_doi.py
=============
Le das uno o varios DOI o titulos de articulo (uno por linea) y devuelve, por
cada consulta, una lista con:
    - Titulo
    - Revista
    - Anio
    - Fecha de publicacion (solo anio si Crossref no trae mes)
    - Cuartil (Q1..Q4, "Sin cuartil" o "REVISAR")
    - ISSN / ISBN
    - Enlace

Los datos bibliograficos salen de Crossref; el cuartil, del indice local
datos/scimago.db (generado por actualizar_scimago.py). La logica vive en
nucleo.py; aqui solo se maneja la consola.

Uso:
    python buscar_doi.py
"""

import sys

import requests

# Evita errores/caracteres rotos al imprimir titulos con acentos o en otros idiomas.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config import LINEA
from nucleo import (
    conectar_indice,
    detectar_tipo,
    parsear_entradas,
    resolver_entrada,
)

PREFIJO = {"doi": "DOI", "titulo": "Consulta"}


def mostrar(r):
    print(LINEA)
    print("%s: %s" % (PREFIJO.get(r.get("tipo"), "DOI"), r.get("identificador")))
    print("  %-21s %s" % ("Titulo:", r.get("titulo")))
    print("  %-21s %s" % ("Revista:", r.get("revista")))
    print("  %-21s %s" % ("Anio:", r.get("anio")))
    print("  %-21s %s" % ("Fecha de publicacion:", r.get("fecha")))
    print("  %-21s %s" % ("Cuartil:", r.get("indexacion")))
    if r.get("issn"):
        print("  %-21s %s" % ("ISSN:", r["issn"]))
    if r.get("isbn"):
        print("  %-21s %s" % ("ISBN:", r["isbn"]))
    print("  %-21s %s" % ("Enlace:", r.get("enlace")))
    print(LINEA)


def error_no_resuelto(entrada, nota):
    print(LINEA)
    print("%s: %s" % (PREFIJO.get(detectar_tipo(entrada) or "titulo", "Consulta"), entrada))
    print("  (!) %s" % nota)
    print(LINEA)


def leer_entradas():
    """Lee lineas (cada una, un DOI o un titulo) hasta una linea vacia."""
    print("Pega uno o varios DOI o titulos de articulo, uno por linea.")
    print("ENTER en vacio para terminar.\n")
    lineas = []
    while True:
        try:
            linea = input("> ")
        except EOFError:
            break
        if not linea.strip():
            break
        lineas.append(linea)
    return parsear_entradas("\n".join(lineas))


def main():
    entradas = leer_entradas()
    if not entradas:
        print("No ingresaste ningun DOI ni titulo.")
        return

    conexion = conectar_indice()

    for entrada in entradas:
        print()
        try:
            mostrar(resolver_entrada(entrada, conexion))
        except LookupError as error:
            error_no_resuelto(entrada, str(error))
        except requests.RequestException as error:
            print("%s\n  Error de red al consultar %s: %s" % (LINEA, entrada, error))


if __name__ == "__main__":
    main()
