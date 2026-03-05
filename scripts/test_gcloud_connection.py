import dotenv

dotenv.load_dotenv()

from google.cloud import storage


def main():
    """Test Google Cloud Storage connection by listing buckets and counting files."""
    print("Testing Google Cloud Storage connection...\n")

    # Initialize the storage client
    client = storage.Client()

    # List all buckets
    print("Listing all buckets:")
    print("-" * 60)

    buckets = list(client.list_buckets())

    if not buckets:
        print("No buckets found.")
        return

    total_files = 0

    for bucket in buckets:
        print(f"\nBucket: {bucket.name}")
        print(f"  Location: {bucket.location}")
        print(f"  Storage Class: {bucket.storage_class}")
        print(f"  Created: {bucket.time_created}")

        # Count files (blobs) in this bucket
        blobs = list(bucket.list_blobs())
        file_count = len(blobs)
        total_files += file_count

        print(f"  File count: {file_count}")

        # Show first few files as examples (if any)
        if blobs:
            print(f"  Sample files:")
            for blob in blobs[:5]:  # Show up to 5 files
                print(f"    - {blob.name} ({blob.size} bytes)")
            if file_count > 5:
                print(f"    ... and {file_count - 5} more files")

    print("\n" + "=" * 60)
    print(f"Total buckets: {len(buckets)}")
    print(f"Total files across all buckets: {total_files}")
    print("=" * 60)


if __name__ == "__main__":
    main()
