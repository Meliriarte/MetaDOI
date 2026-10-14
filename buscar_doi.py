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
datos/scimago.csv (generado por actualizar_scimago.py).

Uso:
    python buscar_doi.py
"""

import csv
import re
import sys

import requests

# Evita errores/caracteres rotos al imprimir titulos con acentos o en otros idiomas.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config import (
    CABECERAS_CROSSREF,
    CROSSREF_URL,
    LINEA,
    MAX_GAP_ANIOS,
    MESES_ES,
    SCIMAGO_CSV,
    TIPOS_SIN_CUARTIL,
    VALOR_REVISAR,
    VALOR_SIN_CUARTIL,
)
from actualizar_scimago import normalizar_issn


def cargar_indice():
    """Carga datos/scimago.csv en un dict  issn -> {anio: cuartil}."""
    if not SCIMAGO_CSV.exists():
        raise SystemExit(
            "No existe %s.\nEjecuta primero:  python actualizar_scimago.py"
            % SCIMAGO_CSV
        )
    indice = {}
    with open(SCIMAGO_CSV, encoding="utf-8") as archivo:
        for fila in csv.DictReader(archivo):
            indice.setdefault(fila["issn"], {})[fila["anio"]] = fila["cuartil"]
    return indice


def buscar_cuartil(indice, issns, anio):
    """Devuelve (cuartil, anio_del_cuartil) o (None, None).

    1. Busca el anio exacto en cualquiera de los ISSN de la revista.
    2. Si no hay, usa el anio mas cercano de la revista (preferencia: el mas
       reciente <= anio de publicacion), sin superar MAX_GAP_ANIOS. Esto cubre
       el rezago anual con que Scimago publica sus datos.
    """
    for issn in issns:
        cuartil = indice.get(issn, {}).get(str(anio))
        if cuartil:
            return cuartil, anio

    mejor = None  # (clave_orden, cuartil, anio_encontrado)
    for issn in issns:
        for anio_str, cuartil in indice.get(issn, {}).items():
            if not cuartil:
                continue
            candidato = int(anio_str)
            if abs(candidato - anio) > MAX_GAP_ANIOS:
                continue
            if candidato <= anio:
                clave = (0, anio - candidato)   # mas reciente <= anio
            else:
                clave = (1, candidato - anio)   # mas proximo por arriba
            if mejor is None or clave < mejor[0]:
                mejor = (clave, cuartil, candidato)

    if mejor:
        return mejor[1], mejor[2]
    return None, None


def limpiar_doi(texto):
    """Deja solo el DOI, quitando prefijos de URL o 'doi:'."""
    limpio = texto.strip()
    limpio = re.sub(r"^https?://(dx\.)?doi\.org/", "", limpio, flags=re.I)
    limpio = re.sub(r"^doi:\s*", "", limpio, flags=re.I)
    return limpio.strip().rstrip(". ")


def consultar_crossref(doi):
    """Devuelve el 'message' de Crossref o lanza excepcion."""
    respuesta = requests.get(
        CROSSREF_URL % doi, headers=CABECERAS_CROSSREF, timeout=30
    )
    if respuesta.status_code == 404:
        raise LookupError("DOI no registrado en Crossref")
    respuesta.raise_for_status()
    try:
        return respuesta.json()["message"]
    except (KeyError, ValueError) as error:
        raise LookupError("Respuesta invalida de Crossref") from error


def obtener_fecha(mensaje):
    """Primera fecha disponible como lista [anio, mes?, dia?]."""
    for clave in ("published-print", "published-online", "issued"):
        valor = mensaje.get(clave)
        if not valor:
            continue
        partes = valor.get("date-parts") or []
        if partes and partes[0] and partes[0][0]:
            return partes[0]
    return None


def formatear_fecha(partes):
    """[2025, 12] -> 'diciembre 2025'. Si no hay mes, solo el anio."""
    if not partes:
        return None
    anio = partes[0]
    if len(partes) >= 2 and partes[1] in MESES_ES:
        return "%s %s" % (MESES_ES[partes[1]], anio)
    return str(anio)


def construir_resultado(doi, mensaje, indice):
    """Calcula los 5 campos a partir del registro de Crossref."""
    fecha = obtener_fecha(mensaje)
    anio = fecha[0] if fecha else None

    revistas = mensaje.get("container-title") or []
    revista = revistas[0].strip() if revistas else ""
    if not revista:
        revista = (mensaje.get("publisher") or "").strip()

    tipo = (mensaje.get("type") or "").strip().lower()
    if tipo in TIPOS_SIN_CUARTIL:
        indexacion = VALOR_SIN_CUARTIL
    else:
        indexacion = VALOR_REVISAR
        if anio:
            issns = normalizar_issn(", ".join(mensaje.get("ISSN") or []))
            cuartil, anio_cuartil = buscar_cuartil(indice, issns, anio)
            if cuartil:
                if anio_cuartil == anio:
                    indexacion = cuartil
                else:
                    # Se anota el anio real del cuartil cuando difiere.
                    indexacion = "%s (%s)" % (cuartil, anio_cuartil)

    recurso = mensaje.get("resource") or {}
    primario = recurso.get("primary") or {}
    enlace = (
        primario.get("URL")
        or mensaje.get("URL")
        or "https://doi.org/%s" % doi
    )

    return {
        "doi": doi,
        "anio": str(anio) if anio else VALOR_REVISAR,
        "fecha": formatear_fecha(fecha) or VALOR_REVISAR,
        "revista": revista or VALOR_REVISAR,
        "indexacion": indexacion,
        "enlace": enlace,
    }


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

    indice = cargar_indice()

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

        mostrar(construir_resultado(doi, mensaje, indice))


if __name__ == "__main__":
    main()
