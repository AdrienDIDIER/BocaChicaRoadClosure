from gettext import textdomain
from db import *
from scrap import *
from twitter import *
import schedule
import time

print("Start Execution")
# DATABASE
db = get_database()

# GET ROAD closure
df = get_data_table("https://www.cameroncountytx.gov/spacex/")
row_added, row_updated = insert_new_road_closure(db, df)
dates_list = get_rc_to_check(db)

# GET INFOS ABOUT FLIGHT DURING ROAD closure
df_flight = get_infos_flight("https://www.cameroncountytx.gov/spacex/", dates_list)
flight_update(db, df_flight)
# ---- DELETE PDF FILES
delete_download_file(".pdf")

# GET DATA OF NEW AND UPDATED ROAD closure
df_created = get_rc_with_id(db, row_added, True)
df_updated = get_rc_with_id(db, row_updated, False)

df_to_tweet = pd.concat([df_created, df_updated])

api = connect_api_twitter()

if len(df_to_tweet) > 0:
    print(f"Update / Creation of {len(df_created) + len(df_updated)} RC.")
    tweet_road_closure(api, df_to_tweet)
    
check_OP_Mary(api, db, "BocaChicaGal", 1)
# textNSF = getScreenNSF("https://www.youtube.com/watch?v=mhJRzQsLZGg")
# check_NSF(api, db, textNSF)

print("Stop Execution")
