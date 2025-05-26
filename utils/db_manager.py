import sqlite3
import time
# Removed: from utils.config import DATABASE_NAME # This line caused the circular import

# Define DATABASE_NAME directly here to break the circular dependency
DATABASE_NAME = 'jewellery_app.db'

class DBManager:
    def __init__(self, db_path=DATABASE_NAME):
        self.db_path = db_path

    def _execute_query(self, query, params=(), fetch_mode='none', retries=5, delay=0.1):
        for i in range(retries):
            conn = None
            try:
                # Add timeout to connection attempt
                conn = sqlite3.connect(self.db_path, timeout=10) # 10 seconds timeout
                cursor = conn.cursor()
                cursor.execute(query, params)

                if fetch_mode == 'all':
                    result = cursor.fetchall()
                elif fetch_mode == 'one':
                    result = cursor.fetchone()
                else:
                    result = None # For 'none' (INSERT/UPDATE/DELETE)

                conn.commit()
                return result
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and i < retries - 1:
                    print(f"Database locked. Retrying in {delay}s... (Attempt {i+1}/{retries})")
                    time.sleep(delay)
                    delay *= 2 # Exponential backoff
                else:
                    print(f"Database operation failed after retries or for other reason: {e}")
                    if conn:
                        conn.rollback() # Rollback on final failure
                    raise # Re-raise the exception if it's not a lock or after max retries
            except Exception as e:
                print(f"An unexpected error occurred: {e}")
                if conn:
                    conn.rollback() # Rollback on any other exception
                raise # Re-raise other exceptions
            finally:
                if conn:
                    conn.close()
        return None # Should not be reached if exceptions are re-raised

    def fetch_all(self, query, params=()):
        return self._execute_query(query, params, fetch_mode='all')

    def fetch_one(self, query, params=()):
        return self._execute_query(query, params, fetch_mode='one')

    def execute_query(self, query, params=()):
        self._execute_query(query, params, fetch_mode='none')

