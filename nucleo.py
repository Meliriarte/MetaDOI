# -*- coding: utf-8 -*-
"""
nucleo.py
=========
Logica compartida del proyecto MetaDOI, sin entrada/salida de consola.
La usan el CLI (buscar_doi.py) y la interfaz grafica (app_gui.py).

Los datos bibliograficos salen de Crossref; el cuartil, del indice local
datos/scimago.db (generado por actualizar_scimago.py).

Se busca por DOI o por titulo de articulo:
    - DOI     -> /works/{doi}
    - Titulo  -> /works?query.title={titulo}  (mejor coincidencia -> DOI)
"""

import difflib
import re
import sqlite3
import unicodedata
from urllib.parse import quote

import requests

from config import (
    CABECERAS_CROSSREF,
    CROSSREF_URL,
    CROSSREF_URL_BUSQUEDA,
    CUARTILES_VALIDOS,
    MAX_GAP_ANIOS,
    MESES_ES,
    SCIMAGO_DB,
    TIPOS_SIN_CUARTIL,
    UMBRAL_SIMILITUD_TITULO,
    VALOR_REVISAR,
    VALOR_SIN_CUARTIL,
)
from actualizar_scimago import normalizar_issn


# --------------------------------------------------------------------------
# Entrada: DOI o titulo
# --------------------------------------------------------------------------
# DOI: 10.xxxx/yyyy (sufijo sin espacios).
_RE_DOI = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)


def detectar_tipo(texto):
    """Devuelve 'doi' si el texto es un DOI; None si no (se asume titulo)."""
    if texto and _RE_DOI.match(texto.strip()):
        return "doi"
    return None


def limpiar_identificador(texto):
    """Quita prefijos ('doi:', URL) y signos de puntuacion de los extremos."""
    limpio = str(texto).strip().strip(".,;()[]<>")
    limpio = re.sub(r"^(doi|issn|isbn)\s*[:=]?\s*", "", limpio, flags=re.IGNORECASE)
    limpio = re.sub(r"^https?://(dx\.)?doi\.org/", "", limpio, flags=re.IGNORECASE)
    limpio = re.sub(r"^https?://(www\.)?doi\.org/", "", limpio, flags=re.IGNORECASE)
    return limpio.strip()


def parsear_entradas(texto):
    """Convierte el texto de la caja en una lista de consultas.

    Cada linea es un DOI o un titulo. Si TODOS los tokens de una linea son DOI,
    se parten en varios DOI; si no, la linea entera se trata como un titulo
    (asi no se rompen los titulos, que llevan espacios).
    """
    entradas = []
    for linea in str(texto).splitlines():
        linea = limpiar_identificador(linea)
        if not linea:
            continue
        tokens = [t for t in re.split(r"[\s,;]+", linea) if t]
        if tokens and all(detectar_tipo(t) == "doi" for t in tokens):
            for token in tokens:
                if token not in entradas:
                    entradas.append(token)
        elif linea not in entradas:
            entradas.append(linea)
    return entradas


# --------------------------------------------------------------------------
# Indice local de Scimago
# --------------------------------------------------------------------------
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
        "SELECT issn, anio, cuartil FROM cuartiles WHERE issn IN (%s)" % marcadores,
        tuple(issns),
    ).fetchall()

    por_issn = {}
    for issn, anio_fila, cuartil in filas:
        # Se ignoran valores que no son un cuartil (p. ej. "-" o vacio).
        if cuartil not in CUARTILES_VALIDOS:
            continue
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


def separar_cuartil(indexacion):
    """Devuelve (base, tiene_cuartil). base = 'Q1'.., 'Sin cuartil' o 'REVISAR'."""
    base = (indexacion or "").split(" ")[0]
    return base, base in CUARTILES_VALIDOS


# --------------------------------------------------------------------------
# Crossref
# --------------------------------------------------------------------------
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


def normalizar_titulo(texto):
    """Deja un titulo en minusculas, sin acentos ni signos, para comparar."""
    sin_acentos = unicodedata.normalize("NFKD", texto or "")
    sin_acentos = "".join(c for c in sin_acentos if not unicodedata.combining(c))
    sin_acentos = re.sub(r"[^a-z0-9 ]+", " ", sin_acentos.lower())
    return " ".join(sin_acentos.split())


