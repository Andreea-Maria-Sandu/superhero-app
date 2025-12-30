# CONEXIUNEA CU BAZA DE DATE

#modul standard python(se citesc variabilele de mediu+accesez sistemul de operare)
import os

#importa functia care citeste fisierul .env + incarca variabilele din el in mediul de rulare
from dotenv import load_dotenv

#create_engine -> creeaza conexiunea catre baza de date (obiectivul central prin care fac query-uri SQL)
#conexiunea se deschide atunci cand se foloseste baza de date
from sqlalchemy import create_engine

#cauta fisierul .env + citeste liniile din el + le pune ca variabile de mediu
load_dotenv()

#ia valoarea variabilei DATABASE_URL din mediu (stringul acela cu root + parola)
DATABASE_URL = os.getenv("DATABASE_URL")

#verificare importanta pentru evitarea bug-urilor(daca db nu exista aplicatia se opreste , dar nu crapa)
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing. Create a .env file in project root.")

#Engine-ul SQLAlchemy
#Engine = obiect care stie unde este baza de date + ce driver foloseste (pymysql) => folosit la query-uri
#pool_pre_ping = True => verifica automat daca conexiunea la DB mai este valida
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
