# -*- coding: utf-8 -*-
"""
app_gui.py
==========
Interfaz de escritorio del proyecto MetaDOI (CustomTkinter).

Pegas uno o varios DOI o titulos de articulo (uno por linea), pulsas "Consultar" y
la app devuelve titulo, revista, anio, fecha, cuartil, ISSN/ISBN y enlace.

Las consultas a Crossref corren en un hilo aparte para no congelar la ventana.
"""

import queue
import threading
import webbrowser

import customtkinter as ctk
import requests

from config import BASE_DIR, SCIMAGO_DB, VALOR_REVISAR
from nucleo import (
    conectar_indice,
    detectar_tipo,
    parsear_entradas,
    resolver_entrada,
)

# Colores de la barra vertical de cada tarjeta.
COLOR_OK = "#1f8f4e"    # se obtuvo el cuartil (Q1..Q4)
COLOR_NO = "#c0392b"    # no se obtuvo el cuartil (Sin cuartil / REVISAR)

# Prefijo que encabeza cada tarjeta segun lo que se busco.
PREFIJO = {"doi": "DOI", "titulo": "Consulta"}

# Paleta general.
GRIS_TEXTO = "#9aa0a6"
AZUL_ENLACE = "#6ea8fe"
AMBAR_NOTA = "#e0a030"


