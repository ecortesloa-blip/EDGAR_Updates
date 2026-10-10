import time



import os

import re

import json

import threading

import subprocess
import webbrowser

import shutil

import requests
from pathlib import Path

from tkinter import filedialog, messagebox



import customtkinter as ctk

import numpy as np

import sounddevice as sd

import speech_recognition as sr



from dotenv import load_dotenv

from google import genai

from docx import Document

from pptx import Presentation



# ==========================================

# EDGAR V18 - PEPE CON VOZ Y MEMORIA

# ==========================================



BASE = Path.home()

load_dotenv(BASE / ".env")

load_dotenv()



API_KEY = os.getenv("GEMINI_API_KEY", "").strip()



MODELOS = [

    "gemini-3-flash-preview",

    "gemini-3.6-flash"

]



CARPETA = BASE / "EDGAR"

CARPETA.mkdir(parents=True, exist_ok=True)

ARCHIVO_MEMORIA = CARPETA / "memoria_pepe.json"



ctk.set_appearance_mode("dark")

ctk.set_default_color_theme("blue")





# ==========================================

# MEMORIA

# ==========================================



def cargar_memoria():

    if ARCHIVO_MEMORIA.exists():

        try:

            datos = json.loads(

                ARCHIVO_MEMORIA.read_text(encoding="utf-8")

            )

            if isinstance(datos, list):

                return datos

        except Exception as error:

            print("Error de memoria:", error)

    return []





def guardar_memoria(historial):

    temporal = ARCHIVO_MEMORIA.with_suffix(".tmp")

    temporal.write_text(

        json.dumps(historial, ensure_ascii=False, indent=2),

        encoding="utf-8"

    )

    temporal.replace(ARCHIVO_MEMORIA)





# ==========================================

# INTELIGENCIA ARTIFICIAL

# ==========================================



# Control de cuota para no repetir solicitudes inútiles durante un bloqueo.
GEMINI_PAUSA_HASTA = 0.0


def consultar_gemini(mensajes, instruccion):
    global GEMINI_PAUSA_HASTA
    if not API_KEY:
        raise ValueError("Falta GEMINI_API_KEY en tu archivo .env")
    if time.monotonic() < GEMINI_PAUSA_HASTA:
        raise RuntimeError("Gemini alcanzó su límite temporal. Los comandos de tu Mac siguen disponibles; prueba el chat más tarde.")

    contenido = instruccion + "\n\n"
    for mensaje in mensajes[-24:]:
        rol = "Estudiante" if mensaje["rol"] == "usuario" else "Pepe"
        contenido += rol + ": " + mensaje["texto"] + "\n"

    try:
        cliente = genai.Client(api_key=API_KEY)
        for modelo in MODELOS:
            try:
                respuesta = cliente.models.generate_content(model=modelo, contents=contenido)
                if respuesta.text:
                    return respuesta.text
            except Exception as error:
                detalle = str(error).lower()
                if any(x in detalle for x in ("429", "resource_exhausted", "quota exceeded", "quota_exceeded")):
                    GEMINI_PAUSA_HASTA = time.monotonic() + 90
                    raise RuntimeError("Gemini agotó su cuota gratuita por ahora. Pepe todavía puede usar los comandos locales. Intenta conversar más tarde.") from None
                if any(x in detalle for x in ("503", "unavailable", "overloaded")):
                    continue
                if any(x in detalle for x in ("401", "403", "api key", "permission_denied")):
                    raise RuntimeError("Gemini rechazó la conexión. Revisa la configuración de la clave API en tu Mac.") from None
                print("[EDGAR] Fallo del modelo:", type(error).__name__)
        raise RuntimeError("Gemini está ocupado o no respondió. Los comandos locales siguen funcionando; intenta el chat después.")
    finally:
        try:
            cliente.close()
        except Exception:
            pass



# ==========================================

# APLICACIÓN

# ==========================================



