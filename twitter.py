import tweepy
import os
import pandas as pd
import re
import pdf2image
import io
import requests
import pytesseract
import time
import json

from selenium import webdriver
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver import ActionChains

from db import *
from PIL import Image, ImageFont, ImageDraw 

def connect_page_twitter():
    options = Options()
    options.add_argument('--headless')
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.get('https://twitter.com/')

    # with open("/cookies/cookie-twitter", 'rb') as cookiesfile:
    #      cookies = json.load(cookiesfile)
    #      for cookie in cookies:
    #         if 'sameSite' in cookie:
    #             del cookie['sameSite']
    #         driver.add_cookie(cookie)

    with open("./cookies.json", 'rb') as cookiesfile:
         cookies = json.load(cookiesfile)
         for cookie in cookies:
            if 'sameSite' in cookie:
                del cookie['sameSite']
            driver.add_cookie(cookie)

    # Get page after cookie for connection
    driver.get('https://twitter.com/home')
    return driver

def check_NSF_without_api(driver, db_client, text):

    if not get_last_tweet(db_client, re.sub(r'[^\w\s]', '', text).lower(), "MONGO_DB_URL_TABLE_PT"):
        print('Tweet NSF')
        print(text)
        try:

            element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "br[data-text='true']"))
            )
            element.send_keys(text)
            
            submit = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//div[@data-testid = 'tweetButtonInline']"))
            )
            submit.click()
        except Exception as e:
            print(e)
        set_last_tweet(db_client, re.sub(r'[^\w\s]', '', text).lower(), "MONGO_DB_URL_TABLE_PT")
    else:
        print('No Tweet NSF')

def check_MSIB_without_api(driver, db_client, text, pdf_file):
    check_date = re.sub(r'[^\w\s]', '', text.split('issue date:')[1].split('spacex')[0]).lower().strip().replace(" ",'').replace('\n', ' ').replace('\r', '')
    to_tweet = 'New MSIB :'
    if not get_last_msib(db_client, check_date, "MONGO_DB_URL_TABLE_MSIB"):
        print('Tweet MSIB')
        try:
            img = pdf2image.convert_from_bytes(pdf_file, fmt='jpeg')[0]
            with io.BytesIO() as buf:
                img.save(buf, 'jpeg')
                image_bytes = buf.getvalue()

            image = Image.open(io.BytesIO(image_bytes))
            save_path = os.getcwd() + "/tmp/msib.jpeg"
            image.save(save_path)
            
            element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "br[data-text='true']"))
            )
            element.send_keys(to_tweet)

            add_photo = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[data-testid='fileInput']"))
            )
            add_photo.send_keys(save_path)
            time.sleep(2)

            submit = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//div[@data-testid = 'tweetButtonInline']"))
            )
            submit.click()
            time.sleep(2)
            os.remove(save_path)
        except Exception as e:
            print(e)
        set_last_msib(db_client, check_date, "MONGO_DB_URL_TABLE_MSIB")
    else:
        print('No Tweet MSIB')

