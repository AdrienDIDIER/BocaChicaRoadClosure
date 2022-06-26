import pandas as pd
import os

from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv
load_dotenv()

def get_database():
    # Provide the mongodb atlas url to connect python to mongodb using pymongo
    CONNECTION_STRING = os.getenv('MONGO_DB_URL')
    # Create a connection using MongoClient. You can import MongoClient or use pymongo.MongoClient
    client = MongoClient(CONNECTION_STRING)
    return client['bocachicaroadclosure']
    
def get_data_old_date(client):
    db_infos = client["RoadClosure"].find()
    data = pd.DataFrame(columns=['Date', 'Flight'])
    for info in db_infos:
        if 'Flight' in info.keys():
            data.loc[len(data.index)] = [info['Date'], info['Flight']]
    return data

def insert_new_road_closure(client, df):
    
    data = get_data_old_date(client)

    df = df.merge(data, on='Date', how='left')
    df['Flight'] = df['Flight'].fillna(-1)

    df_data_old = pd.DataFrame(list(client["RoadClosure"].find({})))

    list_id_new = []
    for row in df.to_dict(orient='records'):
        result = client["RoadClosure"].replace_one(
            {'index': row.get('index')}, row, upsert=True
        )
        if result.upserted_id is not None:
            list_id_new.append(result.upserted_id)

    list_id_change = []
    df_data = pd.DataFrame(list(client["RoadClosure"].find({})))
    df_changes = pd.concat([df_data_old,df_data]).drop_duplicates(keep=False)
    for obj in df_changes['_id'].unique():
        if obj not in list_id_new:
            list_id_change.append(obj)
    return list_id_new, list_id_change

def get_rc_with_id(client, ids, created):
    rcs = client["RoadClosure"].find({'_id' : {"$in": ids}})
    df = pd.DataFrame(list(rcs))
    if len(df) > 0:
        df['created'] = created
    return df

def get_rc_to_check(client):
    rcs = client["RoadClosure"].find({'Flight': -1})
    result = []
    for rc in rcs:
        result.append(datetime.strftime(rc['Date'], "%Y-%m-%d"))
    return result

def flight_update(client, df):
    for row in df.to_dict(orient='records'):
        client["RoadClosure"].update_many(
            {'Date': row.get('Date')}, {"$set": row}, 
        )
    return 'PDF Checking'