class EdgarApp(ctk.CTk):


    def comprobar_actualizaciones(self):
        def revisar():
            try:
                url = "https://raw.githubusercontent.com/ecortesloa-blip/EDGAR_Updates/main/version.json"

                respuesta = requests.get(url, timeout=10)
                respuesta.raise_for_status()

                datos = respuesta.json()
                nueva_version = datos.get("version", "")

                if nueva_version and nueva_version != self.version_actual:
                    self.after(
                        0,
                        lambda version=nueva_version: self.mostrar_aviso_actualizacion(version)
                    )
                else:
                    print("EDGAR está actualizado.")

            except Exception as error:
                print("No se pudieron comprobar actualizaciones:", error)

        threading.Thread(target=revisar, daemon=True).start()

    def mostrar_aviso_actualizacion(self, nueva_version):
        ventana = ctk.CTkToplevel(self)
        ventana.title("Actualización de EDGAR")
        ventana.geometry("420x310")
        ventana.transient(self)
        ventana.grab_set()

        ctk.CTkLabel(
            ventana,
            text="Nueva versión disponible",
            font=("Arial", 20, "bold")
        ).pack(pady=20)

        ctk.CTkLabel(
            ventana,
            text=(
                f"Versión instalada: {self.version_actual}\n"
                f"Versión disponible: {nueva_version}"
            )
        ).pack(pady=10)

        barra = ctk.CTkProgressBar(ventana, width=330)
        barra.set(0)
        barra.pack(pady=15)

        estado = ctk.CTkLabel(
            ventana,
            text="Listo para actualizar"
        )
        estado.pack(pady=5)

        def actualizar():
            import subprocess
            import sys
            from pathlib import Path

            actualizador = (
                Path(__file__).resolve().parent
                / "actualizador_edgar.py"
            )

            if not actualizador.exists():
                estado.configure(text="No se encontró el actualizador.")
                return

            estado.configure(text="Iniciando actualización...")
            boton.configure(state="disabled")

            try:
                subprocess.Popen([
                    sys.executable,
                    str(actualizador)
                ])
                estado.configure(text="Actualizador iniciado.")
                ventana.after(1500, ventana.destroy)
            except Exception as error:
                estado.configure(text=f"Error: {error}")
                boton.configure(state="normal")

        boton = ctk.CTkButton(
            ventana,
            text="Actualizar ahora",
            command=actualizar
        )
        boton.pack(pady=15)
    def __init__(self):

        super().__init__()



        self.title("EDGAR V31 - Tu asistente inteligente")
        self.version_actual = "32.0"
        self.comprobar_actualizaciones()
        self.geometry("1050x780")
        self.minsize(800, 600)


        self.historial = cargar_memoria()

        self.texto_generado = ""

        self.ocupado = False

        self.escuchando = False

        self.conversacion_continua = False

        self.sesion_voz = 0

        self.voz_activada = True

        self.proceso_voz = None

        self.pantalla_actual = ""

        self.cerrando = False
        self.activacion_voz = False
        self.generacion_activacion = 0
        self.hilo_activacion = False



        self.contenedor = ctk.CTkFrame(

            self, fg_color="transparent"

        )

        self.contenedor.pack(

            fill="both", expand=True, padx=22, pady=20

        )



        self.protocol("WM_DELETE_WINDOW", self.cerrar)

        self.chat_pepe()
        self.after(900, self.activar_automaticamente)



    def cerrar(self):

        self.cerrando = True
        self.activacion_voz = False
        self.generacion_activacion += 1

        self.conversacion_continua = False

        self.sesion_voz += 1

        self.detener_voz()

        guardar_memoria(self.historial)

        self.destroy()



    def limpiar(self):

        self.conversacion_continua = False

        self.sesion_voz += 1

        self.detener_voz()

        for widget in self.contenedor.winfo_children():

            widget.destroy()



    def ejecutar(self, funcion):

        threading.Thread(

            target=funcion, daemon=True

        ).start()



    def actualizar(self, funcion):

        if not self.cerrando:

            try:

                self.after(0, funcion)

            except RuntimeError:

                pass



    def encabezado(self, titulo):

        fila = ctk.CTkFrame(

            self.contenedor, fg_color="transparent"

        )

        fila.pack(fill="x", pady=(0, 15))



        ctk.CTkButton(

            fila, text="← Inicio", width=110,

            command=self.inicio

        ).pack(side="left", padx=(0, 20))



        ctk.CTkLabel(

            fila, text=titulo,

            font=("Arial", 28, "bold")

        ).pack(side="left")



    # ======================================

    # INICIO

    # ======================================



    def inicio(self):
        self.pantalla_actual = "inicio"
        self.limpiar()

        fondo = ctk.CTkFrame(
            self.contenedor,
            fg_color="#101827",
            corner_radius=18
        )
        fondo.pack(fill="both", expand=True)

        # CABECERA
        cabecera = ctk.CTkFrame(
            fondo, fg_color="transparent"
        )
        cabecera.pack(fill="x", padx=28, pady=(24, 16))

        marca = ctk.CTkFrame(
            cabecera, fg_color="transparent"
        )
        marca.pack(side="left")

        ctk.CTkLabel(
            marca,
            text="EDGAR",
            font=("Arial", 32, "bold"),
            text_color="#FFFFFF"
        ).pack(anchor="w")

        ctk.CTkLabel(
            marca,
            text="Tu asistente académico inteligente",
            font=("Arial", 13),
            text_color="#94A3B8"
        ).pack(anchor="w")

        # AVISO DE ACTUALIZACIONES
        self.zona_actualizacion = ctk.CTkFrame(
            cabecera, fg_color="transparent"
        )
        self.zona_actualizacion.pack(side="right")

        # BIENVENIDA
        ctk.CTkLabel(
            fondo,
            text="Bienvenido a EDGAR",
            font=("Arial", 26, "bold"),
            text_color="#FFFFFF"
        ).pack(anchor="w", padx=30, pady=(12, 0))

        ctk.CTkLabel(
            fondo,
            text="¿Qué vamos a hacer hoy?",
            font=("Arial", 14),
            text_color="#94A3B8"
        ).pack(anchor="w", padx=30, pady=(5, 20))

        # SECCIONES
        opciones = [
            (
                "✦",
                "Chat con Pepe",
                "Conversa usando texto o voz.",
                self.chat_pepe
            ),
            (
                "▤",
                "Analizar",
                "Analiza tareas y crea documentos.",
                self.analizar
            ),
            (
                "▣",
                "Temarios",
                "Genera guías de estudio con Gemini.",
                self.temarios
            ),
            (
                "▦",
                "Calendario",
                "Organiza tus actividades escolares.",
                self.calendario
            )
        ]

        cuadricula = ctk.CTkFrame(
            fondo, fg_color="transparent"
        )
        cuadricula.pack(
            fill="both",
            expand=True,
            padx=25,
            pady=(0, 18)
        )

        cuadricula.grid_columnconfigure(
            (0, 1),
            weight=1,
            uniform="tarjetas"
        )
        cuadricula.grid_rowconfigure(
            (0, 1),
            weight=1
        )

        for indice, (icono, titulo, descripcion, funcion) in enumerate(opciones):
            fila, columna = divmod(indice, 2)

            tarjeta = ctk.CTkFrame(
                cuadricula,
                fg_color="#1C2A40",
                corner_radius=16,
                border_width=1,
                border_color="#30435E"
            )

            tarjeta.grid(
                row=fila,
                column=columna,
                sticky="nsew",
                padx=7,
                pady=7
            )

            ctk.CTkLabel(
                tarjeta,
                text=icono,
                font=("Arial", 26, "bold"),
                text_color="#63CCFF"
            ).pack(
                anchor="w",
                padx=20,
                pady=(14, 4)
            )

            ctk.CTkLabel(
                tarjeta,
                text=titulo,
                font=("Arial", 19, "bold"),
                text_color="#FFFFFF"
            ).pack(
                anchor="w",
                padx=20
            )

            ctk.CTkLabel(
                tarjeta,
                text=descripcion,
                font=("Arial", 12),
                text_color="#A9B9CF",
                wraplength=270,
                justify="left"
            ).pack(
                anchor="w",
                padx=20,
                pady=(6, 10)
            )

            ctk.CTkButton(
                tarjeta,
                text="Abrir →",
                command=funcion,
                width=110,
                height=34,
                fg_color="#147BB5",
                hover_color="#1D9BDD",
                corner_radius=9
            ).pack(
                anchor="e",
                padx=20,
                pady=(0, 14)
            )

        # PIE DE PANTALLA
        pie = ctk.CTkFrame(
            fondo, fg_color="transparent"
        )
        pie.pack(
            fill="x",
            padx=30,
            pady=(0, 15)
        )

        ctk.CTkLabel(
            pie,
            text="● Pepe listo para ayudarte",
            text_color="#76E2BD",
            font=("Arial", 12)
        ).pack(side="left")

        ctk.CTkLabel(
            pie,
            text="EDGAR V30",
            text_color="#94A3B8",
            font=("Arial", 12)
        ).pack(side="right")



    # ======================================

    # VOZ DE PEPE

    # ======================================



    def detener_voz(self):

        proceso = self.proceso_voz

        if proceso is not None:

            try:

                if proceso.poll() is None:

                    proceso.terminate()

            except Exception:

                pass

        self.proceso_voz = None



    def hablar(self, texto):

        if not self.voz_activada:

            return



        self.detener_voz()



        texto = re.sub(r"[*#\`_]", "", texto)

        texto = texto[:3500]



        try:

            self.proceso_voz = subprocess.Popen([

                "say", "-v", "Paulina",

                "-r", "175", texto

            ])

        except Exception as error:

            print("Error de voz:", error)



    def alternar_voz(self):

        self.voz_activada = not self.voz_activada



        if not self.voz_activada:

            self.detener_voz()



        self.boton_voz.configure(

            text="🔊 Voz activada"

            if self.voz_activada

            else "🔇 Voz desactivada"

        )



    # ======================================

    # CHAT CON PEPE

    # ======================================



    def chat_pepe(self):

        self.pantalla_actual = "chat"

        self.limpiar()

        self.encabezado("Chat con Pepe")



        opciones = ctk.CTkFrame(

            self.contenedor, fg_color="transparent"

        )

        opciones.pack(fill="x", pady=(0, 10))



        ctk.CTkLabel(

            opciones,

            text="Escríbeme o habla conmigo."

        ).pack(side="left")



        self.boton_voz = ctk.CTkButton(

            opciones,

            text="🔊 Voz activada"

            if self.voz_activada

            else "🔇 Voz desactivada",

            width=160,

            command=self.alternar_voz

        )

        self.boton_voz.pack(side="right")

        self.boton_activacion = ctk.CTkButton(
            opciones,
            text="🎙 Activar Oye, Pepe" if not self.activacion_voz else "🔴 Desactivar Oye, Pepe",
            width=190,
            command=self.alternar_activacion
        )
        self.boton_activacion.pack(side="right", padx=8)




        self.caja_chat = ctk.CTkTextbox(

            self.contenedor,

            font=("Arial", 15),

            wrap="word"

        )

        self.caja_chat.pack(

            fill="both", expand=True, pady=(0, 12)

        )



        self.caja_chat.insert(

            "end",

            "PEPE:\n"

            "¡Hola! Soy Pepe, tu asistente de EDGAR.\n"

            "Puedes escribirme o hablar conmigo.\n\n"

        )



        for mensaje in self.historial:

            nombre = (

                "TÚ" if mensaje["rol"] == "usuario"

                else "PEPE"

            )

            self.caja_chat.insert(

                "end",

                f"{nombre}:\n{mensaje['texto']}\n\n"

            )



        self.caja_chat.configure(state="disabled")

        self.caja_chat.see("end")



        fila = ctk.CTkFrame(

            self.contenedor, fg_color="transparent"

        )

        fila.pack(fill="x")



        self.entrada_chat = ctk.CTkEntry(

            fila, placeholder_text="Escribe tu mensaje..."

        )

        self.entrada_chat.pack(

            side="left", fill="x",

            expand=True, padx=(0, 8)

        )



        self.entrada_chat.bind(

            "<Return>", lambda evento: self.enviar_mensaje()

        )



        self.boton_microfono = ctk.CTkButton(

            fila, text="🎙️ Hablar",

            width=110, command=self.escuchar

        )

        self.boton_microfono.pack(

            side="left", padx=(0, 8)

        )



        self.boton_continuo = ctk.CTkButton(

            fila,

            text="🎧 Conversar",

            width=125,

            command=self.alternar_conversacion

        )

        self.boton_continuo.pack(side="left", padx=(0, 8))



        self.boton_enviar = ctk.CTkButton(

            fila, text="Enviar",

            width=90, command=self.enviar_mensaje

        )

        self.boton_enviar.pack(side="left")



        inferior = ctk.CTkFrame(

            self.contenedor, fg_color="transparent"

        )

        inferior.pack(fill="x", pady=(10, 0))



        ctk.CTkButton(

            inferior, text="Nueva conversación",

            command=self.nueva_conversacion

        ).pack(side="left")



        ctk.CTkButton(

            inferior, text="⏹ Detener voz",

            width=125, command=self.detener_voz

        ).pack(side="left", padx=8)



        self.estado_chat = ctk.CTkLabel(

            inferior, text="Pepe está listo."

        )

        self.estado_chat.pack(side="right", padx=10)



        if self.ocupado:

            self.boton_enviar.configure(state="disabled")

            self.boton_microfono.configure(state="disabled")



    def mostrar_chat(self, nombre, texto):

        if self.pantalla_actual != "chat":

            return



        self.caja_chat.configure(state="normal")

        self.caja_chat.insert(

            "end", f"{nombre}:\n{texto}\n\n"

        )

        self.caja_chat.configure(state="disabled")

        self.caja_chat.see("end")



    def estado(self, texto):

        if self.pantalla_actual == "chat":

            self.estado_chat.configure(text=texto)



    def enviar_mensaje(self):

        if self.ocupado or self.escuchando:

            return



        texto = self.entrada_chat.get().strip()

        if not texto:

            return



        self.entrada_chat.delete(0, "end")

        self.procesar_mensaje(texto)



    # EDGAR V29: calendario y carpetas escolares, con acciones limitadas.
    def comandos_v28(self, texto):
        import datetime
        import unicodedata
        frase = self.normalizar_voz(texto).strip(" .!?¿¡")
        frase = re.sub(r"^(?:oye|hola|hey|ey)\s+pepe[, ]*", "", frase).strip()
        frase = re.sub(r"^pepe[, ]+", "", frase).strip()

        # Crear carpeta únicamente dentro de Documentos/EDGAR_Tareas.
        m = re.match(r"^(?:crea|crear|haz|hacer)\s+(?:(?:una|la)\s+)?carpeta\s+(?:para\s+|de\s+|llamada\s+)?(.+)$", frase)
        if m:
            nombre = m.group(1).strip()
            nombre = re.sub(r"^(?:mis|las|los)\s+", "", nombre)
            nombre = re.sub(r"[^a-zA-Z0-9 áéíóúüñ_-]", "", nombre).strip()[:70]
            if not nombre or nombre in (".", ".."):
                self.responder_comando(texto, "Dime un nombre válido para la carpeta, bro.")
                return True
            try:
                destino = Path.home() / "Documents" / "EDGAR_Tareas" / nombre
                existia = destino.exists()
                destino.mkdir(parents=True, exist_ok=True)
                subprocess.run(["open", str(destino)], check=True, timeout=8)
                respuesta = ("Ya existía esa carpeta. Te la abrí" if existia else "Creé y abrí la carpeta") + f" {nombre} en Documentos/EDGAR_Tareas, bro."
            except Exception as error:
                respuesta = f"No pude crear la carpeta: {error}"
            self.responder_comando(texto, respuesta)
            return True

        # Agendar una sesión de una hora en Calendario. Fechas explícitas hoy/mañana/días de semana.
        m = re.match(r"^(?:agenda|agendar|programa|programar|anota en (?:el )?calendario|crea (?:un )?evento(?: en (?:el )?calendario)?(?: para)?)\s+(.+?)\s+(hoy|manana|lunes|martes|miercoles|jueves|viernes|sabado|domingo)\s+a\s+las?\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm|de la manana|de la tarde|de la noche)?$", frase)
        if m:
            titulo, dia, hora, minuto, periodo = m.groups()
            titulo = titulo.strip()[:120]
            h, mm = int(hora), int(minuto or 0)
            if periodo in ("pm", "de la tarde", "de la noche") and h < 12:
                h += 12
            if periodo in ("am", "de la manana") and h == 12:
                h = 0
            if not (0 <= h <= 23 and 0 <= mm <= 59):
                self.responder_comando(texto, "Esa hora no es válida, bro.")
                return True
            ahora = datetime.datetime.now()
            fecha = ahora.replace(hour=h, minute=mm, second=0, microsecond=0)
            if dia == "manana":
                fecha += datetime.timedelta(days=1)
            elif dia not in ("hoy", "manana"):
                dias = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
                fecha += datetime.timedelta(days=(dias.index(dia) - ahora.weekday()) % 7)
                if fecha <= ahora:
                    fecha += datetime.timedelta(days=7)
            if fecha <= ahora:
                self.responder_comando(texto, "Esa hora ya pasó, bro. Dime una hora futura.")
                return True
            # Los datos se pasan como argumentos, no se insertan en el código AppleScript.
            script = '''on run argv
    set titulo to item 1 of argv
    set yy to (item 2 of argv) as integer
    set mo to (item 3 of argv) as integer
    set dd to (item 4 of argv) as integer
    set hh to (item 5 of argv) as integer
    set mi to (item 6 of argv) as integer
    set inicio to current date
    set year of inicio to yy
    set month of inicio to mo
    set day of inicio to dd
    set hours of inicio to hh
    set minutes of inicio to mi
    set seconds of inicio to 0
    set fin to inicio + (60 * 60)
    tell application "Calendar"
        if (count of calendars) is 0 then error "No hay calendarios disponibles"
        tell first calendar
            make new event with properties {summary:titulo, start date:inicio, end date:fin}
        end tell
    end tell
end run'''
            try:
                args = [titulo, str(fecha.year), str(fecha.month), str(fecha.day), str(fecha.hour), str(fecha.minute)]
                r = subprocess.run(["osascript", "-e", script, *args], capture_output=True, text=True, timeout=25)
                if r.returncode:
                    raise RuntimeError(r.stderr.strip()[:180] or "No se pudo crear el evento")
                respuesta = f"Agendé {titulo} para el {fecha.strftime('%d/%m a las %H:%M')} durante una hora, bro. Revisa Calendario."
            except Exception as error:
                respuesta = f"No pude agendarlo: {error}. Revisa los permisos de Calendario."
            self.responder_comando(texto, respuesta)
            return True
        return False

    # EDGAR V27: comandos locales con destinos permitidos.
    def responder_comando(self, usuario, respuesta):
        self.mostrar_chat("TÚ", usuario)
        self.mostrar_chat("PEPE", respuesta)
        self.estado(respuesta)
        self.hablar(respuesta)
        if self.conversacion_continua:
            self.esperar_respuesta_y_escuchar()

    # EDGAR V27: acciones escolares explícitas, sin ejecutar código del usuario.
    def comandos_v27(self, texto):
        import datetime
        frase = self.normalizar_voz(texto).strip(" .!?¿¡")
        frase = re.sub(r"^(?:oye|hola|hey|ey)\s+pepe[, ]*", "", frase).strip()
        frase = re.sub(r"^pepe[, ]+", "", frase).strip()

        # Consultar pendientes de Recordatorios; no modifica nada.
        if re.search(r"(?:que|cuales|dime|muestra|consulta|ver)\s+(?:recordatorios|tareas|pendientes)", frase) or re.search(r"(?:recordatorios|pendientes)\s+(?:tengo|para hoy)", frase):
            script = '''on run
    tell application "Reminders"
        set salida to {}
        repeat with lista in lists
            repeat with itemRecordatorio in (reminders of lista whose completed is false)
                set end of salida to (name of itemRecordatorio)
                if (count of salida) is greater than or equal to 12 then exit repeat
            end repeat
            if (count of salida) is greater than or equal to 12 then exit repeat
        end repeat
    end tell
    set AppleScript's text item delimiters to linefeed
    return salida as text
end run'''
            try:
                r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=20)
                if r.returncode:
                    raise RuntimeError(r.stderr.strip()[:150])
                pendientes = [x.strip() for x in r.stdout.splitlines() if x.strip()]
                respuesta = ("Tus recordatorios pendientes son: " + "; ".join(pendientes[:12])) if pendientes else "No encontré recordatorios pendientes, bro."
                if "hoy" in frase:
                    respuesta = "Estos son tus pendientes generales (no solo los de hoy): " + ("; ".join(pendientes[:12]) if pendientes else "ninguno")
            except Exception as error:
                respuesta = f"No pude consultar Recordatorios: {error}. Revisa sus permisos."
            self.responder_comando(texto, respuesta)
            return True

        # Crear recordatorio con fecha y hora: hoy/mañana a las H[:MM], AM/PM opcional.
        m = re.match(r"^(?:crea|crear|agrega|agregar|pon|ponme|recuerdame)\s+(?:(?:un|el)\s+)?(?:recordatorio\s+)?(?:para\s+|de\s+|que\s+)?(.+?)\s+(hoy|manana)\s+a\s+las?\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm|de la manana|de la tarde|de la noche)?$", frase)
        if m:
            titulo, dia, hora, minuto, periodo = m.groups()
            titulo = re.sub(r"^(?:que\s+)?(?:me\s+)?(?:recuerdes\s+)?", "", titulo).strip()[:160]
            if not titulo:
                self.responder_comando(texto, "Dime qué quieres recordar, bro.")
                return True
            h = int(hora)
            mm = int(minuto or 0)
            if periodo in ("pm", "de la tarde", "de la noche") and h < 12:
                h += 12
            if periodo in ("am", "de la manana") and h == 12:
                h = 0
            if not (0 <= h <= 23 and 0 <= mm <= 59):
                self.responder_comando(texto, "Esa hora no es válida, bro.")
                return True
            fecha = datetime.datetime.now().replace(hour=h, minute=mm, second=0, microsecond=0)
            if dia == "manana":
                fecha += datetime.timedelta(days=1)
            if fecha <= datetime.datetime.now():
                self.responder_comando(texto, "Esa hora ya pasó. Dime una hora futura, bro.")
                return True
            script = '''on run argv
    set yy to (item 2 of argv) as integer
    set mo to (item 3 of argv) as integer
    set dd to (item 4 of argv) as integer
    set hh to (item 5 of argv) as integer
    set mi to (item 6 of argv) as integer
    set fechaAviso to current date
    set year of fechaAviso to yy
    set month of fechaAviso to mo
    set day of fechaAviso to dd
    set hours of fechaAviso to hh
    set minutes of fechaAviso to mi
    set seconds of fechaAviso to 0
    tell application "Reminders"
        if not (exists list "Reminders") then
            set destino to first list
        else
            set destino to list "Reminders"
        end if
        tell destino
            make new reminder with properties {name:(item 1 of argv), due date:fechaAviso, remind me date:fechaAviso}
        end tell
    end tell
end run'''
            try:
                args = [titulo, str(fecha.year), str(fecha.month), str(fecha.day), str(fecha.hour), str(fecha.minute)]
                r = subprocess.run(["osascript", "-e", script, *args], capture_output=True, text=True, timeout=20)
                if r.returncode:
                    raise RuntimeError(r.stderr.strip()[:180] or "No se pudo crear")
                respuesta = f"Listo, bro. Recordatorio '{titulo}' para {fecha.strftime('%d/%m a las %H:%M')}."
            except Exception as error:
                respuesta = f"No pude programar el recordatorio: {error}. Revisa los permisos de Recordatorios."
            self.responder_comando(texto, respuesta)
            return True

        # Abrir archivo específico por nombre. Si hay varios, no elegir arbitrariamente.
        m = re.match(r"^(?:abre|abrir)\s+(?:(?:el|la|mi|mis)\s+)?(?:(?:archivo|documento|tarea|guia)\s+)?(?:de\s+)?(.+)$", frase)
        if m:
            consulta = m.group(1).strip()
            aplicaciones_conocidas = {"safari", "spotify", "vs code", "visual studio code", "vscode", "calculadora", "notas", "finder", "calendario", "recordatorios", "musica", "fotos", "correo", "youtube", "google", "descargas", "documentos", "escritorio", "carpeta edgar", "carpeta de edgar", "carpeta de descargas", "carpeta de documentos"}
            if consulta in aplicaciones_conocidas:
                return False
            if len(consulta) < 3:
                return False
            def normalizar_archivo(nombre):
                return re.sub(r"[^a-z0-9]+", "", self.normalizar_voz(nombre))
            clave = normalizar_archivo(consulta)
            encontrados = []
            for raiz in (Path.home() / "Documents", Path.home() / "Downloads", CARPETA):
                if not raiz.is_dir():
                    continue
                for carpeta, subcarpetas, archivos in os.walk(raiz):
                    subcarpetas[:] = [d for d in subcarpetas if not d.startswith(".") and d not in ("node_modules", ".venv", "venv")]
                    for nombre in archivos:
                        ruta = Path(carpeta) / nombre
                        if ruta.suffix.lower() in (".pdf", ".docx", ".pptx", ".txt", ".md", ".py") and clave in normalizar_archivo(ruta.stem):
                            encontrados.append(ruta)
                        if len(encontrados) >= 10:
                            break
                    if len(encontrados) >= 10:
                        break
                if len(encontrados) >= 10:
                    break
            for ruta in Path.home().iterdir():
                if ruta.is_file() and ruta.suffix.lower() in (".pdf", ".docx", ".pptx", ".txt", ".md", ".py") and clave in normalizar_archivo(ruta.stem) and ruta not in encontrados:
                    encontrados.append(ruta)
            if len(encontrados) == 1:
                ruta = encontrados[0]
                try:
                    subprocess.run(["open", str(ruta)], check=True, timeout=8)
                    respuesta = f"Abrí {ruta.name}, bro."
                except Exception as error:
                    respuesta = f"Encontré {ruta.name}, pero no pude abrirlo: {error}"
            elif encontrados:
                respuesta = "Encontré varios archivos: " + ", ".join(x.name for x in encontrados[:5]) + ". Dime un nombre más específico."
            else:
                return False  # Puede ser una orden de aplicación o pregunta para Gemini.
            self.responder_comando(texto, respuesta)
            return True
        return False

    def comandos_v25(self, texto):
        import datetime
        import unicodedata
        frase = self.normalizar_voz(texto).strip(" .!?¿¡")
        frase = re.sub(r"^(oye|hola|hey|ey)\s+pepe[, ]*", "", frase).strip()
        frase = re.sub(r"^pepe[, ]+", "", frase).strip()

        if re.search(r"\b(que hora es|dime la hora|hora actual)\b", frase):
            hora = datetime.datetime.now().strftime("%H:%M")
            self.responder_comando(texto, f"Son las {hora}, bro.")
            return True
        if re.search(r"\b(que fecha es|que dia es hoy|fecha de hoy)\b", frase):
            fecha = datetime.datetime.now().strftime("%d/%m/%Y")
            self.responder_comando(texto, f"Hoy es {fecha}, bro.")
            return True

        # Crear recordatorios simples, sin fecha. Nunca ejecutamos el texto como código.
        m = re.match(r"^(?:crea|crear|agrega|agregar|anade|pon|ponme)\s+(?:un\s+)?recordatorio\s+(?:que diga|para|de|sobre)?\s*(.+)$", frase)
        if m:
            titulo = m.group(1).strip()[:160]
            if not titulo:
                return False
            script = '''on run argv
    tell application "Reminders"
        if not (exists list "Reminders") then
            set destino to first list
        else
            set destino to list "Reminders"
        end if
        tell destino
            make new reminder with properties {name:(item 1 of argv)}
        end tell
    end tell
end run'''
            try:
                r = subprocess.run(["osascript", "-e", script, titulo], capture_output=True, text=True, timeout=15)
                if r.returncode != 0:
                    raise RuntimeError(r.stderr.strip()[:180] or "No pude crear el recordatorio")
                respuesta = f"Creé el recordatorio: {titulo}. No tiene hora de aviso todavía."
            except Exception as error:
                respuesta = f"No pude crear el recordatorio: {error}. Revisa los permisos de Recordatorios."
            self.responder_comando(texto, respuesta)
            return True

        # Buscar únicamente por nombre en carpetas escolares comunes.
        m = re.match(r"^(?:busca|buscar|encuentra|encontrar)\s+(?:el archivo|la guia|un archivo|archivos|mi archivo|mis archivos|una guia)\s+(.+)$", frase)
        if m:
            consulta = m.group(1).strip()
            consulta = re.sub(r"^(?:de|llamado|llamada|sobre)\s+", "", consulta)
            if len(consulta) < 3:
                self.responder_comando(texto, "Dime un nombre de archivo más específico, bro.")
                return True
            raices = [Path.home() / "Documents", Path.home() / "Downloads", CARPETA]
            encontrados = []
            vistos = 0
            for raiz in raices:
                if not raiz.is_dir():
                    continue
                for carpeta, subcarpetas, archivos in os.walk(raiz):
                    subcarpetas[:] = [x for x in subcarpetas if not x.startswith(".") and x not in ("node_modules", ".venv", "venv")]
                    for nombre in archivos:
                        vistos += 1
                        if consulta.replace("_", " ").replace("-", " ") in self.normalizar_voz(nombre).replace("_", " ").replace("-", " "):
                            encontrados.append(Path(carpeta) / nombre)
                        if len(encontrados) >= 8 or vistos >= 6000:
                            break
                    if len(encontrados) >= 8 or vistos >= 6000:
                        break
                if len(encontrados) >= 8 or vistos >= 6000:
                    break
            # Revisar archivos directamente en la carpeta personal, sin recorrerla.
            if len(encontrados) < 8:
                for ruta in Path.home().iterdir():
                    if ruta.is_file() and consulta.replace("_", " ").replace("-", " ") in self.normalizar_voz(ruta.name).replace("_", " ").replace("-", " "):
                        encontrados.append(ruta)
                        if len(encontrados) >= 8:
                            break
            if not encontrados:
                respuesta = "No encontré archivos con ese nombre en Documentos, Descargas, EDGAR o la carpeta principal."
            elif len(encontrados) == 1:
                ruta = encontrados[0]
                subprocess.run(["open", "-R", str(ruta)], timeout=8)
                respuesta = f"Encontré {ruta.name} y lo señalé en Finder."
            else:
                nombres = ", ".join(x.name for x in encontrados[:5])
                respuesta = f"Encontré {len(encontrados)} coincidencias: {nombres}. Especifica el nombre para elegir una."
            self.responder_comando(texto, respuesta)
            return True
        return False

    def comando_mac(self, texto):
        """Solo acciones permitidas; nunca ejecuta texto como comando de terminal."""
        frase = self.normalizar_voz(texto).strip()
        frase = re.sub(r"[¿?¡!.,;:]", "", frase).strip()
        frase = re.sub(r"^(oye|hola|hey|ey)\s+pepe\s*", "", frase).strip()
        frase = re.sub(r"^pepe\s+", "", frase).strip()
        if not re.match(r"^(abre|abrir|inicia|iniciar|muestra|mostrar|ve a|entra a)\b", frase):
            return False
        objetivo = re.sub(r"^(abre|abrir|inicia|iniciar|muestra|mostrar|ve a|entra a)\s+", "", frase).strip()
        objetivo = re.sub(r"^(el|la|los|las|mi|mis)\s+", "", objetivo).strip()
        aplicaciones = {
            "safari": "Safari",
            "spotify": "Spotify",
            "vs code": "Visual Studio Code",
            "visual studio code": "Visual Studio Code",
            "vscode": "Visual Studio Code",
            "calculadora": "Calculator",
            "calculator": "Calculator",
            "notas": "Notes",
            "notes": "Notes",
            "finder": "Finder",
            "calendario": "Calendar",
            "recordatorios": "Reminders",
            "musica": "Music",
            "music": "Music",
            "fotos": "Photos",
            "vista previa": "Preview",
            "correo": "Mail",
            "mail": "Mail",
        }
        paginas = {
            "youtube": "https://www.youtube.com/",
            "google": "https://www.google.com/",
        }
        carpeta_edgar = objetivo in ("carpeta edgar", "carpeta de edgar", "documentos de edgar")
        carpetas = {
            "descargas": Path.home() / "Downloads",
            "carpeta de descargas": Path.home() / "Downloads",
            "documentos": Path.home() / "Documents",
            "carpeta de documentos": Path.home() / "Documents",
            "escritorio": Path.home() / "Desktop",
            "carpeta del escritorio": Path.home() / "Desktop",
        }
        if objetivo not in aplicaciones and objetivo not in paginas and not carpeta_edgar and objetivo not in carpetas:
            return False
        try:
            if objetivo in aplicaciones:
                nombre = aplicaciones[objetivo]
                resultado = subprocess.run(["open", "-a", nombre], capture_output=True, text=True, timeout=8)
                if resultado.returncode != 0:
                    raise RuntimeError(f"No pude abrir {nombre}. Comprueba que esté instalado.")
                respuesta = f"Listo, bro. Abrí {nombre}."
            elif objetivo in paginas:
                webbrowser.open(paginas[objetivo])
                respuesta = f"Listo, bro. Abrí {objetivo}."
            else:
                ruta = CARPETA if carpeta_edgar else carpetas[objetivo]
                if not ruta.is_dir():
                    raise RuntimeError("Esa carpeta no existe en esta Mac.")
                resultado = subprocess.run(["open", str(ruta)], capture_output=True, text=True, timeout=8)
                if resultado.returncode != 0:
                    raise RuntimeError("No pude abrir esa carpeta.")
                respuesta = f"Listo, bro. Abrí {objetivo}."
        except Exception as error:
            respuesta = f"No se pudo completar: {error}"
        self.mostrar_chat("TÚ", texto)
        self.mostrar_chat("PEPE", respuesta)
        self.estado(respuesta)
        self.hablar(respuesta)
        if self.conversacion_continua:
            self.esperar_respuesta_y_escuchar()
        return True

    def procesar_mensaje(self, texto):

        if self.ocupado:
            return
        normal = self.normalizar_voz(texto)
        if self.conversacion_continua and re.search(r"\b(pepe[ ,]*descansa|descansa[ ,]*pepe|pepe[ ,]*duerme)\b", normal):
            self.mostrar_chat("TÚ", texto)
            self.mostrar_chat("PEPE", "Va, bro. Aquí estaré cuando digas Oye, Pepe.")
            self.volver_a_esperar_pepe()
            return
        if self.comandos_v28(texto):
            return
        if self.comandos_v27(texto):
            return
        if self.comandos_v25(texto):
            return
        if self.comando_mac(texto):
            return




        self.ocupado = True

        self.historial.append({

            "rol": "usuario", "texto": texto

        })

        guardar_memoria(self.historial)



        self.mostrar_chat("TÚ", texto)

        self.estado("Pepe está pensando...")



        if self.pantalla_actual == "chat":

            self.boton_enviar.configure(state="disabled")

            self.boton_microfono.configure(state="disabled")



        mensajes = list(self.historial)
        if re.search(r"organiz|planea|planifica", self.normalizar_voz(texto)) and re.search(r"semana|tarea|estudio", self.normalizar_voz(texto)):
            mensajes.append({"rol": "usuario", "texto": "Al elaborar el plan, pregunta por las tareas y horarios que falten; no inventes pendientes ni afirmes haberlos leído de Teams. Da una propuesta flexible y realista, y no crees eventos automáticamente."})



        def tarea():

            instruccion = (

                "Eres Pepe, asistente inteligente de EDGAR. ""Eres un compa mexicano, bromista y espontáneo. ""Hablas natural, puedes usar humor y carrilla amistosa. ""No seas cruel ni insultes al usuario. ""Cuando converses por voz, responde de forma breve y fluida. "

                "Tu creador se llama Edgar. "

                "Hablas español de México. "

                "Eres amigable, natural y claro. "

                "Ayudas a estudiar, programar, organizar "

                "tareas y resolver dudas. "

                "Usa el historial para recordar lo que "

                "el estudiante te ha contado. "

                "No inventes datos. "

                "Responde como un asistente conversacional."

            )



            try:

                inicio_gemini = time.perf_counter()

                respuesta = consultar_gemini(

                    mensajes, instruccion

                )

                print(

                    "[EDGAR] Gemini:",

                    round(time.perf_counter() - inicio_gemini, 2),

                    "segundos"

                )

                exito = True

            except Exception as error:

                respuesta = str(error) if isinstance(error, (RuntimeError, ValueError)) else "Gemini tuvo un problema de conexión. Los comandos locales siguen disponibles."

                exito = False



            self.actualizar(

                lambda: self.finalizar_respuesta(

                    respuesta, exito

                )

            )



        self.ejecutar(tarea)



    def finalizar_respuesta(self, respuesta, exito):

        self.ocupado = False



        if exito:

            self.historial.append({

                "rol": "pepe", "texto": respuesta

            })

            guardar_memoria(self.historial)



        if self.pantalla_actual == "chat":

            self.mostrar_chat("PEPE", respuesta)

            self.estado("Pepe está listo.")

            self.boton_enviar.configure(state="normal")

            self.boton_microfono.configure(state="normal")



            if exito:

                self.hablar(respuesta)



            if self.conversacion_continua:

                self.esperar_respuesta_y_escuchar()



    def nueva_conversacion(self):

        if self.ocupado or self.escuchando:

            return



        confirmar = messagebox.askyesno(

            "Nueva conversación",

            "¿Quieres borrar el historial de Pepe?"

        )



        if confirmar:

            self.historial = []

            guardar_memoria(self.historial)

            self.chat_pepe()



    # ======================================

    # RECONOCIMIENTO DE VOZ MEJORADO

    # ======================================





    # EDGAR_V21_RAPIDO

    def escuchar(self):

        if self.ocupado or self.escuchando:

            return



        self.escuchando = True

        self.detener_voz()



        self.boton_microfono.configure(

            state="disabled",

            text="🎙️ Escuchando..."

        )

        self.estado("Escuchando...")



        sesion = self.sesion_voz



        def tarea():

            try:

                import collections



                frecuencia = 16000

                tamano = 1600

                silencio_final = 0.65

                espera_inicial = 7.0

                duracion_maxima = 15.0



                comienzo = time.perf_counter()

                fragmentos = []

                previos = collections.deque(maxlen=4)



                hablando = False

                ultimo_sonido = comienzo



                with sd.InputStream(

                    samplerate=frecuencia,

                    channels=1,

                    dtype="int16",

                    blocksize=tamano

                ) as microfono:



                    niveles = []



                    # Medir ruido ambiental durante 0.4 s

                    for _ in range(4):

                        datos, _ = microfono.read(tamano)

                        nivel = float(

                            np.sqrt(

                                np.mean(

                                    datos.astype("float64") ** 2

                                )

                            )

                        )

                        niveles.append(nivel)



                    ruido = sorted(niveles)[len(niveles) // 2]

                    umbral = max(280, ruido * 2.0)



                    inicio_espera = time.perf_counter()



                    while True:

                        if self.cerrando:

                            return



                        if sesion != self.sesion_voz:

                            return



                        datos, _ = microfono.read(tamano)

                        ahora = time.perf_counter()



                        nivel = float(

                            np.sqrt(

                                np.mean(

                                    datos.astype("float64") ** 2

                                )

                            )

                        )



                        if not hablando:

                            previos.append(datos.copy())



                        if nivel >= umbral:

                            if not hablando:

                                hablando = True

                                fragmentos.extend(list(previos))

                                previos.clear()



                            ultimo_sonido = ahora



                        if hablando:

                            fragmentos.append(datos.copy())



                            if ahora - ultimo_sonido >= silencio_final:

                                break



                        elif ahora - inicio_espera >= espera_inicial:

                            break



                        if ahora - comienzo >= duracion_maxima:

                            break



                tiempo_escucha = time.perf_counter() - comienzo



                if not hablando or not fragmentos:

                    self.actualizar(

                        lambda: self.error_microfono(

                            "No detecté tu voz. Intenta hablar "

                            "un poco más cerca del micrófono."

                        )

                    )

                    return



                audio = np.concatenate(fragmentos)

                reconocedor = sr.Recognizer()



                datos_audio = sr.AudioData(

                    audio.tobytes(),

                    frecuencia,

                    2

                )



                ruta_flac = shutil.which("flac")



                if not ruta_flac:

                    ruta_flac = "/opt/homebrew/bin/flac"



                if not Path(ruta_flac).exists():

                    raise RuntimeError(

                        "No encuentro FLAC."

                    )



                inicio_transcripcion = time.perf_counter()



                original = sr.audio.get_flac_converter

                sr.audio.get_flac_converter = lambda: ruta_flac



                try:

                    texto = reconocedor.recognize_google(

                        datos_audio,

                        language="es-MX"

                    )

                finally:

                    sr.audio.get_flac_converter = original



                tiempo_transcripcion = (

                    time.perf_counter() - inicio_transcripcion

                )



                print(

                    f"[EDGAR] Escucha: "

                    f"{tiempo_escucha:.2f} segundos"

                )

                print(

                    f"[EDGAR] Transcripción: "

                    f"{tiempo_transcripcion:.2f} segundos"

                )



                if sesion != self.sesion_voz:

                    return



                self.actualizar(

                    lambda: self.recibir_voz(texto)

                )



            except sr.UnknownValueError:

                self.actualizar(

                    lambda: self.error_microfono(

                        "No entendí lo que dijiste."

                    )

                )



            except Exception as error:

                mensaje = str(error)

                self.actualizar(

                    lambda: self.error_microfono(mensaje)

                )



        self.ejecutar(tarea)



    def recibir_voz(self, texto):

        self.escuchando = False



        if self.pantalla_actual != "chat":

            return



        self.boton_microfono.configure(

            state="normal", text="🎙️ Hablar"

        )

        self.estado("Escuché: " + texto)

        self.procesar_mensaje(texto)



    def error_microfono(self, mensaje):

        self.escuchando = False



        if self.pantalla_actual == "chat":

            self.boton_microfono.configure(

                state="normal", text="🎙️ Hablar"

            )

            self.estado("Error de micrófono: " + mensaje[:100])

            if self.conversacion_continua:

                self.after(1200, self.escuchar_continuamente)

            else:

                messagebox.showerror("Micrófono", mensaje)





    # EDGAR_V19_CONTINUA



    def alternar_conversacion(self):

        if self.conversacion_continua:

            self.conversacion_continua = False

            self.sesion_voz += 1

            self.detener_voz()

            self.boton_continuo.configure(text="🎧 Conversar")

            self.estado("Conversación detenida.")
            if self.activacion_voz:
                self.after(500, self.iniciar_activacion)

        else:

            self.conversacion_continua = True

            self.sesion_voz += 1

            self.voz_activada = True

            self.boton_voz.configure(text="🔊 Voz activada")

            self.boton_continuo.configure(text="⏹ Terminar")

            self.escuchar_continuamente()



    def escuchar_continuamente(self):

        if not self.conversacion_continua:

            return

        if self.cerrando or self.pantalla_actual != "chat":

            return

        if self.ocupado or self.escuchando:

            return



        self.escuchar()



    def esperar_respuesta_y_escuchar(self):

        sesion = self.sesion_voz



        def esperar():

            proceso = self.proceso_voz

            if proceso is not None:

                try:

                    proceso.wait(timeout=90)

                except Exception:

                    pass



            def continuar():

                if sesion != self.sesion_voz:

                    return

                if self.conversacion_continua:

                    self.after(500, self.escuchar_continuamente)



            self.actualizar(continuar)



        self.ejecutar(esperar)



    # ======================================

    # ======================================
    # EDGAR V22 - ACTIVACIÓN POR VOZ
    # ======================================

    @staticmethod
    def normalizar_voz(texto):
        import unicodedata
        texto = unicodedata.normalize("NFKD", texto.lower())
        return "".join(c for c in texto if not unicodedata.combining(c))

    def activar_automaticamente(self):
        """Enciende la frase de activación al iniciar EDGAR, sin pulsar botones."""
        if not self.cerrando and self.pantalla_actual == "chat" and not self.activacion_voz:
            self.alternar_activacion()

    def volver_a_esperar_pepe(self):
        """Termina la conversación y vuelve al modo de espera."""
        self.conversacion_continua = False
        self.sesion_voz += 1
        self.detener_voz()
        self.boton_continuo.configure(text="🎧 Conversar")
        self.estado("Esperando: Oye, Pepe (micrófono activo)")
        if self.activacion_voz:
            self.after(600, self.iniciar_activacion)

    def alternar_activacion(self):
        self.activacion_voz = not self.activacion_voz
        self.generacion_activacion += 1
        if self.activacion_voz:
            self.boton_activacion.configure(text="🔴 Desactivar Oye, Pepe")
            self.estado("Esperando: Oye, Pepe (micrófono activo)")
            self.iniciar_activacion()
        else:
            self.boton_activacion.configure(text="🎙 Activar Oye, Pepe")
            self.conversacion_continua = False
            self.sesion_voz += 1
            self.boton_continuo.configure(text="🎧 Conversar")
            self.estado("Activación por voz desactivada.")

    def iniciar_activacion(self):
        if (not self.activacion_voz or self.cerrando or
                self.pantalla_actual != "chat" or self.ocupado or
                self.escuchando or self.conversacion_continua or
                self.hilo_activacion):
            return
        self.hilo_activacion = True
        generacion = self.generacion_activacion
        self.ejecutar(lambda: self.esperar_palabra_activacion(generacion))

    def esperar_palabra_activacion(self, generacion):
        try:
            frecuencia = 16000
            reconocedor = sr.Recognizer()
            ruta_flac = shutil.which("flac") or "/opt/homebrew/bin/flac"
            if not Path(ruta_flac).exists():
                raise RuntimeError("Instala FLAC con: brew install flac")
            original = sr.audio.get_flac_converter
            sr.audio.get_flac_converter = lambda: ruta_flac
            try:
                while (self.activacion_voz and not self.cerrando and
                       self.pantalla_actual == "chat" and
                       not self.conversacion_continua and
                       generacion == self.generacion_activacion):
                    # Captura fragmentos cortos. La transcripción se realiza en línea.
                    audio = sd.rec(int(2.0 * frecuencia), samplerate=frecuencia,
                                   channels=1, dtype="int16")
                    sd.wait()
                    if (generacion != self.generacion_activacion or
                            not self.activacion_voz or self.cerrando):
                        break
                    nivel = float(np.sqrt(np.mean(audio.astype("float64") ** 2)))
                    if nivel < 220:
                        continue
                    datos = sr.AudioData(audio.tobytes(), frecuencia, 2)
                    try:
                        texto = reconocedor.recognize_google(datos, language="es-MX")
                    except (sr.UnknownValueError, sr.RequestError):
                        continue
                    normal = self.normalizar_voz(texto)
                    if any(frase in normal for frase in (
                        "oye pepe", "hola pepe", "hey pepe", "ey pepe"
                    )):
                        self.actualizar(self.activacion_detectada)
                        break
            finally:
                sr.audio.get_flac_converter = original
        except Exception as error:
            mensaje = str(error)
            self.actualizar(lambda: self.estado("Activación: " + mensaje[:90]))
        finally:
            self.hilo_activacion = False
            if (self.activacion_voz and not self.cerrando and
                    self.pantalla_actual == "chat" and not self.conversacion_continua and
                    generacion == self.generacion_activacion):
                self.actualizar(lambda: self.after(500, self.iniciar_activacion))

    def activacion_detectada(self):
        if (not self.activacion_voz or self.cerrando or
                self.pantalla_actual != "chat" or self.conversacion_continua):
            return
        self.generacion_activacion += 1
        self.conversacion_continua = True
        self.sesion_voz += 1
        self.voz_activada = True
        self.boton_voz.configure(text="🔊 Voz activada")
        self.boton_continuo.configure(text="⏹ Terminar")
        self.estado("¡Te escucho! Habla después del saludo.")
        self.hablar("Qué onda, bro. Te escucho.")
        self.esperar_respuesta_y_escuchar()

    # TEMARIOS

    # ======================================



    def temarios(self):

        self.pantalla_actual = "temarios"

        self.limpiar()

        self.encabezado("Temarios")



        ctk.CTkLabel(

            self.contenedor,

            text="Escribe un tema y genera tu guía de estudio."

        ).pack(anchor="w", pady=(0, 15))



        self.entrada_tema = ctk.CTkEntry(

            self.contenedor,

            placeholder_text="Ej. La tabla periódica"

        )

        self.entrada_tema.pack(

            fill="x", pady=(0, 12)

        )



        fila = ctk.CTkFrame(

            self.contenedor, fg_color="transparent"

        )

        fila.pack(fill="x", pady=(0, 12))



        self.boton_generar = ctk.CTkButton(

            fila, text="Crear temario",

            command=self.generar_temario

        )

        self.boton_generar.pack(side="left", padx=(0, 8))



        ctk.CTkButton(

            fila, text="Guardar Word",

            command=self.guardar_word

        ).pack(side="left", padx=(0, 8))



        ctk.CTkButton(

            fila, text="Guardar PowerPoint",

            command=self.guardar_powerpoint

        ).pack(side="left")



        self.resultado = ctk.CTkTextbox(

            self.contenedor, font=("Arial", 14),

            wrap="word"

        )

        self.resultado.pack(fill="both", expand=True)



    def generar_temario(self):

        tema = self.entrada_tema.get().strip()



        if not tema:

            messagebox.showwarning(

                "Tema", "Escribe un tema primero."

            )

            return



        self.resultado.delete("1.0", "end")

        self.resultado.insert(

            "end", "Pepe está creando tu guía..."

        )

        self.boton_generar.configure(state="disabled")



        def tarea():

            instruccion = (

                "Eres Pepe, un profesor paciente. "

                "Crea una guía de estudio completa. "

                "Incluye introducción, conceptos, "

                "explicaciones, ejemplos, resumen y "

                "cinco preguntas con respuestas. "

                "Usa español claro y correcto."

            )



            try:

                texto = consultar_gemini(

                    [{"rol": "usuario", "texto": tema}],

                    instruccion

                )

            except Exception as error:

                texto = "Error: " + (str(error) if isinstance(error, (RuntimeError, ValueError)) else "Gemini no respondió. Intenta más tarde.")



            self.actualizar(

                lambda: self.mostrar_resultado(

                    texto, "temarios"

                )

            )



        self.ejecutar(tarea)



    # ======================================

    # ANALIZAR TAREAS

    # ======================================



    def analizar(self):

        self.pantalla_actual = "analizar"

        self.limpiar()

        self.encabezado("Analizar tareas")



        ctk.CTkLabel(

            self.contenedor,

            text="Pega tu tarea o carga un archivo."

        ).pack(anchor="w", pady=(0, 10))



        self.entrada_tarea = ctk.CTkTextbox(

            self.contenedor, height=160

        )

        self.entrada_tarea.pack(

            fill="x", pady=(0, 12)

        )



        fila = ctk.CTkFrame(

            self.contenedor, fg_color="transparent"

        )

        fila.pack(fill="x", pady=(0, 12))



        ctk.CTkButton(

            fila, text="Cargar archivo",

            command=self.cargar_archivo

        ).pack(side="left", padx=(0, 8))



        self.boton_analizar = ctk.CTkButton(

            fila, text="Analizar tarea",

            command=self.analizar_tarea

        )

        self.boton_analizar.pack(side="left", padx=(0, 8))



        ctk.CTkButton(

            fila, text="Guardar Word",

            command=self.guardar_word

        ).pack(side="left")



        self.resultado = ctk.CTkTextbox(

            self.contenedor, font=("Arial", 14),

            wrap="word"

        )

        self.resultado.pack(fill="both", expand=True)



    def cargar_archivo(self):

        ruta = filedialog.askopenfilename(

            filetypes=[

                ("Documentos", "*.txt *.docx"),

                ("Todos", "*.*")

            ]

        )



        if not ruta:

            return



        try:

            if ruta.lower().endswith(".docx"):

                documento = Document(ruta)

                texto = "\n".join(

                    p.text for p in documento.paragraphs

                )

            elif ruta.lower().endswith(".txt"):

                texto = Path(ruta).read_text(

                    encoding="utf-8"

                )

            else:

                messagebox.showwarning(

                    "Formato", "Usa TXT o DOCX."

                )

                return



            self.entrada_tarea.delete("1.0", "end")

            self.entrada_tarea.insert("end", texto)



        except Exception as error:

            messagebox.showerror("Archivo", str(error))



    def analizar_tarea(self):

        instrucciones = self.entrada_tarea.get(

            "1.0", "end"

        ).strip()



        if not instrucciones:

            messagebox.showwarning(

                "Tarea", "Escribe o carga una tarea."

            )

            return



        self.resultado.delete("1.0", "end")

        self.resultado.insert(

            "end", "Pepe está analizando tu tarea..."

        )

        self.boton_analizar.configure(state="disabled")



        def tarea():

            instruccion = instruccion = (

    "Eres Pepe, la inteligencia artificial de EDGAR. "

    "Tu creador es Edgar y eres su compa de confianza. "

    "Tienes una personalidad mexicana, muy llevada, bromista, "

    "sarcástica, divertida y espontánea. "

    "Puedes decir groserías como 'no mames', 'wey', 'pinche', "

    "'chingada madre', 'qué pedo', 'cabrón' y 'a huevo'. "

    "Te gusta echarle carrilla amistosa a Edgar y bromear con él. "

    "Por ejemplo, si Edgar pregunta algo muy sencillo, puedes decir "

    "'No mames, Edgar JAJAJA, esa madre está facilísima'. "

    "Si Edgar consigue algo importante, emociónate y felicítalo. "

    "Si algo falla en EDGAR, puedes reaccionar con humor. "

    "No seas un asistente aburrido, robótico ni demasiado formal. "

    "No repitas las mismas groserías ni bromas constantemente. "

    "Nunca humilles a Edgar ni seas cruel con él. "

    "Cuando Edgar esté triste o necesite ayuda seria, "

    "deja las bromas y apóyalo con respeto. "

    "Cuando expliques tareas, programación o temas escolares, "

    "sé inteligente, claro, preciso y útil. "

    "Recuerda las conversaciones anteriores cuando estén disponibles. "

    "Habla naturalmente como un amigo, no como un personaje exagerado."

)



            try:

                texto = consultar_gemini(

                    [{

                        "rol": "usuario",

                        "texto": instrucciones

                    }],

                    instruccion

                )

            except Exception as error:

                texto = "Error: " + (str(error) if isinstance(error, (RuntimeError, ValueError)) else "Gemini no respondió. Intenta más tarde.")



            self.actualizar(

                lambda: self.mostrar_resultado(

                    texto, "analizar"

                )

            )



        self.ejecutar(tarea)



    def mostrar_resultado(self, texto, pantalla):

        self.texto_generado = texto



        if self.pantalla_actual != pantalla:

            return



        self.resultado.delete("1.0", "end")

        self.resultado.insert("end", texto)



        if pantalla == "temarios":

            self.boton_generar.configure(state="normal")

        elif pantalla == "analizar":

            self.boton_analizar.configure(state="normal")



    # ======================================

    # DOCUMENTOS

    # ======================================



    def obtener_texto(self):

        if self.pantalla_actual not in (

            "temarios", "analizar"

        ):

            return ""



        return self.resultado.get(

            "1.0", "end"

        ).strip()



    def guardar_word(self):

        texto = self.obtener_texto()



        if not texto or texto.startswith(

            ("Error:", "Pepe está")

        ):

            messagebox.showwarning(

                "Documento", "Primero genera contenido."

            )

            return



        ruta = filedialog.asksaveasfilename(

            defaultextension=".docx",

            filetypes=[("Word", "*.docx")],

            initialfile="EDGAR_documento.docx"

        )



        if not ruta:

            return



        try:

            documento = Document()

            documento.add_heading(

                "Documento generado por EDGAR", 0

            )



            for linea in texto.splitlines():

                if linea.strip():

                    documento.add_paragraph(linea)



            documento.save(ruta)

            messagebox.showinfo(

                "EDGAR", "Documento Word guardado."

            )

        except Exception as error:

            messagebox.showerror("Word", str(error))



    def guardar_powerpoint(self):

        texto = self.obtener_texto()



        if not texto or texto.startswith(

            ("Error:", "Pepe está")

        ):

            messagebox.showwarning(

                "Presentación", "Primero genera contenido."

            )

            return



        ruta = filedialog.asksaveasfilename(

            defaultextension=".pptx",

            filetypes=[("PowerPoint", "*.pptx")],

            initialfile="EDGAR_presentacion.pptx"

        )



        if not ruta:

            return



        try:

            presentacion = Presentation()



            portada = presentacion.slides.add_slide(

                presentacion.slide_layouts[0]

            )

            portada.shapes.title.text = "Presentación EDGAR"

            portada.placeholders[1].text = "Creada con Pepe"



            lineas = [

                linea.strip()

                for linea in texto.splitlines()

                if linea.strip()

            ]



            for indice in range(0, len(lineas), 5):

                bloque = lineas[indice:indice + 5]



                diapositiva = presentacion.slides.add_slide(

                    presentacion.slide_layouts[1]

                )

                diapositiva.shapes.title.text = (

                    f"Tema {indice // 5 + 1}"

                )

                diapositiva.placeholders[1].text = (

                    "\n\n".join(bloque)

                )



            presentacion.save(ruta)

            messagebox.showinfo(

                "EDGAR", "PowerPoint guardado."

            )

        except Exception as error:

            messagebox.showerror(

                "PowerPoint", str(error)

            )



    # ======================================

    # CALENDARIO

    # ======================================



    def calendario(self):

        self.pantalla_actual = "calendario"

        self.limpiar()

        self.encabezado("Calendario")



        ctk.CTkLabel(

            self.contenedor,

            text="Calendario de EDGAR",

            font=("Arial", 24, "bold")

        ).pack(pady=(60, 20))



        ctk.CTkLabel(

            self.contenedor,

            text=(

                "Próximamente conectaremos Microsoft "

                "Teams para consultar tareas y entregas."

            ),

            font=("Arial", 15),

            wraplength=650

        ).pack(pady=10)





# ==========================================

# INICIAR EDGAR

# ==========================================



if __name__ == "__main__":

    app = EdgarApp()

    app.mainloop()


