import os
import yaml
import time
from bs4 import BeautifulSoup
from mailjet_rest import Client

from selenium import webdriver
from splinter import Browser, Config
chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument("--log-level=3")

from dotenv import load_dotenv
load_dotenv()

import db

def read_yaml(filename: str):
    with open(filename, "r") as f:
        data = yaml.safe_load(f)
    return data

db_queries = read_yaml("db_query.yaml")
params = read_yaml("params.yaml")

def send_email(provider: str, new_val: str):
    api_key=os.getenv("MAILJET_KEY")
    api_secret=os.getenv("MAILJET_SECRET")
    email=os.getenv("EMAIL")

    mailjet = Client(auth=(api_key, api_secret), version="v3.1")
    data = {
    'Messages': [
        {
        "From": {
            "Email": email,
            "Name": "lagenhet-alert"
        },
        "To": [
            {
            "Email": email,
            "Name": "Shaan"
            }
        ],
        "Subject": "Lägenhet alert",
        "TextPart": f"New change detected with {provider}. Change: {new_val}",
        }
    ]
    }
    _ = mailjet.send.create(data=data)
    print(_.status_code)

def return_page(link: str, wait_param: str):
    myconfig = Config(headless=True)
    browser = Browser('chrome', config=myconfig, options=chrome_options)
    browser.visit(link)
    start = time.monotonic()
    while( not browser.is_text_present(wait_param)):
        # wait until relevant page information is loaded or 5 seconds are up, whichever is faster
        if (time.monotonic() - start > 5):
            break
        pass
    page = browser.html
    browser.quit()

    return page

def check_and_update(connection, provider: str, link: str, wait_param: str):
    soup = BeautifulSoup(return_page(link=link, wait_param=wait_param), 'html.parser')
    match provider:
        case "qasa":
            check = soup.find("p", {"class": "qds-fht3xa"}).string
        case "wallenstam":
            check = soup.find("p", {"class": "object-number"})
            check = check.contents[0].string + check.contents[-1].string
        case "heimstaden":
            check = soup.find("h3", {"class": "search-result-options__summary-heading"}).string
            check = check + ' ' + soup.find("span", {"data-hose-total-nr-of-matches-nr": True}).string
    
    select_query = db_queries["SELECT"].format(value="'" + provider + "'")
    entries = db.execute_read_query(connection, select_query)
    if len(entries) == 0:
        db.execute_query(connection, db_queries["INSERT"].format(value = (provider, check)))
    else:
        # ideally should only return one row because of primary key
        old = entries[0][-1] # gets the results column from the table
        if old != check:
            db.execute_query(db_queries["UPDATE"].format(results_column="'" + check + "'", provider=provider))
            send_email(provider, new_val=check)
        
        else:
            print("no change in entries")


if __name__ == "__main__":
    connection = db.create_connection("store.sqlite")
    
    # Create a table if doesn't exist
    db.execute_query(connection, db_queries["CREATE"])
    print("Press Ctrl + Z/Ctrl + C to exit.")
    try:
        while True:
            for item in params["LINKS"]:
                name = item[0]
                wait_param = item[1]
                link = item[2]
                check_and_update(connection, name, link, wait_param)
            time.sleep(5)
    except KeyboardInterrupt:
        print("Stopping..")