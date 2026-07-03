class Logger:
    disabled: bool = False
    
    @staticmethod
    def _print(*args, **kwargs):
        if not Logger.disabled:
            print(*args, **kwargs)
    
    @staticmethod
    def disable(): Logger.disabled = True

    @staticmethod
    def enable(): Logger.disabled = False
    
    @staticmethod
    def info(*args, **kwargs): Logger._print("[grain/INFO]", *args, **kwargs)

    @staticmethod
    def warn(*args, **kwargs): Logger._print("[grain/WARN]", *args, **kwargs)
    
    @staticmethod
    def error(*args, **kwargs): Logger._print("[grain/ERROR]", *args, **kwargs)
