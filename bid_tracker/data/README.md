# bid_tracker/data — local scratch only

Nothing in this folder is committed (see `.gitignore`). This repo is public; bid data is not.

The real data lives in the private `paulodantasl/ideal-bid-data` repo. Point the tool at a clone of it:

```bash
export BID_TRACKER_DATA=/path/to/ideal-bid-data
python3 -m bid_tracker rebuild        # replays every package into $BID_TRACKER_DATA/bids.db
```

Without `BID_TRACKER_DATA`, the tool falls back to this folder (`bid_tracker/data/bids.db`), which is
fine for a scratch run and is wiped with the cloud container.
