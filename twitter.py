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
    message_fr = []

    df["DateTime_Start"] = df["DateTime_Start"].dt.tz_localize(tz='America/Chicago')
    df["DateTime_Stop"] = df["DateTime_Stop"].dt.tz_localize(tz='America/Chicago')

    for index, row in df.iterrows():
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
        else:
            row["DateTime_Stop"] = row["DateTime_Stop"].strftime("%I:%M %p")

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
            row["DateTime_Start"].strftime("%I:%M %p") +
            " to "+
            row["DateTime_Stop"] +
            " Boca Chica Time \n"+
            row["Flight"]
        )

    df["DateTime_Start"] = df["DateTime_Start"].dt.tz_convert(tz='Europe/Paris')
    df["DateTime_Stop"] = df["DateTime_Stop"].dt.tz_convert(tz='Europe/Paris')

    for index, row in df.iterrows():
        locale.setlocale(locale.LC_TIME,'fr_FR.UTF-8')
        # STATUS
        if "Canceled" in row["Status"]:
            row["Status"] = "Fermeture des routes annulées"
        elif "Scheduled" in row["Status"]:
            row["Status"] = "Fermeture des routes programmées"
        elif "Possible" in row["Status"]:
            row["Status"] = "Fermeture des routes possible"
        
        # DATETIME
        if row["Date"].strftime("%d") != row["DateTime_Stop"].strftime("%d"):
            row["DateTime_Stop"] = row["DateTime_Stop"].strftime("%A, %d %B, %Y - %H:%M")
        else:
            row["DateTime_Stop"] = row["DateTime_Stop"].strftime("%H:%M")

        # TYPE
        if row["created"] is True:
            row["created"] = "🇫🇷 Nouvelle Fermeture: \n"
        else:
            row["created"] = "🇫🇷 Modification de Fermeture: \n"

        # FLIGHT
        if row["Flight"] == 0:
            row["Flight"] = "❌ NB : Ceci n'est pas une fermeture pour vol"
        elif row["Flight"] == 1:
            row["Flight"] = "✅ NB : Ceci peut être une fermeture pour vol"
        else:
            row["Flight"] = ""
        
        # TYPE
        if row["Type"] == 'Primary Date':
            row["Type"] = "🚧 Fermeture principale"
        elif row["Type"] == 'Alternative Date':
            row["Type"] = "🚧 Fermeture secondaire"

        message_fr.append(
            row["created"]+
            row["Type"] +
            ": " +
            row["Status"] +
            " pour le " +
            row["Date"].strftime("%A, %d %B, %Y") +
            " de "+
            row["DateTime_Start"].strftime("%H:%M") +
            " à "+
            row["DateTime_Stop"] +
            " Heure de Paris \n"+
            row["Flight"]
        )
    for n in range(len(message)):
        try:
            reponse = api.update_status(message[n])
            tweet_id = reponse['id']
            api.update_status(status = message_fr[n], in_reply_to_status_id = tweet_id , auto_populate_reply_metadata=True)
        except Exception as e:
            print(e)     
    return

def check_OP_Mary(api, db_client, account_name, nb_tweets):
    tweets = api.user_timeline(screen_name=account_name,count=nb_tweets)
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
                    api.update_status("🚀🔥 Alert notice for possible Ship OR Booster static fire 🚀🔥\n" + "🚀🔥Alerte recu pour un potentiel static fire d'un Ship ou d'un Booster🚀🔥")
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
