#!/usr/bin/python3
import sqlite3

datenbankname = "02_Lagerbank2024.db"

def create_database(datenbankname):
    # Verbindung zur Datenbank herstellen
    connection = sqlite3.connect(datenbankname)
    cursor = connection.cursor()

    # Tabelle "Produkte" erstellen
    cursor.execute('''CREATE TABLE IF NOT EXISTS Produkt (
        P_ID INTEGER PRIMARY KEY AUTOINCREMENT,
        Beschreibung VARCHAR(100),
        P_Barcode VARCHAR(255),  -- Hauptbarcode für das Produkt
        Preis DECIMAL(10, 2),
        Anzahl_verkauft INT
        
    );
    
    ''')

    # Tabelle "Teilnehmer" erstellen
    cursor.execute('''CREATE TABLE IF NOT EXISTS Teilnehmer (
        T_ID INTEGER PRIMARY KEY AUTOINCREMENT, 
        Name VARCHAR(50),
        TN_Barcode VARCHAR(255),  -- Spalte für Barcode hinzugefügt
        Checkout BOOLEAN DEFAULT 0
    );
    
    ''')

    # Tabelle "Konto" erstellen
    cursor.execute('''CREATE TABLE IF NOT EXISTS Konto (
        K_ID INTEGER PRIMARY KEY AUTOINCREMENT,
        Einzahlung DECIMAL(10, 2),
        Kontostand DECIMAL(10, 2),
        Eröffnungsdatum DATE,
        T_ID INT,
        FOREIGN KEY (T_ID) REFERENCES Teilnehmer(T_ID)
    );
    
    ''')
    
    # Tabelle "Transaktion" erstellen
    cursor.execute('''CREATE TABLE IF NOT EXISTS Transaktion (
        TRANS_ID INTEGER PRIMARY KEY AUTOINCREMENT,
        K_ID INT,
        P_ID INT,  -- Spalte für den Fremdschlüssel zur Produkt-Tabelle
        Typ VARCHAR(50),
        Menge INT,
        Datum DATE,
        FOREIGN KEY (K_ID) REFERENCES Konto(K_ID),
        FOREIGN KEY (P_ID) REFERENCES Produkt(P_ID)  -- Fremdschlüsselbeziehung zu Produkt
    );
    ''')
    
    # Neue Tabelle für zusätzliche Produkt-Barcodes
    cursor.execute('''CREATE TABLE IF NOT EXISTS Produkt_Barcode (
        PB_ID INTEGER PRIMARY KEY AUTOINCREMENT,
        P_ID INT,
        Barcode VARCHAR(255),
        FOREIGN KEY (P_ID) REFERENCES Produkt(P_ID)
    );
    ''')
    
    cursor.execute('''INSERT INTO Teilnehmer (Name, TN_Barcode) VALUES ('Break', 'Break')''')

    # Verbindung schließen
    connection.close()
    print(f'Datenbank "{datenbankname}" wurde erfolgreich erstellt!')

create_database(datenbankname)
