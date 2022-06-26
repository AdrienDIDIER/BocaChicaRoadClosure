from db import *
from scrap import *
from twitter import *

# DATABASE
db = get_database()

# GET ROAD CLOASURE
df = get_data_table("https://www.cameroncountytx.gov/spacex/")
row_added, row_updated = insert_new_road_cloasure(db, df)
dates_list = get_rc_to_check(db)

# GET INFOS ABOUT FLIGHT DURING ROAD CLOASURE
df_flight = get_infos_flight("https://www.cameroncountytx.gov/spacex/", dates_list)
flight_update(db, df_flight)
# ---- DELETE PDF FILES
delete_download_file(".pdf")

# GET DATA OF NEW AND UPDATED ROAD CLOASURE
df_created = get_rc_with_id(db, row_added, True)
df_updated = get_rc_with_id(db, row_updated, False)

df_to_tweet = pd.concat([df_created, df_updated])

if len(df_to_tweet) > 0:
    api = connect_api_twitter()
    tweet_road_cloasure(api, df_to_tweet)
