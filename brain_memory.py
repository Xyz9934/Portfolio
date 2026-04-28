from cloud_memory import cloud_store
from cloud_brain import learn_cloud


def store_ai_knowledge(text):

    # store in realtime database
    cloud_store(text)

    # store in firestore
    learn_cloud(text)

    print("Stored in both clouds")
