import pandas as pd
import requests
import urllib.request
import fitz
import pytesseract
import os
import numpy as np
import dateutil.parser

from datetime import datetime
from tempfile import TemporaryDirectory
from bs4 import BeautifulSoup
from PIL import Image
from dotenv import load_dotenv
load_dotenv()

def get_data_table(url):
    df = pd.read_html(url)[0]
    df = df.rename(columns={"Unnamed: 0": "Type", "Temp. Closure Date": "Date", "Time of Closure": "DateTime", "Current Beach Status": "Status"}, errors="raise")
    
    df["DateTime"] = df["DateTime"].str.replace(".", "", regex=False)
    df["DateTime"] = df["DateTime"].str.replace("am", "AM", regex=False)
    df["DateTime"] = df["DateTime"].str.replace("pm", "PM", regex=False)

    df[['DateTime_Start','DateTime_Stop']] = df["DateTime"].str.split("to",expand=True,)
    
    df["DateTime_Start"] = df["Date"] + " " + df["DateTime_Start"]

    df["DateTime_Stop"] = np.where(df["DateTime_Stop"].str.contains('–'), df["DateTime_Stop"].str.replace('–', str(datetime.now().year)), df["Date"] + " " + df["DateTime_Stop"])

    df["DateTime_Start"] = pd.to_datetime(df['DateTime_Start']) #.dt.tz_localize('America/Chicago')
    df["DateTime_Stop"] = pd.to_datetime(df['DateTime_Stop']) #.dt.tz_localize('America/Chicago')

    del df["DateTime"]

    df["Date"] = pd.to_datetime(df['Date'], format="%A, %B %d, %Y")

    df['index'] = (
        df['DateTime_Start'].dt.strftime('%Y-%M-%d %H%m%s').str.replace(" ", "_", regex=False)
    )

    return df

def download_file(download_url, filename):
    response = urllib.request.urlopen(download_url)    
    file = open(os.getenv('TMP_URL') + filename + ".pdf", 'wb')
    file.write(response.read())
    file.close()
    print("dl ok")
    return

def delete_download_file(filename_type):
    dir_name = os.getenv('TMP_URL')
    list_files = os.listdir(dir_name)

    for file in list_files:
        if file.endswith(filename_type):
            os.remove(os.path.join(dir_name, file))
    return

def pdf_to_text(filename):

    file =  os.getenv('TMP_URL') + filename + ".pdf"
    # pytesseract.pytesseract.tesseract_cmd = (
    #     os.getenv('TESSERACT_URL')
    # )

    with TemporaryDirectory() as tempdir:

        pdffile = file
        doc = fitz.open(pdffile)
        page = doc.load_page(0)
        pix = page.get_pixmap()
        output = f"{tempdir}\{filename}.png"
        pix.save(output)

        # Recognize the text as string in image using pytesserct
        text = str(((pytesseract.image_to_string(Image.open(f"{tempdir}\{filename}.png")))))
        text = text.replace("-\n", "").lower()
    
    return text

def get_infos_flight(url, dates_list):
    response = requests.get(url)
    if response.status_code != 200:
        print("Error fetching page home")
        exit()
    else:
        content = response.content

    soup = BeautifulSoup(content, 'html.parser')

    all_articles = soup.find_all('article')[1:]

    df = pd.DataFrame(columns=['Date', 'Flight'])

    for article in all_articles:
        page_url = article.find('a').get('href')
        response_page = requests.get(page_url)
        if response_page.status_code != 200:
            print("Error fetching page pdf")
            exit()
        else:
            content_page = response_page.content

        soup_page = BeautifulSoup(content_page, 'html.parser')

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
            download_file(pdf_link, date)
            text = pdf_to_text(date)
            print("img to text ok")
            if "non-flight testing" in text:
                df.loc[len(df.index)] = [date, 0]
            elif " flight testing" in text:
                df.loc[len(df.index)] = [date, 1]
            else:
                df.loc[len(df.index)] = [date, 0]
    df['Date'] = df['Date'].str.replace('Original', '')
    df['Date'] = pd.to_datetime(df['Date'])
    return df