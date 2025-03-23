from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

def setup_driver(DRIVER_PATH):
    try:
        webdriver_path = DRIVER_PATH
        service = Service(webdriver_path)
        options = Options()
        #options.add_argument("--headless")

        driver = webdriver.Chrome(service=service, options=options)
        return driver
    except Exception as e:
        error_msg = f"Error during setting up the driver: {e}"
        raise Exception(error_msg)