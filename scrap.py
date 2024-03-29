import pandas as pd
import requests
import pytesseract
import numpy as np
import dateutil.parser
import webcolors
import pdf2image
import requests

from selenium import webdriver
from tfr_scraper import tfr_scraper
from io import StringIO 
from vidgear.gears import CamGear
from color_detector import BackgroundColorDetector
from datetime import datetime
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from html_table_parser.parser import HTMLTableParser
from fp.fp import FreeProxy

def closest_colour(requested_colour):
    min_colours = {}
    for key, name in webcolors.CSS3_HEX_TO_NAMES.items():
        r_c, g_c, b_c = webcolors.hex_to_rgb(key)
        rd = (r_c - requested_colour[0]) ** 2
        gd = (g_c - requested_colour[1]) ** 2
        bd = (b_c - requested_colour[2]) ** 2
        min_colours[(rd + gd + bd)] = name
    return min_colours[min(min_colours.keys())]

def get_colour_name(requested_colour):
    try:
        closest_name, actual_name = webcolors.rgb_to_name(requested_colour)
    except Exception as e:
        closest_name = closest_colour(requested_colour)
        actual_name = None
    return actual_name, closest_name

def get_data_table_simple(url):

    x = requests.get(url)
    df = pd.read_html(StringIO(x.text))[0]
    df_tmp = pd.read_html(StringIO(x.text))[1]  
    
    df_tmp = df_tmp.rename(columns={"Unnamed: 0": "Type", "Temp. Delay Date": "Date", "Time of Delay": "DateTime"})
    df_tmp["Status"] = 'Transport Closure'
    df = df.rename(columns={"Unnamed: 0": "Type", "Temp. Closure Date": "Date", "Time of Closure": "DateTime", "Current Beach Status": "Status"}, errors="raise")
    df = pd.concat([df, df_tmp])

    df = df[~df["Date"].isna()]

    df["DateTime"] = df["DateTime"].str.replace(".", "", regex=False)
    df["DateTime"] = df["DateTime"].str.replace("am", "AM", regex=False)
    df["DateTime"] = df["DateTime"].str.replace("pm", "PM", regex=False)
    
    df['Type'] = df['Type'].fillna("Date")
    df['index'] = df['Date'] + " " + df['DateTime']
    return df

def get_data_table(url):

    x = requests.get(url)
    df = pd.read_html(StringIO(x.text))[0]
    df_tmp = pd.read_html(StringIO(x.text))[1]  
    
    df_tmp = df_tmp.rename(columns={"Unnamed: 0": "Type", "Temp. Delay Date": "Date", "Time of Delay": "DateTime"})
    df_tmp["Status"] = 'Transport Closure'
    df = df.rename(columns={"Unnamed: 0": "Type", "Temp. Closure Date": "Date", "Time of Closure": "DateTime", "Current Beach Status": "Status"}, errors="raise")
    df = pd.concat([df, df_tmp])

    df = df[~df["Date"].isna()]

    df['Date'] = df['Date'].str.replace(r'(202$)', '2022')
    df['Date'] = df['Date'].str.replace('Wednesday, March 8th thru 9th, 2023', 'Wednesday March 8th 2023 thru Thursday March 9th, 2023')
    df['Date'] = df['Date'].str.replace(',', '')
    print(df)    
    df['DateTime'] = df['DateTime'].str.replace('2:00 am of Oct 11', '2:00 am', regex=False)

    df["DateTime"] = df["DateTime"].str.replace(".", "", regex=False)
    df["DateTime"] = df["DateTime"].str.replace("am", "AM", regex=False)
    df["DateTime"] = df["DateTime"].str.replace("pm", "PM", regex=False)


    df[['DateTime_Start','DateTime_Stop']] = df["DateTime"].str.split("to",expand=True,)
    del df["DateTime"]

    Date = []
    DateTime_Start = []
    DateTime_Stop = []
    for _, row in df.iterrows():
        if 'to' in row['Date']:
            DateTime_Start.append((row["Date"].split("to")[0] + " " + row["DateTime_Start"]).replace(',', ''))
            DateTime_Stop.append((row["Date"].split("to")[1] + " " + row["DateTime_Stop"]).replace(',', ''))
            Date.append(row['Date'].split("to")[0])
        elif 'thru' in row['Date']:
            DateTime_Start.append((row["Date"].split("thru")[0] + " " + row["DateTime_Start"]).replace(',', ''))
            DateTime_Stop.append((row["Date"].split("thru")[1] + " " + row["DateTime_Stop"]).replace(',', ''))
            Date.append(row['Date'].split("thru")[0])
        else:
            DateTime_Start.append((row["Date"] + " " + row["DateTime_Start"]).replace(',', ''))
            DateTime_Stop.append(row["Date"] + " " + row["DateTime_Stop"].replace(',', ''))
            Date.append(row['Date'])

    df["Date"] = Date
    df["DateTime_Start"] = DateTime_Start
    df["DateTime_Stop"] = DateTime_Stop

    df["DateTime_Start"] = pd.to_datetime(df['DateTime_Start']) #.dt.tz_localize('America/Chicago')
    df["DateTime_Stop"] = pd.to_datetime(df['DateTime_Stop']) #.dt.tz_localize('America/Chicago')

    df["Date"] = pd.to_datetime(df['Date'])
    
    df['Type'] = df['Type'].fillna("Date")
    df['index'] = df['DateTime_Start'].values.astype(np.int64) // 10 ** 9
    return df

