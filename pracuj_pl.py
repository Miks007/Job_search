from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import configparser
import time
import pandas as pd
import logging
import os
import random
import sys
from typing import Dict
from datetime import datetime
from pydantic import BaseModel, Field
from utils.parse_json_to_model import parse_json_to_model
from utils.send_email import send_email

# TODO:
# - CREATE A MASTER SCRIPT THAT WILL RUN THIS SCRIPT AND THE OTHER ONES.
# - move email sending to the master script
# - add error handling
# - add check for max page number and limit the number of pages to scrape
# - add logging

BASE_PATH = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
CONFIG_PATH = os.path.join(BASE_PATH, 'config.ini')
LOG_DIR_PATH = os.path.join(BASE_PATH, 'logs')
DRIVER_PATH = os.path.join(BASE_PATH, 'chromedriver.exe')
PRACUJ_PL_FILE = os.path.join(BASE_PATH, 'data', 'offers_pracuj_pl.xlsx')
NEW_OFFERS_FILE = os.path.join(BASE_PATH, 'data', 'new_offers.xlsx')
MONTH_MAPPING_PATH = os.path.join(BASE_PATH, 'resources', 'month_mapping.json')

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
        self.SENDER_EMAIL = self.get_config('EMAIL', 'SENDER_EMAIL')
        self.SENDER_PASSWORD = self.get_config('EMAIL', 'SENDER_PASSWORD')
        self.RECIPIENT_EMAIL = self.get_config('EMAIL', 'RECIPIENT_EMAIL')
        
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

def read_old_data(file_path=None):
    if file_path is None:
        return None, datetime.now().strftime('%d-%m-%Y')
    df = pd.read_excel(file_path)
    df['date_scraped'] = pd.to_datetime(df['date_scraped'])
    max_date_scraped = df['date_scraped'].max()
    return df, max_date_scraped

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
            date_tag = offer.find("p", {"data-test": "text-added"})  #//

            title = title_tag.text.strip() if title_tag else None
            title_link = title_tag.find("a")["href"] if title_tag and title_tag.find("a") else None
            company = company_tag.text.strip() if company_tag else None
            company_link = company_tag.find("a")["href"] if company_tag and company_tag.find("a") else None
            location = location_tag.text.strip() if location_tag else None
            salary = salary_tag.text.strip() if salary_tag else None
            
            if date_tag:
                raw_date = date_tag.text.replace("Opublikowana: ", "").strip()
                date_posted = datetime.strptime(convert_date(raw_date, month_mapping), '%d-%m-%Y')
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

def set_up_logging(log_dir_path):
    os.makedirs(log_dir_path, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = f'{log_dir_path}/pracuj_pl_{timestamp}.log'
    
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
    # logger = set_up_logging(log_dir_path)
    # logger.info("Setting up driver...")
    try:
        config = load_config()
    except Exception as e:
        logging.error(f"Error loading configuration: {e}")
        sys.exit(1)
    
    driver = setup_driver()
    df = pd.DataFrame()
    month_mapping = read_month_mapping(MONTH_MAPPING_PATH)
    
    df_old_data, last_date_scraped = read_old_data(PRACUJ_PL_FILE)
    offers_max_date = last_date_scraped
    i = 1
    while offers_max_date >= last_date_scraped:
        URL = f"https://www.pracuj.pl/praca/{config.KEYWORD};kw/{config.CITY};wp?rd={config.DISTANCE}&pn={i}"
        driver.get(URL)
        
        if i == 1:
            click_cookie_button(driver)
            
        time.sleep(random.randint(3, 5))
        
        df_offers = scrapp_offers(driver, month_mapping)
        if df_offers.empty:
            print("No more offers found")
            break
            
        df = pd.concat([df, df_offers])
        offers_max_date = df_offers['date_posted'].max()
        i += 1
        time.sleep(random.randint(1, 3))
        
    driver.quit()
    
    print('Deduplicating offers...')
    if df_old_data is not None and not df_old_data.empty:
        df_old_data = pd.concat([df_old_data, df])
        df_new = df[~df['job_link'].isin(df_old_data['job_link'])]
        df = df_old_data.drop_duplicates(subset=['job_link'])
    else:
        df_new = df
    
    print('Saving offers to excel...')

    os.makedirs(os.path.dirname(PRACUJ_PL_FILE), exist_ok=True)
    os.makedirs(os.path.dirname(NEW_OFFERS_FILE), exist_ok=True)
    
    # Save DataFrame to Excel in the base directory
    df.to_excel(PRACUJ_PL_FILE, index=False, engine='openpyxl')
    df_new.to_excel(NEW_OFFERS_FILE, index=False, engine='openpyxl')
    print('Offers saved to excel')

    if not df_new.empty:
        subject = f"New offers for {config.KEYWORD}!  [{datetime.now().strftime('%d-%m-%Y')}]"
        body = f"Please find the attached offers from Pracuj.pl for {config.KEYWORD} in {config.CITY} within {config.DISTANCE} km"

        # Send email with attachment
        #send_email(config.SENDER_EMAIL, config.SENDER_PASSWORD, config.RECIPIENT_EMAIL, subject, body, attachment_path = PRACUJ_PL_FILE)
        #send_email(config.SENDER_EMAIL, config.SENDER_PASSWORD, config.RECIPIENT_EMAIL, subject, body, attachment_path = NEW_OFFERS_FILE)
        
if __name__ == "__main__":
    main()









