from db import *
from scrap import *
from twitter import *
import schedule
import time

def job():    
    # DATABASE
    db = get_database()

    # GET ROAD closure
    df = get_data_table("https://www.cameroncountytx.gov/spacex/")
    print(df)
    row_added, row_updated = insert_new_road_closure(db, df)
    print(row_added, row_updated)
    dates_list = get_rc_to_check(db)
    print(dates_list)

    # GET INFOS ABOUT FLIGHT DURING ROAD closure
    df_flight = get_infos_flight("https://www.cameroncountytx.gov/spacex/", dates_list)
    flight_update(db, df_flight)
    # ---- DELETE PDF FILES
    delete_download_file(".pdf")

    # GET DATA OF NEW AND UPDATED ROAD closure
    df_created = get_rc_with_id(db, row_added, True)
    df_updated = get_rc_with_id(db, row_updated, False)

    df_to_tweet = pd.concat([df_created, df_updated])

    if len(df_to_tweet) > 0:
        api = connect_api_twitter()
        tweet_road_closure(api, df_to_tweet)

schedule.every(1).minutes.do(job)

while 1:
    schedule.run_pending()
    time.sleep(1)
 
