"""Pull daily Wikipedia pageviews (retail-attention proxy) into data/raw/attention/."""

from pinpricer.data import attention

if __name__ == "__main__":
    attention.run()
