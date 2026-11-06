import pandas as pd
import requests
import folium
from flask import Flask,render_template
import dt

dt.make_map()
app = Flask(__name__)


@app.route("/")
def hello_world():
  return render_template('map.html')


if __name__ == "__main__":
  app.run(debug=True)