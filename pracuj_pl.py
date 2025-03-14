from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import configparser
import time
import pandas as pd
import logging
from datetime import datetime
import os
import random
import sys
from typing import Dict, Type, TypeVar, Optional
from datetime import datetime
import json
from pydantic import BaseModel, Field
from utils.parse_json_to_model import parse_json_to_model

BASE_PATH = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
CONFIG_PATH = os.path.join(BASE_PATH, 'config.ini')
LOG_DIR_PATH = os.path.join(BASE_PATH, 'logs')
DRIVER_PATH = os.path.join(BASE_PATH, 'chromedriver.exe')
OUTPUT_FILE = os.path.join(BASE_PATH, 'offers_pracuj_pl.xlsx')
MONTH_MAPPING_PATH = os.path.join(BASE_PATH, 'month_mapping.json')

class Language(BaseModel):
    name: str
    months: Dict[str, str]

class MonthMapping(BaseModel):
    languages: Dict[str, Language] = Field(..., description="Mapping of language codes to month names")

class Config:
    def __init__(self, config_path=CONFIG_PATH):
        self.config = configparser.ConfigParser(interpolation=None)
        config_file = os.path.abspath(config_path)
        if not self.config.read(config_file):
            raise FileNotFoundError(f"Configuration file '{config_file}' not found or is empty.")

        self.KEYWORD = self.get_config('JOB', 'KEYWORD')
        self.CITY = self.get_config('JOB', 'CITY')
        self.DISTANCE = self.get_config('JOB', 'DISTANCE')
        
        # Decrypt the credentials
        #try:
            #cipher_suite = Fernet(CRYPTO_KEY)
            #self.USERNAME = cipher_suite.decrypt(ast.literal_eval(self.USERNAME)).decode('utf-8')
            #self.PASSWORD = cipher_suite.decrypt(ast.literal_eval(self.PASSWORD)).decode('utf-8')
        #except Exception as e:
            #raise Exception(f"Error: Failed to decrypt credentials: {str(e)}")

    def get_config(self, section, key):
        try:
            return self.config[section][key]
        except KeyError:
            error_msg = f"Missing '{key}' in section '{section}' of the configuration file."
            raise KeyError(error_msg)
        
        
def load_config(config_path=CONFIG_PATH):
    """Loads configuration from the specified config file."""
    try:
        config = Config(config_path)
        logging.info("Configuration loaded successfully.")
        return config
    except Exception as e:
        error_msg = f"Error during reading config.ini file: {e}"
        raise KeyError(error_msg)

def read_last_date_scraped(file_path):
    df = pd.read_excel(file_path)
    df['date_scraped'] = pd.to_datetime(df['date_scraped'])
    max_date_scraped = df['date_scraped'].max()
    return max_date_scraped

def setup_driver():
    webdriver_path = DRIVER_PATH

    service = Service(webdriver_path)

    options = Options()
    #options.add_argument("--headless")

    driver = webdriver.Chrome(service=service, options=options)
    return driver

def click_cookie_button(driver):
    print('Clicking cookie button...')
    button = driver.find_element(By.XPATH, "//button[@data-test='button-submitCookie']")
    button.click()
    print('Cookie button clicked')

## ----------------------------------------- OFFERS -----------------------------------------  

def read_month_mapping(file_path):
    with open(file_path, 'r') as file:
        month_mapping = parse_json_to_model(file_path, MonthMapping)
    return month_mapping

def convert_date(date_str, month_mapping):
    parts = date_str.split()
    if len(parts) == 3:  # Ensure the format is correct
        day, month, year = parts
        month_num = month_mapping.languages['pl'].months.get(month.lower(), "00")  # Get month number
        return f"{day}-{month_num}-{year}"  # Return in dd-mm-yyyy format
    else:
        print(f"Invalid date format: {date_str}")
    return date_str

def scrapp_offers(driver, month_mapping):
    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")
    offers = []
    print('Scraping offers...')
    try:
        for offer in soup.find_all("div", {"data-test": "default-offer"}):
            title_tag = offer.find("h2", {"data-test": "offer-title"})
            company_tag = offer.find("h3", {"data-test": "text-company-name"})
            location_tag = offer.find("h4", {"data-test": "text-region"})
            salary_tag = offer.find("span", {"data-test": "offer-salary"})
            date_tag = offer.find("p", {"data-test": "text-added"})  # Extracts the posting date

            title = title_tag.text.strip() if title_tag else None
            title_link = title_tag.find("a")["href"] if title_tag and title_tag.find("a") else None
            company = company_tag.text.strip() if company_tag else None
            company_link = company_tag.find("a")["href"] if company_tag and company_tag.find("a") else None
            location = location_tag.text.strip() if location_tag else None
            salary = salary_tag.text.strip() if salary_tag else None
            
            if date_tag:
                raw_date = date_tag.text.replace("Opublikowana: ", "").strip()
                date_posted = convert_date(raw_date, month_mapping)
            else:
                date_posted = None

            offers.append({
                "title": title,
                "job_link": title_link,
                "company": company,
                "company_link": company_link,
                "location": location,
                "salary": salary,
                "date_posted": date_posted,
            })
    except Exception as e:
        print(f"Error: {e}")
    print('Offers scraped')
    df= pd.DataFrame(offers)
    df['date_scraped'] = datetime.now().strftime('%d-%m-%Y')
    return df


def set_up_logging():
    os.makedirs('logs', exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = f'logs/pracuj_pl_{timestamp}.log'
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()  
        ]
    )
    logger = logging.getLogger(__name__)
    return logger

def main():
    # logger = set_up_logging()
    # logger.info("Setting up driver...")
    try:
        config = load_config()
    except Exception as e:
        logging.error(f"Error loading configuration: {e}")
        sys.exit(1)
    
    driver = setup_driver()
    df = pd.DataFrame()
    month_mapping = read_month_mapping(MONTH_MAPPING_PATH)
    for i in range(1, 3):
        URL = f"https://www.pracuj.pl/praca/{config.KEYWORD};kw/{config.CITY};wp?rd={config.DISTANCE}&pn={i}"
        driver.get(URL)
        if i == 1:
            click_cookie_button(driver)
        time.sleep(random.randint(3, 5))
        df_offers = scrapp_offers(driver, month_mapping)
        df = pd.concat([df, df_offers])
        time.sleep(random.randint(1, 3))
    driver.quit()
    
    print('Saving offers to excel...')
    # Save DataFrame to Excel in the base directory
    df.to_excel(OUTPUT_FILE, index=False, engine='openpyxl')
    print('Offers saved to excel')

if __name__ == "__main__":
    main()









