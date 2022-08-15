import tweepy
import os
import pandas as pd
import re
import pdf2image
import io
from db import *
from PIL import Image, ImageFont, ImageDraw 

def connect_api_twitter():
    # Authenticate to Twitter
    auth = tweepy.OAuthHandler(os.getenv("TWITTER_API_KEY"), os.getenv("TWITTER_API_SECRET_KEY"))
    auth.set_access_token(os.getenv("TWITTER_ACCESS_TOKEN"), os.getenv("TWITTER_ACCESS_TOKEN_SECRET"))
    api = tweepy.API(auth)
    
    try:
        api.verify_credentials()
        print("Authentication Successful")
    except:
        print("Authentication Error")

    return api

def tweet_road_closure(api, df):

    message = []
    image_to_tweet = []

    df["DateTime_Start"] = df["DateTime_Start"].dt.tz_localize(tz='America/Chicago')
    df["DateTime_Stop"] = df["DateTime_Stop"].dt.tz_localize(tz='America/Chicago')

    df["DateTime_Start_EU"] = df["DateTime_Start"].dt.tz_convert(tz='Europe/Paris')
    df["DateTime_Stop_EU"] = df["DateTime_Stop"].dt.tz_convert(tz='Europe/Paris')

    for _, row in df.iterrows():
        
        if row['created'] == True:
            img = Image.open("/home/ubuntu/BocaChicaRoadClosure/images/Road_new.png")
        elif "Canceled" in row["Status"]:
            img = Image.open("/home/ubuntu/BocaChicaRoadClosure/images/Road_canceled.png")
        else:
            img = Image.open("/home/ubuntu/BocaChicaRoadClosure/images/Road_update.png")
        
        Date_start = row["DateTime_Start"].strftime("%A, %B %d, %Y - %I:%M %p")
        Date_end = row["DateTime_Stop"].strftime("%A, %B %d, %Y - %I:%M %p")
        Date_status = row["Status"]
        title_font = ImageFont.truetype('fonts/dejavu-sans.book.ttf', 60)
        img_edit = ImageDraw.Draw(img)
        img_edit.text((273,97), str(Date_start), (0, 0, 0), font=title_font)
        img_edit.text((167,235), str(Date_end), (0, 0, 0), font=title_font)
        img_edit.text((617,359), str(Date_status), (0, 0, 0), font=title_font)

        image_to_tweet.append(img)

        # STATUS
        if "Canceled" in row["Status"]:
            row["Status"] = "🚧 Road closure canceled"
        elif "Scheduled" in row["Status"]:
            row["Status"] = "🚧 Road closure scheduled"
        elif "Possible" in row["Status"]:
            row["Status"] = "🚧 Possible road closure"
           
        # DATETIME
        if row["Date"].strftime("%d") != row["DateTime_Stop"].strftime("%d"):
            row["DateTime_Stop"] = row["DateTime_Stop"].strftime("%A, %B %d, %Y - %I:%M %p")
            row["DateTime_Stop_EU"] = row["DateTime_Stop_EU"].strftime("%A, %B %d, %Y - %H:%M %p")
        else:
            row["DateTime_Stop"] = row["DateTime_Stop"].strftime("%I:%M %p")
            row["DateTime_Stop_EU"] = row["DateTime_Stop_EU"].strftime("%A, %B %d, %Y - %H:%M")

        # TYPE
        if row["created"] is True:
            row["created"] = "🇺🇸 NEW RC : \n"
        else:
            row["created"] = "🇺🇸 RC UDPATE : \n"

        # FLIGHT
        if row["Flight"] == 0:
            row["Flight"] = "❌ NB : This is a non flight closure"
        elif row["Flight"] == 1:
            row["Flight"] = "✅ NB : This can be a flight closure"
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
            api.update_status_with_media(filename = "", file = img_byte_arr, status = message[i])
        except Exception as e:
            print(e)    
    return

def check_OP_Mary(api, db_client, account_name, nb_tweets):
    tweets = api.user_timeline(screen_name=account_name,count=nb_tweets,include_rts=False)
    tweets_clean = []
    for t in tweets:
        tweets_clean.append(t.__dict__)

    df_tweets= pd.DataFrame.from_records(tweets_clean)
    df_tweets.drop(["_api", "_json"],axis=1, inplace=True)

    for _, row in df_tweets.iterrows():
        if 'alert' in row['text'].lower() and 'static fire' in row['text'].lower():
            if not get_last_tweet(db_client, row['id'], "MONGO_DB_URL_TABLE_RC"):
                print('Tweet Mary')
                set_last_tweet(db_client, row['id'], "MONGO_DB_URL_TABLE_RC")
                try:
                    api.update_status("🚀🔥 Alert notice for possible Ship OR Booster static fire 🚀🔥")
                except Exception as e:
                    print(e)
            else:
                print('No Tweet Mary')
        else:
            print('No Tweet Mary')
    return

def check_NSF(api, db_client, text):

    if not get_last_tweet(db_client, re.sub(r'[^\w\s]', '', text).lower(), "MONGO_DB_URL_TABLE_PT"):
        print('Tweet NSF')
        try:
            api.update_status(text)
        except Exception as e:
            print(e)
        set_last_tweet(db_client, re.sub(r'[^\w\s]', '', text).lower(), "MONGO_DB_URL_TABLE_PT")
    else:
        print('No Tweet NSF')

def check_MSIB(api, db_client, text, pdf_file):
    check_date = re.sub(r'[^\w\s]', '', text.split('issue date:')[1].split('spacex')[0]).lower().strip().replace(" ",'').replace('\n', ' ').replace('\r', '')
    to_tweet = 'New MSIB from ' + (text.split('10 p.m.')[1].split('each day,')[0]).replace('\n', ' ').replace('\r', '').replace('through', 'to')
    if not get_last_msib(db_client, check_date, "MONGO_DB_URL_TABLE_MSIB"):
        print('Tweet MSIB')
        try:
            img = pdf2image.convert_from_bytes(pdf_file, fmt='jpeg')[0]
            # Create a buffer to hold the bytes
            buf = io.BytesIO()
            # Save the image as jpeg to the buffer
            img.save(buf, 'jpeg')
            # Rewind the buffer's file pointer
            buf.seek(0)
            # Read the bytes from the buffer
            image_bytes = buf.read()
            api.update_status_with_media(filename = "", file = image_bytes, status = to_tweet)
        except Exception as e:
            print(e)
        set_last_msib(db_client, check_date, "MONGO_DB_URL_TABLE_MSIB")
    else:
        print('No Tweet MSIB')