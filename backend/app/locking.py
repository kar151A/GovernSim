"""One-process SQLite write coordination, shared by API and account workflows."""
import threading
transaction_lock = threading.Lock()
