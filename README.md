# Metadatos-DOI

Herramienta que, a partir de uno o varios **DOI** o **títulos de artículo** (el mejor
match de Crossref), devuelve una lista con los datos bibliográficos de cada publicación:

| Campo | Descripción |
| --- | --- |
| **Titulo** | Título del artículo, libro o capítulo. |
| **Año** | Año de publicación. |
| **Fecha de publicación** | Mes y año (ej. `diciembre 2025`); si Crossref no trae mes, **solo el año**. |
| **Revista** | Nombre de la revista, congreso o libro. |
| **Cuartil** | Cuartil Scimago (`Q1`..`Q4`), `Sin cuartil` o `REVISAR`. |
| **ISSN / ISBN** | Identificadores que Crossref asocia a la obra. |
| **Enlace** | URL del editor (o `https://doi.org/<doi>` si no hay otra). |

Se puede buscar por:

- **DOI** → datos del artículo y su cuartil.
- **Título del artículo** → Crossref devuelve la mejor coincidencia y de ahí se toma el DOI.

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
              DOI o título         API de Crossref              Índice Scimago local
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
2. **`nucleo.py`** resuelve la consulta: si es un DOI, va directo a Crossref; si es un
   título, Crossref devuelve el mejor match (`query.title`, solo la mejor coincidencia)
   y de ahí se toma el DOI. Después cruza ISSN + año contra el índice local
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

Pega uno o varios DOI o títulos de artículo (uno por línea) en la caja de texto y pulsa
**Consultar**. Los resultados aparecen en tarjetas, cada una con su barra lateral
(verde si obtuvo cuartil, roja si no) y un botón **copiar** junto a cada campo
(más **Abrir** en el enlace).

**Consola:**

```
python buscar_doi.py
```

Pega **uno o varios DOI o títulos** y pulsa **ENTER en vacío** para terminar:

```
Pega uno o varios DOI o titulos de articulo, uno por linea.
ENTER en vacio para terminar.

> 10.3390/s26144610
> Women's empowerment in tourism: a bibliometric approach
>
```

Salida:

```
------------------------------------------------------------
DOI: 10.3390/s26144610
  Titulo:               LLM-Mediated Smart Tele-Primary Care for Rural Older Adults
  Revista:              Sensors
  Anio:                 2026
  Fecha de publicacion: julio 2026
  Cuartil:              Q1 (2025)
  ISSN:                 1424-8220
  Enlace:               https://www.mdpi.com/1424-8220/26/14/4610
------------------------------------------------------------
```

> **Tip:** puedes pegar los identificadores en cualquier formato; el programa limpia
> los prefijos `https://doi.org/...` y `doi:` automáticamente. Si en una línea pones
> **varios DOI**, los parte en varios; si no, la línea completa se trata como un título.
> Puedes mezclar DOI y títulos en la misma consulta.
>
> **Fecha:** Crossref trae mes en `published-print`, `published-online` o `issued`.
> Si ninguno tiene mes, se muestra **solo el año** (no se inventa fecha).

---

## Reglas de indexación (cuartil)

La búsqueda del cuartil es **escalonada**:

1. **ISSN + año exacto.** Se prueba cada ISSN de la obra (revista, serie o libro).
2. **ISSN + año más cercano.** Si no hay cuartil en el año exacto, se usa el año más
   cercano de esa revista, con preferencia por el más reciente **≤ año de publicación**.
   Solo se permite hasta **3 años de diferencia** (`MAX_GAP_ANIOS`). Cuando el año del
   cuartil no coincide, se anota entre paréntesis: **`Q1 (2025)`**.
   - Esto cubre el **rezago de Scimago**, que publica sus datos con ~1 año de retraso
     (p. ej. un artículo de 2026 usa el cuartil de 2025).
3. **Sin coincidencia:** si la obra es de un tipo que Scimago no cubre (libros,
   reportes, etc.) se marca **`Sin cuartil`**; en los demás casos, **`REVISAR`**.

Caso especial:

