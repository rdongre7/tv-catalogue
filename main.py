from flask import Flask, render_template, request
import json
import sqlalchemy
import logging
import os
from sqlalchemy.sql import select
import requests
import time


# If `entrypoint` is not defined in app.yaml, App Engine will look for an app
# called `app` in `main.py`.
app = Flask(__name__)
searchTerms = {}

@app.route('/')
def run():
    """Return a friendly HTTP greeting."""
    return render_template("index.html")

@app.route('/search', methods = ['POST'])
def get_post_javascript_data():
  db_user = os.environ["DB_USER"]
  db_pass = os.environ["DB_PASS"]
  db_name = os.environ["DB_NAME"]
  db_socket_dir = os.environ.get("DB_SOCKET_DIR", "/cloudsql")
  cloud_sql_connection_name = os.environ["CLOUD_SQL_CONNECTION_NAME"]

  db_config = {
        "pool_size": 5,
        "max_overflow": 2,
        "pool_timeout": 30,
        "pool_recycle": 1800
    }
  pool = sqlalchemy.create_engine(
      sqlalchemy.engine.url.URL(
          drivername="mysql+pymysql",
          username=db_user,  # e.g. "my-database-user"
          password=db_pass,  # e.g. "my-database-password"
          database=db_name,  # e.g. "my-database-name"
          query={
              "unix_socket": "{}/{}".format(
                  db_socket_dir,  # e.g. "/cloudsql"
                  cloud_sql_connection_name)  # i.e "<PROJECT-NAME>:<INSTANCE-REGION>:<INSTANCE-NAME>"
          }
      ),
      **db_config
  )
  clicked=request.get_json(force=True)
  with pool.begin() as connection:
    stmt = "SELECT * FROM master"
    for i, entry in enumerate(clicked["data"]["tags"]):
      if (i == 0):
        stmt += " WHERE LOWER(tags) LIKE LOWER('%%{}%%')".format(entry)
      else: 
        stmt += " AND LOWER(tags) LIKE LOWER('%%{}%%')".format(entry)
    for i, entry in enumerate(clicked["data"]["types"]):
      if i == 0 and len(clicked["data"]["tags"]) == 0: 
        stmt += " WHERE LOWER(type) = LOWER('{}')".format(entry)
      else: 
        stmt += " OR LOWER(type) = LOWER('{}')".format(entry)
    stmt += " ORDER BY RATING DESC"
    r1 = connection.execute(stmt)
  shows = [dict(row) for row in r1]
  data = {"data": []}
  for show in shows: 
    showType = show['type'].lower()
    if (showType == "" or showType == "anime"):
      response = requests.get("https://api.jikan.moe/v3/search/anime?q="+show['name'])
      if response.status_code == 429:
        logging.error("This IP is being rate limited. Waiting 1 second and trying again.")
        time.sleep(1)
        response = requests.get("https://api.jikan.moe/v3/search/anime?q="+show['name'])
        if response.status_code == 429: 
          logging.error("Rate limits caused timeout. Please try again later.")
          return 
      if (response.status_code == 200):
        anime = response.json()['results'][0]
        data["data"].append({"name": anime['title'], "url": anime['url'], "synopsis": anime['synopsis'], "img": anime['image_url'], 
        "tags": show['tags'], "rating": show['rating']})
        continue
      else: 
        logging.error(response)
    if (showType == "" or showType == "manga"):
      response = requests.get("https://api.jikan.moe/v3/search/manga?q="+show['name'])
      if (response.status_code != 404):
        manga = response.json()['results'][0]
        data["data"].append({"name": manga['title'], "url": manga['url'], "synopsis": manga['synopsis'], "img": manga['image_url']})
        continue
  return data

if __name__ == '__main__':
    # Used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    app.run(host='localhost', port=8080, debug=True)