def tweet_road_closure_without_api(driver, df):

    message = []
    image_to_tweet = []

    df["DateTime_Start"] = df["DateTime_Start"].dt.tz_localize(tz='America/Chicago')
    df["DateTime_Stop"] = df["DateTime_Stop"].dt.tz_localize(tz='America/Chicago')

    df["DateTime_Start_EU"] = df["DateTime_Start"].dt.tz_convert(tz='Europe/Paris')
    df["DateTime_Stop_EU"] = df["DateTime_Stop"].dt.tz_convert(tz='Europe/Paris')

    for _, row in df.iterrows():
        
        if row['created'] == True:
            img_tmp = Image.open("./images/Road_new.png")
            img = img_tmp.copy()
            img_tmp.close()
        elif "Canceled" in row["Status"]:
            img_tmp = Image.open("./images/Road_canceled.png")
            img = img_tmp.copy()
            img_tmp.close()
        else:
            img_tmp = Image.open("./images/Road_update.png")
            img = img_tmp.copy()
            img_tmp.close()
        
        Date_start = row["DateTime_Start"].strftime("%A, %B %d, %Y - %I:%M %p")
        Date_end = row["DateTime_Stop"].strftime("%A, %B %d, %Y - %I:%M %p")
        Date_status = row["Status"]
        title_font = ImageFont.truetype('./fonts/dejavu-sans.book.ttf', 60)
        img_edit = ImageDraw.Draw(img)
        img_edit.text((273,97), str(Date_start), (0, 0, 0), font=title_font)
        img_edit.text((167,235), str(Date_end), (0, 0, 0), font=title_font)
        img_edit.text((617,359), str(Date_status), (0, 0, 0), font=title_font)

        image_to_tweet.append(img)

        # STATUS
        if "Canceled" in row["Status"]:
            row["Status"] = "Road closure canceled"
        elif "Scheduled" in row["Status"]:
            row["Status"] = "Road closure scheduled"
        elif "Possible" in row["Status"]:
            row["Status"] = "Possible road closure"
           
        # DATETIME
        if row["Date"].strftime("%d") != row["DateTime_Stop"].strftime("%d"):
            row["DateTime_Stop"] = row["DateTime_Stop"].strftime("%A, %B %d, %Y - %I:%M %p")
            row["DateTime_Stop_EU"] = row["DateTime_Stop_EU"].strftime("%A, %B %d, %Y - %H:%M %p")
        else:
            row["DateTime_Stop"] = row["DateTime_Stop"].strftime("%I:%M %p")
            row["DateTime_Stop_EU"] = row["DateTime_Stop_EU"].strftime("%A, %B %d, %Y - %H:%M")

        # TYPE
        if row["created"] is True:
            row["created"] = "RC : \n"
        else:
            row["created"] = "RC UDPATE : \n"

        # FLIGHT
        if row["Flight"] == 0:
            row["Flight"] = "NB : This is a non flight closure"
        elif row["Flight"] == 1:
            row["Flight"] = "NB : This can be a flight closure"
        else:
            row["Flight"] = ""
        
        message.append(
            row["created"]+
            row["Type"] +
            ": " +
            row["Status"] +
            " for " +
            row["Date"].strftime("%A, %B %d, %Y") +
            " from "+
            row["DateTime_Start"].strftime("%I:%M %p") + " (" + row["DateTime_Start_EU"].strftime("%H:%M") + " UTC+2)" +
            " to "+
            row["DateTime_Stop"] +
            " Boca Chica Time " + " (" + row["DateTime_Stop_EU"]  + " UTC+2) \n" +
            row["Flight"]
        )

    for i in range(len(message)):
        try:
            img_byte_arr = io.BytesIO()
            image_to_tweet[i].save(img_byte_arr, format='PNG')
            img_byte_arr = img_byte_arr.getvalue()

            image = Image.open(io.BytesIO(img_byte_arr))
            save_path = os.getcwd() + "/tmp/rc.jpeg"
            image.save(save_path)
            
            element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "br[data-text='true']"))
            )
            element.send_keys(message[i])

            add_photo = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[data-testid='fileInput']"))
            )
            add_photo.send_keys(save_path)
            time.sleep(2)

            submit = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//div[@data-testid = 'tweetButtonInline']"))
            )
            submit.click()
            time.sleep(2)
            os.remove(save_path)
        except Exception as e:
            print(e)    
    return

def check_TFR_without_api(driver, db_client, row):
    if not get_last_TFR(db_client, row['NOTAM'], 'MONGO_DB_URL_TABLE_TFR'):
        print(f"Ajout TFR {row['NOTAM']} BDD")
        i_formated = row['NOTAM'].replace("/", "_")
        image_url = f"https://tfr.faa.gov/save_maps/sect_{i_formated}.gif"
        img_data = requests.get(image_url).content
        print('Tweet TFR')
        t = row['Type']
        d = row['Description']
        n = row['NOTAM'].replace('/', '_')

        to_tweet = f"NEW TFR :\nType : {t}\nDescription : {d}\nPlus : See here https://tfr.faa.gov/save_pages/detail_{n}.html"
        
        image = Image.open(io.BytesIO(img_data))
        save_path = os.getcwd() + "/tmp/TFR.png"
        image.save(save_path)    
        
        element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "br[data-text='true']"))
        )
        element.send_keys(to_tweet)

        add_photo = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[data-testid='fileInput']"))
        )
        add_photo.send_keys(save_path)
        time.sleep(2)

        submit = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//div[@data-testid = 'tweetButtonInline']"))
        )
        submit.click()
        time.sleep(2)
        os.remove(save_path)

        set_last_TFR(db_client, row['NOTAM'], 'MONGO_DB_URL_TABLE_TFR')
    else:
        print('No Tweet TFR')

# def connect_api_twitter():
#     # Authenticate to Twitter
#     auth = tweepy.OAuthHandler(os.getenv("TWITTER_API_KEY"), os.getenv("TWITTER_API_SECRET_KEY"))
#     auth.set_access_token(os.getenv("TWITTER_ACCESS_TOKEN"), os.getenv("TWITTER_ACCESS_TOKEN_SECRET"))
#     api = tweepy.API(auth)
    
