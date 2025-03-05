import os
import json
import time

class truthCompass:
    def __init__(self, data_dir, ttl=30*86400):
        """Initialize truthCompass with data directory and TTL in seconds."""
        self.data_dir = data_dir
        self.default_ttl = ttl
        os.makedirs(data_dir, exist_ok=True)
        
    def _get_filepath(self, exchange, account, asset):
        """Generate filepath for storing order history."""
        return os.path.join(self.data_dir, f"truthCompass.{exchange}.{account}.{asset}")
    
    def _generate_key(self, signal):
        """Generate a unique key for the signal."""
        # Customize this based on your signal structure
        return (signal.get('recipe', '').replace(" ", "") + 
                signal.get('exchange', '') + 
                signal.get('account', '') + 
                signal.get('asset', '') + 
                str(signal.get('tcycles', '')) + 
                str(signal.get('tbuys', '')))
    
    def _load_data(self, filepath):
        """Load the timed list from disk."""
        if not os.path.exists(filepath):
            return {}
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            # Clean expired entries
            now = time.time()
            data = {k: v for k, v in data.items() if v.get('expire', 0) == 0 or v.get('expire', 0) > now}
            return data
        except Exception as e:
            print(f"Error loading data: {e}")
            return {}
    
    def _save_data(self, filepath, data):
        """Save the timed list to disk."""
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Error saving data: {e}")
    
    def update(self, signal):
        """Update the signal in the timed list and return status."""
        # Get file path
        filepath = self._get_filepath(
            signal.get('exchange', 'unknown'),
            signal.get('account', 'unknown'),
            signal.get('asset', 'unknown')
        )
        
        # Generate unique key
        key = self._generate_key(signal)
        
        # Load existing data
        data = self._load_data(filepath)
        
        # Determine expiration
        if signal.get('action', '').lower() == 'close':
            expire = 0
        else:
            expire = time.time() + self.default_ttl
        
        # Clean signal copy
        signal_copy = signal.copy()
        signal_copy.pop('identity', None)  # Remove sensitive info
        
        # Check if key exists
        status = {}
        if key in data:
            if data[key].get('expire', 0) > time.time() or data[key].get('expire', 0) == 0:
                status = {'status': 'Found'}
            else:
                status = {'status': 'Replaced'}
        else:
            status = {'status': 'New'}
        
        # Update data
        data[key] = {
            'data': signal_copy,
            'expire': expire,
            'timestamp': time.time()
        }
        
        # Save back to disk
        self._save_data(filepath, data)
        
        return status
    
    def is_duplicate(self, signal):
        """Check if a signal is a duplicate that should be rejected."""
        result = self.update(signal)
        
        # Only reject duplicate buy signals
        if result['status'] in ['Found', 'Replaced'] and signal.get('action', '').lower() == 'buy':
            return True
        
        return False