# -*- coding: utf-8 -*-
"""
nucleo.py
=========
Logica compartida del proyecto MetaDOI, sin entrada/salida de consola.
La usan el CLI (buscar_doi.py) y la interfaz grafica (app_gui.py).

Los datos bibliograficos salen de Crossref; el cuartil, del indice local
datos/scimago.db (generado por actualizar_scimago.py).
"""

import re
import sqlite3

import requests

from config import (
    CABECERAS_CROSSREF,
    CROSSREF_URL,
    MAX_GAP_ANIOS,
    MESES_ES,
    SCIMAGO_DB,
    TIPOS_SIN_CUARTIL,
    VALOR_REVISAR,
    VALOR_SIN_CUARTIL,
)
from actualizar_scimago import normalizar_issn


def conectar_indice():
    """Abre datos/scimago.db. Lanza SystemExit si no existe."""
    if not SCIMAGO_DB.exists():
        raise SystemExit(
            "No existe %s.\nEjecuta primero:  python actualizar_scimago.py"
            % SCIMAGO_DB
        )
    return sqlite3.connect(SCIMAGO_DB)


def buscar_cuartil(conexion, issns, anio):
    """Devuelve (cuartil, anio_del_cuartil) o (None, None).

    1. Busca el anio exacto en cualquiera de los ISSN de la revista.
    2. Si no hay, usa el anio mas cercano de la revista (preferencia: el mas
       reciente <= anio de publicacion), sin superar MAX_GAP_ANIOS. Esto cubre
       el rezago anual con que Scimago publica sus datos.
    """
    if not issns:
        return None, None

    marcadores = ",".join("?" * len(issns))
    filas = conexion.execute(
        "SELECT issn, anio, cuartil FROM cuartiles "
        "WHERE cuartil <> '' AND issn IN (%s)" % marcadores,
        tuple(issns),
    ).fetchall()

    por_issn = {}
    for issn, anio_fila, cuartil in filas:
        por_issn.setdefault(issn, []).append((anio_fila, cuartil))

    # 1. Anio exacto, respetando el orden de los ISSN recibidos.
    for issn in issns:
        for anio_fila, cuartil in por_issn.get(issn, []):
            if anio_fila == anio:
                return cuartil, anio

    # 2. Anio mas cercano dentro del margen permitido.
    mejor = None  # (clave_orden, cuartil, anio_encontrado)
    for issn in issns:
        for anio_fila, cuartil in por_issn.get(issn, []):
            if abs(anio_fila - anio) > MAX_GAP_ANIOS:
                continue
            if anio_fila <= anio:
                clave = (0, anio - anio_fila)   # mas reciente <= anio
            else:
                clave = (1, anio_fila - anio)   # mas proximo por arriba
            if mejor is None or clave < mejor[0]:
                mejor = (clave, cuartil, anio_fila)

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


def construir_resultado(doi, mensaje, conexion):
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
            cuartil, anio_cuartil = buscar_cuartil(conexion, issns, anio)
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