#     try:
#         api.verify_credentials()
#         print("Authentication Successful")
#     except:
#         print("Authentication Error")

#     return api

# def tweet_road_closure(api, df):

#     message = []
#     image_to_tweet = []

#     df["DateTime_Start"] = df["DateTime_Start"].dt.tz_localize(tz='America/Chicago')
#     df["DateTime_Stop"] = df["DateTime_Stop"].dt.tz_localize(tz='America/Chicago')

#     df["DateTime_Start_EU"] = df["DateTime_Start"].dt.tz_convert(tz='Europe/Paris')
#     df["DateTime_Stop_EU"] = df["DateTime_Stop"].dt.tz_convert(tz='Europe/Paris')

#     for _, row in df.iterrows():
        
#         if row['created'] == True:
#             img_tmp = Image.open("./images/Road_new.png")
#             img = img_tmp.copy()
#             img_tmp.close()
#         elif "Canceled" in row["Status"]:
#             img_tmp = Image.open("./images/Road_canceled.png")
#             img = img_tmp.copy()
#             img_tmp.close()
#         else:
#             img_tmp = Image.open("./images/Road_update.png")
#             img = img_tmp.copy()
#             img_tmp.close()
        
#         Date_start = row["DateTime_Start"].strftime("%A, %B %d, %Y - %I:%M %p")
#         Date_end = row["DateTime_Stop"].strftime("%A, %B %d, %Y - %I:%M %p")
#         Date_status = row["Status"]
#         title_font = ImageFont.truetype('./fonts/dejavu-sans.book.ttf', 60)
#         img_edit = ImageDraw.Draw(img)
#         img_edit.text((273,97), str(Date_start), (0, 0, 0), font=title_font)
#         img_edit.text((167,235), str(Date_end), (0, 0, 0), font=title_font)
#         img_edit.text((617,359), str(Date_status), (0, 0, 0), font=title_font)

#         image_to_tweet.append(img)

#         # STATUS
#         if "Canceled" in row["Status"]:
#             row["Status"] = "🚧 Road closure canceled"
#         elif "Scheduled" in row["Status"]:
#             row["Status"] = "🚧 Road closure scheduled"
#         elif "Possible" in row["Status"]:
#             row["Status"] = "🚧 Possible road closure"
           
#         # DATETIME
#         if row["Date"].strftime("%d") != row["DateTime_Stop"].strftime("%d"):
#             row["DateTime_Stop"] = row["DateTime_Stop"].strftime("%A, %B %d, %Y - %I:%M %p")
#             row["DateTime_Stop_EU"] = row["DateTime_Stop_EU"].strftime("%A, %B %d, %Y - %H:%M %p")
#         else:
#             row["DateTime_Stop"] = row["DateTime_Stop"].strftime("%I:%M %p")
#             row["DateTime_Stop_EU"] = row["DateTime_Stop_EU"].strftime("%A, %B %d, %Y - %H:%M")

#         # TYPE
#         if row["created"] is True:
#             row["created"] = "\U0001F1FA\U0001F1F8	 NEW RC : \n"
#         else:
#             row["created"] = "\U0001F1FA\U0001F1F8	 RC UDPATE : \n"

#         # FLIGHT
#         if row["Flight"] == 0:
#             row["Flight"] = "❌ NB : This is a non flight closure"
#         elif row["Flight"] == 1:
#             row["Flight"] = "✅ NB : This can be a flight closure"
#         else:
#             row["Flight"] = ""
        
#         message.append(
#             row["created"]+
#             row["Type"] +
#             ": " +
#             row["Status"] +
#             " for " +
#             row["Date"].strftime("%A, %B %d, %Y") +
#             " from "+
#             row["DateTime_Start"].strftime("%I:%M %p") + " (" + row["DateTime_Start_EU"].strftime("%H:%M") + " UTC+2)" +
#             " to "+
#             row["DateTime_Stop"] +
#             " Boca Chica Time " + " (" + row["DateTime_Stop_EU"]  + " UTC+2) \n" +
#             row["Flight"]
#         )

#     for i in range(len(message)):
#         try:
#             img_byte_arr = io.BytesIO()
#             image_to_tweet[i].save(img_byte_arr, format='PNG')
#             img_byte_arr = img_byte_arr.getvalue()
#             api.update_status_with_media(filename = "", file = img_byte_arr, status = message[i])
#         except Exception as e:
#             print(e)    
#     return

# def check_OP_Mary(api, db_client, account_name, nb_tweets):
#     tweets = api.user_timeline(screen_name=account_name,count=nb_tweets,include_rts=False, exclude_replies=True)

