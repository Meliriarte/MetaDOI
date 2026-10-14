# Metadatos-DOI

Herramienta de línea de comandos que, a partir de uno o varios **DOI**, devuelve
una lista con los datos bibliográficos de cada publicación:

| Campo | Descripción |
| --- | --- |
| **Año** | Año de publicación. |
| **Fecha de publicación / creación** | Mes y año (ej. `diciembre 2025`). |
| **Revista** | Nombre de la revista, congreso o libro. |
| **Indexación** | Cuartil Scimago (`Q1`..`Q4`), o `otro` para libros, o `REVISAR`. |
| **Enlace** | URL del editor (o `https://doi.org/<doi>` si no hay otra). |

Todo corre **local y gratis**, sin inteligencia artificial:

- Los datos bibliográficos salen de la **API de Crossref** (`api.crossref.org`).
- El cuartil sale del **ranking anual de Scimago (SJR)**, descargado a un índice local.

---

## ¿Cómo funciona? (flujo)

```
              DOI               API de Crossref              Índice Scimago local
   usuario ──────────►  buscar_doi.py ──────────► reúne metadatos ──────► cruza ISSN+año
                                                          │                     │
                                                          ▼                     ▼
                                            Año / Fecha / Revista       Cuartil (Q1..Q4)
                                                          \                    /
                                                           ▼                  ▼
                                                        Lista de 5 campos en pantalla
```

1. **`actualizar_scimago.py`** descarga el ranking de Scimago (1999–2025) y construye
   el índice local `datos/scimago.csv`. Se corre **una vez al año**.
2. **`buscar_doi.py`** pide los DOI, consulta Crossref y cruza el ISSN + año contra el
   índice local para obtener el cuartil.

---

## Requisitos

- **Python 3.8 o superior**.
- La librería **`requests`** (es la única dependencia externa):

```
pip install -r requirements.txt
```

---

## Puesta en marcha

### 1. Instalar dependencias (una sola vez)

```
pip install -r requirements.txt
```

### 2. Construir el índice de Scimago (una vez al año)

```
python actualizar_scimago.py
```

Descarga los CSV oficiales de Scimago año por año y genera `datos/scimago.csv`
(~65 MB, ~1.1 millones de registros). Tarda un par de minutos.

### 3. Consultar DOI(s)

```
python buscar_doi.py
```

Pega **uno o varios DOI** (uno por línea) y pulsa **ENTER en vacío** para terminar:

```
Pega el/los DOI (uno por linea). ENTER en vacio para terminar.

DOI > 10.3390/s26144610
DOI > 10.1038/s41586-020-2649-2
DOI > 10.1007/978-3-540-68161-8_1
DOI >
```

Salida:

```
------------------------------------------------------------
DOI: 10.3390/s26144610
  Anio:                 2026
  Fecha de publicacion: julio 2026
  Revista:              Sensors
  Indexacion:           Q1 (2025)
  Enlace:               https://www.mdpi.com/1424-8220/26/14/4610
------------------------------------------------------------

------------------------------------------------------------
DOI: 10.1038/s41586-020-2649-2
  Anio:                 2020
  Fecha de publicacion: septiembre 2020
  Revista:              Nature
  Indexacion:           Q1
  Enlace:               https://www.nature.com/articles/s41586-020-2649-2
------------------------------------------------------------

------------------------------------------------------------
DOI: 10.1007/978-3-540-68161-8_1
  Anio:                 2007
  Fecha de publicacion: 2007
  Revista:              Beiträge zum ausländischen öffentlichen Recht und Völkerrecht
  Indexacion:           otro
  Enlace:               http://link.springer.com/10.1007/978-3-540-68161-8_1
------------------------------------------------------------
```

> **Tip:** puedes pegar los DOI en cualquier formato; el script limpia los prefijos
> `https://doi.org/...` y `doi:` automáticamente. También acepta varios DOI separados
> por espacios o comas en una misma línea.

---

## Reglas de indexación (cuartil)

La búsqueda del cuartil es **escalonada**:

1. **ISSN + año exacto.** Se prueba cada ISSN de la revista (impreso y electrónico).
2. **ISSN + año más cercano.** Si no hay cuartil en el año exacto, se usa el año más
   cercano de esa revista, con preferencia por el más reciente **≤ año de publicación**.
   Solo se permite hasta **3 años de diferencia** (`MAX_GAP_ANIOS`). Cuando el año del
   cuartil no coincide, se anota entre paréntesis: **`Q1 (2025)`**.
   - Esto cubre el **rezago de Scimago**, que publica sus datos con ~1 año de retraso
     (p. ej. un artículo de 2026 usa el cuartil de 2025).
