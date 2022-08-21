import pandas as pd
import requests
import pytesseract
import numpy as np
import dateutil.parser
import webcolors
import pdf2image
import io

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

def get_data_table(url):
    df = pd.read_html(url)[0]
    df = df.rename(columns={"Unnamed: 0": "Type", "Temp. Closure Date": "Date", "Time of Closure": "DateTime", "Current Beach Status": "Status"}, errors="raise")
    
    df['Date'] = df['Date'].str.replace(r'(202$)', '2022')
    print(df)

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
    url_ok = url

    cookies = {
        'JSESSIONID': '0000ha9pmE4c-kV-a-ZK63U4BCl:17ll4pu41',
        'ak_bmsc': '301383ED91E9C982800A4BB0A280B84A~000000000000000000000000000000~YAAQPGgRYBdOYZaCAQAAfO7mwBCZvcCC2+fnFvXuI+pEMvwoyTZZM2SP8bVlnyotkK3osPrx7QSs8IZyWOcFr/cT2atVoU+j76efsfUsjSZbpGj946FWtu7evkbE2KvLUCfq2HklNXWMdD5UUUbmDYmn5Af01O9+Rurz/Iolwfz6FhJqSfRWylGrqAACOl7+df4hV3a+5knC9CdQoJWkhIhkfFk6MgDPbHYbPKWxFlhVd/DTKcZ3RkJYuFS4H0K9ZVLQ/p9fYmcKxmPZernTJZsz5TR++QBHtWHRTP3AR9VZ5om6mlXU8cGocee0YYNsiEJZbfIJvP/kVPTyLcylUvpBsF6icSj8P+Or+Bv3+UoMIYawu4y/g3LD80o9PSjDmX+M4Ay1a7Wuc/44S8q6t8GLXlOaZA==',
        'bm_mi': '3B9D6F2953659260D4620F6F4D462A05~YAAQPGgRYBxOYZaCAQAAgQDnwBD+E4J9RCKpiXh6aQRxJ4PknyCem25u5RHMnNMC3NFCDU3wwMObZjApU/iSNd82kGB/9tDCPo+JwIFgURWIZco/HCmRlvSVDvwuGX1YvgR2p6vD5pgKCGaVnB4+hMvPsKnwiVzhw10TVm9S3L+kkOwPZCt6AMxbFuefdM0KxS34nQH2AkcNLNLuDNan82PTa2LluWmNi5S2ZgmI7BXR+l31yMdqyiPkiG7HUJsGht15MrhKg652WBgvzLDGNa4u0YPh4Ttvs/dCivQHTMSSbQ1E0X4lbAlpc4mh1n9zRfT6nRNaddEc~1',
        'bm_sv': '08FC34F2E03176FF3300BB8261EF7B92~YAAQPGgRYB1OYZaCAQAAgQDnwBC/Kbx8XSOKv72S8jScpckGQVXutrBmLQOT+s5OszR+io5p+pIgxdLhx1T3fMPoPd8Q+gtcgnHYz+f4laVIBa71fr1KWF2INej+ZDZV6//obrz5FzR7/G+YFQV4YfTRJhBJxs5A+t5d38SaGJLOh4tlkhacxPxa3TGLvMeCcPu6BdsWvxhWXfO9b1TrNG/7srEd7SraZMPuswmqgQ9p3cXJS6NkFr3z5vcN~1',
    }

    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'Accept-Language': 'en,fr;q=0.9',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive',
        # Requests sorts cookies= alphabetically
        # 'Cookie': 'JSESSIONID=0000ha9pmE4c-kV-a-ZK63U4BCl:17ll4pu41; ak_bmsc=301383ED91E9C982800A4BB0A280B84A~000000000000000000000000000000~YAAQPGgRYBdOYZaCAQAAfO7mwBCZvcCC2+fnFvXuI+pEMvwoyTZZM2SP8bVlnyotkK3osPrx7QSs8IZyWOcFr/cT2atVoU+j76efsfUsjSZbpGj946FWtu7evkbE2KvLUCfq2HklNXWMdD5UUUbmDYmn5Af01O9+Rurz/Iolwfz6FhJqSfRWylGrqAACOl7+df4hV3a+5knC9CdQoJWkhIhkfFk6MgDPbHYbPKWxFlhVd/DTKcZ3RkJYuFS4H0K9ZVLQ/p9fYmcKxmPZernTJZsz5TR++QBHtWHRTP3AR9VZ5om6mlXU8cGocee0YYNsiEJZbfIJvP/kVPTyLcylUvpBsF6icSj8P+Or+Bv3+UoMIYawu4y/g3LD80o9PSjDmX+M4Ay1a7Wuc/44S8q6t8GLXlOaZA==; bm_mi=3B9D6F2953659260D4620F6F4D462A05~YAAQPGgRYBxOYZaCAQAAgQDnwBD+E4J9RCKpiXh6aQRxJ4PknyCem25u5RHMnNMC3NFCDU3wwMObZjApU/iSNd82kGB/9tDCPo+JwIFgURWIZco/HCmRlvSVDvwuGX1YvgR2p6vD5pgKCGaVnB4+hMvPsKnwiVzhw10TVm9S3L+kkOwPZCt6AMxbFuefdM0KxS34nQH2AkcNLNLuDNan82PTa2LluWmNi5S2ZgmI7BXR+l31yMdqyiPkiG7HUJsGht15MrhKg652WBgvzLDGNa4u0YPh4Ttvs/dCivQHTMSSbQ1E0X4lbAlpc4mh1n9zRfT6nRNaddEc~1; bm_sv=08FC34F2E03176FF3300BB8261EF7B92~YAAQPGgRYB1OYZaCAQAAgQDnwBC/Kbx8XSOKv72S8jScpckGQVXutrBmLQOT+s5OszR+io5p+pIgxdLhx1T3fMPoPd8Q+gtcgnHYz+f4laVIBa71fr1KWF2INej+ZDZV6//obrz5FzR7/G+YFQV4YfTRJhBJxs5A+t5d38SaGJLOh4tlkhacxPxa3TGLvMeCcPu6BdsWvxhWXfO9b1TrNG/7srEd7SraZMPuswmqgQ9p3cXJS6NkFr3z5vcN~1',
        'If-Modified-Since': 'Sun, 21 Aug 2022 14:36:31 GMT',
        'Referer': 'https://www.google.com/',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'cross-site',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Chromium";v="104", " Not A;Brand";v="99", "Google Chrome";v="104"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
    }

    response = requests.get(url_ok, cookies=cookies, headers=headers)
    print(response.text)
    exit()
    df = pd.read_html(
        response.text,
        attrs = {
            'width': '970',
            'border': '0',
            'cellpadding': '2',
            'cellspacing': '1',
            },
        skiprows=[0,1],
        header=0
        )[0]
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
