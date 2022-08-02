import tweepy
import os
import locale
import pandas as pd

from db import *
from dotenv import load_dotenv

load_dotenv()

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

    df["DateTime_Start"] = df["DateTime_Start"].dt.tz_localize(tz='America/Chicago')
    df["DateTime_Stop"] = df["DateTime_Stop"].dt.tz_localize(tz='America/Chicago')

    df["DateTime_Start_EU"] = df["DateTime_Start"].dt.tz_localize(tz='Europe/Paris')
    df["DateTime_Stop_EU"] = df["DateTime_Stop"].dt.tz_localize(tz='Europe/Paris')

    for _, row in df.iterrows():
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
            row["DateTime_Stop_EU"] = row["DateTime_Stop_EU"].strftime("%A, %B %d, %Y - %I:%M %p")
        else:
            row["DateTime_Stop"] = row["DateTime_Stop"].strftime("%I:%M %p")
            row["DateTime_Stop_EU"] = row["DateTime_Stop_EU"].strftime("%A, %B %d, %Y - %I:%M %p")

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
            row["DateTime_Start"].strftime("%I:%M %p") + "(" + row["DateTime_Start_EU"].strftime("%I:%M %p") + " UTC+2)" +
            " to "+
            row["DateTime_Stop"] + "(" + row["DateTime_Stop_EU"]  + " UTC+2)" +
            " Boca Chica Time \n"+
            row["Flight"]
        )

    for n in range(len(message)):
        try:
            api.update_status(message[n])
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
        if (('alert') and ('static fire')) in row['text'].lower():
            if not get_last_tweet(db_client, row['id'], "MONGO_DB_URL_TABLE_RC"):
                print('Tweet Mary')
                set_last_tweet(db_client, row['id'], "MONGO_DB_URL_TABLE_RC")
                try:
                    api.update_status("🚀🔥 Alert notice for possible Ship OR Booster static fire 🚀🔥")
                except Exception as e:
                    print(e)
        else:
            print('No Tweet Mary')
    return

def check_NSF(api, db_client, text):

    if not get_last_tweet(db_client, text, "MONGO_DB_URL_TABLE_PT"):
        print('Tweet NSF')
        try:
            api.update_status(text)
        except Exception as e:
            print(e)
        set_last_tweet(db_client, text, "MONGO_DB_URL_TABLE_PT")
    else:
        print('No Tweet NSF')
