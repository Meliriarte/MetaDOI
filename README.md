# Metadatos-DOI

Herramienta que, a partir de uno o varios **DOI**, devuelve una lista con los datos
bibliográficos de cada publicación:

| Campo | Descripción |
| --- | --- |
| **Año** | Año de publicación. |
| **Fecha de publicación / creación** | Mes y año (ej. `diciembre 2025`). |
| **Revista** | Nombre de la revista, congreso o libro. |
| **Indexación** | Cuartil Scimago (`Q1`..`Q4`), o `otro` para libros, o `REVISAR`. |
| **Enlace** | URL del editor (o `https://doi.org/<doi>` si no hay otra). |

Se puede usar de dos formas:

- **App de escritorio** (`app_gui.py`, con interfaz gráfica). Pensada para Windows.
- **Línea de comandos** (`buscar_doi.py`).

Todo corre **local y gratis**, sin inteligencia artificial:

- Los datos bibliográficos salen de la **API de Crossref** (`api.crossref.org`).
- El cuartil sale del **ranking anual de Scimago (SJR)**, guardado en un índice
  local en formato **SQLite** (`datos/scimago.db`).

---

## ¿Cómo funciona? (flujo)

```
              DOI               API de Crossref              Índice Scimago local
   usuario ──────────►  nucleo.py ──────────► reúne metadatos ──────► cruza ISSN+año
                                                          │                     │
                                                          ▼                     ▼
                                            Año / Fecha / Revista       Cuartil (Q1..Q4)
                                                          \                    /
                                                           ▼                  ▼
                                                     App de escritorio o consola
```

1. **`actualizar_scimago.py`** descarga el ranking de Scimago (1999–2025) y construye
   el índice local `datos/scimago.db`. Se corre **una vez al año**.
2. **`nucleo.py`** consulta Crossref y cruza el ISSN + año contra el índice local
   para obtener el cuartil.
3. **`app_gui.py`** (interfaz gráfica) o **`buscar_doi.py`** (consola) muestran el resultado.

---

## Requisitos

- **Python 3.8 o superior**.
- Dependencias (**`requests`** y **`customtkinter`**):

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

Descarga los CSV oficiales de Scimago año por año y genera `datos/scimago.db`
(~24 MB, ~1.1 millones de registros). Tarda un par de minutos.

> Si ya tienes un CSV de Scimago descargado antes, puedes migrarlo sin volver a
> bajar todo: `python actualizar_scimago.py --desde-csv datos/scimago.csv`.

### 3. Usar la herramienta

**App de escritorio:**

```
python app_gui.py
```

Pega uno o varios DOI en la caja de texto y pulsa **Consultar**. Los resultados
aparecen en tarjetas.

**Consola:**

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
```

> **Tip:** puedes pegar los DOI en cualquier formato; el programa limpia los prefijos
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

## Construir la app para Windows (`.exe`)

Con PyInstaller se empaqueta la app en un **único archivo `.exe`** que **no requiere
Python** ni la carpeta de datos: la base de Scimago (`datos/scimago.db`) viaja **dentro**
del ejecutable.

```
pip install -r requirements-dev.txt
pyinstaller --noconfirm --windowed --onefile --name MetaDOI ^
  --icon MetaDOI.ico ^
  --collect-all customtkinter ^
  --add-data "datos/scimago.db;datos" ^
  --exclude-module numpy --exclude-module PIL --exclude-module cryptography ^
  --exclude-module bcrypt --exclude-module setuptools ^
  --exclude-module h2 --exclude-module hpack --exclude-module hyperframe ^
  app_gui.py
```

- `--onefile` → un solo `dist/MetaDOI.exe` (~20 MB), sin carpetas ni archivos sueltos.
- `--add-data "datos/scimago.db;datos"` → incrusta el índice de Scimago dentro del `.exe`.
- `--windowed` → sin ventana de consola.
- `--icon MetaDOI.ico` → icono del ejecutable.
- `--collect-all customtkinter` → incluye los temas/recursos de CustomTkinter.
- Los `--exclude-module` sacan librerías que no se usan (numpy, PIL, cryptography...).

**Distribución:** basta con entregar **`dist/MetaDOI.exe`**. El receptor lo ejecuta y ya;
no necesita más archivos. La app resuelve la base de datos desde dentro del ejecutable
(la extrae a una carpeta temporal al abrir; ver `_resolver_datos()` en `config.py`).

> **Notas del modo `--onefile`:** el arranque tarda unos segundos (se autoextrae a
> `%TEMP%`), algunos antivirus pueden mostrarse recelosos, y **para actualizar Scimago
> hay que reconstruir el `.exe`** con el nuevo `datos/scimago.db`.

> Windows puede mostrar un aviso de *"editor desconocido"* (normal, el `.exe` no está
> firmado digitalmente). Se elige "Más información → Ejecutar de todas formas".

---

## Estructura del proyecto

```
Metadatos-DOI/
├─ actualizar_scimago.py   # descarga Scimago y genera el índice SQLite
├─ nucleo.py               # lógica compartida (Crossref + cuartil)
├─ app_gui.py              # interfaz gráfica (CustomTkinter)
├─ buscar_doi.py           # interfaz de consola
├─ config.py               # configuración central (correo, rutas, reglas)
├─ datos/
│  └─ scimago.db           # índice local: issn, anio, cuartil
├─ requirements.txt        # dependencias (requests, customtkinter)
├─ requirements-dev.txt    # dependencias de build (pyinstaller)
└─ README.md
```

| Archivo | Qué hace |
| --- | --- |
| `config.py` | Configuración: correo de Crossref, rutas, rango de años, reglas y meses. |
| `actualizar_scimago.py` | Descarga Scimago (1999–2025) y genera `datos/scimago.db`. |
| `nucleo.py` | Consulta Crossref y busca el cuartil en el índice. |
| `app_gui.py` | Interfaz gráfica de escritorio. |
| `buscar_doi.py` | Interfaz de consola. |
| `datos/scimago.db` | Índice SQLite con columnas `issn, anio, cuartil`. |

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
No. La salida es en pantalla (o en la ventana de la app), por diseño.

**¿Usa inteligencia artificial?**
No. Son consultas estructuradas (Crossref + Scimago). Sin alucinaciones.

---

## Notas técnicas

- Scimago está detrás de **Cloudflare**; por eso la descarga usa cabeceras de navegador
  reales. Si algún año falla, el script reintenta 3 veces.
- El índice local en SQLite (`WITHOUT ROWID`) evita depender de la web de Scimago en
  cada consulta, es liviano (~24 MB) y hace las búsquedas instantáneas.
