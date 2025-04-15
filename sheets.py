import logging
import os
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Union, Any, Tuple, Callable

# Московское время (UTC+3)
MSK_TIMEZONE = timezone(timedelta(hours=3))

import gspread
from google.oauth2.service_account import Credentials

from config import GOOGLE_CREDENTIALS_FILE, SPREADSHEET_ID, SHEET_NAME, DEBUG

# Define the scopes
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

# Cache settings
CACHE_DURATION = 10  # Reduced cache duration in seconds to more quickly detect manual changes


class CacheManager:
    """Cache manager for Google Sheets data with monitoring and statistics."""
    
    def __init__(self):
        """Initialize the cache manager."""
        self.cache = {}
        self.hits = 0
        self.misses = 0
        self.last_access_time = {}
        self.invalidations = 0
        
    def get(self, key: str) -> Tuple[Any, bool]:
        """
        Get a value from the cache.
        
        Args:
            key: Cache key
            
        Returns:
            Tuple[Any, bool]: (value, exists) pair
        """
        self.last_access_time[key] = time.time()
        
        if key in self.cache:
            timestamp, value = self.cache[key]
            # Check if cache is still valid
            if time.time() - timestamp < CACHE_DURATION:
                self.hits += 1
                return value, True
                
            # Cache expired
            del self.cache[key]
            self.invalidations += 1
        
        self.misses += 1
        return None, False
        
    def set(self, key: str, value: Any) -> None:
        """
        Set a value in the cache.
        
        Args:
            key: Cache key
            value: Value to cache
        """
        self.cache[key] = (time.time(), value)
        
    def invalidate(self, key: str = None) -> None:
        """
        Invalidate cache for a specific key or all keys.
        
        Args:
            key: Optional key to invalidate, if None invalidates all
        """
        if key is None:
            cache_size = len(self.cache)
            self.cache.clear()
            self.invalidations += cache_size
            logging.debug(f"Invalidated all cache entries ({cache_size} items)")
        elif key in self.cache:
            del self.cache[key]
            self.invalidations += 1
            logging.debug(f"Invalidated cache entry: {key}")
            
    def invalidate_pattern(self, pattern: str) -> None:
        """
        Invalidate cache for keys matching a pattern.
        
        Args:
            pattern: Pattern to match keys against
        """
        keys_to_delete = [k for k in self.cache.keys() if pattern in k]
        for key in keys_to_delete:
            del self.cache[key]
        
        self.invalidations += len(keys_to_delete)
        if keys_to_delete:
            logging.debug(f"Invalidated {len(keys_to_delete)} cache entries matching pattern: {pattern}")
            
    def invalidate_transaction_cache(self, transaction_id: Optional[int] = None) -> None:
        """
        Invalidate transaction cache entries. If transaction_id is provided,
        only invalidates cache entries for that transaction.
        
        Args:
            transaction_id: Optional transaction ID to invalidate
        """
        if transaction_id is not None:
            # Invalidate specific transaction
            self.invalidate(f"get_transaction:{transaction_id}")
            logging.debug(f"Invalidated cache for transaction {transaction_id}")
        else:
            # Invalidate all transaction-related caches
            patterns = [
                "get_transaction", 
                "get_all_transactions", 
                "get_daily_transactions",
                "get_unpaid_transactions",
                "get_daily_statistics"
            ]
            
            for pattern in patterns:
                self.invalidate_pattern(pattern)
                
            logging.debug("Invalidated all transaction-related cache entries")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the cache usage.
        
        Returns:
            Dict with cache statistics
        """
        total_requests = self.hits + self.misses
        hit_rate = self.hits / total_requests if total_requests > 0 else 0
        
        # Calculate average age of cached items
        current_time = time.time()
        ages = [current_time - timestamp for timestamp, _ in self.cache.values()]
        avg_age = sum(ages) / len(ages) if ages else 0
        
        # Sort cache items by creation time (oldest first)
        sorted_items = sorted(
            [(k, timestamp) for k, (timestamp, _) in self.cache.items()], 
            key=lambda x: x[1]
        )
        
        # Get oldest and most recently accessed items
        oldest_items = [k for k, _ in sorted_items[:5]] if sorted_items else []
        
        # Sort by last access time (least recently accessed first)
        lru_items = sorted(
            [(k, t) for k, t in self.last_access_time.items() if k in self.cache],
            key=lambda x: x[1]
        )
        least_used = [k for k, _ in lru_items[:5]] if lru_items else []
        
        return {
            "size": len(self.cache),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "invalidations": self.invalidations,
            "avg_age_seconds": avg_age,
            "oldest_items": oldest_items,
            "least_recently_used": least_used
        }


def cache_result(key_pattern: str):
    """
    Decorator to cache function results.
    
    Args:
        key_pattern: Pattern for cache key (can use {0}, {1}, etc. for function args)
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            # First argument should be self (GoogleSheetsClient instance)
            self_obj = args[0]
            
            # If in dummy mode, don't use cache
            if hasattr(self_obj, 'dummy_mode') and self_obj.dummy_mode:
                return func(*args, **kwargs)
                
            # If DEBUG is True and we're not forcing cache, don't use cache
            if DEBUG and not kwargs.get('force_cache', False):
                # Remove force_cache from kwargs if it exists
                if 'force_cache' in kwargs:
                    del kwargs['force_cache']
                return func(*args, **kwargs)
            
            # Check if the instance has a cache manager
            if not hasattr(self_obj, 'cache_manager'):
                self_obj.cache_manager = CacheManager()
            
            # Format the key with function arguments
            arg_strings = [str(arg) for arg in args[1:]]  # Skip self
            kwarg_strings = [f"{k}={v}" for k, v in kwargs.items() if k != 'force_cache']
            full_args = arg_strings + kwarg_strings
            function_name = func.__name__
            
            # Generate the cache key
            if full_args:
                try:
                    key = key_pattern.format(*full_args)
                except (IndexError, KeyError):
                    # If formatting fails, use a simpler key
                    key = f"{function_name}:{','.join(full_args)}"
            else:
                key = function_name
                
            # Check if cached value exists
            value, exists = self_obj.cache_manager.get(key)
            if exists:
                return value
                
            # Execute the function
            result = func(*args, **kwargs)
            
            # Cache the result (unless it's None or an error)
            if result is not None:
                self_obj.cache_manager.set(key, result)
                
            return result
            
        return wrapper
    return decorator


