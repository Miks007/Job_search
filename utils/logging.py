import os
import logging
from datetime import datetime

def set_up_logging(log_dir_path, logs_name):
    os.makedirs(log_dir_path, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = f'{log_dir_path}/{logs_name}_{timestamp}.log'
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()  
        ]
    )
    logger = logging.getLogger(__name__)
    return logger

def delete_old_logs(log_dir_path, RETENTION_DAYS):
    try:
        current_time = datetime.now()
        for file in os.listdir(log_dir_path):
            if file.endswith('.log'):
                file_path = os.path.join(log_dir_path, file)
                file_time = datetime.fromtimestamp(os.path.getctime(file_path))
                age_days = (current_time - file_time).days
            
            if age_days > RETENTION_DAYS:
                    os.remove(file_path)
                    logging.info(f"Deleted log file {file} - {age_days} days old")
    except Exception as e:
        error_msg = f"Error during deleting old logs: {e}"
        raise Exception(error_msg)