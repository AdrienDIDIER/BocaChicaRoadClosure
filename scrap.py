import pandas as pd
import requests
import urllib.request
import fitz
import pytesseract
import os
import numpy as np
import dateutil.parser
import cv2
import webcolors
import PyPDF2
from vidgear.gears import CamGear
from color_detector import BackgroundColorDetector
from datetime import datetime
from tempfile import TemporaryDirectory
from bs4 import BeautifulSoup
from PIL import Image
from dotenv import load_dotenv
load_dotenv()

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
    except ValueError:
        closest_name = closest_colour(requested_colour)
        actual_name = None
    return actual_name, closest_name

def get_data_table(url):
    df = pd.read_html(url)[0]
    df = df.rename(columns={"Unnamed: 0": "Type", "Temp. Closure Date": "Date", "Time of Closure": "DateTime", "Current Beach Status": "Status"}, errors="raise")
    
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

def download_file(download_url, filename):
    response = urllib.request.urlopen(download_url)    
    file = open(os.getenv('TMP_URL') + filename + ".pdf", 'wb')
    file.write(response.read())
    file.close()
    return

def delete_download_file(filename_type):
    dir_name = os.getenv('TMP_URL')
    list_files = os.listdir(dir_name)

    for file in list_files:
        if file.endswith(filename_type):
            os.remove(os.path.join(dir_name, file))
    return

def pdf_to_img_to_text(filename):

    file =  os.getenv('TMP_URL') + filename + ".pdf"
    
    # if sys.platform.startswith('win'):
    #     pytesseract.pytesseract.tesseract_cmd = (
    #         os.getenv('TESSERACT_URL')
    #     )

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

def pdf_to_text(filename):

    file =  os.getenv('TMP_URL') + filename + ".pdf"
    #create file object variable
    #opening method will be rb
    pdffileobj=open(file,'rb')
    #create reader variable that will read the pdffileobj
    pdfreader=PyPDF2.PdfFileReader(pdffileobj)
    #This will store the number of pages of this pdf file
    x=pdfreader.numPages 
    #create a variable that will select the selected number of pages
    pageobj=pdfreader.getPage(x+1)  
    #(x+1) because python indentation starts with 0.
    #create text variable which will store all text datafrom pdf file
    text=pageobj.extractText()
    return text

def get_infos_flight(url, dates_list):
    response = requests.get(url)
    if response.status_code != 200:
        print("Error fetching page home")
    else:
        content = response.content

    soup = BeautifulSoup(content, 'html.parser')

    all_articles = soup.find_all('article')[1:5]

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
                    download_file(pdf_link, date)
                    text = pdf_to_img_to_text(date)
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

def img_to_text(url):

    # pytesseract.pytesseract.tesseract_cmd = (
    #     os.getenv('TESSERACT_URL')
    # )

    BackgroundColor = BackgroundColorDetector(url)
    _, closest_name = get_colour_name(BackgroundColor.detect())
    print(closest_name)
    if closest_name == 'firebrick':
        text = str(((pytesseract.image_to_string(Image.open(url)))))
        textEN = text.replace("-\n", "")
        os.remove(url)
        return "🇺🇸 " + textEN
    else:
        os.remove(url)
        return None

def getScreenNSF(url):
    stream = CamGear(source=url, stream_mode = True, logging=False).start() # YouTube Video URL as input
    frame = stream.read()
    crop_frame = frame[995:1080, 245:99999]
    cv2.imwrite(os.getenv("TMP_URL") + "NSF.png", crop_frame)
    print("la")
    ret = img_to_text(os.getenv("TMP_URL") + "NSF.png")
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
    download_file(url_msib, 'msib')
    text = pdf_to_img_to_text('msib')
    return text, 'msib'