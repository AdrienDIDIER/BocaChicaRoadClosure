import dotenv
import logging
import pytz
import warnings
import os

from flask import Flask
from db import *
from scrap import *
from twitter import *
from datetime import datetime

warnings.filterwarnings('ignore')
# logging.getLogger().setLevel(logging.ERROR)

dotenv.load_dotenv()

def process():
    print("Start Execution")
    now = datetime.utcnow()
    now_paris = now.astimezone(pytz.timezone("Europe/Paris"))
    current_time = now_paris.strftime("%H:%M:%S")
    print("Current Time =", current_time)
    # DATABASE
    db = get_database()
    api = connect_api_twitter()
    # driver = connect_page_twitter()

    try:
        # GET ROAD closure
        df = get_data_table("https://www.cameroncountytx.gov/spacex/")
        row_added, row_updated = insert_new_road_closure(db, df)
        # dates_list = get_rc_to_check(db)

        # GET INFOS ABOUT FLIGHT DURING ROAD closure
        # df_flight = get_infos_flight("https://www.cameroncountytx.gov/spacex/", dates_list)
        # flight_update(db, df_flight)

        # GET DATA OF NEW AND UPDATED ROAD closure
        df_created = get_rc_with_id(db, row_added, True)
        df_updated = get_rc_with_id(db, row_updated, False)
        df_to_tweet = pd.concat([df_created, df_updated])
        print(df_to_tweet)
        if len(df_to_tweet) > 0:
            print(f"Update / Creation of {len(df_created) + len(df_updated)} RC.")
            # tweet_road_closure_without_api(driver, df_to_tweet)
            tweet_road_closure(api, df)
        else:
            print("No Tweet RC")
    except Exception as e:
        print("Error RC")
        print(e)

    try:
        check_OP_Mary(api, db, "BocaChicaGal", 5)
    except Exception as e:
        print("Error MARY")
        print(e)
    
    try:
        textNSF = getScreenNSF("https://www.youtube.com/watch?v=mhJRzQsLZGg")
        if textNSF is not None:
            # check_NSF_without_api(driver, db, textNSF)
            check_NSF(api, db, textNSF)
        else:
            print('No Tweet NSF') 
    except Exception as e:
        print("Error NSF")
        print(e)
    
    try:
        textMSIB, pdf_file = getMSIB()
        if textMSIB is not None:
            # check_MSIB_without_api(driver, db, textMSIB, pdf_file)
            check_MSIB(api, db, textMSIB, pdf_file)
        else:
            print('No Tweet MSIB')
    except Exception as e:
        print("Error MSIB")
        print(e)

    try:
        df_notam, proxy= getTFR()

        for _, row in df_notam.iterrows():
            # check_TFR_without_api(driver, db, row, proxy)
            check_TFR(api, db, row, proxy)
    
    except Exception as e:
        print("Error TFR")
        print(e)

    # driver.quit()
    print("Stop Execution")

# app = Flask(__name__)

# @app.route("/")
# def hello_world():
#     return "Hello !"

# @app.route("/go")
# def process_task():
#     process()
#     return "Process launch"

# if __name__ == "__main__":
#     app.run(debug=False, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

process()