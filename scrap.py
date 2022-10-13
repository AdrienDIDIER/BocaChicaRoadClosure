import pandas as pd
import requests
import pytesseract
import numpy as np
import dateutil.parser
import webcolors
import pdf2image
import requests
from io import StringIO 
from vidgear.gears import CamGear
from color_detector import BackgroundColorDetector
from datetime import datetime
from bs4 import BeautifulSoup
from screenshot import make_screenshot

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

def find_proxies_available():
    url = "https://free-proxy-list.net/"
    response = requests.get(url)
    if response.status_code != 200:
        print("Error fetching page home")
    else:
        content = response.content

    soup_page = BeautifulSoup(content, 'html.parser')
    table = soup_page.find("table", {"class": "table-striped"})
    rows = table.find_all('tr')
    proxies = []
    for row in rows:
        cols = row.find_all('td')
        cols = [ele.text.strip() for ele in cols]
        if len(cols) > 0:
            if cols[1] == "Yes":
                proxies.append("https://" + cols[0] + ":" + cols[1])
            else:
                proxies.append("http://" + cols[0] + ":" + cols[1])
    return proxies

def get_data_table(url):

    proxies = find_proxies_available()

    for proxie in proxies:
        if "http" in proxie:
            p = {
                'http': proxie,
            }
        else:
            p = {
                'https': proxie,
            }
            
        try:
            x = requests.get(url, proxies=p)
            df = pd.read_html(StringIO(x.text))[0]
        except Exception:
            print(f"Proxie {str(p)} not ok")
            continue

        df = df.rename(columns={"Unnamed: 0": "Type", "Temp. Closure Date": "Date", "Time of Closure": "DateTime", "Current Beach Status": "Status"}, errors="raise")
        
        df['Date'] = df['Date'].str.replace(r'(202$)', '2022')

        df["DateTime"] = df["DateTime"].str.replace(".", "", regex=False)
        df["DateTime"] = df["DateTime"].str.replace("am", "AM", regex=False)
        df["DateTime"] = df["DateTime"].str.replace("pm", "PM", regex=False)

        df[['DateTime_Start','DateTime_Stop']] = df["DateTime"].str.split("to",expand=True,)
        del df["DateTime"]

        df["DateTime_Start"] = df["Date"] + " " + df["DateTime_Start"]

        df["DateTime_Stop"] = np.where(df["DateTime_Stop"].str.contains(','), df["DateTime_Stop"].str.replace(',', ''), df["Date"] + " " + df["DateTime_Stop"])

        df["DateTime_Start"] = pd.to_datetime(df['DateTime_Start']) #.dt.tz_localize('America/Chicago')
        df["DateTime_Stop"] = pd.to_datetime(df['DateTime_Stop']) #.dt.tz_localize('America/Chicago')

        df["Date"] = pd.to_datetime(df['Date'], format="%A, %B %d, %Y",errors='ignore')

        df['index'] = df['DateTime_Start'].values.astype(np.int64) // 10 ** 9
        break

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
    stream = CamGear(source=url, stream_mode=True, logging=True).start() # YouTube Video URL as input
    frame = stream.read()
    crop_frame = frame[995:1080, 245:99999]
    ret = img_to_text(crop_frame)
    ret = ret.replace("$", "S")
    if ret==None or '@NASASpaceflight' in ret:
        return None
    else:
        return "Infos @NASASpaceflight : \n" + ret

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

def getTFR(url):

    proxies = find_proxies_available()

    for proxie in proxies:
        if "http" in proxie:
            p = {
                'http': proxie,
            }
        else:
            p = {
                'https': proxie,
            }

        try:
            r = requests.get(url, proxies=p)
            df = pd.read_html(
                r.text,
                attrs = {
                    'width': '970',
                    'border': '0',
                    'cellpadding': '2',
                    'cellspacing': '1',
                    },
                skiprows=[0,1],
                header=0
                )[0]
        except Exception:
            print(f"Proxie {str(p)} not ok")
            continue
        # Clear Columns Zoom + others ?
        df = df.drop(columns=['Zoom','Unnamed: 7'])
        # No footer
        df = df.drop([len(df) - 1,len(df) - 2,len(df) - 3,])
        # Only Space Operations
        df = df[(df['Type'] == 'SPACE OPERATIONS') & (df['Description'].str.contains("Brownsville"))]
        df = df.reset_index(drop=True)
        tab_image = []
        for _, row in df.iterrows():
            img_bytes = make_screenshot(f"https://tfr.faa.gov/save_pages/detail_{row['NOTAM'].replace('/', '_')}.html")
            tab_image.append(img_bytes)

    return df, tab_image