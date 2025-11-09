import datetime

def log(message: str, log_type="INFO"):
    '''
    Logs a message with a timestamp and type.

    Args:
        message (str): The log message.
        log_type (str): The type of log (e.g., "INFO", "ERROR", "DEBUG"). Defaults to "INFO".
    '''
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{log_type.upper()}] {message}")