3. **Sin coincidencia → `REVISAR`.**

Casos especiales:

| Situación | Resultado |
| --- | --- |
| Artículo de revista o congreso con cuartil | `Q1` / `Q2` / `Q3` / `Q4` |
| Cuartil de otro año (rezago de Scimago) | `Q1 (2025)` |
| **Libro o capítulo de libro** | `otro` |
| Revista **no indexada** en Scimago | `REVISAR` |
| Artículo **sin ISSN** (típico en algunos congresos) | `REVISAR` |
| Dato más antiguo que el límite de 3 años | `REVISAR` |
| DOI **inexistente** en Crossref | `REVISAR` |

> **Nota:** Scimago solo cubre revistas y algunas memorias de congreso. Muchos papers
> de congreso de IEEE (tipo `proceedings-article`) **no están indexados** en Scimago y
> no tienen ISSN, por lo que aparecerán como `REVISAR`. Eso es correcto: Scimago no
> tiene ese dato.

---

## Estructura del proyecto

```
Metadatos-DOI/
├─ actualizar_scimago.py   # descarga Scimago y genera el índice local
├─ buscar_doi.py           # consulta DOI(s) y muestra la lista
├─ config.py               # configuración central (correo, rutas, reglas)
├─ datos/
│  └─ scimago.csv          # índice local: issn, anio, cuartil, tipo, titulo
├─ requirements.txt        # dependencias (requests)
└─ README.md
```

| Archivo | Qué hace |
| --- | --- |
| `config.py` | Configuración: correo de Crossref, rutas, rango de años, reglas y meses. |
| `actualizar_scimago.py` | Descarga Scimago (1999–2025) y genera `datos/scimago.csv`. |
| `buscar_doi.py` | Pide DOI(s) y muestra la lista de metadatos. |
| `datos/scimago.csv` | Índice local con columnas `issn, anio, cuartil, tipo, titulo`. |

---

## Configuración (`config.py`)

| Variable | Para qué sirve |
| --- | --- |
| `MAILTO` | **Cámbialo por un correo real.** Te mete en el "polite pool" de Crossref (respuestas más rápidas y fiables). |
| `ANIO_INICIO` / `ANIO_FIN` | Rango de años de Scimago a descargar (por defecto 1999–2025). |
| `MAX_GAP_ANIOS` | Máxima diferencia de años permitida al buscar el cuartil cercano (por defecto 3). |
| `TIPOS_SIN_CUARTIL` | Tipos de obra de Crossref que no llevan cuartil (libros, capítulos, etc.). |
| `VALOR_SIN_CUARTIL` / `VALOR_REVISAR` | Marcadores `otro` y `REVISAR`. |
| `MESES_ES` | Nombres de los meses en español. |

---

## Mantenimiento

- **Una vez al año**, cuando Scimago publique el ranking del año nuevo, vuelve a
  ejecutar `python actualizar_scimago.py` para regenerar el índice. Si quieres incluir
  el año nuevo, actualiza también `ANIO_FIN` en `config.py`.

---

## Preguntas frecuentes

**¿Por qué me sale `REVISAR` si el artículo sí tiene cuartil?**
Puede ser por:
- El artículo es de un año que Scimago aún no publica (rezago) y la revista no tiene
  datos dentro del margen de 3 años.
- La revista no está indexada en Scimago (no es lo mismo que Scopus).
- Es un paper de congreso sin ISSN que Scimago no cubre.

Verifica el cuartil manualmente en <https://www.scimagojr.com> buscando por ISSN.

**¿Necesito internet?**
Sí, para consultar Crossref en cada búsqueda. La descarga de Scimago también requiere
internet, pero una vez construido el índice, la consulta del cuartil es local.

**¿Se guarda un archivo con los resultados?**
No. La salida es solo en pantalla, por diseño.

**¿Usa inteligencia artificial?**
No. Son consultas estructuradas (Crossref + Scimago). Sin alucinaciones.

---

## Notas técnicas

- Scimago está detrás de **Cloudflare**; por eso la descarga usa cabeceras de navegador
  reales. Si algún año falla, el script reintenta 3 veces.
- El índice local evita depender de la web de Scimago en cada consulta y hace las
  búsquedas instantáneas.
