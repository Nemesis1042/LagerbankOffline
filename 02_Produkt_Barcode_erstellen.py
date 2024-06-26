# Schritt 1: Notwendige Bibliotheken importieren
import barcode
from barcode.writer import ImageWriter
from PIL import Image
import tkinter as tk
from tkinter import filedialog
import pandas as pd
import openpyxl 
from openpyxl import load_workbook


def barcode_erstellen(datei):
    # Schritt 2: Daten für die Barcodes aus einer Excel-Datei lesen
    try:
        if datei.endswith('.xlsx'):
            engine = 'openpyxl'
        elif datei.endswith('.ods'):
            engine = 'odf'
        else:
            print("Fehler: Dateiformat wird nicht unterstützt.")
            return
        df = pd.read_excel(datei, engine=engine, header=0)
        print(df.columns)  # Added this line to print the column names
    except ImportError as e:
        print(f"Fehler: {e}. Bitte installieren Sie die benötigte Bibliothek für die Verarbeitung von Excel-Dateien.")
        return

    barcode_type = "code128"  # Änderung zu Code 128

    # Schritt 3: Barcodes generieren und speichern
    for index, row in df.iterrows():
        # Zusammenführung von Vorname und Nachname zu einem eindeutigen String
        # Umlaute und Sonderzeichen umwandeln
        product_name = row['Product'].replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue')

        barcode_data = product_name
        ean = barcode.get_barcode_class(barcode_type)
        barcode_instance = ean(barcode_data, writer=ImageWriter())
        
        # Den Barcode als Bilddatei speichern
        output_file = f"barcode_{product_name}.png"
        barcode_instance.save(output_file)
        print(f"Barcode für {product_name} wurde erstellt und gespeichert.")

    print("Barcodes wurden erfolgreich erstellt und gespeichert.")


def ui_datei_einlesen_und_verarbeiten():
    root = tk.Tk()
    root.withdraw()  # Versteckt das Hauptfenster von Tkinter
    dateipfad = filedialog.askopenfilename(title="Wählen Sie die Excel-Datei für Barcodes", filetypes=[("Excel files", "*.ods *.xls *.xlsx")])
    if dateipfad:
        print(f"Datei ausgewählt: {dateipfad}")
        barcode_erstellen(dateipfad)
    else:
        print("Keine Datei ausgewählt.")
    
    # Diese Funktion kann nun aufgerufen werden, um die UI zu starten und die Datei auszuwählen
ui_datei_einlesen_und_verarbeiten()
