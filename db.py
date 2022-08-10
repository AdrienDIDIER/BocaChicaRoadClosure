import pandas as pd
import os

from datetime import datetime
from pymongo import MongoClient

def get_database():
    # Provide the mongodb atlas url to connect python to mongodb using pymongo
    CONNECTION_STRING = os.getenv('MONGO_DB_URL')
    # Create a connection using MongoClient. You can import MongoClient or use pymongo.MongoClient
    client = MongoClient(CONNECTION_STRING)
    return client['bocachicaroadclosure']
    
def get_data_old_date(client):
    db_infos = client[os.getenv('MONGO_DB_URL_TABLE')].find()
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
        result = client[os.getenv('MONGO_DB_URL_TABLE')].replace_one(
            {'index': row.get('index')}, row, upsert=True
        )
        if result.upserted_id is not None:
            list_id_new.append(result.upserted_id)

    list_id_change = []
    df_data = pd.DataFrame(list(client[os.getenv('MONGO_DB_URL_TABLE')].find({})))
    df_changes = pd.concat([df_data_old,df_data]).drop_duplicates(keep=False)
    for obj in df_changes['_id'].unique():
        if obj not in list_id_new:
            list_id_change.append(obj)
    return list_id_new, list_id_change

def get_rc_with_id(client, ids, created):
    rcs = client[os.getenv('MONGO_DB_URL_TABLE')].find({'_id' : {"$in": ids}})
    df = pd.DataFrame(list(rcs))
    if len(df) > 0:
        df['created'] = created
    return df

def get_rc_to_check(client):
    rcs = client[os.getenv('MONGO_DB_URL_TABLE')].find({'Flight': -1})
    result = []
    for rc in rcs:
        result.append(datetime.strftime(rc['Date'], "%Y-%m-%d"))
    return result

def flight_update(client, df):
    for row in df.to_dict(orient='records'):
        client[os.getenv('MONGO_DB_URL_TABLE')].update_many(
            {'Date': row.get('Date')}, {"$set": row}, 
        )
    return 'PDF Checking'

def set_last_tweet(client, id, table):
    client[os.getenv(table)].replace_one(
        {"last_id":id}, {"last_id":id}, upsert=True
    )
    return 

def get_last_tweet(client, id, table):
    res = client[os.getenv(table)].find_one({"last_id": id})
    if res is not None:
        return True
    return False

def set_last_msib(client, id, table):
    client[os.getenv(table)].replace_one(
        {"last_issue_date":id}, {"last_issue_date":id}, upsert=True
    )
    return 

def get_last_msib(client, id, table):
    res = client[os.getenv(table)].find_one({"last_issue_date": id})
    if res is not None:
        return True
    return False