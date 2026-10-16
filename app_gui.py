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

import customtkinter as ctk
import requests

from config import SCIMAGO_DB, VALOR_REVISAR
from nucleo import (
    conectar_indice,
    construir_resultado,
    consultar_crossref,
    limpiar_doi,
)


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
        self.geometry("780x640")
        self.cola = queue.Queue()
        self.consultando = False
        self._construir()

    def _construir(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        ctk.CTkLabel(
            self, text="MetaDOI", font=ctk.CTkFont(size=24, weight="bold")
        ).pack(padx=20, pady=(18, 2), anchor="w")
        ctk.CTkLabel(
            self,
            text="Pega uno o varios DOI (uno por linea) y pulsa Consultar.",
        ).pack(padx=20, pady=(0, 10), anchor="w")

        entrada = ctk.CTkFrame(self)
        entrada.pack(padx=20, pady=5, fill="x")
        self.caja = ctk.CTkTextbox(entrada, height=96)
        self.caja.pack(padx=10, pady=10, fill="x")

        botones = ctk.CTkFrame(self, fg_color="transparent")
        botones.pack(padx=20, pady=5, fill="x")
        self.boton = ctk.CTkButton(botones, text="Consultar", command=self.consultar)
        self.boton.pack(side="left")
        ctk.CTkButton(
            botones,
            text="Limpiar",
            fg_color="gray35",
            hover_color="gray25",
            command=self.limpiar,
        ).pack(side="left", padx=10)

        self.estado = ctk.CTkLabel(self, text="", anchor="w")
        self.estado.pack(padx=20, pady=(4, 0), anchor="w")

        self.resultados = ctk.CTkScrollableFrame(self)
        self.resultados.pack(padx=20, pady=10, fill="both", expand=True)

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
        self.consultando = True
        self.boton.configure(state="disabled")
        self.estado.configure(text="Preparando ...")
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
                    self.estado.configure(text="Consultando %d de %d ..." % (indice, total))
                elif tipo == "tarjeta":
                    self._tarjeta(evento[1])
                elif tipo == "fin":
                    self.consultando = False
                    self.boton.configure(state="normal")
                    self.estado.configure(text="Listo.")
                    return
        except queue.Empty:
            pass

        if self.consultando:
            self.after(120, self._revisar_cola)

    def _tarjeta(self, resultado):
        tarjeta = ctk.CTkFrame(self.resultados)
        tarjeta.pack(fill="x", padx=6, pady=6)
        ctk.CTkLabel(
            tarjeta,
            text=resultado["doi"],
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", padx=14, pady=(10, 4))

        campos = (
            ("Anio", resultado["anio"]),
            ("Fecha de publicacion", resultado["fecha"]),
            ("Revista", resultado["revista"]),
            ("Indexacion", resultado["indexacion"]),
            ("Enlace", resultado["enlace"]),
        )
        for etiqueta, valor in campos:
            ctk.CTkLabel(
                tarjeta, text="%s: %s" % (etiqueta, valor), justify="left", wraplength=680
            ).pack(anchor="w", padx=14)

        if resultado.get("nota"):
            ctk.CTkLabel(
                tarjeta, text="(!) %s" % resultado["nota"], text_color="#e0a030"
            ).pack(anchor="w", padx=14, pady=(2, 4))

        ctk.CTkLabel(tarjeta, text="").pack(pady=2)

    def _vaciar(self):
        for hijo in self.resultados.winfo_children():
            hijo.destroy()

    def limpiar(self):
        self.caja.delete("1.0", "end")
        self._vaciar()
        self.estado.configure(text="")


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
