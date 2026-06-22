import logging
import os
import time

# Define a custom level for SUCCESS (between INFO=20 and WARNING=30)
logging.SUCCESS = 25
logging.addLevelName(logging.SUCCESS, "SUCCESS")

def success(self, message, *args, **kws):
    if self.isEnabledFor(logging.SUCCESS):
        self._log(logging.SUCCESS, message, args, **kws)

logging.Logger.success = success

class ColorFormatter(logging.Formatter):
    """Custom logging formatter supporting ANSI colors and clean prefixes."""
    GREY = "\033[90m"
    WHITE = "\033[0m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD_RED = "\033[1;91m"
    RESET = "\033[0m"
    
    def __init__(self, use_time: bool = False):
        super().__init__()
        self.use_time = use_time
        
    def format(self, record):
        # Determine prefix based on level
        if record.levelno == logging.DEBUG:
            prefix = f"{self.BLUE}[DEBUG]{self.RESET}"
        elif record.levelno == logging.INFO:
            prefix = f"{self.WHITE}[INFO]{self.RESET}"
        elif record.levelno == logging.SUCCESS:
            prefix = f"{self.GREEN}[SUCCESS]{self.RESET}"
        elif record.levelno == logging.WARNING:
            prefix = f"{self.YELLOW}[WARNING]{self.RESET}"
        elif record.levelno == logging.ERROR:
            prefix = f"{self.RED}[ERROR]{self.RESET}"
        elif record.levelno == logging.CRITICAL:
            prefix = f"{self.BOLD_RED}[CRITICAL]{self.RESET}"
        else:
            prefix = f"[{record.levelname}]"
            
        # Temporarily backup levelname to prevent side-effects on other handlers
        orig_levelname = record.levelname
        record.levelname = prefix
        
        fmt = "%(asctime)s %(levelname)s %(message)s" if self.use_time else "%(levelname)s %(message)s"
        formatter = logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")
        result = formatter.format(record)
        
        # Restore original levelname
        record.levelname = orig_levelname
        return result

def get_logger(name: str = "Portraitron", level: int = logging.INFO, use_time: bool = False) -> logging.Logger:
    """Configures and returns a color-enabled logger."""
    logger = logging.getLogger(name)
    
    # If handlers are already set up, do not duplicate them
    if logger.handlers:
        return logger
        
    logger.setLevel(level)
    
    handler = logging.StreamHandler()
    handler.setFormatter(ColorFormatter(use_time=use_time))
    logger.addHandler(handler)
    
    # Prevent propagation to the root logger to avoid duplicate prints in custom runtimes
    logger.propagate = False
    
    return logger