def resultado_revisar(entrada, nota=None):
    """Resultado vacio para una entrada que no se pudo resolver."""
    es_doi = detectar_tipo(entrada) == "doi"
    datos = {
        "tipo": "doi" if es_doi else "titulo",
        "identificador": entrada,
        "titulo": VALOR_REVISAR,
        "anio": VALOR_REVISAR,
        "fecha": VALOR_REVISAR,
        "revista": VALOR_REVISAR,
        "indexacion": VALOR_REVISAR,
        "issn": "",
        "isbn": "",
        "enlace": "https://doi.org/%s" % entrada if es_doi else "",
        "tiene_cuartil": False,
    }
    if nota:
        datos["nota"] = nota
    return datos


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("MetaDOI")
        self.minsize(720, 560)
        self.cola = queue.Queue()
        self.consultando = False
        self.ultimos = []
        self._centrar(820, 700)
        self._poner_icono()
        self._construir()

    def _centrar(self, ancho, alto):
        self.update_idletasks()
        x = max(0, (self.winfo_screenwidth() - ancho) // 2)
        y = max(0, (self.winfo_screenheight() - alto) // 3)
        self.geometry("%dx%d+%d+%d" % (ancho, alto, x, y))

    def _poner_icono(self):
        ruta = BASE_DIR / "MetaDOI.ico"
        if ruta.exists():
            try:
                self.iconbitmap(str(ruta))
            except Exception:
                pass

    def _construir(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Encabezado.
        cabecera = ctk.CTkFrame(self, fg_color="transparent")
        cabecera.pack(padx=24, pady=(18, 4), fill="x")
        ctk.CTkLabel(
            cabecera, text="MetaDOI", font=ctk.CTkFont(size=28, weight="bold")
        ).pack(side="left")
        ctk.CTkLabel(
            cabecera,
            text="metadatos + cuartil Scimago a partir de DOI o titulo",
            text_color=GRIS_TEXTO,
        ).pack(side="left", padx=12, pady=(10, 0))

        # Panel de entrada.
        panel = ctk.CTkFrame(self, corner_radius=12)
        panel.pack(padx=24, pady=8, fill="x")
        ctk.CTkLabel(
            panel, text="Pega uno o varios DOI o titulos de articulo (uno por linea):", anchor="w"
        ).pack(padx=16, pady=(14, 4), anchor="w")
        self.caja = ctk.CTkTextbox(panel, height=84, corner_radius=8)
        self.caja.pack(padx=16, pady=(0, 12), fill="x")

        botones = ctk.CTkFrame(panel, fg_color="transparent")
        botones.pack(padx=16, pady=(0, 14), fill="x")
        self.boton = ctk.CTkButton(
            botones, text="Consultar", width=130, height=34, command=self.consultar
        )
        self.boton.pack(side="left")
        ctk.CTkButton(
            botones,
            text="Limpiar",
            width=90,
            height=34,
            fg_color="gray35",
            hover_color="gray25",
            command=self.limpiar,
        ).pack(side="left", padx=8)
        self.boton_copiar = ctk.CTkButton(
            botones,
            text="Copiar resultados",
            width=150,
            height=34,
            fg_color="gray35",
            hover_color="gray25",
            state="disabled",
            command=self.copiar,
        )
        self.boton_copiar.pack(side="right")

        # Barra de progreso y estado.
        self.progreso = ctk.CTkProgressBar(self, height=6, corner_radius=3)
        self.progreso.set(0)
        self.progreso.pack(padx=24, pady=(4, 0), fill="x")

        self.estado = ctk.CTkLabel(self, text="", anchor="w", text_color=GRIS_TEXTO)
        self.estado.pack(padx=24, pady=(6, 0), anchor="w")

        # Resultados.
        self.resultados = ctk.CTkScrollableFrame(self, corner_radius=12)
        self.resultados.pack(padx=24, pady=(6, 18), fill="both", expand=True)
        self._mensaje_vacio("Aun no hay resultados.")

    def _mensaje_vacio(self, texto):
        ctk.CTkLabel(
            self.resultados, text=texto, text_color=GRIS_TEXTO
        ).pack(pady=30)

    def consultar(self):
        if self.consultando:
            return

        identificadores = parsear_entradas(self.caja.get("1.0", "end"))
        if not identificadores:
            self.estado.configure(text="No ingresaste ningun DOI ni titulo.")
            return
        if not SCIMAGO_DB.exists():
            self.estado.configure(
                text="Falta datos/scimago.db. Ejecuta: python actualizar_scimago.py"
            )
            return

        self._vaciar()
        self.ultimos = []
        self.consultando = True
        self.boton.configure(state="disabled")
        self.boton_copiar.configure(state="disabled")
        self.progreso.set(0)
        self.estado.configure(text="Consultando 0 de %d ..." % len(identificadores))
        threading.Thread(target=self._trabajar, args=(identificadores,), daemon=True).start()
        self.after(120, self._revisar_cola)

    def _trabajar(self, identificadores):
        """Resuelve cada DOI o titulo en un hilo aparte; manda eventos a la cola."""
        conexion = conectar_indice()
        try:
            for indice, entrada in enumerate(identificadores, 1):
                self.cola.put(("progreso", indice, len(identificadores)))
                try:
                    resultado = resolver_entrada(entrada, conexion)
                    self.cola.put(("tarjeta", resultado))
                except LookupError as error:
                    self.cola.put(("tarjeta", resultado_revisar(entrada, str(error))))
                except requests.RequestException as error:
                    self.cola.put(
                        ("tarjeta", resultado_revisar(entrada, "Error de red: %s" % error))
                    )
        finally:
            conexion.close()
            self.cola.put(("fin",))

    def _revisar_cola(self):
        try:
            while True:
                evento = self.cola.get_nowait()
                tipo = evento[0]
                if tipo == "progreso":
                    _, indice, total = evento
                    self.progreso.set(indice / total)
                    self.estado.configure(text="Consultando %d de %d ..." % (indice, total))
                elif tipo == "tarjeta":
                    self._tarjeta(evento[1])
                elif tipo == "fin":
                    self.consultando = False
                    self.boton.configure(state="normal")
                    self.progreso.set(1)
                    if self.ultimos:
                        self.boton_copiar.configure(state="normal")
                    self.estado.configure(text="Listo: %d resultado(s)." % len(self.ultimos))
                    return
        except queue.Empty:
            pass

        if self.consultando:
            self.after(120, self._revisar_cola)

    def _tarjeta(self, resultado):
        self.ultimos.append(resultado)

        tarjeta = ctk.CTkFrame(self.resultados, corner_radius=12)
        tarjeta.pack(fill="x", padx=6, pady=6)
        tarjeta.columnconfigure(0, weight=0)
        tarjeta.columnconfigure(1, weight=1)

        # Barra vertical de estado a la izquierda: verde si hay cuartil, rojo si no.
        color_barra = COLOR_OK if resultado.get("tiene_cuartil") else COLOR_NO
        ctk.CTkFrame(tarjeta, fg_color=color_barra, corner_radius=6, width=8).grid(
            row=0, column=0, sticky="ns", padx=(6, 0), pady=8
        )

        # Contenido de la tarjeta.
        contenido = ctk.CTkFrame(tarjeta, fg_color="transparent")
        contenido.grid(row=0, column=1, sticky="nsew", padx=(10, 14), pady=(12, 12))
        contenido.columnconfigure(0, weight=0)
        contenido.columnconfigure(1, weight=1)
        contenido.columnconfigure(2, weight=0)

        # Encabezado: tipo + identificador.
        prefijo = PREFIJO.get(resultado.get("tipo"), "DOI")
        ctk.CTkLabel(
            contenido,
            text="%s: %s" % (prefijo, resultado.get("identificador", "")),
            font=ctk.CTkFont(size=15, weight="bold"),
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))

        # Campos alineados, cada uno con su boton "copiar".
        filas = [
            ("Titulo", resultado.get("titulo") or VALOR_REVISAR),
            ("Revista", resultado.get("revista") or VALOR_REVISAR),
            ("Anio", resultado.get("anio") or VALOR_REVISAR),
            ("Fecha", resultado.get("fecha") or VALOR_REVISAR),
            ("Cuartil", resultado.get("indexacion") or VALOR_REVISAR),
        ]
        if resultado.get("issn"):
            filas.append(("ISSN", resultado["issn"]))
        if resultado.get("isbn"):
            filas.append(("ISBN", resultado["isbn"]))

        for i, (nombre, valor) in enumerate(filas, start=1):
            ctk.CTkLabel(
                contenido, text=nombre, text_color=GRIS_TEXTO, width=64, anchor="w"
            ).grid(row=i, column=0, sticky="w", pady=1)
            extra = {}
            if nombre == "Cuartil":
                extra = {
                    "text_color": COLOR_OK if resultado.get("tiene_cuartil") else COLOR_NO,
                    "font": ctk.CTkFont(size=13, weight="bold"),
                }
            ctk.CTkLabel(
                contenido, text=valor, anchor="w", justify="left", wraplength=440, **extra
            ).grid(row=i, column=1, sticky="w", pady=1)
            self._boton_copiar(contenido, valor).grid(
                row=i, column=2, sticky="w", padx=(8, 0), pady=1
            )

        # Enlace: valor + copiar + Abrir.
        fila_enlace = len(filas) + 1
        ctk.CTkLabel(
            contenido, text="Enlace", text_color=GRIS_TEXTO, width=64, anchor="w"
        ).grid(row=fila_enlace, column=0, sticky="w", pady=1)
        enlace = resultado.get("enlace") or ""
        ctk.CTkLabel(
            contenido,
            text=enlace or VALOR_REVISAR,
            text_color=AZUL_ENLACE if enlace else GRIS_TEXTO,
            anchor="w",
            justify="left",
            wraplength=380,
        ).grid(row=fila_enlace, column=1, sticky="w", pady=1)
        acciones = ctk.CTkFrame(contenido, fg_color="transparent")
        acciones.grid(row=fila_enlace, column=2, sticky="w", padx=(8, 0), pady=1)
        if enlace:
            self._boton_copiar(acciones, enlace).pack(side="left")
            ctk.CTkButton(
                acciones,
                text="Abrir",
                width=52,
                height=20,
                command=lambda u=enlace: webbrowser.open(u),
            ).pack(side="left", padx=(6, 0))

        if resultado.get("nota"):
            ctk.CTkLabel(
                contenido,
                text="(!) %s" % resultado["nota"],
                text_color=AMBAR_NOTA,
                anchor="w",
                wraplength=520,
            ).grid(row=fila_enlace + 1, column=0, columnspan=3, sticky="w", pady=(6, 0))

    def _boton_copiar(self, padre, valor):
        """Boton pequeno que copia un solo dato al portapapeles."""
        return ctk.CTkButton(
            padre,
            text="copiar",
            width=52,
            height=20,
            fg_color="gray35",
            hover_color="gray25",
            command=lambda v=valor: self._copiar_dato(v),
        )

    def _copiar_dato(self, valor):
        self.clipboard_clear()
        self.clipboard_append(valor)
        self.estado.configure(text="Dato copiado al portapapeles.")

    def _vaciar(self):
        for hijo in self.resultados.winfo_children():
            hijo.destroy()

    def copiar(self):
        lineas = []
        for r in self.ultimos:
            prefijo = PREFIJO.get(r.get("tipo"), "DOI")
            lineas.append("%s: %s" % (prefijo, r.get("identificador")))
            lineas.append("  Titulo: %s" % r.get("titulo"))
            lineas.append("  Revista: %s" % r.get("revista"))
            lineas.append("  Anio: %s" % r.get("anio"))
            lineas.append("  Fecha de publicacion: %s" % r.get("fecha"))
            lineas.append("  Cuartil: %s" % r.get("indexacion"))
            if r.get("issn"):
                lineas.append("  ISSN: %s" % r["issn"])
            if r.get("isbn"):
                lineas.append("  ISBN: %s" % r["isbn"])
            lineas.append("  Enlace: %s" % r.get("enlace"))
            lineas.append("")
        self.clipboard_clear()
        self.clipboard_append("\n".join(lineas))
        self.estado.configure(text="Resultados copiados al portapapeles.")

    def limpiar(self):
        self.caja.delete("1.0", "end")
        self._vaciar()
        self._mensaje_vacio("Aun no hay resultados.")
        self.ultimos = []
        self.progreso.set(0)
        self.boton_copiar.configure(state="disabled")
        self.estado.configure(text="")


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