def buscar_dois_por_titulo(titulo):
    """Devuelve (doi, titulo_crossref, similitud) de la mejor coincidencia."""
    respuesta = requests.get(
        CROSSREF_URL_BUSQUEDA % quote(titulo, safe=""),
        headers=CABECERAS_CROSSREF,
        timeout=30,
    )
    if respuesta.status_code == 404:
        raise LookupError("Titulo no encontrado en Crossref")
    respuesta.raise_for_status()
    try:
        items = respuesta.json()["message"]["items"]
    except (KeyError, ValueError) as error:
        raise LookupError("Respuesta invalida de Crossref") from error
    if not items:
        raise LookupError("No se encontro ningun articulo con ese titulo")

    item = items[0]
    doi = item.get("DOI")
    encontrado = primer_texto(item.get("title"))
    similitud = difflib.SequenceMatcher(
        None, normalizar_titulo(titulo), normalizar_titulo(encontrado)
    ).ratio()
    return doi, encontrado, similitud


def obtener_fecha(mensaje):
    """Primera fecha disponible como lista [anio, mes?, dia?]."""
    # Se busca el mes en varios campos; si ninguno lo trae, queda solo el anio.
    for clave in ("published-print", "published-online", "published", "issued"):
        valor = mensaje.get(clave)
        if not valor:
            continue
        partes = valor.get("date-parts") or []
        if partes and partes[0] and partes[0][0]:
            return partes[0]
    return None


def primer_texto(valor):
    """Devuelve el primer texto de un campo que puede venir como lista o cadena.

    En /works/{doi} los campos 'title' y 'container-title' son listas.
    """
    if not valor:
        return ""
    if isinstance(valor, (list, tuple)):
        return str(valor[0]).strip() if valor else ""
    return str(valor).strip()


def formatear_fecha(partes):
    """[2025, 12] -> 'diciembre 2025'. Si no hay mes, solo el anio."""
    if not partes:
        return None
    anio = partes[0]
    if len(partes) >= 2 and partes[1] in MESES_ES:
        return "%s %s" % (MESES_ES[partes[1]], anio)
    return str(anio)


# --------------------------------------------------------------------------
# Resultados
# --------------------------------------------------------------------------
def construir_resultado(doi, mensaje, conexion, enlace=None):
    """Calcula los campos a partir de un registro de Crossref."""
    fecha = obtener_fecha(mensaje)
    anio = fecha[0] if fecha else None

    titulo = primer_texto(mensaje.get("title"))

    revista = primer_texto(mensaje.get("container-title"))
    if not revista:
        revista = primer_texto(mensaje.get("publisher"))

    issns = normalizar_issn(", ".join(mensaje.get("ISSN") or []))
    isbns = [b for b in (mensaje.get("ISBN") or []) if b]

    tipo_obra = (mensaje.get("type") or "").strip().lower()

    # Cuartil: se intenta siempre que haya ISSN y anio.
    indexacion = VALOR_REVISAR
    if anio:
        cuartil, anio_cuartil = buscar_cuartil(conexion, issns, anio)
        if cuartil:
            if anio_cuartil == anio:
                indexacion = cuartil
            else:
                # Se anota el anio real del cuartil cuando difiere.
                indexacion = "%s (%s)" % (cuartil, anio_cuartil)
        elif tipo_obra in TIPOS_SIN_CUARTIL:
            # Obra que Scimago no cubre y no se encontro cuartil.
            indexacion = VALOR_SIN_CUARTIL

    recurso = mensaje.get("resource") or {}
    primario = recurso.get("primary") or {}
    if not enlace:
        enlace = (
            primario.get("URL")
            or mensaje.get("URL")
            or "https://doi.org/%s" % (mensaje.get("DOI") or doi)
        )

    return {
        "tipo": "doi",
        "identificador": doi,
        "titulo": titulo or VALOR_REVISAR,
        "anio": str(anio) if anio else VALOR_REVISAR,
        "fecha": formatear_fecha(fecha) or VALOR_REVISAR,
        "revista": revista or VALOR_REVISAR,
        "indexacion": indexacion,
        "issn": ", ".join(issns),
        "isbn": ", ".join(isbns),
        "enlace": enlace,
        "tiene_cuartil": separar_cuartil(indexacion)[1],
    }


def resolver_entrada(entrada, conexion):
    """Resuelve un DOI o un titulo de articulo a un diccionario de resultado."""
    if detectar_tipo(entrada) == "doi":
        doi = limpiar_identificador(entrada)
        return construir_resultado(doi, consultar_crossref(doi), conexion)

    # No es un DOI: se asume un titulo de articulo; se busca el mejor match.
    doi, titulo_crossref, similitud = buscar_dois_por_titulo(entrada)
    if not doi:
        raise LookupError("No se encontro ningun articulo con ese titulo")
    resultado = construir_resultado(doi, consultar_crossref(doi), conexion)
    if similitud < UMBRAL_SIMILITUD_TITULO:
        resultado["nota"] = (
            "Coincidencia debil: se encontro \"%s\". Verifica que sea el articulo correcto."
            % (titulo_crossref or "sin titulo")
        )
    return resultado
