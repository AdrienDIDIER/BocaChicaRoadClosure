import os 
import cv2
from dotenv import load_dotenv

from selenium import webdriver  
from selenium.webdriver.chrome.options import Options

load_dotenv()

CHROME_PATH = os.getenv('CHROME_PATH')
CHROMEDRIVER_PATH = os.getenv('CHROMEDRIVER_PATH')
WINDOW_SIZE = "1920,1080"
TMP = os.getenv('TMP')

chrome_options = Options()  
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--window-size=%s" % WINDOW_SIZE)
chrome_options.add_argument('--proxy-server=%s' % 'http://159.197.250.171:3128')
chrome_options.binary_location = CHROME_PATH

def make_screenshot(url):
    if not url.startswith('http'):
        raise Exception('URLs need to start with "http"')

    driver = webdriver.Chrome(
        executable_path=CHROMEDRIVER_PATH,
        chrome_options=chrome_options
    )

    driver.get(url)
    driver.save_screenshot(f"{TMP}/tmp.jpg")
    img = cv2.imread(f"{TMP}/tmp.jpg")
    img = img[0:1080, 0:1000]
    _, im_buf_arr = cv2.imencode(".jpg", img)
    byte_im = im_buf_arr.tobytes()
    os.remove(f"{TMP}/tmp.jpg")
    driver.close()
    return byte_im