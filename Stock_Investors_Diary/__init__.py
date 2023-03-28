from flask import Flask
# from flask_cors import CORS
import pymongo
from dotenv import load_dotenv
import os
from datetime import timedelta

app = Flask(__name__)
# CORS(app)
load_dotenv()
app.secret_key = os.getenv("SECRET_KEY")
app.permanent_session_lifetime = timedelta(minutes=5)
app.jinja_env.globals.update(zip=zip)
DEFAULT_CONNECTION_URL = os.getenv("DEFAULT_CONNECTION_URL")
DB_NAME = os.getenv("DATABASE_NAME")
client = pymongo.MongoClient(DEFAULT_CONNECTION_URL)
db = client[DB_NAME]

from Stock_Investors_Diary import routes
