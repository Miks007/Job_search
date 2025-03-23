from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
import configparser
import time
import pandas as pd
import logging
import os
import random
import sys
from typing import Dict
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from utils.parse_json_to_model import parse_json_to_model
from utils.logging import set_up_logging, delete_old_logs
from utils.set_up_driver import setup_driver
from utils.read_previous_data import read_previous_data
from utils.send_email import send_email
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

RETENTION_DAYS = 30
PORTAL_NAME = 'praca_pl'

# TODO:
# - CREATE A MASTER SCRIPT THAT WILL RUN THIS SCRIPT AND THE OTHER ONES.
# - move email sending to the master script

BASE_PATH = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
CONFIG_PATH = os.path.join(BASE_PATH, 'config.ini')
LOG_DIR_PATH = os.path.join(BASE_PATH, 'logs')
DRIVER_PATH = os.path.join(BASE_PATH, 'resources', 'chromedriver.exe')
OFFERS_FILE = os.path.join(BASE_PATH, 'data', f'offers_{PORTAL_NAME}.xlsx')
NEW_OFFERS_FILE = os.path.join(BASE_PATH, 'data', f'new_offers_{PORTAL_NAME}.xlsx')
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

def click_cookie_button(driver):
    try:
        logging.info('Clicking cookie button...')
        coockie_button = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, '//*[@id="cookiesPopup"]/div/div/div[2]/button[1]')))
        coockie_button.click()
        logging.info('Cookie button clicked')
    except Exception as e:
        error_msg = f"Error during clicking cookie button: {e}"
        raise Exception(error_msg)

def convert_date(date_str, now):
    try:
        if 'godz.' in date_str:
            hours = int(date_str.split()[0])
            return now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=hours)
        elif 'dni' in date_str:
            days = int(date_str.split()[0])
            return now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days)
        else:   
            return None
    except Exception as e:
        error_msg = f"Error during converting date: {e}"
        raise Exception(error_msg)

def read_max_page_number(driver):
    try:
        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")
        max_page_number = soup.find("a", {"class": "pagination__item pagination__item--last"})
        if max_page_number:
            return int(max_page_number.text)
        else:
            return 1
    except Exception as e:
        error_msg = f"Error during reading max page number: {e}"
        raise Exception(error_msg)

def scrapp_offers(driver: webdriver.Chrome) -> pd.DataFrame:
    """Scrape job offers from the current page.
    
    Args:
        driver: Selenium WebDriver instance
        
    Returns:
        DataFrame containing scraped job offers
    """
    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")
    offers = []
    logging.info('Scraping offers...')
    
    now = datetime.now()
    try:
        offers = []
        for offer in soup.find_all("li", class_="listing__item"):
            try:
                title_tag = offer.find("a", class_="listing__title")
                company_tag = offer.find("a", class_="listing__employer-name")
                location_tag = offer.find("span", class_="listing__location-name")
                work_model_tag = offer.find("span", class_="listing__work-model")
                details_tag = offer.find("div", class_="listing__main-details")
                posted_tag = offer.find("div", class_="listing__secondary-details")
                teaser_tag = offer.find("div", class_="listing__teaser")
                logo_tag = offer.find("img", class_="listing__logo")

                # Process offer data
                offer_data = {
                    "job_title": title_tag.text.strip() if title_tag else None,
                    "job_id": title_tag.get("data-id") if title_tag else None,
                    "job_url": title_tag.get("href") if title_tag else None,
                    "company": company_tag.text.strip() if company_tag else None,
                    "location": location_tag.text.strip() if location_tag else None,
                    "work_model": work_model_tag.text.strip() if work_model_tag else None,
                    "details": details_tag.text.strip() if details_tag else None,
                    "date_posted": posted_tag.text.strip() if posted_tag else None,
                    "description": teaser_tag.text.strip() if teaser_tag else None,
                    "logo_url": logo_tag.get("src") if logo_tag else None
                }

                offers.append(offer_data)
            except Exception as e:
                logging.error(f"Error processing offer: {str(e)}")
                continue

    except Exception as e:
        logging.error(f"Error scraping offers: {str(e)}")
    
    logging.info(f'Successfully scraped {len(offers)} offers')
    df = pd.DataFrame(offers)
    df['date_posted'] = df['date_posted'].apply(convert_date, now=now)
    df['date_scraped'] = now
    return df

def main():
    logger = set_up_logging(LOG_DIR_PATH, PORTAL_NAME)
    delete_old_logs(LOG_DIR_PATH, RETENTION_DAYS)
    
    logger.info("Starting job scraping process...")
    driver = None

    try:
        config = load_config()
        driver = setup_driver(DRIVER_PATH)
        df_old_data, last_date_scraped = read_previous_data(OFFERS_FILE)
        
        page = 1
        max_page_number = None
        df = pd.DataFrame()

        while True:
            URL = f"https://www.praca.pl/s-{config.KEYWORD}_m-{config.CITY.lower()}_{page}.html?p={config.KEYWORD}&m={config.CITY}&cr={config.DISTANCE}"
            logger.info(f"Processing page {page}")
            driver.get(URL)
            if page == 1:
                click_cookie_button(driver)
                max_page_number = read_max_page_number(driver)
                logger.info(f"Total pages to scrape: {max_page_number}")
            
            time.sleep(random.randint(3, 5))
            
            df_offers = scrapp_offers(driver)
            if df_offers.empty:
                logger.info("[BREAK] No offers found on current page")
                break
                
            df = pd.concat([df, df_offers])
            df = df.sort_values(by='date_posted', ascending=False)
            
            # Break if we've reached the max page or if we're past the last scrape date
            if page >= max_page_number:
                logger.info("[BREAK] Reached maximum page number")
                break
            
            if df_offers['date_posted'].max() < last_date_scraped:
                logger.info("[BREAK] Reached previously scraped offers")
                break
                
            page += 1
            time.sleep(random.randint(1, 3))

        logger.info('Processing scraped data...')
        try:
            if df_old_data is not None and not df_old_data.empty:
                df_old_data = pd.concat([df_old_data, df])
                df_new = df[~df['job_link'].isin(df_old_data['job_link'])]
                df = df_old_data.drop_duplicates(subset=['job_link'])
            else:
                df_new = df
        except Exception as e:
            error_msg = f"Error during processing scraped data: {e}"
            raise Exception(error_msg)

        # Ensure directories exist
        os.makedirs(os.path.dirname(OFFERS_FILE), exist_ok=True)
        os.makedirs(os.path.dirname(NEW_OFFERS_FILE), exist_ok=True)
        
        # Save results
        df.to_excel(OFFERS_FILE, index=False, engine='openpyxl')
        df_new.to_excel(NEW_OFFERS_FILE, index=False, engine='openpyxl')
        logger.info(f'Saved {len(df)} total offers and {len(df_new)} new offers')

        if not df_new.empty:
            subject = f"New offers for {config.KEYWORD}! [{datetime.now().strftime('%d-%m-%Y')}]"
            body = f"Found {len(df_new)} new offers for {config.KEYWORD} in {config.CITY} within {config.DISTANCE} km"
            # Uncomment when ready to send emails
            # send_email(config.SENDER_EMAIL, config.SENDER_PASSWORD, config.RECIPIENT_EMAIL, 
            #           subject, body, attachment_path=NEW_OFFERS_FILE)

    except Exception as e:
        logger.error(f"An error occurred: {str(e)}", exc_info=True)
        raise
    finally:
        if driver:
            driver.quit()
            logger.info("Browser closed")
    
    logger.info("Job scraping process completed")

if __name__ == "__main__":
    main()








