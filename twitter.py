import tweepy
import os
import locale

from dotenv import load_dotenv

load_dotenv()

def connect_api_twitter():
    # Authenticate to Twitter
    auth = tweepy.OAuthHandler(os.getenv("TWITTER_API_KEY"), os.getenv("TWITTER_API_SECRET_KEY"))
    auth.set_access_token(os.getenv("TWITTER_ACCESS_TOKEN"), os.getenv("TWITTER_ACCESS_TOKEN_SECRET"))
    api = tweepy.API(auth)
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
            row["DateTime_Stop"] = row["DateTime_Stop"].strftime("%A, %B %d, %Y - %I:%H")
        else:
            row["DateTime_Stop"] = row["DateTime_Stop"].strftime("%I:%H")

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
            row["Type"] = "🚧🚧🚧 Fermeture principale"
        elif row["Type"] == 'Alternative Date':
            row["Type"] = "🚧🚧🚧 Fermeture secondaire"

        message_fr.append(
            row["created"]+
            row["Type"] +
            ": " +
            row["Status"] +
            " pour le " +
            row["Date"].strftime("%A, %B %d, %Y") +
            " de "+
            row["DateTime_Start"].strftime("%H:%M") +
            " à "+
            row["DateTime_Stop"] +
            " Heure de Paris \n"+
            row["Flight"]
        )
    
    for n in range(len(message)):
        api.update_status(message[n])
        api.update_status(message_fr[n])