class GoogleSheetsClient:
    """Client for Google Sheets API."""
    
    def __init__(self):
        """Initialize the client with credentials."""
        try:
            logging.info("Starting Google Sheets client initialization...")
            # Инициализация кэша
            self.cache = {}
            # Инициализация кэш-менеджера
            self.cache_manager = CacheManager()
            
            # Проверяем, находимся ли мы в dummy_mode
            self.dummy_mode = False
            logging.info(f"Initial dummy_mode state: {self.dummy_mode}")
            
            # Check for missing credentials or invalid spreadsheet ID
            if not GOOGLE_CREDENTIALS_FILE or not os.path.exists(GOOGLE_CREDENTIALS_FILE) or not SPREADSHEET_ID or SPREADSHEET_ID == "your_spreadsheet_id_here":
                logging.warning(f"Missing or invalid credentials. Using development mode.")
                self._initialize_dummy_mode()
                return
            
            logging.info(f"Loading credentials from {GOOGLE_CREDENTIALS_FILE}")    
            # Load credentials from the service account file
            self.creds = Credentials.from_service_account_file(
                GOOGLE_CREDENTIALS_FILE, scopes=SCOPES
            )
            logging.info(f"Credentials loaded successfully, service account: {self.creds.service_account_email}")
            
            # Create client
            logging.info("Authorizing with gspread...")
            self.client = gspread.authorize(self.creds)
            logging.info("gspread authorization successful")
            
            try:
                # First open the spreadsheet
                try:
                    logging.info(f"Opening spreadsheet with ID: {SPREADSHEET_ID}")
                    spreadsheet = self.client.open_by_key(SPREADSHEET_ID)
                    logging.info(f"Successfully opened spreadsheet: {spreadsheet.title}")
                except Exception as e:
                    logging.error(f"Error accessing spreadsheet with ID {SPREADSHEET_ID}: {e}")
                    logging.error("Please make sure the spreadsheet exists and the service account has access to it.")
                    logging.error(f"Share the spreadsheet with: {self.creds.service_account_email}")
                    self._initialize_dummy_mode()
                    return
                
                # Then try to access the specific worksheet
                try:
                    logging.info(f"Accessing worksheet: {SHEET_NAME}")
                    self.sheet = spreadsheet.worksheet(SHEET_NAME)
                    logging.info(f"Successfully accessed worksheet: {SHEET_NAME}")
                except Exception as e:
                    logging.error(f"Error accessing worksheet '{SHEET_NAME}': {e}")
                    logging.error(f"Available worksheets: {[ws.title for ws in spreadsheet.worksheets()]}")
                    logging.error(f"Please create a worksheet named '{SHEET_NAME}' or update SHEET_NAME in .env")
                    self._initialize_dummy_mode()
                    return
                
                # Initialize headers if not exists
                logging.info("Initializing headers...")
                self._initialize_headers()
                logging.info("Headers initialization complete")
                
                self.dummy_mode = False
                logging.info("Google Sheets client successfully initialized")
            except Exception as e:
                logging.error(f"Unexpected error initializing Google Sheets: {e}")
                self._initialize_dummy_mode()
        except Exception as e:
            logging.warning(f"Error initializing Google Sheets client: {e}. Using development mode.")
            self._initialize_dummy_mode()
            
    def _initialize_dummy_mode(self):
        """Initialize dummy mode with fake data for development."""
        self.dummy_mode = True
        self.transaction_id_counter = 1
        # Инициализация кэша для режима разработки
        self.cache = {}
        
        # Sample transactions for testing
        self.daily_transactions = [
            {
                "id": 1,
                "datetime": datetime.now(MSK_TIMEZONE).strftime("%d.%m.%Y %H:%M"),
                "amount": 10000,
                "method": "USDT TRC20",
                "commission": 5.0,
                "rate": 92.5,
                "status": "Не оплачено",
                "group": "Test Group",
                "hash": ""
            }
        ]
        
        self.day_settings = {"rate": 92.5, "commission": 5.0}
        self.day_open = True
        logging.info("Initialized in dummy mode with sample data")
    
    def _initialize_headers(self):
        """Initialize the headers of the sheet if they don't exist."""
        try:
            logging.info("Starting headers initialization...")
            # Define the headers
            headers = [
                "ID", "Дата/время", "Сумма (₽)", "Метод", "Комиссия", 
                "Курс", "Статус выплаты", "Группа", "Хэш транзакции", "chat_id"
            ]
            
            # Check if headers exist
            logging.info("Checking existing headers...")
            try:
                existing_headers = self.sheet.row_values(1)
                logging.info(f"Existing headers found: {existing_headers}")
                
                if not existing_headers:
                    # Sheet is empty, add headers
                    logging.info("No headers found, adding headers to the sheet...")
                    self.sheet.update('A1', [headers])
                    logging.info("Headers initialized in Google Sheet")
                else:
                    logging.info("Headers already exist, skipping initialization")
            except Exception as e:
                logging.error(f"Error checking headers: {e}")
                # Try to update headers anyway
                logging.info("Attempting to update headers despite error...")
                self.sheet.update('A1', [headers])
                logging.info("Headers forcefully initialized")
            
            logging.info("Headers initialization completed successfully")
        except Exception as e:
            logging.error(f"Unhandled error in _initialize_headers: {e}")
            # Continue without failing the initialization - this is important to prevent hanging
            logging.warning("Continuing without proper header initialization")
    
    def add_transaction(self, data: Dict[str, Any]) -> int:
        """
        Add a new transaction to the sheet.
        
        Args:
            data: Dictionary with transaction details
            
        Returns:
            int: ID of the added transaction
        """
        try:
            # Handle dummy mode
            if hasattr(self, 'dummy_mode') and self.dummy_mode:
                # Get a new ID based on current transactions
                new_id = 1
                if self.daily_transactions:
                    new_id = max(t.get("id", 0) for t in self.daily_transactions) + 1
                
                # Create a transaction record
                transaction = {
                    "id": new_id,
                    "datetime": datetime.now(MSK_TIMEZONE).strftime("%d.%m.%Y %H:%M:%S"),
                    "amount": data["amount"],
                    "method": data["method"],
                    "commission": data["commission"],
                    "rate": data["rate"],
                    "status": "Не выплачено",
                    "group": data.get("group", "Development Group"),
                    "hash": "",
                    "chat_id": data.get("chat_id", "")
                }
                
                # Add to our in-memory list
                self.daily_transactions.append(transaction)
                logging.info(f"Transaction {new_id} added to in-memory storage (dummy mode)")
                
                # Invalidate caches for data changes
                if hasattr(self, 'cache_manager'):
                    self.cache_manager.invalidate_transaction_cache()
                    
                return new_id
                
            # Normal mode with Google Sheets
            # Get the last ID
            all_ids = self.sheet.col_values(1)[1:]  # Skip header
            new_id = 1
            if all_ids:
                new_id = max(int(id_) for id_ in all_ids if id_.isdigit()) + 1
            
            # Format the data
            row = [
                new_id,  # ID
                datetime.now(MSK_TIMEZONE).strftime("%d.%m.%Y %H:%M:%S"),  # Date/time
                data["amount"],  # Amount
                data["method"],  # Method
                data["commission"],  # Commission
                data["rate"],  # Rate
                "Не выплачено",  # Payment status
                data.get("group", ""),  # Group name
                "",  # Transaction hash
                data.get("chat_id", "")  # Chat ID (Telegram)
            ]
            
            # Append to the sheet
            self.sheet.append_row(row)
            logging.info(f"Transaction {new_id} added to Google Sheet")
            
            # Invalidate caches for transaction data changes
            if hasattr(self, 'cache_manager'):
                self.cache_manager.invalidate_transaction_cache()
                
            return new_id
        except Exception as e:
            logging.error(f"Error adding transaction: {e}")
            raise
    
    def update_transaction(self, transaction_id: int, data: Dict[str, Any]) -> bool:
        """
        Update an existing transaction.
        
        Args:
            transaction_id: ID of the transaction to update
            data: Dictionary with updated transaction details
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Handle dummy mode
            if hasattr(self, 'dummy_mode') and self.dummy_mode:
                # Find the transaction in our in-memory list
                for i, transaction in enumerate(self.daily_transactions):
                    if transaction["id"] == transaction_id:
                        # Update the transaction
                        for key, value in data.items():
                            if key in transaction:
                                transaction[key] = value
                        
                        # Update in the list
                        self.daily_transactions[i] = transaction
                        logging.info(f"Transaction {transaction_id} updated in in-memory storage (dummy mode)")
                        return True
                
                logging.error(f"Transaction ID {transaction_id} not found in dummy mode")
                return False
            
            # Regular mode
            # Find the row with the given ID
            id_col = self.sheet.col_values(1)
            row_idx = None
            
            for i, value in enumerate(id_col):
                if value == str(transaction_id):
                    row_idx = i + 1  # +1 because sheet rows are 1-indexed
                    break
            
            if row_idx is None:
                logging.error(f"Transaction ID {transaction_id} not found")
                return False
            
            # Get the existing row data
            row_data = self.sheet.row_values(row_idx)
            
            # Update the values
            updated_row = [
                row_data[0],  # ID (unchanged)
                row_data[1],  # Date/time (unchanged)
                data.get("amount", row_data[2]),  # Amount
                data.get("method", row_data[3]),  # Method
                data.get("commission", row_data[4]),  # Commission
                data.get("rate", row_data[5]),  # Rate
                data.get("status", row_data[6]),  # Payment status
                row_data[7],  # Group (unchanged)
                data.get("hash", row_data[8] if len(row_data) > 8 else "")  # Transaction hash
            ]
            
            # Check if we have a 10th column for chat_id
            if len(row_data) > 9:
                updated_row.append(data.get("chat_id", row_data[9]))
            else:
                updated_row.append(data.get("chat_id", ""))
            
            # Update the row with all columns including chat_id
            self.sheet.update(f'A{row_idx}:J{row_idx}', [updated_row])
            logging.info(f"Transaction {transaction_id} updated in Google Sheet")
            
            # Invalidate caches for transaction data changes
            if hasattr(self, 'cache_manager'):
                self.cache_manager.invalidate_transaction_cache(transaction_id)
                
            return True
        except Exception as e:
            logging.error(f"Error updating transaction: {e}")
            return False
    
    @cache_result(key_pattern="get_transaction:{0}")
    def get_transaction(self, transaction_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a transaction by ID.
        
        Args:
            transaction_id: ID of the transaction
            
        Returns:
            Optional[Dict]: Transaction details or None if not found
        """
        try:
            # Handle dummy mode
            if hasattr(self, 'dummy_mode') and self.dummy_mode:
                # Find the transaction in our in-memory list
                for transaction in self.daily_transactions:
                    if transaction["id"] == transaction_id:
                        return transaction
                
                return None
            
            # Regular mode
            # Find the row with the given ID
            id_col = self.sheet.col_values(1)
            row_idx = None
            
            for i, value in enumerate(id_col):
                if value == str(transaction_id):
                    row_idx = i + 1  # +1 because sheet rows are 1-indexed
                    break
            
            if row_idx is None:
                return None
            
            # Get the row data
            row_data = self.sheet.row_values(row_idx)
            
            # Map to a dictionary
            transaction = {
                "id": int(row_data[0]),
                "datetime": row_data[1],
                "amount": row_data[2],
                "method": row_data[3],
                "commission": row_data[4],
                "rate": row_data[5],
                "status": row_data[6],
                "group": row_data[7] if len(row_data) > 7 else "",
                "hash": row_data[8] if len(row_data) > 8 else "",
                "chat_id": row_data[9] if len(row_data) > 9 else ""
            }
            
            return transaction
        except Exception as e:
            logging.error(f"Error getting transaction: {e}")
            return None
    
    @cache_result(key_pattern="get_all_transactions:{0}")
    def get_all_transactions(self, date: Optional[str] = None, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Get all transactions, optionally filtered by date.
        
        Args:
            date: Optional date filter in format DD.MM.YYYY
            force_refresh: Whether to force a data refresh from the sheet
            
        Returns:
            List[Dict]: List of transaction dictionaries
        """
        # If force_refresh is True, invalidate the cache first
        if force_refresh and hasattr(self, 'cache_manager'):
            self.cache_manager.invalidate_pattern("get_all_transactions")
            self.cache_manager.invalidate_pattern("get_transaction")
        try:
            # Handle dummy mode
            if hasattr(self, 'dummy_mode') and self.dummy_mode:
                logging.info("Using dummy mode in get_all_transactions")
                if not date:
                    return self.daily_transactions
                
                # Filter by date if provided
                return [t for t in self.daily_transactions if t["datetime"].startswith(date)]
            
            # Regular mode
            logging.info("Using regular mode in get_all_transactions")
            # Get all data
            all_data = self.sheet.get_all_values()
            logging.info(f"Got {len(all_data)} rows from sheet")
            
            # Skip header
            data_rows = all_data[1:]
            logging.info(f"Processing {len(data_rows)} data rows")
            
            # Convert to list of dictionaries
            transactions = []
            
            for row in data_rows:
                if len(row) < 7:  # Ensure row has enough columns
                    logging.warning(f"Skipping row with insufficient columns: {row}")
                    continue
                
                if date and not row[1].startswith(date):
                    continue
                
                # Логируем данные для отладки проверки по группе
                group_name = row[7] if len(row) > 7 else ""
                logging.info(f"Processing transaction with group: '{group_name}'")
                
                # The dict structure
                transaction = {
                    "id": int(row[0]) if row[0].isdigit() else 0,
                    "datetime": row[1],
                    "amount": row[2],
                    "method": row[3],
                    "commission": row[4],
                    "rate": row[5],
                    "status": row[6],
                    "group": row[7] if len(row) > 7 else "",
                    "hash": row[8] if len(row) > 8 else "",
                    "chat_id": row[9] if len(row) > 9 else ""
                }
                
                transactions.append(transaction)
                logging.info(f"Added transaction: {transaction}")
            
            return transactions
        except Exception as e:
            logging.error(f"Error getting all transactions: {e}")
            return []
    
    @cache_result(key_pattern="get_daily_transactions")
    def get_daily_transactions(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Get all transactions for the current day.
        
        Args:
            force_refresh: Whether to force a data refresh from the sheet
            
        Returns:
            List[Dict]: List of transaction dictionaries
        """
        current_date = datetime.now(MSK_TIMEZONE).strftime("%d.%m.%Y")
        return self.get_all_transactions(date=current_date, force_refresh=force_refresh)
    
    @cache_result(key_pattern="get_unpaid_transactions")
    def get_unpaid_transactions(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Get all unpaid transactions.
        
        Args:
            force_refresh: Whether to force a data refresh from the sheet
            
        Returns:
            List[Dict]: List of unpaid transaction dictionaries
        """
        logging.info("Starting get_unpaid_transactions")
        all_transactions = self.get_all_transactions(force_refresh=force_refresh)
        logging.info(f"Got {len(all_transactions)} total transactions")
        
        # Используем более гибкую проверку статуса
        unpaid_transactions = []
        for tx in all_transactions:
            status = str(tx.get('status', '')).lower()
            logging.info(f"Checking transaction {tx['id']} with status '{status}'")
            # Если статус содержит "не" или пустой, считаем транзакцию невыплаченной
            if 'не' in status or status == '':
                logging.info(f"Adding unpaid transaction {tx['id']}")
                unpaid_transactions.append(tx)
            else:
                logging.info(f"Skipping paid transaction {tx['id']}")
        
        logging.info(f"Found {len(unpaid_transactions)} unpaid transactions out of {len(all_transactions)} total")
        return unpaid_transactions
    
    def mark_transaction_paid(self, transaction_id: int, transaction_hash: str) -> bool:
        """
        Mark a transaction as paid.
        
        Args:
            transaction_id: ID of the transaction
            transaction_hash: Hash of the transaction
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            transaction = self.get_transaction(transaction_id)
            if not transaction:
                logging.error(f"Transaction {transaction_id} not found")
                return False
            
            # Update the status and hash
            result = self.update_transaction(
                transaction_id, 
                {
                    "status": "Выплачено",
                    "hash": transaction_hash
                }
            )
            
            # Принудительно сбрасываем кэш статистики
            if result and hasattr(self, 'cache_manager'):
                self.cache_manager.invalidate_pattern("get_daily_statistics")
                logging.info(f"Cache invalidated for get_daily_statistics after marking transaction {transaction_id} as paid")
            
            return result
        except Exception as e:
            logging.error(f"Error marking transaction {transaction_id} as paid: {e}")
            return False
    
    @cache_result(key_pattern="get_current_rate:{0}")
    def get_current_rate(self, chat_id: int = None) -> Optional[float]:
        """
        Get the current exchange rate.
        
        Args:
            chat_id: ID of the chat, optional
            
        Returns:
            Optional[float]: The current rate or None if not found
        """
        day_settings = self.get_day_settings(chat_id=chat_id)
        if not day_settings:
            return None
        
        rate = day_settings.get('rate')
        if not rate or rate <= 0:
            return None
            
        return rate
    
    def save_day_settings(self, rate: float, commission_percent: float, chat_id: int = None) -> bool:
        """
        Save settings for the current day.
        
        Args:
            rate: Exchange rate
            commission_percent: Commission percentage
            chat_id: ID of the chat, optional
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Handle dummy mode
            if hasattr(self, 'dummy_mode') and self.dummy_mode:
                current_date = datetime.now(MSK_TIMEZONE).strftime("%d.%m.%Y")
                self.day_settings = {
                    "date": current_date,
                    "rate": rate,
                    "commission_percent": commission_percent
                }
                logging.info(f"Day settings saved in dummy mode: rate={rate}, commission={commission_percent}")
                
                # Invalidate relevant caches
                if hasattr(self, 'cache_manager'):
                    self.cache_manager.invalidate_pattern("get_day_settings")
                    self.cache_manager.invalidate_pattern("get_current_rate")
                    
                return True
                
            # Regular mode
            # We'll use a separate worksheet for day settings
            try:
                settings_sheet = self.client.open_by_key(SPREADSHEET_ID).worksheet("DaySettings")
            except gspread.exceptions.WorksheetNotFound:
                # Create the worksheet if it doesn't exist
                spreadsheet = self.client.open_by_key(SPREADSHEET_ID)
                settings_sheet = spreadsheet.add_worksheet(title="DaySettings", rows=100, cols=20)
                settings_sheet.update('A1:D1', [["Дата", "Курс", "Процент комиссии", "chat_id"]])
            
            # Get all data
            all_data = settings_sheet.get_all_values()
            current_date = datetime.now(MSK_TIMEZONE).strftime("%d.%m.%Y")
            chat_id_str = str(chat_id) if chat_id is not None else ""
            
            # Check if there's an existing entry for this chat_id
            found_existing_entry = False
            if len(all_data) > 1:  # Check if there's data beyond header
                for i, row in enumerate(all_data[1:], start=2):  # Start from row 2 (1-indexed in sheets)
                    if len(row) > 3 and row[3] == chat_id_str:
                        # Found an entry for this chat_id, update it
                        settings_sheet.update(f'A{i}:D{i}', [[current_date, rate, commission_percent, chat_id_str]])
                        logging.info(f"Обновлены настройки дня для chat_id {chat_id_str}: курс={rate}, комиссия={commission_percent}")
                        found_existing_entry = True
                        break
            
            # If no entry found for this chat_id, add a new one
            if not found_existing_entry:
                settings_sheet.append_row([current_date, rate, commission_percent, chat_id_str])
                logging.info(f"Добавлены новые настройки дня для chat_id {chat_id_str}: курс={rate}, комиссия={commission_percent}")
            
            # Инвалидируем кэш только для указанного chat_id
            if hasattr(self, 'cache_manager'):
                if chat_id is not None:
                    self.cache_manager.invalidate(f"get_day_settings:{chat_id}")
                    self.cache_manager.invalidate(f"get_current_rate:{chat_id}")
                else:
                    # Если chat_id не указан, инвалидируем все паттерны (устаревшее поведение)
                    self.cache_manager.invalidate_pattern("get_day_settings")
                    self.cache_manager.invalidate_pattern("get_current_rate")
                
            return True
        except Exception as e:
            logging.error(f"Error saving day settings: {e}")
            return False
    
    @cache_result(key_pattern="get_day_settings:{0}")
    def get_day_settings(self, chat_id: int = None) -> Optional[Dict[str, Union[str, float]]]:
        """
        Get the settings for the current day.
        
        Args:
            chat_id: ID of the chat, optional
            
        Returns:
            Optional[Dict[str, Union[str, float]]]: Day settings or None if not found
        """
        try:
            # Handle dummy mode
            if hasattr(self, 'dummy_mode') and self.dummy_mode:
                return getattr(self, 'day_settings', None)
                
            # Regular mode
            # Get the settings sheet
            try:
                settings_sheet = self.client.open_by_key(SPREADSHEET_ID).worksheet("DaySettings")
            except gspread.exceptions.WorksheetNotFound:
                # Создаем лист, если его нет
                try:
                    spreadsheet = self.client.open_by_key(SPREADSHEET_ID)
                    settings_sheet = spreadsheet.add_worksheet(title="DaySettings", rows=100, cols=20)
                    settings_sheet.update('A1:D1', [["Дата", "Курс", "Процент комиссии", "chat_id"]])
                    logging.info(f"Created DaySettings worksheet")
                except Exception as e:
                    logging.error(f"Error creating DaySettings worksheet: {e}")
                    return None
            
            # Get all data
            all_data = settings_sheet.get_all_values()
            if len(all_data) <= 1:  # Only header or empty
                return None
            
            # Filter by chat_id if provided
            filtered_data = all_data[1:]  # Skip header
            if chat_id is not None:
                str_chat_id = str(chat_id)
                filtered_data = [row for row in filtered_data if len(row) > 3 and row[3] == str_chat_id]
                
                # Если настройки для этого чата не найдены
                if not filtered_data:
                    logging.info(f"Настройки дня не найдены для chat_id {chat_id}")
                    return None
            
            if not filtered_data:
                return None
            
            # Get the latest settings for this chat_id
            # Сортируем по дате для получения самых свежих настроек
            filtered_data.sort(key=lambda row: row[0] if len(row) > 0 else "")
            latest_settings = filtered_data[-1]
            
            # Map to a dictionary
            current_date = latest_settings[0] if len(latest_settings) > 0 else datetime.now(MSK_TIMEZONE).strftime("%d.%m.%Y")
            
            # Проверяем, что значения валидны
            try:
                rate = float(latest_settings[1]) if len(latest_settings) > 1 and latest_settings[1] else 0
                commission = float(latest_settings[2]) if len(latest_settings) > 2 and latest_settings[2] else 0
            except (ValueError, TypeError) as e:
                logging.error(f"Error parsing day settings values: {e}")
                rate = 0
                commission = 0
            
            logging.info(f"Получены настройки дня для chat_id {chat_id}: курс={rate}, комиссия={commission}")
            
            return {
                "date": current_date,
                "rate": rate,
                "commission_percent": commission
            }
        except Exception as e:
            logging.error(f"Error getting day settings: {e}")
            return None
    
    @cache_result(key_pattern="is_day_open:{0}")
    def is_day_open(self, chat_id: int = None) -> bool:
        """
        Check if a day is currently open.
        
        Args:
            chat_id: ID of the chat, optional. Если None, проверяется глобальный статус дня.
            
        Returns:
            bool: True if the day is open, False otherwise
        """
        try:
            # Handle dummy mode
            if hasattr(self, 'dummy_mode') and self.dummy_mode:
                # Return stored value, default to True
                return getattr(self, 'day_open', True)
                
            # Regular mode
            # Get the settings sheet
            try:
                settings_sheet = self.client.open_by_key(SPREADSHEET_ID).worksheet("DayStatus")
            except gspread.exceptions.WorksheetNotFound:
                # Create the worksheet if it doesn't exist
                spreadsheet = self.client.open_by_key(SPREADSHEET_ID)
                settings_sheet = spreadsheet.add_worksheet(title="DayStatus", rows=100, cols=20)
                settings_sheet.update('A1:D1', [["Дата", "Статус", "Время", "chat_id"]])
                return False
            
            # Get the latest status
            all_data = settings_sheet.get_all_values()
            if len(all_data) <= 1:  # Only header or empty
                return False
            
            # Получаем все строки данных, пропуская заголовок
            data_rows = all_data[1:] 
            
            # Текущая дата
            current_date = datetime.now(MSK_TIMEZONE).strftime("%d.%m.%Y")
            
            # Обработка в зависимости от наличия chat_id
            if chat_id is not None:
                # Фильтруем по конкретному chat_id
                str_chat_id = str(chat_id)
                filtered_data = [row for row in data_rows if len(row) > 3 and row[3] == str_chat_id]
                
                # Если у нас нет записей для этого chat_id, значит день не открыт
                if not filtered_data:
                    logging.info(f"День не открыт для chat_id {chat_id} - записей не найдено")
                    return False
                
                # Сортируем записи по времени (колонка 2) и берем последнюю
                filtered_data.sort(key=lambda row: row[2] if len(row) > 2 else "")
                latest_status = filtered_data[-1]
                
                is_open = latest_status[0] == current_date and latest_status[1] == "Открыт"
                logging.info(f"Статус дня для chat_id {chat_id}: {'открыт' if is_open else 'закрыт'}, дата: {latest_status[0]}, статус: {latest_status[1]}")
                return is_open
            else:
                # Если chat_id не указан, ищем записи за сегодня без указания chat_id (глобальный статус)
                # или проверяем что хотя бы для одного чата день открыт
                today_status = [row for row in data_rows if row[0] == current_date]
                
                if not today_status:
                    logging.info("День не открыт - нет записей за сегодня")
                    return False
                
                # Сначала ищем глобальные записи (без указания chat_id)
                global_status = [row for row in today_status if len(row) <= 3 or not row[3]]
                
                if global_status:
                    # Сортируем записи по времени и берем последнюю
                    global_status.sort(key=lambda row: row[2] if len(row) > 2 else "")
                    latest_global = global_status[-1]
                    is_open = latest_global[1] == "Открыт"
                    
                    logging.info(f"Глобальный статус дня: {'открыт' if is_open else 'закрыт'}, дата: {latest_global[0]}")
                    return is_open
                
                # Если нет глобальных записей, проверяем открыт ли день хотя бы в одном чате
                for row in today_status:
                    if row[1] == "Открыт":
                        chat = row[3] if len(row) > 3 else "неизвестный"
                        logging.info(f"День открыт для чата {chat}")
                        return True
                
                logging.info("День закрыт для всех чатов")
                return False
        except Exception as e:
            logging.error(f"Error checking if day is open: {e}")
            return False
    
    def set_day_status(self, is_open: bool, chat_id: int = None) -> bool:
        """
        Set the status of the current day.
        
        Args:
            is_open: Whether the day is open or closed
            chat_id: ID of the chat, optional
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Handle dummy mode
            if hasattr(self, 'dummy_mode') and self.dummy_mode:
                self.day_open = is_open
                status = "Открыт" if is_open else "Закрыт"
                logging.info(f"Day status set to {status} in dummy mode")
                
                # Invalidate day status cache
                if hasattr(self, 'cache_manager'):
                    self.cache_manager.invalidate_pattern("is_day_open")
                    
                return True
                
            # Regular mode
            # Get the settings sheet
            try:
                status_sheet = self.client.open_by_key(SPREADSHEET_ID).worksheet("DayStatus")
            except gspread.exceptions.WorksheetNotFound:
                # Create the worksheet if it doesn't exist
                spreadsheet = self.client.open_by_key(SPREADSHEET_ID)
                status_sheet = spreadsheet.add_worksheet(title="DayStatus", rows=100, cols=20)
                status_sheet.update('A1:D1', [["Дата", "Статус", "Время", "chat_id"]])
            
            # Add the status for today
            current_date = datetime.now(MSK_TIMEZONE).strftime("%d.%m.%Y")
            current_time = datetime.now(MSK_TIMEZONE).strftime("%H:%M:%S")
            status = "Открыт" if is_open else "Закрыт"
            
            # Добавляем новую строку с указанием chat_id
            chat_id_str = str(chat_id) if chat_id is not None else ""
            status_sheet.append_row([current_date, status, current_time, chat_id_str])
            
            # Логируем действие
            logging.info(f"Установлен статус дня для chat_id {chat_id_str}: {status}")
            
            # Инвалидируем кэш только для указанного chat_id
            if hasattr(self, 'cache_manager'):
                if chat_id is not None:
                    self.cache_manager.invalidate(f"is_day_open:{chat_id}")
                else:
                    # Если chat_id не указан, инвалидируем весь паттерн (устаревшее поведение)
                    self.cache_manager.invalidate_pattern("is_day_open")
                
            return True
        except Exception as e:
            logging.error(f"Error setting day status: {e}")
            return False
            
    @cache_result(key_pattern="get_daily_statistics")
    def get_daily_statistics(self, chat_id: int = None, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Получает статистику по транзакциям за текущий день для указанного чата
        
        Args:
            chat_id (int): ID чата для которого нужно получить статистику, optional
            force_refresh (bool): Принудительно обновить кэш
            
        Returns:
            dict: Статистика за день
        """
        cache_key = f"daily_stats_{chat_id}_{datetime.now(MSK_TIMEZONE).strftime('%d.%m.%Y')}"
        
        # Если нужно принудительное обновление, удаляем ключ из кэша
        if force_refresh and cache_key in self.cache:
            logging.info(f"Принудительное обновление статистики - удаляем ключ {cache_key} из кэша")
            del self.cache[cache_key]
            # Также явно инвалидируем кэш в cache_manager если он есть
            if hasattr(self, 'cache_manager'):
                self.cache_manager.invalidate_pattern("get_daily_statistics")
        
        # Проверяем кэш, если не нужно принудительное обновление
        if not force_refresh and cache_key in self.cache:
            return self.cache[cache_key]
        
        try:
            # Получаем текущую дату в MSK timezone
            current_date = datetime.now(MSK_TIMEZONE).strftime("%d.%m.%Y")
            
            # Получаем все транзакции за текущий день
            transactions = self.get_all_transactions(date=current_date)
            logging.info(f"Получено {len(transactions)} транзакций для статистики за {current_date}")
            
            # Фильтруем транзакции по chat_id, если он указан
            if chat_id is not None:
                str_chat_id = str(chat_id)
                
                # Проверяем chat_id и group для совместимости
                filtered_transactions = []
                
                # Если chat_id отрицательный (группа), попробуем получить название группы
                group_name = None
                
                for t in transactions:
                    # Проверяем точное совпадение chat_id
                    if str(t.get('chat_id', '')) == str_chat_id:
                        filtered_transactions.append(t)
                        continue
                    
                    # Проверяем точное совпадение по полю group
                    if str(t.get('group', '')) == str_chat_id:
                        t['chat_id'] = str_chat_id  # Обновляем chat_id для будущей фильтрации
                        filtered_transactions.append(t)
                        continue
                    
                    # Дополнительная проверка для существующих транзакций с именами групп
                    # Если у нас есть транзакции со строковыми именами групп
                    group_field = t.get('group', '')
                    if (group_field and group_field.startswith('E, ') and 
                        ('Илья Кузнецов' in group_field or 'XchangeBot' in group_field) and 
                        str_chat_id == '-4605781130'):
                        # Это совпадение для группы "E, Илья Кузнецов и XchangeBot"
                        t['chat_id'] = str_chat_id
                        filtered_transactions.append(t)
                        continue
                    
                    # Проверка для группы Тест123 -> -4608567148
                    if group_field == 'Тест123' and str_chat_id == '-4608567148':
                        t['chat_id'] = str_chat_id
                        filtered_transactions.append(t)
                        continue
                
                transactions = filtered_transactions
                logging.info(f"После фильтрации по chat_id {chat_id} осталось {len(transactions)} транзакций")
            
            if not transactions:
                empty_stats = {
                    "total_amount": 0,
                    "awaiting_amount": 0,
                    "to_pay_amount": 0,
                    "paid_amount": 0,
                    "avg_rate": 0,
                    "avg_commission": 0,
                    "transactions_count": 0,
                    "unpaid_usdt": 0,
                    "to_pay_usdt": 0,
                    "total_usdt": 0,
                    "paid_usdt": 0,
                    "methods_count": {}
                }
                self.cache[cache_key] = empty_stats
                return empty_stats
            
            # Получаем настройки дня для текущего чата
            day_settings = self.get_day_settings(chat_id=chat_id)
            
            current_rate = day_settings.get('rate', 0) if day_settings else 0
            current_commission = day_settings.get('commission_percent', 0) if day_settings else 0
            
            # Расчет статистики
            total_amount = sum(float(t['amount']) for t in transactions if t['amount'])
            
            # Разделяем на выплаченные и невыплаченные
            paid_transactions = [t for t in transactions if t.get('status', '').lower() == 'выплачено']
            unpaid_transactions = [t for t in transactions if t.get('status', '').lower() != 'выплачено']
            
            paid_amount = sum(float(t['amount']) for t in paid_transactions if t['amount'])
            awaiting_amount = sum(float(t['amount']) for t in unpaid_transactions if t['amount'])
            
            # Расчет суммы к выплате с учетом комиссии
            to_pay_amount = 0
            for tx in unpaid_transactions:
                try:
                    amount = float(tx['amount']) if tx['amount'] else 0
                    
                    # Корректно обрабатываем комиссию в процентах
                    commission_str = tx.get('commission', '')
                    tx_commission = 0
                    
                    if commission_str:
                        if isinstance(commission_str, str) and '%' in commission_str:
                            tx_commission = float(commission_str.replace('%', '').strip())
                        elif isinstance(commission_str, (int, float)):
                            tx_commission = float(commission_str)
                        else:
                            try:
                                tx_commission = float(commission_str)
                            except (ValueError, TypeError):
                                tx_commission = current_commission
                    else:
                        tx_commission = current_commission
                    
                    to_pay_amount += amount * (1 - tx_commission / 100)
                except (ValueError, TypeError) as e:
                    logging.warning(f"Ошибка при расчете суммы к выплате для транзакции: {e}")
                    continue
            
            # Расчет средних значений
            rates = []
            commissions = []
            
            for t in transactions:
                # Обработка значения rate
                rate_value = t.get('rate', '')
                if rate_value:
                    try:
                        # Удаляем все нечисловые символы, кроме точки
                        if isinstance(rate_value, str):
                            rate_value = rate_value.replace('"', '').replace('USDT', '').strip()
                        rates.append(float(rate_value))
                    except (ValueError, TypeError):
                        logging.warning(f"Не удалось преобразовать значение курса '{rate_value}' в число")
                
                # Обработка значения commission
                commission_value = t.get('commission', '')
                if commission_value:
                    try:
                        # Если это строка с процентами, удаляем символ %
                        if isinstance(commission_value, str):
                            commission_value = commission_value.replace('%', '').strip()
                        commissions.append(float(commission_value))
                    except (ValueError, TypeError):
                        logging.warning(f"Не удалось преобразовать значение комиссии '{commission_value}' в число")
            
            avg_rate = sum(rates) / len(rates) if rates else current_rate
            avg_commission = sum(commissions) / len(commissions) if commissions else current_commission
            
            # Используем текущий курс для конвертации в USDT
            usdt_rate = current_rate if current_rate > 0 else (avg_rate if avg_rate > 0 else 90)
            
            unpaid_usdt = round(awaiting_amount / usdt_rate, 2) if usdt_rate > 0 else 0
            to_pay_usdt = round(to_pay_amount / usdt_rate, 2) if usdt_rate > 0 else 0
            total_usdt = round(total_amount / usdt_rate, 2) if usdt_rate > 0 else 0
            paid_usdt = round(paid_amount / usdt_rate, 2) if usdt_rate > 0 else 0
            
            # Подсчет методов оплаты
            methods_count = {}
            for tx in transactions:
                method = tx.get('method', 'Не указан')
                methods_count[method] = methods_count.get(method, 0) + 1
            
            # Формируем результат
            result = {
                "date": current_date,
                "transactions_count": len(transactions),
                "total_amount": round(total_amount, 2),
                "awaiting_amount": round(awaiting_amount, 2),
                "to_pay_amount": round(to_pay_amount, 2),
                "paid_amount": round(paid_amount, 2),
                "avg_rate": round(avg_rate, 2),
                "avg_commission": round(avg_commission, 2),
                "unpaid_usdt": unpaid_usdt,
                "to_pay_usdt": to_pay_usdt,
                "total_usdt": total_usdt,
                "paid_usdt": paid_usdt,
                "methods_count": methods_count
            }
            
            # Кэшируем результат
            self.cache[cache_key] = result
            
            return result
        except Exception as e:
            logging.error(f"Ошибка при получении статистики: {e}")
            return {
                "date": current_date if 'current_date' in locals() else datetime.now(MSK_TIMEZONE).strftime("%d.%m.%Y"),
                "transactions_count": 0,
                "total_amount": 0,
                "awaiting_amount": 0,
                "to_pay_amount": 0,
                "paid_amount": 0,
                "avg_rate": 0,
                "avg_commission": 0,
                "unpaid_usdt": 0,
                "to_pay_usdt": 0,
                "total_usdt": 0,
                "paid_usdt": 0,
                "methods_count": {}
            }


# Create a global instance of the client
sheets_client = GoogleSheetsClient()

# Utility function to migrate old data with group names to proper chat_id
def migrate_transaction_data():
    """
    Migrate old transaction data with group names to proper chat_id values.
    This function updates the chat_id field for existing transactions.
    """
    logging.info("Starting transaction data migration...")
    try:
        # Group name to chat_id mapping
        group_mapping = {
            "E, Илья Кузнецов и XchangeBot": "-4605781130",
            "Тест123": "-4608567148"
        }
        
        # Get all transactions
        all_transactions = sheets_client.get_all_transactions(force_refresh=True)
        logging.info(f"Found {len(all_transactions)} transactions total")
        
        # Track transactions that need updating
        updated_count = 0
        
        for tx in all_transactions:
            tx_id = tx.get('id')
            group = tx.get('group', '')
            chat_id = tx.get('chat_id', '')
            
            # Skip transactions that already have a chat_id set
            if chat_id and chat_id.startswith('-'):
                continue
                
            # If we have a group name mapping, update the chat_id
            new_chat_id = None
            for known_group, known_chat_id in group_mapping.items():
                if group.startswith(known_group) or (group == known_chat_id):
                    new_chat_id = known_chat_id
                    break
            
            # Update the transaction if needed
            if new_chat_id:
                logging.info(f"Updating transaction {tx_id}: group '{group}' -> chat_id '{new_chat_id}'")
                sheets_client.update_transaction(tx_id, {"chat_id": new_chat_id})
                updated_count += 1
        
        logging.info(f"Migration completed: updated {updated_count} transactions")
        return updated_count
    except Exception as e:
        logging.error(f"Error during transaction data migration: {e}")
        return 0

# Run migration when the module is imported
try:
    migrate_count = migrate_transaction_data()
    logging.info(f"Transaction migration status: {migrate_count} updated")
except Exception as e:
    logging.error(f"Failed to run transaction migration: {e}")