def download_file(download_url):
    response = requests.get(download_url)
    return response.content

def pdf_to_img_to_text(file):
    stream = pdf2image.convert_from_bytes(file)[0]
    # Recognize the text as string in image using pytesserct
    text = str(((pytesseract.image_to_string(stream))))
    text = text.replace("-\n", "").lower()
    return text

def get_infos_flight(url, dates_list):
    
        response = requests.get(url)
        content = response.content

        soup = BeautifulSoup(content, 'html.parser')

        all_articles = soup.find_all('article')[1:3]
        df = pd.DataFrame(columns=['Date', 'Flight'])

        for article in all_articles:
            try:
                page_url = article.find('a').get('href')
                response_page = requests.get(page_url)
                if response_page.status_code != 200:
                    print("Error fetching page pdf")
                else:
                    content_page = response_page.content

                soup_page = BeautifulSoup(content_page, 'html.parser')

                if soup_page.find("h1") is not None:
                    if ("Order Closing" or "Temporary And Intermittent Road Delay") in soup_page.find("h1").text:
                        date = soup_page.find("h1").text.split(";")[1]
                        
                        if "Original" in date:
                            date = date.replace("Original", '')
                        date_formated = dateutil.parser.parse(date)
                        date_formated = datetime.strftime(date_formated, "%Y-%m-%d")

                        if date_formated  not in dates_list:
                            continue

                        print("Dowloading data for date : " + date)
                        
                        date = soup_page.find("h1").text.split(";")[1]
                        pdf_link = soup_page.find('article').find(class_="gem-button-container").find("a").get('href')
                        pdf_file = download_file(pdf_link)
                        text = pdf_to_img_to_text(pdf_file)
                        if "non-flight testing" in text:
                            df.loc[len(df.index)] = [date, 0]
                        elif " flight testing" in text:
                            df.loc[len(df.index)] = [date, 0]
                        else:
                            df.loc[len(df.index)] = [date, 0]
            except Exception as e:
                print(e)
        df['Date'] = df['Date'].str.replace('Original', '')
        df['Date'] = pd.to_datetime(df['Date'])
        return df

def img_to_text(crop_frame):

    BackgroundColor = BackgroundColorDetector(crop_frame)
    _, closest_name = get_colour_name(BackgroundColor.detect())
    
    if closest_name == 'firebrick':
        text = str(((pytesseract.image_to_string(crop_frame))))
        textEN = text.replace("-\n", "")
        return textEN
    else:
        return None