| Situación | Resultado |
| --- | --- |
| Artículo de revista o congreso con cuartil | `Q1` / `Q2` / `Q3` / `Q4` |
| Cuartil de otro año (rezago de Scimago) | `Q1 (2025)` |
| **Libro o capítulo** con ISSN de serie indexada | `Q1` .. `Q4` |
| **Libro o capítulo** sin ISSN indexado en Scimago | `Sin cuartil` |
| Revista no indexada en Scimago (artículo/congreso) | `REVISAR` |
| Artículo **sin ISSN** (típico en algunos congresos) | `REVISAR` |
| Dato más antiguo que el límite de 3 años | `REVISAR` |
| DOI **inexistente** en Crossref | `REVISAR` |
| Título sin resultados en Crossref | `REVISAR` |

> **Nota:** Scimago solo cubre revistas y algunas memorias de congreso. Muchos papers
> de congreso de IEEE (tipo `proceedings-article`) **no están indexados** en Scimago y
> no tienen ISSN, por lo que aparecerán como `REVISAR`. Eso es correcto: Scimago no
> tiene ese dato. Para los **libros**, Crossref suele asociar un ISSN de la serie; si
> ese ISSN está en Scimago, el libro **sí** recibe cuartil.

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
| `VALOR_SIN_CUARTIL` / `VALOR_REVISAR` | Marcadores `Sin cuartil` y `REVISAR`. |
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

---

## Historial de mejoras

### Búsqueda por DOI o por título (versión actual)

Antes solo se podía buscar por DOI. Ahora también por **título del artículo**, y de
paso salen **más datos** por cada obra.

**Qué se intentó implementar (y qué pasó):**

| Intento | Resultado | Decisión |
| --- | --- | --- |
| Buscar por **ISSN** | Crossref devolvía la **revista**, no un artículo; el campo `title` de `/journals/{issn}` viene como **texto** (no lista) y mostraba solo la primera letra. | **Se eliminó** la búsqueda por ISSN. |
| Buscar por **ISBN** | Crossref devolvía 20 resultados arbitrarios; el primero solía ser un **capítulo**, no el libro real. | **Se eliminó** la búsqueda por ISBN. |
| Buscar por **título** con `query.bibliographic` | El artículo correcto **no aparecía** ni en el top 5. | Se cambió a **`query.title`** con `rows=1`. |
| Buscar por **título** con `query.title` | Devuelve el artículo correcto como **primera** coincidencia. | **Se adoptó.** |
| Fecha sin mes | Crossref a veces no trae mes (solo el año, p. ej. `2024`). | Si no hay mes, se muestra **solo el año** (no se inventa). |

**Problemas encontrados y corregidos:**

- Un bug en `primer_texto` hacía que el nombre de la revista saliera como **"S"**
  (porque `container-title` es una **lista** y se estaba indexando mal). Se corrigió.
- El parser de la caja de texto separaba por espacios, lo que **rompía los títulos**.
  Se reemplazó por un parser **por líneas**: una línea = un DOI o un título. Si en una
  línea hay **varios DOI**, se parten; si no, la línea entera se trata como título.
- Si el título consultado **no existe**, Crossref igual devuelve algo poco parecido.
  Se agregó un aviso automático: **`Coincidencia debil: ... Verifica que sea el articulo correcto`**
  (comparación de similitud con `difflib`, umbral `UMBRAL_SIMILITUD_TITULO = 0.55`).

**Mejoras que quedaron (lo nuevo):**

- **Búsqueda por título**: pegas el nombre del artículo y la app resuelve el DOI y sus datos.
- **Más datos por tarjeta**: `Titulo`, `Revista`, `Año`, `Fecha`, `Cuartil`, `ISSN`, `ISBN` y `Enlace`.
- **Aviso de coincidencia débil** cuando el título no se parece al resultado de Crossref.
- **Regla de fecha honesta**: mes y año si existe; **solo año** si Crossref no trae mes.
- Etiqueta **`Cuartil:`** (antes `Indexacion:`) y valores **`Sin cuartil`** / **`REVISAR`**.
- Cada tarjeta tiene **barra lateral** verde (obtuvo cuartil) o roja (no lo obtuvo),
  y un botón **copiar** individual por cada campo (y **Abrir** en el enlace).

---

## Estructura de salida del build

Al construir con PyInstaller se genera:

```
dist/
└─ MetaDOI.exe        # un solo archivo (~20 MB), sin instalar Python
```

Basta con entregar **`dist/MetaDOI.exe`**: la base de Scimago viaja embebida dentro del
ejecutable y no requiere archivos externos.
