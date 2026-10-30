"""Pull raw deribit data into data/raw/. Resumable: finished partitions are skipped on rerun."""

from pinpricer.data import deribit

if __name__ == "__main__":
    deribit.run()
