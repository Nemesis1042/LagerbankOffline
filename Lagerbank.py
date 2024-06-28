#!/usr/bin/python3
# Standard library imports
import datetime
from datetime import datetime, timedelta
import os
import re
from time import sleep
import subprocess
from typing import List, Tuple, Callable

# Third-party library imports
import cv2
import psutil
import sqlite3
import numpy as np
import pandas as pd
import tkinter as tk
from tkinter import Entry, StringVar, ttk, messagebox, simpledialog, filedialog
import seaborn as sns
import pyzbar.pyzbar as pyzbar
import matplotlib.pyplot as plt

# Check and handle the import of OpenCV separately
try:
    import cv2
except ImportError as e:
    raise ImportError("Das Modul 'cv2' konnte nicht importiert werden. Stellen Sie sicher, dass es installiert ist.") from e


DB_NAME = "02_Lagerbank2024.db"  # Definiert den Namen der Datenbank

class Database:
    def __init__(self):
        self.connection = sqlite3.connect(DB_NAME)  # Stellt eine Verbindung zur SQLite-Datenbank her
        self.cursor = self.connection.cursor()  # Erstellt ein Cursor-Objekt, um SQL-Befehle auszuführen
        
    def __enter__(self):
        return self  # Unterstützung für den Kontextmanager (with-Anweisung)
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.connection.close()  # Stellt sicher, dass die Datenbankverbindung beim Verlassen des Kontexts geschlossen wird
        
    def execute_select(self, query: str, values: tuple = ()) -> List[Tuple]:
        try:
            print(f"Executing SELECT query: {query} with values: {values}")
            self.cursor.execute(query, values)
            return self.cursor.fetchall()  # Ruft alle Zeilen vom letzten ausgeführten Befehl ab und gibt sie zurück
        except sqlite3.Error as e:
            print(f"Error executing select: {e}")
            raise Exception(f"Error executing select: {e}")
        
    def execute_insert(self, query: str, values: tuple) -> int:
        try:
            print(f"Executing INSERT query: {query} with values: {values}")
            self.cursor.execute(query, values)
            self.connection.commit()  # Führt die Transaktion aus
            last_row_id = self.cursor.lastrowid  # Ruft die ID der zuletzt eingefügten Zeile ab
            if last_row_id is None:
                raise Exception("Keine Zeile eingefügt, lastrowid ist None")
            return last_row_id
        except sqlite3.Error as e:
            print(f"Fehler beim Ausführen der Einfügung: {e}")
            raise Exception("Fehler beim Ausführen der Einfügung")
    
    def execute_update(self, query: str, values: tuple) -> int:
        try:
            print(f"Executing UPDATE query: {query} with values: {values}")
            self.cursor.execute(query, values)
            self.connection.commit()  # Führt die Transaktion aus
            return self.cursor.rowcount  # Gibt die Anzahl der betroffenen Zeilen zurück
        except sqlite3.Error as e:
            print(f"Error executing update: {e}")
            raise Exception(f"Error executing update: {e}")
        
    def execute_delete(self, query: str, values: tuple) -> int:
        try:
            print(f"Executing DELETE query: {query} with values: {values}")
            self.cursor.execute(query, values)
            self.connection.commit()  # Führt die Transaktion aus
            return self.cursor.rowcount  # Gibt die Anzahl der betroffenen Zeilen zurück
        except sqlite3.Error as e:
            print(f"Error executing delete: {e}")
            raise Exception(f"Error executing delete: {e}")
        
    def delete_database(self):
        try:
            # Führt SQL-Befehle aus, um Tabellen zu löschen, falls sie existieren
            self.cursor.execute("DROP TABLE IF EXISTS Teilnehmer")
            self.cursor.execute("DROP TABLE IF EXISTS Produkt")
            self.cursor.execute("DROP TABLE IF EXISTS Konto")
            self.cursor.execute("DROP TABLE IF EXISTS Transaktion")
            self.cursor.execute("DROP TABLE IF EXISTS Produkt_Barcode")
            self.connection.commit()  # Führt die Transaktion aus
        except sqlite3.Error as e:
            print(f"Error deleting database: {e}")
            raise Exception(f"Error deleting database: {e}")

class MultitabGUI:
    def __init__(self, db: Database):
        self.db = db  # Speichert das Datenbankobjekt
        self.root = tk.Tk()  # Erstellt das Hauptfenster
        self.root.title("BuLa Online Banking")  # Setzt den Fenstertitel
        self.root.geometry("960x540")  # Setzt die Fenstergröße
        self.tab_control = ttk.Notebook(self.root)  # Erstellt ein Tab-Control-Widget
        
    def add_tab_with_content(self, name: str, content_creator: Callable):
        tab = ttk.Frame(self.tab_control)  # Erstellt einen neuen Tab
        self.tab_control.add(tab, text=name)  # Fügt den Tab dem Tab-Control hinzu
        content_creator(tab, self.db)  # Füllt den Tab mit Inhalt
        
    def run(self):
        self.tab_control.pack(expand=1, fill="both")  # Zeigt das Tab-Control an
        self.root.mainloop()  # Startet die Hauptschleife
        
    def destroy(self):
        self.root.destroy()  # Zerstört das Hauptfenster

##### Hilfsfunktionen #####

def fetch_users(db: Database) -> List[str]:
    users = [user[0] for user in db.execute_select("SELECT Name FROM Teilnehmer ORDER BY Name")]  # Ruft Benutzernamen aus der Datenbank ab
    return users

def fetch_products(db: Database) -> List[str]:
    products = [product[0] for product in db.execute_select("SELECT Beschreibung FROM Produkt ORDER BY Preis")]  # Ruft Produktbeschreibungen aus der Datenbank ab
    return products

def fetch_p_barcode(db: Database) -> str:
    p_barcode = db.execute_select("SELECT P_Barcode FROM Produkt ") # Ruft den Produktbarcode aus der Datenbank ab
    return p_barcode

def fetch_p_barcode_plus(db: Database) -> str:
    p_barcode_plus = db.execute_select("SELECT Barcode FROM Produkt_Barcode ") # Ruft den Produktbarcode aus der Datenbank ab
    return p_barcode_plus

def fetch_tn_barcode(db: Database) -> str:
    tn_barcode = db.execute_select("SELECT TN_Barcode FROM Teilnehmer ")  # Ruft den Benutzerbarcode aus der Datenbank ab
    return tn_barcode

def add_transaction(db: Database, TN_Barcode: str, P_Barcode: str, menge: int):
    try:
        # IDs basierend auf Benutzer- und Produktbarcode abrufen
        T_ID = db.execute_select("SELECT T_ID FROM Teilnehmer WHERE TN_Barcode = ?", (TN_Barcode,))
        K_ID = db.execute_select("SELECT K_ID FROM Konto WHERE T_ID = ?", (T_ID[0][0],))
        P_ID = db.execute_select("SELECT P_ID FROM Produkt WHERE P_Barcode = ?", (P_Barcode,))
        
        # Neue Transaktion einfügen und zugehörige Tabellen aktualisieren
        db.execute_insert("INSERT INTO Transaktion (K_ID, P_ID, Menge, Typ, Datum) VALUES (?, ?, ?, 'Kauf', CURRENT_TIMESTAMP)", 
                          (K_ID[0][0], P_ID[0][0], menge))
        db.execute_update("UPDATE Konto SET Kontostand = Kontostand - (SELECT Preis FROM Produkt WHERE P_ID = ?) * ? WHERE K_ID = ?", 
                          (P_ID[0][0], menge, K_ID[0][0]))
        db.execute_update("UPDATE Produkt SET Anzahl_verkauft = Anzahl_verkauft + ? WHERE P_ID = ?", 
                          (menge, P_ID[0][0]))
        print("Erfolg: Transaktion erfolgreich hinzugefügt!")
    except Exception as e:
        messagebox.showerror("Fehler", f"Fehler beim Hinzufügen der Transaktion: {e}")

def fetch_transactions(db: Database, user_id: int) -> List[Tuple]:
    transactions = db.execute_select("SELECT * FROM Transaktion WHERE K_ID = ? ORDER BY Datum DESC", (user_id,))  # Ruft Transaktionen für einen bestimmten Benutzer ab
    return transactions

def update_product_dropdowns(product_combobox: ttk.Combobox, db: Database):
    products = fetch_products(db)  # Ruft Produktbeschreibungen ab
    product_combobox['values'] = products  # Aktualisiert die Werte der Combobox
 
def update_user_dropdowns(*comboboxes, db):
    users = fetch_users(db)  # Ruft Benutzernamen ab
    for combobox in comboboxes:
        combobox['values'] = users  # Aktualisiert die Werte der Comboboxes
      