def getScreenNSF(url):
    stream = CamGear(source=url, stream_mode=True, logging=False).start() # YouTube Video URL as input
    frame = stream.read()
    crop_frame = frame[995:1080, 245:1820]
    ret = img_to_text(crop_frame)
    if ret==None or '@nasaspaceflight' in ret.lower():
        return None
    else:
        ret = ret.replace("$", "S")
        return "Infos @NASASpaceflight : \n" + ret

def getMSIB():

    # options = Options()
    # options.add_argument('--headless')
    # options.add_argument("--disable-setuid-sandbox") 
    # options.add_argument("--remote-debugging-port=9222")
    # options.add_argument("--disable-dev-shm-using") 
    # options.add_argument("--disable-extensions") 
    # options.add_argument("--disable-gpu") 
    # options.add_argument("disable-infobars")
    # options.add_argument("--no-sandbox")

    # driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    # driver.get('https://homeport.uscg.mil/my-homeport/safety-Notifications/MSIB?cotpid=22')

    # _ = WebDriverWait(driver, 10).until(
    #             EC.presence_of_element_located((By.ID, "contents"))
    #         )

    # df = pd.read_html(driver.page_source)[0]
    # df['Title_low'] = df['Title'].str.lower()
    # df_spacex = df[df['Title_low'].str.contains('spacex')].copy()
    # if len(df_spacex) == 0:
    #     return None, None 
    # df_spacex['ts'] = pd.to_datetime(df_spacex['Modified'])
    # df_spacex = df_spacex.sort_values(by=['ts'],ascending=False)
    
    # title_to_check = df_spacex.iloc[0]['Title']

    # url = WebDriverWait(driver, 10).until(
    #             EC.presence_of_element_located((By.XPATH, f"//*[contains(text(),'{title_to_check}')]"))
    # )

    # href_page = url.get_attribute('href')

    # driver.get(href_page)
    # _ = WebDriverWait(driver, 10).until(
    #             EC.presence_of_element_located((By.ID, "idAttachmentsTable"))
    #         )

    # url_page_2 = WebDriverWait(driver, 10).until(
    #             EC.presence_of_element_located((By.XPATH, f"//a[contains(text(),'{title_to_check}')]"))
    # )

    # url_msib = url_page_2.get_attribute('href')
    # print("Check " + url_msib)

    url = "http://msib.bocachica.com/"
    response = requests.get(url)
    if response.status_code != 200:
        print("Error fetching page home")
    else:
        content = response.content

    soup_page = BeautifulSoup(content, 'html.parser')
    url_msib = soup_page.find("frame")['src']

    pdf_file = download_file(url_msib)
    text = pdf_to_img_to_text(pdf_file)
    # driver.quit()
    
    return text, pdf_file 

def url_get_contents(url):
    proxy = FreeProxy().get()
    f = requests.post(url, data={"type" : "SPACE OPERATIONS"}, proxies={'https' : proxy})
    return f.text, proxy

def getTFR():
    """Downloads TFR table and parses, returns a list of tfrs as dictionaries"""
    url = "https://tfr.faa.gov/tfr2/list.jsp"
    xhtml, proxy = url_get_contents(url)
    p = HTMLTableParser()
    p.feed(xhtml)
    df = pd.DataFrame(p.tables[4])
    new_header = df.iloc[2] #grab the first row for the header
    df = df[3:] #take the data less the header row
    df.columns = new_header #set the header row as the df header
    df.replace("", None, inplace=True)
    list_TFR = df.dropna(how='any', subset=['NOTAM'])
    list_TFR_clean = list_TFR[(list_TFR['Type'] == 'SPACE OPERATIONS') & (list_TFR['Description'].str.contains("Brownsville"))]
    print(list_TFR_clean.head())
    return list_TFR_clean, proxy