#     tweets_clean = []
#     for t in tweets:
#         tweets_clean.append(t.__dict__)

#     df_tweets= pd.DataFrame.from_records(tweets_clean)
#     df_tweets.drop(["_api", "_json"],axis=1, inplace=True)

#     for _, row in df_tweets.iterrows():
#         if 'extended_entities' in row.index:
#             if isinstance(row['extended_entities'], dict):
#                 for entitie in row['extended_entities']['media']:
#                     media_url = entitie['media_url']
#                     media_data = requests.get(media_url).content
#                     with open('image_name.jpg', 'wb') as handler:
#                         handler.write(media_data)

#                     img = Image.open('image_name.jpg')
#                     media_text = str(((pytesseract.image_to_string(img)))).lower()
#                     os.remove("image_name.jpg")

#                     if 'alert' in media_text and 'action' in media_text and 'required' in media_text:
#                         if not get_last_tweet(db_client, str(row['id']), "MONGO_DB_URL_TABLE_RC"):
#                             print(f"[Mary] Tweet Mary [{row['id']}]")
#                             set_last_tweet(db_client, str(row['id']), "MONGO_DB_URL_TABLE_RC")
#                             try:
#                                 api.update_status_with_media(
#                                     filename = "",
#                                     file = media_data,
#                                     status = "🚀🔥 @BocaChicaGal: Alert notice for possible Ship OR Booster Test 🚀🔥"
#                                 )
#                             except Exception as e:
#                                 print(e)
#                         else:
#                             print(f"[Mary] Tweet already exist [{row['id']}]")

#                         break
#                     else:
#                         print(f"[Mary] Not an alert tweet [{row['id']}]")
#         print(f"[Mary] Not an alert tweet [{row['id']}]")
#     return

# def check_NSF(api, db_client, text):

#     if not get_last_tweet(db_client, re.sub(r'[^\w\s]', '', text).lower(), "MONGO_DB_URL_TABLE_PT"):
#         print('Tweet NSF')
#         try:
#             api.update_status(text)
#         except Exception as e:
#             print(e)
#         set_last_tweet(db_client, re.sub(r'[^\w\s]', '', text).lower(), "MONGO_DB_URL_TABLE_PT")
#     else:
#         print('No Tweet NSF')

# def check_MSIB(api, db_client, text, pdf_file):
#     check_date = re.sub(r'[^\w\s]', '', text.split('issue date:')[1].split('spacex')[0]).lower().strip().replace(" ",'').replace('\n', ' ').replace('\r', '')
#     to_tweet = 'New MSIB :'
#     if not get_last_msib(db_client, check_date, "MONGO_DB_URL_TABLE_MSIB"):
#         print('Tweet MSIB')
#         try:
#             img = pdf2image.convert_from_bytes(pdf_file, fmt='jpeg')[0]
#             # Create a buffer to hold the bytes
#             buf = io.BytesIO()
#             # Save the image as jpeg to the buffer
#             img.save(buf, 'jpeg')
#             # Rewind the buffer's file pointer
#             buf.seek(0)
#             # Read the bytes from the buffer
#             image_bytes = buf.read()
#             api.update_status_with_media(filename = "", file = image_bytes, status = to_tweet)
#         except Exception as e:
#             print(e)
#         set_last_msib(db_client, check_date, "MONGO_DB_URL_TABLE_MSIB")
#     else:
#         print('No Tweet MSIB')
    
# def check_TFR(api, db_client, row):
    # if not get_last_TFR(db_client, row['NOTAM'], 'MONGO_DB_URL_TABLE_TFR'):
    #     print(f"Ajout TFR {row['NOTAM']} BDD")
    #     i_formated = row['NOTAM'].replace("/", "_")
    #     image_url = f"https://tfr.faa.gov/save_maps/sect_{i_formated}.gif"
    #     img_data = requests.get(image_url).content

    #     print('Tweet TFR')
    #     t = row['Type']
    #     d = row['Description']
    #     n = row['NOTAM'].replace('/', '_')

    #     to_tweet = f"NEW TFR :\nType : \t\t {t}\nDescription : \t\t{d}\nPlus : \t\tSee here https://tfr.faa.gov/save_pages/detail_{n}.html"
        
    #     api.update_status_with_media(
    #         filename = "",
    #         file = img_data,
    #         status = to_tweet)

    #     set_last_TFR(db_client, row['NOTAM'], 'MONGO_DB_URL_TABLE_TFR')
    # else:
    #     print('No Tweet TFR')