def barcode_scanner():
            cap = cv2.VideoCapture(0)
            barcode_value = None
            while True:
                ret, frame = cap.read()
                if not ret:
                    messagebox.showerror("Fehler", "Kamerafehler!")
                    cap.release()
                    cv2.destroyAllWindows()
                    return None
                decoded_objects = pyzbar.decode(frame)
                if decoded_objects:
                    barcode_value = decoded_objects[0].data.decode("utf-8")
                    if barcode_value == "Brake":
                        print("Barcode Brake erkannt")
                        cap.release()
                        cv2.destroyAllWindows()
                        return None
                    print(f"Barcode erkannt: {barcode_value}")
                    cap.release()
                    cv2.destroyAllWindows()
                    return barcode_value
                cv2.imshow("Barcode Scanner", frame)
                key = cv2.waitKey(50) # 50 ms delay
                if key & 0xFF == ord('q') or key & 0xFF == 27:  # 27 is the ASCII code for ESC
                    cap.release()
                    cv2.destroyAllWindows()
                    return None

highlighted_users = []


##### Tab-Erstellungsfunktionen #####

def create_scan_only_tab(tab: tk.Frame, db: Database):
    def scan_transaction(db: Database):
        # Lade alle notwendigen Daten einmalig
        users_barcode = [barcode[0] for barcode in fetch_tn_barcode(db)]
        produk_barcode = set([barcode[0] for barcode in fetch_p_barcode(db)])
        produk_barcode_plus = set([barcode[0] for barcode in fetch_p_barcode_plus(db)])

        print(f"Users Barcode: {users_barcode}")

        barcode_value = barcode_scanner()
        if barcode_value is None:
            messagebox.showerror("Fehler", "Kein Barcode erkannt!")
            return

        if barcode_value not in users_barcode:
            messagebox.showerror("Fehler", "User nicht gefunden!")
            return

        TN_Barcode = barcode_value
        print(f"TN_Barcode: {TN_Barcode}")

        for _ in range(6):  # Erlaubt genau sechs Produktscans
            P_Barcode = barcode_scanner()
            if P_Barcode is None:
                messagebox.showerror("Fehler", "Kein Barcode erkannt!")
                return

            if P_Barcode not in produk_barcode and P_Barcode not in produk_barcode_plus:
                messagebox.showerror("Fehler", "Produkt nicht gefunden!")
                continue  # Erlaubt dem Benutzer, einen weiteren Scanversuch zu machen, ohne die Schleife zu verlassen

            menge = 1  # Menge auf 1 setzen, da jedes Produkt einmal gescannt wird
            add_transaction(db, TN_Barcode, P_Barcode, menge)
            print("Erfolg: Transaktion erfolgreich hinzugefügt!")
            print(f"Transaktion: {TN_Barcode} hat {P_Barcode} gekauft.")
                       
                       
    scan_transaction_button = ttk.Button(tab, text="Transaktion scannen", command=lambda: scan_transaction(db))
    scan_transaction_button.grid(row=1, column=0, columnspan=2, padx=10, pady=10)
    
    
def create_watch_tab(tab: tk.Frame, db: Database):
    highlighted_users = db.execute_select("SELECT Name FROM Teilnehmer WHERE Checkout = 1")
    def watch_transactions():       
        print("Anzeige der Transaktionen...")
        print("Higlighted Users", highlighted_users)
        try: 
            # Fetch product ids, descriptions, and prices, rounding the prices to two decimal places
            produkt_infos = db.execute_select("SELECT P_ID, Beschreibung, ROUND(Preis, 2) as Preis FROM Produkt")
            
            # Create SQL parts for sum calculations and include rounded price in the column headers
            produkt_summen = ", ".join([f"SUM(CASE WHEN Transaktion.P_ID = {pid} THEN Transaktion.Menge ELSE 0 END) AS '{desc} ({preis:.2f}€)'" for pid, desc, preis in produkt_infos])
            
            sql_query = f"""
                SELECT 
                    Teilnehmer.Name,
                    Konto.Einzahlung AS Einzahlung_€,
                    printf('%04.2f', ROUND(Konto.Kontostand, 2)) AS Kontostand_€,
                    {produkt_summen}
                FROM Teilnehmer 
                JOIN Konto ON Teilnehmer.T_ID = Konto.T_ID
                LEFT JOIN Transaktion ON Konto.K_ID = Transaktion.K_ID
                GROUP BY Teilnehmer.T_ID, Teilnehmer.Name, ROUND(Konto.Kontostand, 2)
                ORDER BY Teilnehmer.Name;
            """
            result = db.execute_select(sql_query)  # Execute the dynamic SQL query to fetch transaction data
            
            # Create a DataFrame from the query result
            df = pd.DataFrame(result, columns=[desc[0] for desc in db.cursor.description])
            
            # Create a Treeview widget to display the data
            tree = ttk.Treeview(tab)
            tree["columns"] = df.columns.tolist()  # Definiere die Spalten des Treeview
            tree["show"] = "headings"  # Zeige die Überschriften der Spalten
            
            # Setze Spaltenüberschriften und konfiguriere Spalten
            for col in df.columns:
                tree.heading(col, text=col)
                tree.column(col, anchor="center")
            
            # Füge Zeilen in das Treeview ein
            for index, row in df.iterrows():
                iid = tree.insert("", "end", values=row.tolist())
                if row['Name'] in highlighted_users:
                    tree.item(iid, tags=('highlighted',))
            tree.tag_configure('highlighted', background='yellow')
            
            # Zeige das Treeview an
            tree.grid(row=1, column=0, sticky='nsew')
            tab.grid_rowconfigure(1, weight=1)
            tab.grid_columnconfigure(0, weight=1)

        except Exception as e:
            messagebox.showerror("Fehler", f"Fehler beim Ausführen der Abfrage: {e}")  # Show error message if the query fails

    watch_button = ttk.Button(tab, text="Transaktionen anzeigen", command=watch_transactions)  # Erstellt einen Button, um die Transaktionsanzeige auszulösen
    watch_button.grid(row=0, column=0, padx=10, pady=5)
   
