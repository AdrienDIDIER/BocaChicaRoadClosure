import pandas as pd
import requests
import urllib.request
import pytesseract
import os
import numpy as np
import dateutil.parser
import cv2
import webcolors
import io
import pdf2image
import fitz
from vidgear.gears import CamGear
from color_detector import BackgroundColorDetector
from datetime import datetime
from tempfile import TemporaryDirectory
from bs4 import BeautifulSoup
from PIL import Image

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

def get_data_table(url):
    df = pd.read_html(url)[0]
    df = df.rename(columns={"Unnamed: 0": "Type", "Temp. Closure Date": "Date", "Time of Closure": "DateTime", "Current Beach Status": "Status"}, errors="raise")
    
    df["Date"] = df['Date'].str.replace('Tuesday, August 16, 202','Tuesday, August 16, 2022')

    df["DateTime"] = df["DateTime"].str.replace(".", "", regex=False)
    df["DateTime"] = df["DateTime"].str.replace("am", "AM", regex=False)
    df["DateTime"] = df["DateTime"].str.replace("pm", "PM", regex=False)

    df[['DateTime_Start','DateTime_Stop']] = df["DateTime"].str.split("to",expand=True,)
    del df["DateTime"]

    df["DateTime_Start"] = df["Date"] + " " + df["DateTime_Start"]

    df["DateTime_Stop"] = np.where(df["DateTime_Stop"].str.contains(','), df["DateTime_Stop"].str.replace(',', ''), df["Date"] + " " + df["DateTime_Stop"])

    df["DateTime_Start"] = pd.to_datetime(df['DateTime_Start']) #.dt.tz_localize('America/Chicago')
    df["DateTime_Stop"] = pd.to_datetime(df['DateTime_Stop']) #.dt.tz_localize('America/Chicago')

    df["Date"] = pd.to_datetime(df['Date'], format="%A, %B %d, %Y")

    df['index'] = (
        df['DateTime_Start'].dt.strftime('%Y-%M-%d %H%m%s').str.replace(" ", "_", regex=False)
    )

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
    if response.status_code != 200:
        print("Error fetching page home")
    else:
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
        return "🇺🇸 " + textEN
    else:
        return None

def getScreenNSF(url):
    stream = CamGear(source=url, stream_mode = True, logging=False).start() # YouTube Video URL as input
    frame = stream.read()
    crop_frame = frame[995:1080, 245:99999]
    ret = img_to_text(crop_frame)
    if ret==None or '@NASASpaceflight' in ret:
        return None
    else:
        return "Infos NSF : \n" + ret

def getMSIB():
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
    return text, pdf_file 
