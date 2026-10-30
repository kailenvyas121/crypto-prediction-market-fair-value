"""Pull raw spot data into data/raw/. Resumable: finished partitions are skipped on rerun."""

from pinpricer.data import spot

if __name__ == "__main__":
    spot.run()
