from src.config import get_qdrant_client, COLLECTION_NAME
import sys


def main():
    client = get_qdrant_client()

    info = client.get_collection(COLLECTION_NAME)
    print("⚠️ .. DESTRUCTIVE OPERATION\n")
    print(f"Collection name: {COLLECTION_NAME}")
    print(f"Points {info.points_count}")
    print()
    print("This will permanently delete the entire collection")
    print()
    typed = input(f"Type the collection name to proceed: ")
    if typed != COLLECTION_NAME:
        print("Confirmation mismatch. Aborting. Nothing was deleted")
        sys.exit(1)

    print()
    print(f"Deleting collection '{COLLECTION_NAME}'...")
    client.delete_collection(collection_name=COLLECTION_NAME)

    print("Collection deleted.")
    print()
    print("Verifying with get_collections()...")

    remaining = client.get_collections().collections
    remaining_names = [collection.name for collection in remaining]

    if COLLECTION_NAME not in remaining_names:
        print(f"Verified: '{COLLECTION_NAME}' no longer exists.")
    else:
        print(f"WARNING: '{COLLECTION_NAME}' still exists.")


if __name__ == '__main__':
    main()