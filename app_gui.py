# -*- coding: utf-8 -*-
"""
app_gui.py
==========
Interfaz de escritorio del proyecto MetaDOI (CustomTkinter).

Pegas uno o varios DOI, pulsas "Consultar" y la app devuelve anio, fecha,
revista, indexacion y enlace de cada publicacion.

Las consultas a Crossref corren en un hilo aparte para no congelar la ventana.
"""

import queue
import re
import threading
import webbrowser

import customtkinter as ctk
import requests

from config import BASE_DIR, SCIMAGO_DB, VALOR_REVISAR
from nucleo import (
    conectar_indice,
    construir_resultado,
    consultar_crossref,
    limpiar_doi,
)

# Colores del badge de indexacion, uno por cuartil.
COLORES_INDEXACION = {
    "Q1": "#1f8f4e",
    "Q2": "#2f7ed8",
    "Q3": "#c99a1c",
    "Q4": "#cc6a2f",
}
COLOR_INDEXACION_OTRO = "#5a5f66"  # "otro" / "REVISAR"

# Paleta general.
GRIS_TEXTO = "#9aa0a6"
AZUL_ENLACE = "#6ea8fe"
AMBAR_NOTA = "#e0a030"


def parsear_dois(texto):
    """Separa y limpia los DOI escritos en la caja de texto."""
    dois = []
    for token in re.split(r"[\s,;]+", texto):
        doi = limpiar_doi(token)
        if doi and doi not in dois:
            dois.append(doi)
    return dois


def resultado_revisar(doi, nota=None):
    """Resultado vacio para un DOI que no se pudo resolver."""
    datos = {
        "doi": doi,
        "anio": VALOR_REVISAR,
        "fecha": VALOR_REVISAR,
        "revista": VALOR_REVISAR,
        "indexacion": VALOR_REVISAR,
        "enlace": "https://doi.org/%s" % doi,
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
            text="metadatos + cuartil Scimago a partir de DOI",
            text_color=GRIS_TEXTO,
        ).pack(side="left", padx=12, pady=(10, 0))

        # Panel de entrada.
        panel = ctk.CTkFrame(self, corner_radius=12)
        panel.pack(padx=24, pady=8, fill="x")
        ctk.CTkLabel(
            panel, text="Pega uno o varios DOI (uno por linea):", anchor="w"
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

        dois = parsear_dois(self.caja.get("1.0", "end"))
        if not dois:
            self.estado.configure(text="No ingresaste ningun DOI.")
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
        self.estado.configure(text="Consultando 0 de %d ..." % len(dois))
        threading.Thread(target=self._trabajar, args=(dois,), daemon=True).start()
        self.after(120, self._revisar_cola)

    def _trabajar(self, dois):
        """Consulta Crossref en un hilo aparte; manda eventos a la cola."""
        conexion = conectar_indice()
        try:
            for indice, doi in enumerate(dois, 1):
                self.cola.put(("progreso", indice, len(dois)))
                try:
                    mensaje = consultar_crossref(doi)
                    self.cola.put(("tarjeta", construir_resultado(doi, mensaje, conexion)))
                except LookupError as error:
                    self.cola.put(("tarjeta", resultado_revisar(doi, str(error))))
                except requests.RequestException as error:
                    self.cola.put(("tarjeta", resultado_revisar(doi, "Error de red: %s" % error)))
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

    def _badge(self, padre, indexacion):
        """Etiqueta de color segun el cuartil (Q1..Q4) o gris para otro/REVISAR."""
        base = indexacion.split(" ")[0] if indexacion else ""
        color = COLORES_INDEXACION.get(base, COLOR_INDEXACION_OTRO)
        marco = ctk.CTkFrame(padre, fg_color=color, corner_radius=8)
        ctk.CTkLabel(
            marco,
            text=indexacion,
            text_color="white",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(padx=10, pady=3)
        return marco

    def _tarjeta(self, resultado):
        self.ultimos.append(resultado)

        tarjeta = ctk.CTkFrame(self.resultados, corner_radius=12)
        tarjeta.pack(fill="x", padx=6, pady=6)
        tarjeta.columnconfigure(0, weight=1)

        # Fila superior: DOI + badge.
        cab = ctk.CTkFrame(tarjeta, fg_color="transparent")
        cab.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 6))
        cab.columnconfigure(0, weight=1)
        ctk.CTkLabel(
            cab, text=resultado["doi"], font=ctk.CTkFont(size=15, weight="bold")
        ).grid(row=0, column=0, sticky="w")
        self._badge(cab, resultado["indexacion"]).grid(row=0, column=1, sticky="e")

        # Campos alineados.
        campos = ctk.CTkFrame(tarjeta, fg_color="transparent")
        campos.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))
        campos.columnconfigure(1, weight=1)
        filas = (
            ("Anio", resultado["anio"]),
            ("Fecha", resultado["fecha"]),
            ("Revista", resultado["revista"]),
        )
        for i, (nombre, valor) in enumerate(filas):
            ctk.CTkLabel(
                campos, text=nombre, text_color=GRIS_TEXTO, width=64, anchor="w"
            ).grid(row=i, column=0, sticky="w", pady=1)
            ctk.CTkLabel(
                campos, text=valor, anchor="w", justify="left", wraplength=560
            ).grid(row=i, column=1, sticky="w", pady=1)

        # Enlace + boton Abrir.
        fila_enlace = ctk.CTkFrame(tarjeta, fg_color="transparent")
        fila_enlace.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 6))
        ctk.CTkLabel(
            fila_enlace, text="Enlace", text_color=GRIS_TEXTO, width=64, anchor="w"
        ).pack(side="left")
        ctk.CTkButton(
            fila_enlace,
            text="Abrir",
            width=64,
            height=26,
            command=lambda u=resultado["enlace"]: webbrowser.open(u),
        ).pack(side="right")
        ctk.CTkLabel(
            fila_enlace,
            text=resultado["enlace"],
            text_color=AZUL_ENLACE,
            anchor="w",
            justify="left",
            wraplength=460,
        ).pack(side="left", padx=(0, 8))

        if resultado.get("nota"):
            ctk.CTkLabel(
                tarjeta,
                text="(!) %s" % resultado["nota"],
                text_color=AMBAR_NOTA,
                anchor="w",
                wraplength=600,
            ).grid(row=3, column=0, sticky="w", padx=16, pady=(0, 10))

    def _vaciar(self):
        for hijo in self.resultados.winfo_children():
            hijo.destroy()

    def copiar(self):
        lineas = []
        for r in self.ultimos:
            lineas.append("DOI: %s" % r["doi"])
            lineas.append("  Anio: %s" % r["anio"])
            lineas.append("  Fecha de publicacion: %s" % r["fecha"])
            lineas.append("  Revista: %s" % r["revista"])
            lineas.append("  Indexacion: %s" % r["indexacion"])
            lineas.append("  Enlace: %s" % r["enlace"])
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