def create_admin_tab(tab: tk.Frame, db: Database):
    print("Erstelle Admin-Tab...")
    
    def login():
        print("Login-Versuch")  # Gibt eine Nachricht aus, die einen Login-Versuch anzeigt
        entered_password = password_entry.get()  # Ruft das eingegebene Passwort ab
        if entered_password == "1":  # Überprüft, ob das Passwort korrekt ist
            create_inner_gui(tab, db)  # Erstellt das innere GUI, wenn das Passwort korrekt ist
            login_frame.grid_forget()  # Entfernt den Login-Frame
        else:
            messagebox.showerror("Fehler", "Falsches Passwort! Versuchen Sie es erneut.")  # Zeigt eine Fehlermeldung an, wenn das Passwort falsch ist
    
    def create_inner_gui(parent_tab, db):
        print("Erstelle inneres GUI...")  # Gibt eine Nachricht aus, die die Erstellung des inneren GUIs anzeigt
        tab_control = ttk.Notebook(parent_tab)  # Erstellt ein Tab-Control für das innere GUI
        
        def create_kaufstatistik_tab(tab: tk.Frame, db: Database):
            print("Erstelle Tab für Kaufstatistik...")
            try:
                sql_query = '''SELECT Produkt.Beschreibung,SUM(Transaktion.Menge) AS Anzahl_verkauft
                                FROM Produkt
                                JOIN Transaktion ON Produkt.P_ID = Transaktion.P_ID
                                GROUP BY Produkt.Beschreibung
                                ORDER BY Anzahl_verkauft DESC;
                            '''
                result = db.execute_select(sql_query)  # Führt eine SQL-Abfrage aus, um die Kaufstatistik abzurufen
                df = pd.DataFrame(result, columns=[desc[0] for desc in db.cursor.description])  # Erstellt ein DataFrame aus dem Abfrageergebnis
                tree = ttk.Treeview(tab)  # Erstellt ein Treeview-Widget, um die Daten anzuzeigen
                tree["columns"] = df.columns.tolist()  # Definiert die Spalten des Treeviews
                tree["show"] = "headings"  # Zeigt die Überschriften der Spalten an
                for col in df.columns:
                    tree.heading(col, text=col)
                    tree.column(col, anchor="center")
                for index, row in df.iterrows():
                    tree.insert("", "end", values=row.tolist())
                tree.grid(row=1, column=0, columnspan=3, sticky='nsew')
            except Exception as e:
                messagebox.showerror("Fehler", f"Fehler beim Ausführen der Abfrage: {e}")
            
        def add_user(tab: tk.Frame, db: Database):
            print("Erstelle Tab für Benutzer hinzufügen...")  # Gibt eine Nachricht aus, die die Erstellung des "Benutzer hinzufügen"-Tabs anzeigt
            
            def add_custom_user(db: Database, amount: float, barcode: str, user: str):
                try:
                    amount = float(amount)
                except ValueError:
                    messagebox.showerror("Fehler", "Ungültiger Betrag!")
                    return

                # Überprüfen, ob der Benutzer existiert
                users = fetch_users(db)  # Ruft die Liste der Benutzer ab
                new_user = user_entry.get()  # Ruft den neuen Benutzer ab
                if new_user in users:
                    messagebox.showerror("Fehler", "Benutzer bereits vorhanden!")  # Zeigt eine Fehlermeldung an, wenn der Benutzer bereits existiert
                    return
                else:
                    db.execute_insert("INSERT INTO Teilnehmer (Name, TN_Barcode) VALUES (?, ?)", (new_user, barcode))  # Fügt den neuen Benutzer mit Barcode in die Datenbank ein
                    t_id = db.execute_select("SELECT T_ID FROM Teilnehmer WHERE Name = ?", (new_user,))[0][0]  # Ruft die ID des neuen Benutzers ab
                    db.execute_insert("INSERT INTO Konto (Einzahlung, Kontostand, Eröffnungsdatum, T_ID) VALUES (?, ?, CURRENT_TIMESTAMP, ?)", (amount, amount, t_id))  # Erstellt ein neues Konto für den Benutzer mit Datum und Uhrzeit
                    db.execute_insert("INSERT INTO Transaktion (K_ID, P_ID, Menge, Typ, Datum) VALUES ((SELECT K_ID FROM Konto WHERE T_ID = ?), NULL, ?, 'Einzahlung', datetime('now', 'localtime'))", (t_id, amount))  # Fügt eine Transaktion für die Einzahlung hinzu
                    print("Erfolg: Nutzer erfolgreich hinzugefügt.")  # Gibt eine Erfolgsmeldung aus
                    def clear_entries():
                        user_entry.delete(0, tk.END)
                        barcode_entry.delete(0, tk.END)
                        initial_amount_entry.delete(0, tk.END)
                        print("Eingabefelder wurden zurückgesetzt.")

                    # Nach erfolgreichem Hinzufügen des Benutzers die Eingabefelder leeren
                    print("Erfolg: Nutzer erfolgreich hinzugefügt. Eingabefelder werden zurückgesetzt.")
                    clear_entries()
                
            def scan_barcode():
                cap = cv2.VideoCapture(0)
                barcode_value = None
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        messagebox.showerror("Fehler", "Kamerafehler!")
                        break
                    decoded_objects = pyzbar.decode(frame)
                    if decoded_objects:
                        barcode_value = decoded_objects[0].data.decode("utf-8")
                        break
                    cv2.imshow("Barcode Scanner", frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                cap.release()
                cv2.destroyAllWindows()
                return barcode_value

            user_label = ttk.Label(tab, text="Neuer Nutzer:")  # Erstellt ein Label für die Auswahl des Benutzers
            user_label.grid(row=0, column=0, padx=10, pady=5)
            user_entry = ttk.Entry(tab)  # Erstellt ein Eingabefeld für den neuen Benutzer
            user_entry.grid(row=0, column=1, padx=10, pady=5)

            barcode_label = ttk.Label(tab, text="Barcode des neuen Nutzers:")  # Erstellt ein Label für die Eingabe des Barcodes des neuen Benutzers
            barcode_label.grid(row=1, column=0, padx=10, pady=5)
            barcode_entry = ttk.Entry(tab)  # Erstellt ein Eingabefeld für den Barcode
            barcode_entry.grid(row=1, column=1, padx=10, pady=5)
            scan_button = ttk.Button(tab, text="Barcode scannen", command=lambda: barcode_entry.insert(tk.END, scan_barcode()))  # Erstellt einen Button, um den Barcode zu scannen
            scan_button.grid(row=1, column=2, padx=10, pady=5)
            
            initial_amount_label = ttk.Label(tab, text="Anfangsguthaben:")  # Erstellt ein Label für die Eingabe des Anfangsguthabens
            initial_amount_label.grid(row=2, column=0, padx=10, pady=5)
            initial_amount_entry = ttk.Entry(tab)  # Erstellt ein Eingabefeld für das Anfangsguthaben
            initial_amount_entry.grid(row=2, column=1, padx=10, pady=5)

            add_user_button = ttk.Button(tab, text="Nutzer hinzufügen", command=lambda: add_custom_user(db, float(initial_amount_entry.get()), barcode_entry.get(), user_entry.get()))  # Erstellt einen Button, um den neuen Benutzer hinzuzufügen
            add_user_button.grid(row=3, column=0, columnspan=2, pady=10)
        
        def add_fund(tab: tk.Frame, db: Database):
            print("Erstelle Tab für Einzahlungen...")  # Gibt eine Nachricht aus, die die Erstellung des "Einzahlung hinzufügen"-Tabs anzeigt
            def update_user_dropdowns(combobox):
                users = fetch_users(db)  # Ruft die Liste der Benutzer ab
                combobox['values'] = users  # Aktualisiert die Werte der Combobox
            def add_custom_fund(db: Database, user: str, amount: float):
                # Überprüfen, ob der Benutzer existiert
                users = fetch_users(db)  # Ruft die Liste der Benutzer ab
                if user not in users:
                    messagebox.showerror("Fehler", "Benutzer nicht gefunden!")  # Zeigt eine Fehlermeldung an, wenn der Benutzer nicht gefunden wird
                    return
                
                # Überprüfen, ob der Betrag gültig ist
                if amount <= 0:
                    messagebox.showerror("Fehler", "Ungültiger Betrag!")  # Zeigt eine Fehlermeldung an, wenn der Betrag ungültig ist
                    return
                
                # Guthaben des Benutzers abrufen
                user_balance = db.execute_select("SELECT Kontostand FROM Konto JOIN Teilnehmer ON Konto.T_ID = Teilnehmer.T_ID WHERE Teilnehmer.Name = ?", (user,))  # Ruft das Guthaben des Benutzers ab
                if not user_balance:
                    messagebox.showerror("Fehler", "Benutzer hat kein Guthaben!")  # Zeigt eine Fehlermeldung an, wenn der Benutzer kein Guthaben hat
                    return
                
                # Neues Guthaben berechnen
                new_balance = user_balance[0][0] + amount  # Berechnet das neue Guthaben
                
                # Guthaben aktualisieren
                db.execute_update("UPDATE Konto SET Kontostand = ? WHERE T_ID = (SELECT T_ID FROM Teilnehmer WHERE Name = ?)", (new_balance, user))  # Aktualisiert das Guthaben des Benutzers
                db.execute_insert("INSERT INTO Transaktion (K_ID, P_ID, Menge, Typ, Datum) VALUES ((SELECT K_ID FROM Konto WHERE T_ID = (SELECT T_ID FROM Teilnehmer WHERE Name = ?)), NULL, ?, 'Einzahlung', datetime('now', 'localtime'))", (user, amount))
                # Erfolgsmeldung anzeigen
                print(f"Erfolg: {amount} € erfolgreich hinzugefügt.")  # Zeigt eine Erfolgsmeldung an
                
            user_label = ttk.Label(tab, text="Benutzer auswählen:")  # Erstellt ein Label für die Auswahl des Benutzers
            user_label.grid(row=0, column=0, padx=10, pady=5)
            
            user_combobox = ttk.Combobox(tab)  # Erstellt eine Combobox für die Auswahl des Benutzers
            user_combobox.grid(row=0, column=1, padx=10, pady=5)
            update_user_dropdowns(user_combobox)  # Aktualisiert die Benutzer-Dropdown
            
            amount_label = ttk.Label(tab, text="Betrag:")  # Erstellt ein Label für die Eingabe des Betrags
            amount_label.grid(row=1, column=0, padx=10, pady=5)
            amount_entry = ttk.Entry(tab)  # Erstellt ein Eingabefeld für den Betrag
            amount_entry.grid(row=1, column=1, padx=10, pady=5)
            
            add_button = ttk.Button(tab, text="Hinzufügen", command=lambda: add_custom_fund(db, user_combobox.get(), float(amount_entry.get())))  # Erstellt einen Button, um den Betrag hinzuzufügen
            add_button.grid(row=2, column=0, columnspan=2, pady=10)
            
        def withdraw_fund(tab: tk.Frame, db: Database):
            print("Erstelle Tab für Auszahlungen...")  # Gibt eine Nachricht aus, die die Erstellung des "Auszahlung hinzufügen"-Tabs anzeigt
            def withdraw_custom_fund(db: Database, user: str, amount: float):
                # Überprüfen, ob der Benutzer existiert
                if user not in fetch_users(db):
                    messagebox.showerror("Fehler", "Benutzer nicht gefunden!")  # Zeigt eine Fehlermeldung an, wenn der Benutzer nicht gefunden wird
                    return
                
                # Überprüfen, ob der Benutzer genügend Geld hat
                user_balance = db.execute_select("SELECT Kontostand FROM Konto JOIN Teilnehmer ON Konto.T_ID = Teilnehmer.T_ID WHERE Teilnehmer.Name = ?", (user,))  # Ruft das Guthaben des Benutzers ab
                if not user_balance:
                    messagebox.showerror("Fehler", "Benutzer hat kein Guthaben!")  # Zeigt eine Fehlermeldung an, wenn der Benutzer kein Guthaben hat
                    return
                
                # Überprüfen, ob der Betrag gültig ist
                if amount <= 0:
                    messagebox.showerror("Fehler", "Ungültiger Betrag!")  # Zeigt eine Fehlermeldung an, wenn der Betrag ungültig ist
                    return
                
                # Überprüfen, ob der Benutzer genügend Geld hat
                if amount > user_balance[0][0]:
                    messagebox.showerror("Fehler", "Nicht genügend Guthaben!")  # Zeigt eine Fehlermeldung an, wenn der Benutzer nicht genügend Guthaben hat
                    return
                
                # Geld abziehen
                new_balance = user_balance[0][0] - amount  # Berechnet das neue Guthaben
                db.execute_update("UPDATE Konto SET Kontostand = ? WHERE T_ID = (SELECT T_ID FROM Teilnehmer WHERE Name = ?)", (new_balance, user))  # Aktualisiert das Guthaben des Benutzers
                db.execute_insert("INSERT INTO Transaktion (K_ID, P_ID, Menge, Typ, Datum) VALUES ((SELECT K_ID FROM Konto WHERE T_ID = (SELECT T_ID FROM Teilnehmer WHERE Name = ?)), NULL, ?, 'Auszahlung', datetime('now', 'localtime'))", (user, amount))
                print(f"Erfolg: {amount} € erfolgreich abgehoben.")  # Zeigt eine Erfolgsmeldung an
            
            user_label = ttk.Label(tab, text="Benutzer auswählen:")  # Erstellt ein Label für die Auswahl des Benutzers
            user_label.grid(row=0, column=0, padx=10, pady=5)
            
            users = fetch_users(db)  # Ruft die Liste der Benutzer ab
            user_combobox = ttk.Combobox(tab, values=users)  # Erstellt eine Combobox für die Auswahl des Benutzers
            user_combobox.grid(row=0, column=1, padx=10, pady=5)
            
            balance_label = ttk.Label(tab, text="Guthaben:")  # Erstellt ein Label für das Guthaben des Benutzers
            balance_label.grid(row=0, column=2, padx=10, pady=5)
            def update_balance_label(event):
                user = user_combobox.get()
                if user:
                    user_balance = db.execute_select("SELECT Kontostand FROM Konto JOIN Teilnehmer ON Konto.T_ID = Teilnehmer.T_ID WHERE Teilnehmer.Name = ?", (user,))
                    if user_balance:
                        balance_label.config(text=f"Guthaben: {user_balance[0][0]:.2f} €")
                    else:
                        balance_label.config(text="Guthaben: Nicht verfügbar")
                else:
                    balance_label.config(text="Guthaben: Nicht verfügbar")

            user_combobox.bind("<<ComboboxSelected>>", update_balance_label)
            
            amount_label = ttk.Label(tab, text="Betrag:")  # Erstellt ein Label für die Eingabe des Betrags
            amount_label.grid(row=1, column=0, padx=10, pady=5)
            amount_entry = ttk.Entry(tab)  # Erstellt ein Eingabefeld für den Betrag
            amount_entry.grid(row=1, column=1, padx=10, pady=5)
            
            withdraw_button = ttk.Button(tab, text="Abheben", command=lambda: withdraw_custom_fund(db, user_combobox.get(), float(amount_entry.get())))  # Erstellt einen Button, um den Betrag abzuheben
            withdraw_button.grid(row=2, column=0, columnspan=2, pady=10)
                        
        def edit_users(tab: tk.Frame, db: Database):
            print("Erstelle Tab für Nutzerbearbeitung...")  # Gibt eine Nachricht aus, die die Erstellung des "Nutzer bearbeiten"-Tabs anzeigt
            def update_user():
                selected_user = user_combobox.get()  # Ruft den ausgewählten Benutzer ab
                new_name = new_name_entry.get()  # Ruft den neuen Namen ab
                new_barcode = new_barcode_entry.get()  # Ruft den neuen Barcode ab
                if selected_user and new_name and new_barcode:
                    try:
                        db.execute_update("UPDATE Teilnehmer SET Name = ?, TN_Barcode = ? WHERE Name = ?", (new_name, new_barcode, selected_user))  # Aktualisiert den Namen und Barcode des Benutzers
                        print("Erfolg: Benutzerdaten erfolgreich aktualisiert.")  # Zeigt eine Erfolgsmeldung an
                        update_user_dropdowns(user_combobox, db=db)  # Aktualisiert die Benutzer-Dropdown
                    except Exception as e:
                        messagebox.showerror("Fehler", f"Fehler beim Aktualisieren der Benutzerdaten: {e}")  # Zeigt eine Fehlermeldung an
                else:
                    messagebox.showwarning("Warnung", "Bitte wählen Sie einen Benutzer und geben Sie einen neuen Namen und Barcode ein.")  # Zeigt eine Warnmeldung an

            user_label = ttk.Label(tab, text="Benutzer auswählen:")  # Erstellt ein Label für die Auswahl des Benutzers
            user_label.grid(row=0, column=0, padx=10, pady=5)

            users = fetch_users(db)  # Ruft die Liste der Benutzer ab
            user_combobox = ttk.Combobox(tab, values=users)  # Erstellt eine Combobox für die Auswahl des Benutzers
            user_combobox.grid(row=0, column=1, padx=10, pady=5)

            new_name_label = ttk.Label(tab, text="Neuer Name:")  # Erstellt ein Label für die Eingabe des neuen Namens
            new_name_label.grid(row=1, column=0, padx=10, pady=5)
            new_name_entry = ttk.Entry(tab)  # Erstellt ein Eingabefeld für den neuen Namen
            new_name_entry.grid(row=1, column=1, padx=10, pady=5)

            new_barcode_label = ttk.Label(tab, text="Neuer Barcode:")  # Erstellt ein Label für die Eingabe des neuen Barcodes
            new_barcode_label.grid(row=2, column=0, padx=10, pady=5)
            new_barcode_entry = ttk.Entry(tab)  # Erstellt ein Eingabefeld für den neuen Barcode
            new_barcode_entry.grid(row=2, column=1, padx=10, pady=5)
            
            def scan_barcode():
                cap = cv2.VideoCapture(0)  # Startet die Kamera
                barcode_value = None
                while True:
                    ret, frame = cap.read()  # Liest ein Bild von der Kamera
                    if not ret:
                        messagebox.showerror("Fehler", "Kamerafehler!")
                        break
                    decoded_objects = pyzbar.decode(frame)  # Dekodiert Barcodes im Bild
                    if decoded_objects:
                        barcode_value = decoded_objects[0].data.decode("utf-8")  # Speichert den Barcode-Wert
                        print("Barcode gelesen: " + barcode_value)  # Zeigt die Barcode-Information an
                        break
                    cv2.imshow("Barcode Scanner", frame)  # Zeigt das Kamerabild an
                    if cv2.waitKey(1) & 0xFF == ord('q'):  # Beendet die Schleife, wenn 'q' gedrückt wird
                        break
                cap.release()  # Gibt die Kamera frei
                cv2.destroyAllWindows()  # Schließt alle Fenster
                return barcode_value

            scan_button = ttk.Button(tab, text="Barcode scannen", command=lambda: new_barcode_entry.insert(0, barcode_scanner()))  # Erstellt einen Button zum Starten des Scans
            scan_button.grid(row=3, column=0, columnspan=2, pady=10)

            update_button = ttk.Button(tab, text="Aktualisieren", command=update_user)  # Erstellt einen Button, um die Benutzerdaten zu aktualisieren
            update_button.grid(row=4, column=0, columnspan=2, pady=10)
    
        def add_product(tab: tk.Frame, db: Database ):
            print("Erstelle Tab für Produkt hinzufügen...")  # Gibt eine Nachricht aus, die die Erstellung des "Produkt hinzufügen"-Tabs anzeigt
            def add_custom_product(db: Database, price: float, barcode: str, product: str):
                # Überprüfen, ob das Produkt bereits existiert
                products = fetch_products(db)  # Ruft die Liste der Produkte a
                if barcode in products:
                    print("Fehler: Produkt bereits vorhanden!")  # Zeigt eine Fehlermeldung an, wenn das Produkt bereits existiert
                    return
                else:
                    db.execute_insert("INSERT INTO Produkt (Beschreibung,P_Barcode, Preis, Anzahl_verkauft) VALUES (?, ?, ?, 0)", (barcode, barcode, price))  # Fügt das neue Produkt in die Datenbank ein
                    print("Erfolg: Produkt erfolgreich hinzugefügt.")  # Zeigt eine Erfolgsmeldung an
                    def clear_entries():
                        product_entry.delete(0, tk.END)  # Löscht den Inhalt des Produkt-Eingabefelds
                        add_barcode_entry.delete(0, tk.END)  # Löscht den Inhalt des Barcode-Eingabefelds
                        preis_entry.delete(0, tk.END)  # Löscht den Inhalt des Preis-Eingabefelds
                    clear_entries()  # Löscht die Eingabefelder nach dem Hinzufügen des Produkts

            product_label = ttk.Label(tab, text="Neues Produkt:")  # Erstellt ein Label für die Eingabe des neuen Produkts
            product_label.grid(row=0, column=0, padx=10, pady=5)
            product_entry = ttk.Entry(tab)
            product_entry.grid(row=0, column=1, padx=10, pady=5)
                        
            add_barcode_label = ttk.Label(tab, text="Barcode des neuen Produkts:")  # Erstellt ein Label für die Eingabe des Barcodes
            add_barcode_label.grid(row=1, column=0, padx=10, pady=5)
            add_barcode_entry = ttk.Entry(tab)  # Erstellt ein Eingabefeld für den Barcode
            add_barcode_entry.grid(row=1, column=1, padx=10, pady=5)
                        
            preis_label = ttk.Label(tab, text="Preis (€):")  # Erstellt ein Label für die Eingabe des Preises
            preis_label.grid(row=2, column=0, padx=10, pady=5)
            preis_entry = ttk.Entry(tab)  # Erstellt ein Eingabefeld für den Preis
            preis_entry.grid(row=2, column=1, padx=10, pady=5)

            add_scan_button = ttk.Button(tab, text="Barcode scannen", command=lambda: add_barcode_entry.insert(0, barcode_scanner()))  # Erstellt einen Button, um den Barcode zu scannen
            add_scan_button.grid(row=1, column=2, padx=10, pady=5)
            hinzufuegen_button = ttk.Button(tab, text="Produkt hinzufügen", command=lambda: add_custom_product(db, float(preis_entry.get()), str(add_barcode_entry.get()), str(product_entry.get())))  # Erstellt einen Button, um das Produkt hinzuzufügen
            hinzufuegen_button.grid(row=3, column=0, columnspan=3, pady=10)
            
        def add_barcode_to_product(tab: tk.Frame, db: Database):
            print("Erstelle Tab für Barcode hinzufügen...")
            def add_custom_barcode(db: Database, product: str, barcode: str):
                # Überprüfen, ob das Produkt existiert
                products = fetch_products(db)
                if product not in products:
                    messagebox.showerror("Fehler", "Produkt nicht gefunden!")
                    return
                elif barcode in products:
                    messagebox.showerror("Fehler", "Barcode bereits vorhanden!")
                    return
                else:
                    try:
                        db.execute_insert(
                            "INSERT INTO Produkt_Barcode (P_ID, Barcode) SELECT P_ID, ? FROM Produkt WHERE Beschreibung = ?",
                            (barcode, product)
                        )
                        print("Erfolg: Barcode erfolgreich hinzugefügt.")
                        update_product_dropdowns(product_combobox, db)
                        def clear_entries():
                            product_combobox.set('')
                            barcode_entry.delete(0, tk.END)
                            print("Eingabefelder wurden zurückgesetzt.")
                    except Exception as e:
                        messagebox.showerror("Fehler", f"Fehler beim Hinzufügen des Barcodes: {e}")
                    
                    
            
            product_label = ttk.Label(tab, text="Produkt auswählen:")
            product_label.grid(row=0, column=0, padx=10, pady=5)
            products = fetch_products(db)
            product_combobox = ttk.Combobox(tab, values=products)
            product_combobox.grid(row=0, column=1, padx=10, pady=5)
            
            barcode_label = ttk.Label(tab, text="Neuer Barcode:")
            barcode_label.grid(row=1, column=0, padx=10, pady=5)
            barcode_entry = ttk.Entry(tab)
            barcode_entry.grid(row=1, column=1, padx=10, pady=5)
            
            scan_button = ttk.Button(tab, text="Barcode scannen", command=lambda: barcode_entry.insert(0, barcode_scanner()))
            scan_button.grid(row=1, column=2, padx=10, pady=5)
            
            add_button = ttk.Button(tab, text="Hinzufügen", command=lambda: add_custom_barcode(db, product_combobox.get(), barcode_entry.get()))
            add_button.grid(row=2, column=0, columnspan=2, pady=10)
            update_product_dropdowns(product_combobox, db)
            
        def edit_product_prices(tab: tk.Frame, db: Database):
            print("Erstelle Tab für Preisbearbeitung...")  # Gibt eine Nachricht aus, die die Erstellung des "Produktpreise bearbeiten"-Tabs anzeigt
            def update_product_price():
                selected_product = barcode_scanner()  # Ruft das ausgewählte Produkt ab
                new_price = new_price_entry.get()  # Ruft den neuen Preis ab
                if selected_product and new_price:
                    try:
                        db.execute_update("UPDATE Produkt SET Preis = ? WHERE Beschreibung = ?", (new_price, selected_product))  # Aktualisiert den Preis des Produkts
                        print("Erfolg: Produktpreis erfolgreich aktualisiert.")  # Zeigt eine Erfolgsmeldung an
                        update_product_dropdowns(product_combobox, db)  # Aktualisiert die Produkt-Dropdown
                    except Exception as e:
                        print(f"Fehler: Fehler beim Aktualisieren des Produktpreises: {e}")  # Zeigt eine Fehlermeldung an
                else:
                    # Zeigt eine Warnung an, wenn kein Produkt ausgewählt oder kein neuer Preis eingegeben wurde
                    print("Warnung: Bitte wählen Sie ein Produkt und geben Sie einen neuen Preis ein.")
                    
            product_label = ttk.Label(tab, text="Produkt auswählen:")  # Erstellt ein Label für die Produktwahl
            product_label.grid(row=0, column=0, padx=10, pady=5)
            products = fetch_products(db)  # Ruft die Liste der verfügbaren Produkte ab
            product_combobox = ttk.Combobox(tab, values=products)  # Erstellt eine Combobox zur Auswahl eines Produkts
            product_combobox.grid(row=0, column=1, padx=10, pady=5)
            new_price_label = ttk.Label(tab, text="Neuer Preis:")  # Erstellt ein Label für die Eingabe des neuen Preises
            new_price_label.grid(row=1, column=0, padx=10, pady=5)
            new_price_entry = ttk.Entry(tab)  # Erstellt ein Eingabefeld für den neuen Preis
            new_price_entry.grid(row=1, column=1, padx=10, pady=5)
            update_button = ttk.Button(tab, text="Aktualisieren", command=update_product_price)  # Erstellt einen Button zur Aktualisierung des Preises
            update_button.grid(row=2, column=0, columnspan=2, pady=10)
            # Aktualisiert die Dropdown-Liste der Produkte mit der aktuellen Datenbank
            update_product_dropdowns(product_combobox, db=db)

        def delete_user_tab(tab: tk.Frame, db: Database):
            print("Erstelle Tab für Benutzer löschen...")
            def delete_user():
                selected_user = barcode_scanner()
                if selected_user:
                    try:
                        db.execute_update("DELETE FROM Konto WHERE T_ID = (SELECT T_ID FROM Teilnehmer WHERE Name = ?)", (selected_user,))
                        db.execute_update("DELETE FROM Teilnehmer WHERE Name = ?", (selected_user,))
                        print("Erfolg: Benutzer erfolgreich gelöscht.")
                        update_user_dropdowns(user_combobox, db=db)
                    except Exception as e:
                        print(f"Fehler: Fehler beim Löschen des Benutzers: {e}")
                else:    
                    print("Warnung: Bitte wählen Sie einen Benutzer.")
                    
            user_label = ttk.Label(tab, text="Benutzer auswählen:")  # Erstellt ein Label für die Auswahl des Benutzers
            user_label.grid(row=0, column=0, padx=10, pady=5)
            users = fetch_users(db)  # Ruft die Liste der Benutzer ab
            user_combobox = ttk.Combobox(tab, values=users)  # Erstellt eine Combobox für die Auswahl des Benutzers
            user_combobox.grid(row=0, column=1, padx=10, pady=5)
            delete_button = ttk.Button(tab, text="Benutzer löschen", command=delete_user)  # Erstellt einen Button, um den Benutzer zu löschen
            delete_button.grid(row=1, column=0, columnspan=2, pady=10)
            
        def delete_product_tab(tab: tk.Frame, db: Database):
            print("Erstelle Tab für Produkt löschen...")
            def delete_product():
                selected_product = barcode_scanner()
                if selected_product:
                    try:
                        db.execute_update("DELETE FROM Produkt WHERE Beschreibung = ?", (selected_product,))
                        print("Erfolg: Produkt erfolgreich gelöscht.")
                        update_product_dropdowns(product_combobox, db)
                    except Exception as e:
                        print(f"Fehler: Fehler beim Löschen des Produkts: {e}")
                else:
                    print("Warnung: Bitte wählen Sie ein Produkt.")
                    
            product_label = ttk.Label(tab, text="Produkt auswählen:")
            product_label.grid(row=0, column=0, padx=10, pady=5)
            products = fetch_products(db)
            product_combobox = ttk.Combobox(tab, values=products)
            product_combobox.grid(row=0, column=1, padx=10, pady=5)
            delete_button = ttk.Button(tab, text="Produkt löschen", command=delete_product)
            delete_button.grid(row=1, column=0, columnspan=2, pady=10)
        
        def create_Barcode_tab(tab: tk.Frame, db: Database):
            print("Erstelle Barcode-Tab...")
            def open_file_dialog():
                subprocess.run(["python3", "TN_Barcode_erstellen.py"])
                print("Barcode_erstellen.py wurde im gleichen Verzeichnis ausgeführt.")
            
            
            button = ttk.Button(tab, text="Barcode erstellen", command=open_file_dialog)  # Erstellt einen Button, um den Barcode-Dialog zu öffnen
            button.pack(pady=10)  # Fügt den Button zum Tab hinzu
        
        def run_backup_tab(tab: tk.Frame, db: Database):
            print("Erstelle Tab für Backup...")
            def run_backup():
                try:
                    # Datenbank in eine SQL-Datei speichern
                    with open('database_backup.sql', 'w') as f:
                        for line in db.connection.iterdump():
                            f.write('%s\n' % line)
                    print("Backup der Datenbank wurde erfolgreich erstellt.")
                except Exception as e:
                        print("Fehler beim Erstellen des Backups: {e}")
            
            backup_button = ttk.Button(tab, text="Backup erstellen", command=run_backup)
            backup_button.grid(row=0, column=0, padx=10, pady=5)
        
        def delete_database_tab(tab: tk.Frame, db: Database):
            print("Erstelle Tab für Datenbank löschen...")
            def delete_database():
                password = simpledialog.askstring("Passwort eingeben", "Bitte geben Sie das Administratorpasswort ein:", show='*')
                if password == "IchWillDieDatenbankLöschen":  # Ersetzen Sie 'richtigesPasswort' durch das tatsächliche Passwort
                    try:
                        # Datenbank in eine SQL-Datei speichern
                        with open('database_backup.sql', 'w') as f:
                            for line in db.connection.iterdump():
                                f.write('%s\n' % line)
                        print("Backup erfolgreich: Die Datenbank wurde erfolgreich gesichert.")
                        
                        # Datenbank löschen
                        db.delete_database()
                        print("Erfolg: Die Datenbank wurde erfolgreich gelöscht.")
                    except Exception as e:
                        print(f"Fehler: Fehler beim Löschen der Datenbank: {e}")
                else:
                    print("Falsches Passwort: Das eingegebene Passwort ist falsch.")
                
            delete_button = ttk.Button(tab, text="Datenbank löschen", command=delete_database)
            delete_button.grid(row=0, column=0, padx=10, pady=5)

        def Kontostand_aufteilen(tab: tk.Frame, db: Database):
            print("Erstelle Tab für Geld aufteilen...")
            def geld_aufteilen():
                kontos = db.execute_select("SELECT K_ID, Kontostand FROM Konto")
                
                zwanziger = 0
                zehner = 0
                fuenfer = 0
                zweier = 0
                einer = 0
                halber = 0
                zwanzig_cent = 0
                zehn_cent = 0
                fuenf_cent = 0
                zwei_cent = 0
                ein_cent = 0
                
                for konto in kontos:
                    kontostand = konto[1]  # Extrahiert den Kontostand aus der Liste
                    zwischenstand = round(kontostand, 2)  # Rundet den Kontostand auf zwei Nachkommastellen
                    print(zwischenstand)
                    zzwanziger = (zwischenstand // 20)
                    zwanziger = zwanziger + zzwanziger
                    zwischenstand = zwischenstand - (zzwanziger * 20)
                    zzehner = (zwischenstand // 10)
                    zehner = zehner + zzehner
                    zwischenstand = zwischenstand - (zzehner * 10)
                    zfuenfer = (zwischenstand // 5)
                    fuenfer = fuenfer + zfuenfer
                    zwischenstand = zwischenstand - (zfuenfer * 5)
                    zzweier = (zwischenstand // 2)
                    zweier = zweier + zzweier
                    zwischenstand = zwischenstand - (zzweier * 2)
                    zeiner = (zwischenstand // 1)
                    einer = einer + zeiner
                    zwischenstand = zwischenstand - (zeiner * 1)
                    zhalber = (zwischenstand // 0.5)
                    halber = halber + zhalber
                    zwischenstand = zwischenstand - (zhalber * 0.5)
                    zzwanzig_cent = (zwischenstand // 0.2)
                    zwanzig_cent = zwanzig_cent + zzwanzig_cent
                    zwischenstand = zwischenstand - (zzwanzig_cent * 0.2)
                    zzehn_cent = (zwischenstand // 0.1)
                    zehn_cent = zehn_cent + zzehn_cent
                    zwischenstand = zwischenstand - (zzehn_cent * 0.1)
                    zfuenf_cent = (zwischenstand // 0.05)
                    fuenf_cent = fuenf_cent + zfuenf_cent
                    zwischenstand = zwischenstand - (zfuenf_cent * 0.05)
                    zzwei_cent = (zwischenstand // 0.02)
                    zwei_cent = zwei_cent + zzwei_cent
                    zwischenstand = zwischenstand - (zzwei_cent * 0.02)
                    zein_cent = (zwischenstand // 0.01)
                    ein_cent = ein_cent + zein_cent
                    zwischenstand = zwischenstand - (zein_cent * 0.01)
                    
                
                print(f"20€ Scheine: {zwanziger}")
                print(f"10€ Scheine: {zehner}")
                print(f"5€ Scheine: {fuenfer}")
                print(f"2€ Münzen: {zweier}")
                print(f"1€ Münzen: {einer}")    
                print(f"50 Cent Münzen: {halber}")
                print(f"20 Cent Münzen: {zwanzig_cent}")
                print(f"10 Cent Münzen: {zehn_cent}")
                print(f"5 Cent Münzen: {fuenf_cent}")
                print(f"2 Cent Münzen: {zwei_cent}")
                print(f"1 Cent Münzen: {ein_cent}")
                
                sume = zwanziger*20 + zehner*10 + fuenfer*5 + zweier*2 + einer*1 + halber*0.5 + zwanzig_cent*0.2 + zehn_cent*0.1 + fuenf_cent*0.05 + zwei_cent*0.02 + ein_cent*0.01
                gesamt_kontostand = sum(konto[1] for konto in kontos)
                print(f"Summe: {sume:.2f}")
                print(f"Gesamtkontostand: {gesamt_kontostand:.2f} €")
                     
            geld_aufteilen_button = ttk.Button(tab, text="Geld aufteilen", command=geld_aufteilen)
            geld_aufteilen_button.grid(row=0, column=0, padx=10, pady=5)
            
        def checkout(tab: tk.Frame, db: Database):
            print("Erstelle Tab für Checkout...")
            def last_day():
                def Kontosant_in_geld(kontostand):
                    if kontostand:
                        kontostand_value = kontostand[0][0]  # Zugriff auf den ersten Wert der ersten Zeile
                        zwischenstand = round(kontostand_value, 2)  # Rundet den Kontostand auf zwei Nachkommastellen
                        print(zwischenstand)
                    zwanziger = zehner = fuenfer = zweier = einer = halber = 0
                    zwanzig_cent = zehn_cent = fuenf_cent = zwei_cent = ein_cent = 0
                    
                    zzwanziger = zwischenstand // 20
                    zwanziger += zzwanziger
                    zwischenstand -= zzwanziger * 20
                    zzehner = zwischenstand // 10
                    zehner += zzehner
                    zwischenstand -= zzehner * 10
                    zfuenfer = zwischenstand // 5
                    fuenfer += zfuenfer
                    zwischenstand -= zfuenfer * 5
                    zzweier = zwischenstand // 2
                    zweier += zzweier
                    zwischenstand -= zzweier * 2
                    zeiner = zwischenstand // 1
                    einer += zeiner
                    zwischenstand -= zeiner * 1
                    zhalber = zwischenstand // 0.5
                    halber += zhalber
                    zwischenstand -= zhalber * 0.5
                    zzwanzig_cent = zwischenstand // 0.2
                    zwanzig_cent += zzwanzig_cent
                    zwischenstand -= zzwanzig_cent * 0.2
                    zzehn_cent = zwischenstand // 0.1
                    zehn_cent += zzehn_cent
                    zwischenstand -= zzehn_cent * 0.1
                    zfuenf_cent = zwischenstand // 0.05
                    fuenf_cent += zfuenf_cent
                    zwischenstand -= zfuenf_cent * 0.05
                    zzwei_cent = zwischenstand // 0.02
                    zwei_cent += zzwei_cent
                    zwischenstand -= zzwei_cent * 0.02
                    zein_cent = zwischenstand // 0.01
                    ein_cent += zein_cent
                    zwischenstand -= zein_cent * 0.01
                    
                    print(f"20€ Scheine: {zwanziger}")
                    print(f"10€ Scheine: {zehner}")
                    print(f"5€ Scheine: {fuenfer}")
                    print(f"2€ Münzen: {zweier}")
                    print(f"1€ Münzen: {einer}")    
                    print(f"50 Cent Münzen: {halber}")
                    print(f"20 Cent Münzen: {zwanzig_cent}")
                    print(f"10 Cent Münzen: {zehn_cent}")
                    print(f"5 Cent Münzen: {fuenf_cent}")
                    print(f"2 Cent Münzen: {zwei_cent}")
                    print(f"1 Cent Münzen: {ein_cent}")
                    
                    sume = zwanziger * 20 + zehner * 10 + fuenfer * 5 + zweier * 2 + einer * 1 + halber * 0.5 + zwanzig_cent * 0.2 + zehn_cent * 0.1 + fuenf_cent * 0.05 + zwei_cent * 0.02 + ein_cent * 0.01
                    print(f"Summe: {sume:.2f}")
                    print(f"Gesamtkontostand: {kontostand_value:.2f} €")
                    
                    return zwanziger, zehner, fuenfer, zweier, einer, halber, zwanzig_cent, zehn_cent, fuenf_cent, zwei_cent, ein_cent
                    
                users = fetch_users(db)
                benutzer_id = tn_combobox.get()
                
                if not benutzer_id:
                    print("Bitte wählen Sie einen Teilnehmer aus.")
                    return
                if benutzer_id not in users:
                    print("Der ausgewählte Teilnehmer existiert nicht.")
                    return
                
                kontostand = db.execute_select("SELECT Kontostand FROM Konto WHERE T_ID = (SELECT T_ID FROM Teilnehmer WHERE Name = ?)", (benutzer_id,))
                geldwerte = Kontosant_in_geld(kontostand)
                if geldwerte is None:
                    zwanziger = zehner = fuenfer = zweier = einer = halber = zwanzig_cent = zehn_cent = fuenf_cent = zwei_cent = ein_cent = 0
                else:
                    zwanziger, zehner, fuenfer, zweier, einer, halber, zwanzig_cent, zehn_cent, fuenf_cent, zwei_cent, ein_cent = geldwerte
                checkout_ui(benutzer_id, kontostand[0][0] if kontostand else 0, zwanziger, zehner, fuenfer, zweier, einer, halber, zwanzig_cent, zehn_cent, fuenf_cent, zwei_cent, ein_cent)
            def checkout_ui(benutzer_id, kontostand, zwanziger, zehner, fuenfer, zweier, einer, halber, zwanzig_cent, zehn_cent, fuenf_cent, zwei_cent, ein_cent):
                        checkout_window = tk.Toplevel()
                        checkout_window.title("Checkout Nachverfolgung")
                        checkout_window.geometry("540x540")
                        
                        tk.Label(checkout_window, text="Checkout Status:").grid(row=0, column=0, padx=10, pady=10)
                        status_label = tk.Label(checkout_window, text="Wird verarbeitet...")
                        status_label.grid(row=0, column=1, padx=10, pady=10)
                        tk.Label(checkout_window, text="Benutzer:").grid(row=1, column=0, padx=10, pady=10)
                        benutzer_label = tk.Label(checkout_window, text=benutzer_id)
                        benutzer_label.grid(row=1, column=1, padx=10, pady=10)
                        tk.Label(checkout_window, text="Kontostand:").grid(row=1, column=0, padx=10, pady=10)
                        kontostand_label = tk.Label(checkout_window, text=f"{kontostand:.2f} €")
                        kontostand_label.grid(row=2, column=1, padx=10, pady=10)
                        tk.Label(checkout_window, text="Benötigte Geldaufteilung:").grid(row=1, column=0, padx=10, pady=10)
                        aufteilung_label = tk.Label(checkout_window, text="")
                        aufteilung_label.grid(row=3, column=1, padx=10, pady=10)
                        
                        def show_aufteilung():
                            aufteilung_text = (
                                f"20€ Scheine: {zwanziger}\n"
                                f"10€ Scheine: {zehner}\n"
                                f"5€ Scheine: {fuenfer}\n"
                                f"2€ Münzen: {zweier}\n"
                                f"1€ Münzen: {einer}\n"
                                f"50 Cent Münzen: {halber}\n"
                                f"20 Cent Münzen: {zwanzig_cent}\n"
                                f"10 Cent Münzen: {zehn_cent}\n"
                                f"5 Cent Münzen: {fuenf_cent}\n"
                                f"2 Cent Münzen: {zwei_cent}\n"
                                f"1 Cent Münzen: {ein_cent}"
                            )
                            aufteilung_label.config(text=aufteilung_text)
                        
                        show_aufteilung()
                        
                        def update_status():
                            db.execute_update("UPDATE Konto SET Kontostand = 0 WHERE T_ID = (SELECT T_ID FROM Teilnehmer WHERE Name = ?)", (benutzer_id,))
                            print(f"Kontostand von Benutzer {benutzer_id} wurde auf 0 gesetzt.")
                            status_label.config(text="Checkout abgeschlossen.")
                            highlighted_users.append(benutzer_id)
                            db.execute_update("UPDATE Teilnehmer SET Checkout = 1 WHERE Name = ?", (benutzer_id,))
                            print("Higlighted Users", highlighted_users)
                            sleep(2)
                            checkout_window.destroy()
                        
                        
                        checkout_button = tk.Button(checkout_window, text="Checkout bestätigen", command=update_status)
                        checkout_button.grid(row=4, column=0, columnspan=2, pady=10)
                         
            tn_label = ttk.Label(tab, text="Teilnehmer auswählen:")
            tn_label.grid(row=0, column=0, padx=10, pady=5)
            tn_combobox = ttk.Combobox(tab)
            tn_combobox.grid(row=0, column=1, padx=10, pady=5)
            users = fetch_users(db)
            tn_combobox["values"] = users
            
            checkout_button = ttk.Button(tab, text="Checkout", command=last_day)
            checkout_button.grid(row=1, column=0, columnspan=2, pady=10)
            
        def fetch_participants(db):
            query = '''
                SELECT T_ID FROM Teilnehmer
            '''
            result = db.execute_select(query)
            return [row[0] for row in result]

        def calculate_future_expenses(participant_id, current_date, db):
            # Summe der bisherigen Ausgaben des Teilnehmers berechnen
            query = '''
                SELECT SUM(P.Preis * T.Menge) AS TotalSpent
                FROM Transaktion T
                JOIN Produkt P ON T.P_ID = P.P_ID
                JOIN Konto K ON T.K_ID = K.K_ID
                JOIN Teilnehmer TN ON K.T_ID = TN.T_ID
                WHERE TN.T_ID = ? AND T.Datum <= ?
            '''
            result = db.execute_select(query, (participant_id, current_date))
            total_spent = result[0][0] if result[0][0] is not None else 0

            # Tägliche Ausgaben berechnen
            query = '''
                SELECT DATE(T.Datum) AS TransDate, SUM(P.Preis * T.Menge) AS DailySpent
                FROM Transaktion T
                JOIN Produkt P ON T.P_ID = P.P_ID
                JOIN Konto K ON T.K_ID = K.K_ID
                JOIN Teilnehmer TN ON K.T_ID = TN.T_ID
                WHERE TN.T_ID = ? AND T.Datum <= ?
                GROUP BY DATE(T.Datum)
            '''
            result = db.execute_select(query, (participant_id, current_date))
            daily_expenses = [row[1] for row in result]
            num_days = len(daily_expenses)

            if num_days == 0:
                avg_daily_expense = 0
            else:
                avg_daily_expense = sum(daily_expenses) / num_days

            # Zukünftige geschätzte Ausgaben bis zum Ende des Lagers
            # Berechne das Enddatum des Lagers
            query = '''
                SELECT Wert
                FROM Einstellungen
                WHERE Name = 'Lagerdauer'
            '''
            result = db.execute_select(query)
            lager_dauer = int(result[0][0])

            query = '''
                SELECT Wert
                FROM Einstellungen
                WHERE Name = 'ErsterTag'
            '''
            result = db.execute_select(query)
            erster_tag = datetime.strptime(result[0][0], '%Y-%m-%d').date()

            last_day = erster_tag + timedelta(days=lager_dauer)

            # Berechne die verbleibenden Tage bis zum letzten Tag des Lagers
            days_remaining = (last_day - current_date).days
            future_expenses_estimate = avg_daily_expense * days_remaining

            return total_spent, future_expenses_estimate

        def check_balance_sufficiency(participant_id, db):
            current_date = datetime.today().date()
            total_spent, future_expenses_estimate = calculate_future_expenses(participant_id, current_date, db)

            # Guthaben des Teilnehmers abrufen
            query = '''
                SELECT Kontostand
                FROM Konto
                WHERE T_ID = ?
            '''
            result = db.execute_select(query, (participant_id,))

            available_balance = result[0][0] if result else 0
            endkonto = available_balance - future_expenses_estimate
            print(f"total_spent: {total_spent}")
            print(f"future_expenses_estimate: {future_expenses_estimate}")
            print(f"available_balance: {available_balance}")
            print(f"endkonto: {endkonto}")

            return endkonto,total_spent, future_expenses_estimate, available_balance

        def create_ausgaben_statistik_tab(tab, db):
            # Teilnehmer ID Eingabefeld und Label
            participant_id_label = ttk.Label(tab, text="Teilnehmer ID:")
            participant_id_label.grid(row=0, column=0, padx=10, pady=10)

            participant_id_var = StringVar()
            participant_id_combobox = ttk.Combobox(tab, textvariable=participant_id_var)
            participant_id_combobox['values'] = fetch_participants(db)
            participant_id_combobox.grid(row=0, column=1, padx=10, pady=10)

            # Button zur Überprüfung des Guthabens
            def update_labels():
                endkonto,total_spent, future_expenses_estimate, available_balance = check_balance_sufficiency(participant_id_var.get(), db)
                gesamtausgaben_wert_label.config(text=f"{total_spent:.2f}")
                zukunftige_ausgaben_wert_label.config(text=f"{future_expenses_estimate:.2f}")
                kontostand_wert_label.config(text=f"{available_balance:.2f}")
                end_kontostand_wert_label.config(text=f"{endkonto:.2f}")

            endkonto,total_spent, future_expenses_estimate, available_balance = check_balance_sufficiency(participant_id_var.get(), db)
            gesamtausgaben_label = ttk.Label(tab, text="Gesamtausgaben des Teilnehmers:")
            gesamtausgaben_label.grid(row=1, column=0, padx=10, pady=10)
            gesamtausgaben_wert_label = ttk.Label(tab, text=f"{total_spent:.2f}")
            gesamtausgaben_wert_label.grid(row=1, column=1, padx=10, pady=10)

            zukunftige_ausgaben_label = ttk.Label(tab, text="Geschätzte zukünftige Ausgaben:")
            zukunftige_ausgaben_label.grid(row=2, column=0, padx=10, pady=10)
            zukunftige_ausgaben_wert_label = ttk.Label(tab, text=f"{future_expenses_estimate:.2f}")
            zukunftige_ausgaben_wert_label.grid(row=2, column=1, padx=10, pady=10)

            kontostand_label = ttk.Label(tab, text="Verfügbares Guthaben:")
            kontostand_label.grid(row=3, column=0, padx=10, pady=10)
            kontostand_wert_label = ttk.Label(tab, text=f"{available_balance:.2f}")
            kontostand_wert_label.grid(row=3, column=1, padx=10, pady=10)
            
            end_kontostand_label = ttk.Label(tab, text="Endgültiger Kontostand:")
            end_kontostand_label.grid(row=4, column=0, padx=10, pady=10)
            end_kontostand_wert_label = ttk.Label(tab, text=f"{endkonto:.2f}")
            end_kontostand_wert_label.grid(row=4, column=1, padx=10, pady=10)

            check_button = ttk.Button(tab, text="Guthaben überprüfen", command=update_labels)
            check_button.grid(row=5, column=0, columnspan=2, padx=10, pady=10)

        def create_Einstellungen_tab(tab, db):
            def set_lager_dauer():
                try:
                    lager_dauer = int(lager_dauer_entry.get())
                    print(f"Lagerdauer: {lager_dauer}")
                    db.execute_update("UPDATE Einstellungen SET Wert = ? WHERE Name = 'Lagerdauer'", (lager_dauer,))
                    print("Lagerdauer erfolgreich aktualisiert.")
                except Exception as e:
                    print(f"Fehler beim Aktualisieren der Lagerdauer: {e}")

            def set_first_Day():
                try:
                    first_day = first_day_entry.get()
                    print(f"Erster Tag: {first_day}")
                    db.execute_update("UPDATE Einstellungen SET Wert = ? WHERE Name = 'ErsterTag'", (first_day,))
                    print("Erster Tag erfolgreich aktualisiert.")
                except Exception as e:
                    print(f"Fehler beim Aktualisieren des ersten Tags: {e}")

            # First Day Widgets
            first_day_label = ttk.Label(tab, text="Erster Tag:")
            first_day_label.grid(row=0, column=0, padx=10, pady=10)
            first_day_entry = ttk.Entry(tab)
            first_day_entry.grid(row=0, column=1, padx=10, pady=10)

            # Lager Dauer Widgets
            lager_dauer_label = ttk.Label(tab, text="Lagerdauer (Tage):")
            lager_dauer_label.grid(row=1, column=0, padx=10, pady=10)
            lager_dauer_entry = ttk.Entry(tab)
            lager_dauer_entry.grid(row=1, column=1, padx=10, pady=10)

            # Submit Button
            submit_button = ttk.Button(tab, text="Submit", command=lambda: [set_lager_dauer(), set_first_Day()])
            submit_button.grid(row=2, column=0, columnspan=2, padx=10, pady=10)

        
        def create_inner_tab(parent, name, command):
            inner_tab = ttk.Frame(parent)
            command(inner_tab, db) 
            parent.add(inner_tab, text=name)

        def create_tabs(tab_control):
            create_inner_tab(tab_control, "Einstellungen", create_Einstellungen_tab)
            create_inner_tab(tab_control, "Kaufstatistik", create_kaufstatistik_tab)
            create_inner_tab(tab_control, "Ausgabenstatistik", create_ausgaben_statistik_tab)
            create_inner_tab(tab_control, "Geld aufteilen", Kontostand_aufteilen)
            create_inner_tab(tab_control, "Nutzer hinzufügen", add_user) 
            create_inner_tab(tab_control, "Einzahlung hinzufügen", add_fund) 
            create_inner_tab(tab_control, "Auszahlung hinzufügen", withdraw_fund)  
            create_inner_tab(tab_control, "Nutzer bearbeiten", edit_users) 
            create_inner_tab(tab_control, "Produkt hinzufügen", add_product)
            create_inner_tab(tab_control, "Produktpreise bearbeiten", edit_product_prices)
            create_inner_tab(tab_control, "Barcode hinzufügen", add_barcode_to_product)
            create_inner_tab(tab_control, "Nutzer löschen", delete_user_tab)
            create_inner_tab(tab_control, "Produkt löschen", delete_product_tab)
            create_inner_tab(tab_control, "Checkout", checkout)
            create_inner_tab(tab_control, "Barcode",create_Barcode_tab)
            create_inner_tab(tab_control, "Backup", run_backup_tab)  
            create_inner_tab(tab_control, "Datenbank löschen", delete_database_tab)
        
        create_tabs(tab_control)
        tab_control.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

    login_frame = ttk.Frame(tab)
    login_frame.grid(row=0, column=0, padx=10, pady=10)
    password_label = ttk.Label(login_frame, text="Passwort:")
    password_label.grid(row=0, column=0, padx=10, pady=5)
    password_entry = ttk.Entry(login_frame, show="*")
    password_entry.grid(row=0, column=1, padx=10, pady=5)
    
    login_button = ttk.Button(login_frame, text="Einloggen", command=login)
    login_button.grid(row=1, column=0, columnspan=2, padx=10, pady=5)

##### Main Function #####

def main():
    os.system("python3 02_DB_erstellen.py")
    
    with Database() as db:
        gui = MultitabGUI(db)
        gui.add_tab_with_content("Kauf", create_scan_only_tab)
        gui.add_tab_with_content("Überwachung", create_watch_tab)
        gui.add_tab_with_content("Admin",create_admin_tab)
        gui.run()

if __name__ == "__main__":
    main()
